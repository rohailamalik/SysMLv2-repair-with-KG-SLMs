import torch
import re
import textwrap
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

# --- IMPORT YOUR KG ---
from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS

# --- CONFIGURATION ---
BASE_MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTER_PATH = "./sysml_repair_model_rag_full_set"

def load_inference_model():
    print("Loading Base Model...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.float16,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID, quantization_config=bnb_config, device_map="cuda:0"
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    
    print("Loading Adapters...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    return model, tokenizer

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

def ask_model(model, tokenizer, bad_code):
    kg_context = get_kg_context(bad_code)
    
    # We show the model an example where it SWAPS the connection to a valid neighbor.
    one_shot_example = textwrap.dedent("""\
        ### Instruction:
        Analyze the SysML v2 code for semantic domain inconsistencies. Provide a reasoning trace, then the fixed code.

        ### Knowledge Context:
        - 'EnginePort' belongs to Domain: mechanical_torque
        - 'LightBulbSocket' belongs to Domain: electrical_power
        - 'TransmissionPort' belongs to Domain: mechanical_torque
        Valid Connections Rules:
        - mechanical_torque can ONLY connect to: ['mechanical_torque']

        ### Broken Code:
        part system {
            part eng : Engine;      // mechanical
            part bulb : Light;      // electrical
            part trans : Gearbox;   // mechanical
            
            // Error: Connecting Mechanical to Electrical
            connect eng.p to bulb.p;
        }

        ### Analysis & Fix:
        [ANALYSIS]
        The code connects 'EnginePort' (mechanical_torque) to 'LightBulbSocket' (electrical_power).
        This violates the rule: mechanical_torque can ONLY connect to mechanical_torque.
        FOUND ERROR: Domain mismatch.
        SEARCH: Looking for a valid 'mechanical_torque' component in the system...
        FOUND TARGET: 'trans' (Gearbox) is mechanical_torque.
        ACTION: Reroute connection from 'bulb.p' to 'trans.p'.
        [/ANALYSIS]

        [FIXED CODE]
        part system {
            part eng : Engine;      // mechanical
            part bulb : Light;      // electrical
            part trans : Gearbox;   // mechanical
            
            // Fixed: Re-routed to valid mechanical target
            connect eng.p to trans.p;
        }
        """)

    # this is the actual prompt we want to answer
    actual_prompt = textwrap.dedent(f"""\
        ### Instruction:
        Analyze the SysML v2 code for semantic domain inconsistencies using the provided Knowledge Graph rules. Provide a reasoning trace, then the fixed code.

        ### Knowledge Context:
        {kg_context}

        ### Broken Code:
        {bad_code}

        ### Analysis & Fix:
        """)
    
    full_prompt = one_shot_example + "\n\n" + actual_prompt

    inputs = tokenizer(full_prompt, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs, 
            max_new_tokens=512, 
            eos_token_id=tokenizer.eos_token_id,
            temperature=0.1 
        )
        
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    if "### Analysis & Fix:" in full_output:
        # Get the last analysis block 
        response = full_output.split("### Analysis & Fix:")[-1].strip()
    else:
        response = full_output
    return response

def ask_model_cot(model, tokenizer, bad_code):
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
    
    inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
    
    with torch.no_grad():
        outputs = model.generate(
            **inputs, 
            max_new_tokens=512, 
            eos_token_id=tokenizer.eos_token_id,
            temperature=0.1 
        )
        
    full_output = tokenizer.decode(outputs[0], skip_special_tokens=True)
    # We return the whole thing so you can see the "Thought"
    return full_output.split("### Analysis & Fix:")[-1].strip()

if __name__ == "__main__":
    model, tokenizer = load_inference_model()
    
    print("\n" + "="*60)
    print("TEST: ONE-SHOT PRIMED REPAIR")
    print("============================================================")

    blind_code = """package BlindRepair {
    part def Axle { port p : AxlePort; }
    part def Wheel { port p : WheelHubIF; }
    part def FuelTank { port p : FuelPort; }
    
    part system {
        part axle : Axle;
        part wheel : Wheel;
        part tank : FuelTank;
        
        connect axle.p to tank.p; 
    }
}"""

    fix = ask_model(model, tokenizer, blind_code)
    print(f"[MODEL OUTPUT]:\n{fix}")