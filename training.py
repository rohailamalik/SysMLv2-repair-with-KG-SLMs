import torch, argparse, json, gc
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM, EarlyStoppingCallback
from trl import SFTTrainer, SFTConfig
from peft import LoraConfig, get_peft_model
from datasets import Dataset
from pathlib import Path

from config import MODEL_CONFIGS, TRAIN_TYPES

def parse_arguments():
    """Parse and validate command line arguments."""

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")
    
    if not isinstance(MODEL_CONFIGS, dict):
        raise ValueError("MODEL_CONFIGS must be a dictionary")

    DEFAULT_MODEL = next(iter(MODEL_CONFIGS))
    
    parser = argparse.ArgumentParser(
        description="Fine-tune language models using LoRA adapters"
    )
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Model key from config (default: {DEFAULT_MODEL})"
    )

    parser.add_argument(
        "--type",
        type=str,
        default=TRAIN_TYPES[0],
        help=f"Training type (default: {TRAIN_TYPES[0]})"
    )
    
    args = parser.parse_args()
    
    if args.model not in MODEL_CONFIGS:
        raise ValueError(
            f"Unknown model '{args.model}'. "
            f"Available models: {list(MODEL_CONFIGS.keys())}"
        )
    if args.type not in TRAIN_TYPES:
        raise ValueError(
            f"Unknown test type '{args.type}'. "
            f"Available types: {TRAIN_TYPES}"
        )
    
    return args


def setup_paths(model_name: str, training_type: str):
    """Setup and create necessary directory paths."""
    model_short = model_name.split("/")[1]
    
    WORK_DIR = Path("/scratch/work/malikr2")  # for triton cluster
    # WORK_DIR = Path.cwd()  # for local use
    
    paths = {
        "work_dir": WORK_DIR,
        "train_data": WORK_DIR / "dataset" / "split" / "train_dataset.jsonl",
        "eval_data": WORK_DIR / "dataset" / "split" / "eval_dataset.jsonl",
        "adapter_dir": WORK_DIR / "adapters" / model_short / training_type,
        "logging_dir": WORK_DIR / "results" / "training" / model_short / training_type,
        "model_short": model_short
    }
    
    paths["adapter_dir"].mkdir(parents=True, exist_ok=True)
    paths["logging_dir"].mkdir(parents=True, exist_ok=True)
    
    return paths


def get_training_config(cfg):
    """Extract training configuration from model config."""
    return {
        # LoRA settings
        "lora_r": cfg["lora_r"],
        "lora_alpha": cfg["lora_alpha"],
        "lora_dropout": cfg["lora_dropout"],
        
        # Training settings
        "epochs": cfg["epochs"],
        "batch_size": cfg["batch_size"],
        "grad_accum": cfg["grad_accum"],
        "learning_rate": cfg["learning_rate"],
        
        # Fixed settings
        "warmup_steps": 100,
        "weight_decay": 0.01,
        "max_seq_length": 2048,
        "early_stopping_patience": 3,
        "early_stopping_threshold": 0.005,
    }


def load_tokenizer(model_name: str):
    """Load and configure tokenizer."""
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
    
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    return tokenizer


def compile_chat(example, tokenizer, training_type):
    """Compile chat messages from prompts and responses."""

    prompt = example["prompt"] # rules are always added during training

    if training_type == "code": # output code
        response = example["good_code"]
    else: # output diff patch
        response = example["diff_patch"]

    chat = [
        {"role": "user", "content": "You are a SysML v2 expert."},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": f"```\n{response}\n```" + tokenizer.eos_token}
    ]

    return {"messages": chat}


def load_datasets(train_path: Path, eval_path: Path, tokenizer, training_type):
    """Load and prepare training and evaluation datasets."""

    ds_train = Dataset.from_pandas(pd.read_json(train_path, lines=True))
    ds_train = ds_train.map(
        lambda example: compile_chat(example, tokenizer, training_type),
        batched=False,
        remove_columns=ds_train.column_names
    )
    
    ds_eval = Dataset.from_pandas(pd.read_json(eval_path, lines=True))
    ds_eval = ds_eval.map(
        lambda example: compile_chat(example, tokenizer, training_type),
        batched=False,
        remove_columns=ds_eval.column_names
    )
    
    if training_type == "code":
        print("Datasets loaded with full code as output")
    else:
        print(f"Datasets loaded with diff patches as output")

    print(f"Training size: {len(ds_train)}, Evaluation size: {len(ds_eval)}")
    
    return ds_train, ds_eval


def load_model(model_name: str):
    """Load base model with appropriate configuration."""
    print(f"Loading model: {model_name}")
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        device_map="cuda:0",
        trust_remote_code=True
    )
    
    model.gradient_checkpointing_enable()
    
    return model


def apply_lora(model, config):
    """Apply LoRA configuration to model."""
    peft_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_dropout=config["lora_dropout"],
        bias="none",
        task_type="CAUSAL_LM",
    )
    
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    
    return model


def calculate_training_steps(train_size: int, batch_size: int, grad_accum: int, epochs: int):
    """Calculate training steps and evaluation frequency."""
    steps_per_epoch = train_size // (batch_size * grad_accum)
    total_steps = steps_per_epoch * epochs
    eval_steps = max(steps_per_epoch // 5, 1)  # eval 5 times per epoch
    save_steps = eval_steps
    logging_steps = max(eval_steps // 4, 1)  # log 20 times per epoch
    
    return {
        "steps_per_epoch": steps_per_epoch,
        "total_steps": total_steps,
        "eval_steps": eval_steps,
        "save_steps": save_steps,
        "logging_steps": logging_steps
    }


def create_training_config(config, paths, steps_info):
    """Create SFTConfig for training."""
    return SFTConfig(
        output_dir=str(paths["adapter_dir"]),
        dataset_text_field="messages",
        max_length=config["max_seq_length"],
        
        # Batch and optimization settings
        per_device_train_batch_size=config["batch_size"],
        per_device_eval_batch_size=config["batch_size"],
        gradient_accumulation_steps=config["grad_accum"],
        learning_rate=config["learning_rate"],
        num_train_epochs=config["epochs"],
        
        # Optimizer settings
        optim="adamw_torch",
        weight_decay=config["weight_decay"],
        warmup_steps=config["warmup_steps"],
        
        # Precision settings
        bf16=True,
        fp16=False,
        
        # Packing settings
        packing=False,
        
        # Evaluation and saving
        eval_strategy="steps",
        eval_steps=steps_info["eval_steps"],
        eval_on_start=True,
        save_strategy="steps",
        save_steps=steps_info["save_steps"],
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        
        # Logging
        logging_steps=steps_info["logging_steps"],
        logging_dir=str(paths["logging_dir"]),
        report_to="tensorboard",
        
        # Gradient clipping
        max_grad_norm=1.0,
        
        # Learning rate scheduler
        lr_scheduler_type="cosine",
    )


def print_training_info(model_name: str, training_type: str, steps_info: dict, config: dict):
    """Print training configuration information."""
    print("Training Configuration:")
    print(f"Model: {model_name}, Training Type: {training_type}")
    print(f"Steps per epoch: {steps_info['steps_per_epoch']}")
    print(f"Total steps: {steps_info['total_steps']}")
    print(f"Eval & Save every: {steps_info['eval_steps']} steps")
    print(f"Effective batch size: {config['batch_size'] * config['grad_accum']}")


def save_training_logs(trainer, logging_dir: Path, stopped_early: bool = False):
    """Save training logs and metrics."""
    if trainer.state.log_history:
        log_path = logging_dir / "training_logs.json"
        with open(log_path, "w") as f:
            json.dump(trainer.state.log_history, f, indent=2)
        print(f"Training logs saved to {log_path}")
    
    if stopped_early:
        stopped_at_epoch = trainer.state.epoch
        print(f"Early stopping triggered at epoch {stopped_at_epoch:.2f}")


def cleanup_resources():
    """Clean up GPU memory and resources."""
    gc.collect()
    torch.cuda.empty_cache()
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    print("GPU memory cleaned up")


def main():
    
    args = parse_arguments()
    
    cfg = MODEL_CONFIGS[args.model]
    training_type = args.type
    model_name = cfg["model_name"]
    
    paths = setup_paths(model_name, training_type)
    
    config = get_training_config(cfg)
    
    trainer = None
    
    try:
        # Load tokenizer
        print("Loading tokenizer...")
        tokenizer = load_tokenizer(model_name)
        
        # Load datasets
        print("Loading datasets...")
        ds_train, ds_eval = load_datasets(
            paths["train_data"],
            paths["eval_data"],
            tokenizer,
            training_type
        )
        
        # Load model
        model = load_model(model_name)
        
        # Apply LoRA
        print("Applying LoRA configuration...")
        model = apply_lora(model, config)
        
        # Calculate training steps
        steps_info = calculate_training_steps(
            len(ds_train),
            config["batch_size"],
            config["grad_accum"],
            config["epochs"]
        )
        
        # Print training info
        print_training_info(model_name, training_type, steps_info, config)
        
        # Create training configuration
        training_args = create_training_config(config, paths, steps_info)
        
        # Create early stopping callback
        early_stopping = EarlyStoppingCallback(
            early_stopping_patience=config["early_stopping_patience"],
            early_stopping_threshold=config["early_stopping_threshold"]
        )
        
        # Create trainer
        trainer = SFTTrainer(
            model=model,
            processing_class=tokenizer,
            train_dataset=ds_train,
            eval_dataset=ds_eval,
            args=training_args,
            callbacks=[early_stopping]
        )
        
        # Start training
        print("Starting training...")
        trainer.train()
        
        # Check if early stopping was triggered
        stopped_early = trainer.state.global_step < steps_info["total_steps"]
        
        # Save final model
        print(f"Saving final model to {paths['adapter_dir']}")
        trainer.save_model(str(paths["adapter_dir"]))
        
        # Save training logs
        save_training_logs(trainer, paths["logging_dir"], stopped_early)
        
        print("Training completed successfully!")
        
    except KeyboardInterrupt:
        print("Training interrupted by user")
        
        if trainer is not None:
            try:
                checkpoint_path = paths["adapter_dir"] / "interrupted_checkpoint"
                print(f"Saving interrupted checkpoint to {checkpoint_path}")
                trainer.save_model(str(checkpoint_path))
                save_training_logs(trainer, paths["logging_dir"], stopped_early=True)
            except Exception as e:
                print(f"Could not save interrupted checkpoint: {e}")
    
    except Exception as e:
        print(f"Error during training: {e}")
        raise
    
    finally:
        cleanup_resources()


if __name__ == "__main__":
    main()