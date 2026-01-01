import torch, json, argparse, gc
import pandas as pd
from transformers import AutoTokenizer, AutoModelForCausalLM
from tqdm import tqdm
from peft import PeftModel
from datasets import Dataset
from pathlib import Path

from config import MODEL_CONFIGS, TEST_TYPES, MAX_GEN_TOKEN_LENGTH, TEST_BATCH_SIZE

def parse_arguments():
    """Parse and validate command line arguments."""

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is not available.")
    
    if not isinstance(MODEL_CONFIGS, dict):
        raise ValueError("MODEL_CONFIGS must be a dictionary")
    
    DEFAULT_MODEL = next(iter(MODEL_CONFIGS))
    
    DEFAULT_TYPE = TEST_TYPES[0]
    
    parser = argparse.ArgumentParser(description="Test language models with different configurations")
    parser.add_argument(
        "--model",
        type=str,
        default=DEFAULT_MODEL,
        help=f"Model key (default: {DEFAULT_MODEL})"
    )
    parser.add_argument(
        "--type",
        type=str,
        default=DEFAULT_TYPE,
        help=f"Model type key (default: {DEFAULT_TYPE})"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.model not in MODEL_CONFIGS:
        raise ValueError(
            f"Unknown model '{args.model}'. "
            f"Available models: {list(MODEL_CONFIGS.keys())}"
        )
    if args.type not in TEST_TYPES:
        raise ValueError(
            f"Unknown test type '{args.type}'. "
            f"Available types: {TEST_TYPES}"
        )
    
    return args


def setup_paths(model_name: str, test_type: str):
    """Setup and create necessary directory paths."""
    model_short = model_name.split("/")[1]
    
    WORK_DIR = Path("/scratch/work/malikr2")  # for triton cluster
    # WORK_DIR = Path.cwd()  # for local use

    training_type = "code" if test_type == "fine_tuned_code" else "patch"
    
    paths = {
        "work_dir": WORK_DIR,
        "test_data": WORK_DIR / "dataset" / "split" / "test_dataset.jsonl",
        "adapter_dir": WORK_DIR / "adapters" / model_short / training_type,
        "logging_dir": WORK_DIR / "results" / "testing" / model_short,
        "model_short": model_short
    }
    
    # Create logging directory if it doesn't exist
    paths["logging_dir"].mkdir(parents=True, exist_ok=True)
    
    return paths


def load_tokenizer(model_name: str):
    """Load and configure tokenizer."""
    tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)

    if getattr(tokenizer, "chat_template", None) is None:
        raise ValueError("Tokenizer does not have a chat template.")
    
    tokenizer.padding_side = "left"
    tokenizer.pad_token = tokenizer.eos_token
    
    return tokenizer


def compile_full_prompt(example, test_type: str, tokenizer):
    """Compile prompt with system and user prompt based on test type."""

    if test_type == "baseline":
        prompt = example["base_prompt"] 
    else:
        prompt = example["prompt"]
    
    full_prompt = [
        {"role": "system", "content": "You are a SysML v2 expert."},
        {"role": "user", "content": prompt}
    ]
    
    full_prompt = tokenizer.apply_chat_template(
        full_prompt,
        tokenize=False,
        add_generation_prompt=True
    )

    return {"messages": full_prompt}


def load_dataset(test_data_path: Path, test_type: str, tokenizer):
    """Load and prepare test dataset."""
    ds_test = Dataset.from_pandas(pd.read_json(test_data_path, lines=True))
    
    if test_type == "rag_only":
        # RAG includes rules which do not affect syntax examples at all, drop them
        ds_test = ds_test.filter(lambda x: x['mutation_category'] != 'syntax')
        print("RAG only settings, dropping syntax examples.")
    
    # Map prompts
    ds_test = ds_test.map(
        lambda example: compile_full_prompt(example, test_type, tokenizer),
        batched=False
    )
    
    print(f"Test dataset loaded. Size: {len(ds_test)}")
    return ds_test


def load_model(model_name: str, adapter_dir: Path, test_type: str):
    """Load base model and optionally apply LoRA adapter."""
    print(f"Loading model: {model_name}")
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        dtype=torch.bfloat16,
        device_map="auto"
    )
    
    if test_type in ["fine_tuned_code", "fine_tuned_patch"]:
        print(f"Loading LoRA adapter from: {adapter_dir}")
        model = PeftModel.from_pretrained(
            model,
            str(adapter_dir),
            dtype=torch.bfloat16,
        )
    
    model.eval()
    return model


def test_loop(model, tokenizer, ds_test):
    """Main testing loop with batch processing."""
    results = []
    
    pbar = tqdm(
        range(0, len(ds_test), TEST_BATCH_SIZE),
        desc="Testing"
    )
    
    for i in pbar:
        batch_end = min(i + TEST_BATCH_SIZE, len(ds_test))
        batch = ds_test[i:batch_end]
        
        # Tokenize inputs
        inputs = tokenizer(
            batch["messages"],
            return_tensors="pt",
            padding=True
        ).to(model.device)
        
        # Generate outputs
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=MAX_GEN_TOKEN_LENGTH,
                use_cache=True,
                eos_token_id=tokenizer.eos_token_id
            )
        
        # Extract only the generated tokens
        input_length = inputs["input_ids"].shape[1]
        generated_tokens = outputs[:, input_length:]
        
        # Decode answers
        answers = tokenizer.batch_decode(
            generated_tokens,
            skip_special_tokens=True
        )
        
        # Store results
        for j in range(len(answers)):
            results.append({
                "id": batch["id"][j],
                "answer": answers[j],
            })
        
        # Update progress bar with memory stats
        mem_alloc = torch.cuda.memory_allocated() / 1024**2
        mem_reserved = torch.cuda.memory_reserved() / 1024**2
        pbar.set_postfix(
            mem=f"{mem_alloc:.0f}MB",
            reserved=f"{mem_reserved:.0f}MB"
        )
    
    return results


def cleanup_resources():
    """Clean up GPU memory."""
    gc.collect()
    torch.cuda.empty_cache()
    torch.cuda.synchronize()


def save_results(results, logging_dir: Path, test_type: str, dataset_size: int):
    """Save test results to JSON file."""
    if results:
        save_path = logging_dir / test_type / "test_results.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Processed {len(results)}/{dataset_size} examples")
        print(f"Results saved to {save_path}")
    else:
        print("No results generated")


def main():
    """Main execution function."""
    # Parse arguments
    args = parse_arguments()
    
    # Get model configuration
    cfg = MODEL_CONFIGS[args.model]
    model_name = cfg["model_name"]
    
    # Setup paths
    paths = setup_paths(model_name, args.type)
    
    # Initialize variables to None for proper cleanup
    model = None
    tokenizer = None
    results = None
    
    try:
        print(f"Starting testing on {paths['model_short']} ({args.type})")
        
        tokenizer = load_tokenizer(model_name)
        
        ds_test = load_dataset(paths["test_data"], args.type, tokenizer)
        
        model = load_model(model_name, paths["adapter_dir"], args.type)
        
        results = test_loop(model, tokenizer, ds_test)
        
        print("Testing complete!")
        
    except KeyboardInterrupt:
        print("\nTesting interrupted..")
        
    except Exception as e:
        print(f"Error during testing: {e}")
        raise
        
    finally:

        if results and 'ds_test' in locals():
            save_results(results, paths["logging_dir"], args.type, len(ds_test))
    
        if model is not None:
            cleanup_resources()


if __name__ == "__main__":
    main()