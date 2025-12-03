import json
import torch
import re
import textwrap
import jupyter_client
import queue
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

# --- IMPORT YOUR KG ---
from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS

# =============================================================================
# Config
# =============================================================================

BASE_MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTER_PATH = "./sysml_repair_model_rag_full_set"
VAL_FILE = "./split_data/val_domain.jsonl"
NUM_SAMPLES = 20  # Start small

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
# KG Context Helper
# =============================================================================

def get_kg_context(code):
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

# =============================================================================
# Step 1: Filter to valid samples
# =============================================================================

print("Loading domain validation samples...")
all_samples = []
with open(VAL_FILE, 'r', encoding='utf-8') as f:
    for line in f:
        all_samples.append(json.loads(line))

print(f"Total samples: {len(all_samples)}")

print("\nFiltering to samples where good_code compiles...")
validator = SysMLValidator()

valid_samples = []
for i, entry in enumerate(all_samples):
    result = validator.validate_code(entry['good_code'])
    if result['success']:
        valid_samples.append(entry)
    
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(all_samples)} - Valid so far: {len(valid_samples)}")

print(f"\nValid samples: {len(valid_samples)} / {len(all_samples)} ({len(valid_samples)/len(all_samples)*100:.1f}%)")

# =============================================================================
# Step 2: Load model
# =============================================================================

print("\nLoading model...")
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
)
base_model = AutoModelForCausalLM.from_pretrained(
    BASE_MODEL_ID, quantization_config=bnb_config, device_map="cuda:0"
)
tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
model.eval()
print("Model loaded!")

# =============================================================================
# Step 3: Evaluate
# =============================================================================

test_samples = valid_samples[:NUM_SAMPLES]
results = []

for i, entry in enumerate(test_samples):
    source_id = entry['source_id']
    mutation = entry['mutation_type']
    bad_code = entry['bad_code']
    good_code = entry['good_code']
    
    print(f"\n{'='*60}")
    print(f"Sample {i+1}/{len(test_samples)}: {source_id} / {mutation}")
    
    # Build prompt with KG context
    kg_context = get_kg_context(bad_code)
    
    prompt = textwrap.dedent(f"""\
        ### Instruction:
        Analyze the SysML v2 code for semantic domain inconsistencies using the provided Knowledge Graph rules. Provide a reasoning trace, then the fixed code.

        ### Knowledge Context:
        {kg_context}

        ### Broken Code:
        {bad_code}

        ### Analysis & Fix:
        """)
    
    # Generate
    inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=512,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    
    response = tokenizer.decode(outputs[0], skip_special_tokens=True)
    generated = response[len(prompt):]
    
    # Extract code - find line containing "code" and take everything after
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
        print(generated[:500])
        print(f"\n  --- EXTRACTED CODE ({len(fixed_code) if fixed_code else 0} chars) ---")
        print(fixed_code[:300] if fixed_code else "None")
        print(f"\n  --- GROUND TRUTH ({len(good_code)} chars) ---")
        print(good_code[:300])
        if fixed_code:
            print(f"\n  --- ERROR ---")
            print(result['errors'][0][:150] if result['errors'] else "Unknown")
    else:
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
print("DOMAIN ERROR RESULTS")
print(f"{'='*60}")

extracted = sum(1 for r in results if r['extracted_code'])
compiled = sum(1 for r in results if r['compiles'])

print(f"Code extracted: {extracted}/{len(results)} ({extracted/len(results)*100:.0f}%)")
print(f"Compiles:       {compiled}/{len(results)} ({compiled/len(results)*100:.0f}%)")

# Breakdown by mutation type
print(f"\nBy mutation type:")
mutation_stats = {}
for r in results:
    m = r['mutation']
    if m not in mutation_stats:
        mutation_stats[m] = {'total': 0, 'pass': 0}
    mutation_stats[m]['total'] += 1
    if r['compiles']:
        mutation_stats[m]['pass'] += 1

for m, stats in mutation_stats.items():
    print(f"  {m}: {stats['pass']}/{stats['total']}")