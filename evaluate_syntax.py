import json
import re
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel
import jupyter_client
import queue

# =============================================================================
# Config
# =============================================================================

MODEL_PATH = "./sysml_repair_model_rag_full_set"
BASE_MODEL = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
VAL_FILE = "./split_data/val_syntax_valid.jsonl"
VALID_IDS_FILE = "valid_source_ids.json"
MAX_PROMPT_TOKENS = 400  # Model trained with 512 max, leave room for generation
NUM_SAMPLES = 20  

# =============================================================================
# SysML Validator
# =============================================================================

class SysMLValidator:
    def __init__(self):
        print("Starting SysML kernel...")
        self.km = jupyter_client.KernelManager(kernel_name='sysml')
        self.km.start_kernel()
        self.kc = self.km.client()
        self.kc.start_channels()
        self.kc.wait_for_ready()
        print("SysML kernel started!")

    def validate_code(self, code):
        if not self.kc:
            return {'success': False, 'errors': ['Kernel not available.']}
            
        msg_id = self.kc.execute(code)
        errors = []

        while True:
            try:
                msg = self.kc.get_iopub_msg(timeout=10)
                msg_type = msg['header']['msg_type']
                content = msg['content']

                if msg['parent_header'].get('msg_id') != msg_id:
                    continue

                if msg_type == 'stream':
                    output_text = content['text'].strip()
                    if output_text and ('ERROR:' in output_text or 'failed' in output_text.lower()):
                        errors.append(output_text)
                elif msg_type == 'error':
                    errors.append('\n'.join(content['traceback']))
                elif msg_type == 'status' and content['execution_state'] == 'idle':
                    break
            except queue.Empty:
                break
        
        return {'success': len(errors) == 0, 'errors': errors}

    def shutdown(self):
        if self.km:
            self.kc.stop_channels()
            self.km.shutdown_kernel()

# =============================================================================
# Load Model
# =============================================================================

print("Loading model...")
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)

bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
)

base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL,
    quantization_config=bnb_config,
    device_map="auto",
)

model = PeftModel.from_pretrained(base_model, MODEL_PATH)
model.eval()
print("Model loaded!")

# =============================================================================
# Load Data
# =============================================================================

# Valid source IDs
with open(VALID_IDS_FILE, 'r') as f:
    valid_source_ids = set(json.load(f))
print(f"Loaded {len(valid_source_ids)} valid source IDs")

# Load and filter samples
samples = []
skipped_source = 0
skipped_tokens = 0

with open(VAL_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        entry = json.loads(line)
        
        # Filter by valid source
        if entry['source_id'] not in valid_source_ids:
            skipped_source += 1
            continue
        
        # Build prompt to check token count
        prompt = f"""### Instruction:
Fix the SysML v2 syntax error in the code below.

### Compiler Error:
{entry['error_message']}

### Broken Code:
{entry['bad_code']}

### Analysis & Fix:
"""
        token_count = len(tokenizer.encode(prompt))
        
        if token_count > MAX_PROMPT_TOKENS:
            skipped_tokens += 1
            continue
        
        entry['prompt'] = prompt
        entry['token_count'] = token_count
        samples.append(entry)

print(f"Loaded {len(samples)} samples")
print(f"  Skipped (invalid source): {skipped_source}")
print(f"  Skipped (too long): {skipped_tokens}")

# =============================================================================
# Evaluation
# =============================================================================

validator = SysMLValidator()

results = []
test_samples = samples[20:20+NUM_SAMPLES]

for i, entry in enumerate(test_samples):
    source_id = entry['source_id']
    mutation = entry['mutation_type']
    
    print(f"\n{'='*60}")
    print(f"Sample {i+1}/{len(test_samples)}: {source_id} / {mutation}")
    
    # Generate
    inputs = tokenizer(entry['prompt'], return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    generated = response[len(entry['prompt']):]
    
    # Extract code
    fixed_code = None
    lines = generated.split('\n')
    for j, line in enumerate(lines):
        if 'code' in line.lower():
            fixed_code = '\n'.join(lines[j+1:]).strip()
            break
    
    # Validate
    if fixed_code:
        result = validator.validate_code(fixed_code)
        compiles = result['success']
    else:
        compiles = False
    
    # Print details for failures
    if not compiles:
        print(f"\n  --- RAW OUTPUT ({len(generated)} chars) ---")
        print(generated[:600])
        print(f"\n  --- EXTRACTED CODE ({len(fixed_code) if fixed_code else 0} chars) ---")
        print(fixed_code[:400] if fixed_code else "None")
        print(f"\n  --- GROUND TRUTH ({len(entry['good_code'])} chars) ---")
        print(entry['good_code'][:400])
        if fixed_code:
            print(f"\n  --- ERROR ---")
            print(result['errors'][0][:150] if result['errors'] else "Unknown")
    else:
        # raw output for success
        print(f"  RAW OUTPUT ({len(generated)} chars):")
        print(generated[:600])
        print(f"\n  --- EXTRACTED CODE ({len(fixed_code) if fixed_code else 0} chars) ---")
        print(fixed_code[:400] if fixed_code else "None")
        print(f"\n  --- GROUND TRUTH ({len(entry['good_code'])} chars) ---")
        print(entry['good_code'][:400])
        print(f"  PASS!")
    
    results.append({
        'source_id': source_id,
        'mutation': mutation,
        'compiles': compiles,
        'extracted_code': fixed_code is not None,
    })

validator.shutdown()

# =============================================================================
# Summary
# =============================================================================

print(f"\n{'='*60}")
print("RESULTS")
print(f"{'='*60}")

extracted = sum(1 for r in results if r['extracted_code'])
compiled = sum(1 for r in results if r['compiles'])

print(f"Code extracted: {extracted}/{len(results)} ({extracted/len(results)*100:.0f}%)")
print(f"Compiles:       {compiled}/{len(results)} ({compiled/len(results)*100:.0f}%)")