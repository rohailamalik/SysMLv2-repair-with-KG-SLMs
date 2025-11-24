import json
import torch
import pandas as pd
import os
from datasets import Dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    BitsAndBytesConfig
)
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig  
from tqdm import tqdm

# --- CONFIGURATION ---
MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
# Use absolute paths to avoid file-not-found errors
current_dir = os.getcwd()
SYNTAX_FILE = os.path.join(current_dir, "synthetic_dataset_main_expanded_new_final2.jsonl")
DOMAIN_FILE = os.path.join(current_dir, "synthetic_dataset_domain_aware_full12.jsonl")
OUTPUT_DIR = os.path.join(current_dir, "sysml_repair_model_full_set")

# --- STEP 1: DATA PREPARATION ---
def load_and_format_data():
    print("Initializing data processing...")
    data = []
    
    # Helper to check file existence
    if not os.path.exists(SYNTAX_FILE):
        raise FileNotFoundError(f"Cannot find {SYNTAX_FILE}")
    if not os.path.exists(DOMAIN_FILE):
        raise FileNotFoundError(f"Cannot find {DOMAIN_FILE}")

    # 1. Load Syntax Data
    with open(SYNTAX_FILE, 'r', encoding='utf-8') as f:
        print("Processing Syntax Data...")
        for line in f:
            entry = json.loads(line)
            prompt = f"""### Instruction:
            You are a SysML v2 repair assistant. Fix the code based on the compiler error.

            ### Compiler Error:
            {entry['error_message']}

            ### Broken Code:
            {entry['bad_code']}

            ### Fixed Code:
            """
            completion = f"{entry['good_code']}<|endoftext|>"
            data.append({"text": prompt + completion})
            
    # 2. Load Domain Data
    with open(DOMAIN_FILE, 'r', encoding='utf-8') as f:
        print("Processing Domain Data...")
        for line in f:
            entry = json.loads(line)
            prompt = f"""### Instruction:
            You are a SysML v2 repair assistant. The code compiles, but check for semantic domain inconsistencies.

            ### Compiler Error:
            None

            ### Broken Code:
            {entry['bad_code']}

            ### Fixed Code:
            """
            completion = f"{entry['good_code']}<|endoftext|>"
            data.append({"text": prompt + completion})
    
    print(f"Combined dataset size: {len(data)} samples")
    return Dataset.from_pandas(pd.DataFrame(data))

# --- STEP 2: MODEL LOADING & TRAINING ---
def train():
    dataset = load_and_format_data()
    
    print(f"\nLoading model: {MODEL_ID}...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )

    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="cuda:0"
    )

    model.gradient_checkpointing_enable()
    model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=16,
        lora_alpha=32,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
    )

    # --- CONFIGURING ARGUMENTS (The Fix) ---
    # In latest TRL, everything goes into SFTConfig
    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        dataset_text_field="text",       
        max_length=512,             
        per_device_train_batch_size=1,   
        gradient_accumulation_steps=16,   
        gradient_checkpointing=True,
        learning_rate=2e-4,
        logging_steps=10,
        max_steps=500,
        save_steps=100,
        fp16=True,                       
        optim="paged_adamw_8bit",        
        report_to="none",
        packing=False                    
    )

    print("\nStarting training...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,              
        peft_config=peft_config,
    )

    trainer.train()
    
    print(f"\nTraining complete! Model saved to {OUTPUT_DIR}")
    trainer.save_model(OUTPUT_DIR)

if __name__ == "__main__":
    train()