import json
import torch
import pandas as pd
import os
import inspect
import re
import textwrap  
from datasets import Dataset
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    BitsAndBytesConfig
)
from peft import LoraConfig, prepare_model_for_kbit_training
from trl import SFTTrainer, SFTConfig
from tqdm import tqdm

# import vehicle_kg.py
from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS

# --- CONFIGURATION ---
MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
current_dir = os.getcwd()
SYNTAX_FILE = os.path.join(current_dir, "synthetic_dataset_main_expanded_new_final2.jsonl")
DOMAIN_FILE = os.path.join(current_dir, "synthetic_dataset_domain_aware_full12.jsonl")
OUTPUT_DIR = os.path.join(current_dir, "sysml_repair_model_rag_full_set")

# --- RAG to be injected to the model ---
def get_kg_context(code):
    """Scans code and retrieves relevant domain rules."""
    context_lines = []
    found_domains = set()
    for type_name, domain in TYPE_TO_DOMAIN.items():
        if re.search(r'\b' + re.escape(type_name) + r'\b', code):
            context_lines.append(f"- '{type_name}' belongs to Domain: {domain}")
            found_domains.add(domain)
    
    if found_domains:
        context_lines.append("\nValid Connections Rules:")
        for domain in found_domains:
            allowed = VALID_CONNECTIONS.get(domain, [])
            context_lines.append(f"- {domain} can ONLY connect to: {allowed}")
    return "\n".join(context_lines)

# --- I tried using CoT to get the model to actually work, which works for the one example i tested ---
def load_and_format_data():
    print("Initializing data processing with Chain-of-Thought...")
    data = []
    
    if not os.path.exists(SYNTAX_FILE): raise FileNotFoundError(f"Missing {SYNTAX_FILE}")
    if not os.path.exists(DOMAIN_FILE): raise FileNotFoundError(f"Missing {DOMAIN_FILE}")

    # 1. Syntax Data (Implicit CoT: The Compiler Error is the "Thought")
    with open(SYNTAX_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            # We teach it to acknowledge the error first
            prompt = textwrap.dedent(f"""\
                ### Instruction:
                Analyze the SysML v2 code for syntax errors reported by the compiler. Provide a reasoning trace, then the fixed code.

                ### Compiler Error:
                {entry['error_message']}

                ### Broken Code:
                {entry['bad_code']}

                ### Analysis & Fix:
                """)
            
            # The "Thought" we teach it:
            thought = f"The compiler reports '{entry['error_message']}'. This usually means I need to correct the syntax at the reported line."
            
            completion = f"[ANALYSIS]\n{thought}\n[/ANALYSIS]\n\n[FIXED CODE]\n{entry['good_code']}<|endoftext|>"
            data.append({"text": prompt + completion})
            
    # 2. Domain Data (Explicit RAG CoT)
    with open(DOMAIN_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            entry = json.loads(line)
            
            # Generate Context
            kg_context = get_kg_context(entry['bad_code'])
            
            # Construct the "Thought" dynamically based on the context
            # This is the "Teacher" showing the student how to think.
            # We know it's a domain error, so we synthesize a generic domain analysis.
            thought = (
                "Checking semantic consistency...\n"
                "1. Identified ports and parts in the context.\n"
                "2. Checked Knowledge Graph rules.\n"
                "3. FOUND ERROR: A connection exists between incompatible domains (e.g., Mechanical <-> Fluid).\n"
                "4. ACTION: Rerouting connection to a compatible component."
            )

            prompt = textwrap.dedent(f"""\
                ### Instruction:
                Analyze the SysML v2 code for semantic domain inconsistencies using the provided Knowledge Graph rules. Provide a reasoning trace, then the fixed code.

                ### Knowledge Context:
                {kg_context}

                ### Broken Code:
                {entry['bad_code']}

                ### Analysis & Fix:
                """)
            
            completion = f"[ANALYSIS]\n{thought}\n[/ANALYSIS]\n\n[FIXED CODE]\n{entry['good_code']}<|endoftext|>"
            data.append({"text": prompt + completion})
    
    print(f"Combined CoT dataset size: {len(data)} samples")
    return Dataset.from_pandas(pd.DataFrame(data))

def train():
    torch.cuda.empty_cache()
    dataset = load_and_format_data()
    
    print(f"\nLoading model: {MODEL_ID}...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb_config, device_map="cuda:0"
    )
    
    model.gradient_checkpointing_enable()
    model = prepare_model_for_kbit_training(model)

    peft_config = LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        task_type="CAUSAL_LM", target_modules=["q_proj", "k_proj", "v_proj", "o_proj"]
    )

    training_args = SFTConfig(
        output_dir=OUTPUT_DIR,
        dataset_text_field="text",
        max_length=512,                  
        per_device_train_batch_size=1,
        gradient_accumulation_steps=16,
        gradient_checkpointing=True,
        learning_rate=2e-4,
        logging_steps=5,
        max_steps=300,
        save_steps=50,
        fp16=True,
        optim="paged_adamw_8bit",
        report_to="none",
        packing=False
    )

    print("\nStarting RAG-Native training...")
    trainer = SFTTrainer(
        model=model,
        train_dataset=dataset,
        args=training_args,
        peft_config=peft_config,
    )

    trainer.train()
    trainer.save_model(OUTPUT_DIR)
    print(f"\nTraining complete! RAG-Model saved to {OUTPUT_DIR}")

if __name__ == "__main__":
    train()