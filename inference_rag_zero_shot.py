import torch
import re
import textwrap
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

# --- IMPORT YOUR KG ---
from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS

# --- CONFIGURATION ---
BASE_MODEL_ID = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
ADAPTER_PATH = "./sysml_repair_model_full_set" 

def load_inference_model():
    print("Loading Base Model...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    base_model = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL_ID, quantization_config=bnb_config, device_map="cuda:0"
    )
    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_ID)
    
    print("Loading RAG-Trained Adapters...")
    model = PeftModel.from_pretrained(base_model, ADAPTER_PATH)
    return model, tokenizer

def get_kg_context(code):
    context_lines = []
    found_domains = set()
    for type_name, domain in TYPE_TO_DOMAIN.items():
        # Regex matches whole words only
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
    # 1. Retrieve Context from KG
    kg_context = get_kg_context(bad_code)
    
    # 2. Construct Prompt (Matches Training Format EXACTLY)
    instruction = "You are a SysML v2 repair assistant. The code compiles, but check for semantic domain inconsistencies."
    if kg_context:
        instruction += f"\n\nUse these Domain Rules to verify connections:\n{kg_context}"

    prompt = textwrap.dedent(f"""\
        ### Instruction:
        {instruction}

        ### Compiler Error:
        None

        ### Broken Code:
        {bad_code}

        ### Fixed Code:
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
    
    if "### Fixed Code:" in full_output:
        response = full_output.split("### Fixed Code:")[-1].strip()
    else:
        response = full_output
        
    return response, kg_context

if __name__ == "__main__":
    model, tokenizer = load_inference_model()
    
    print("\n" + "="*60)
    print("TEST: BLIND RAG REPAIR (NO HINTS)")
    print("Scenario: Mechanical connected to Fluid. Mechanical alternative exists.")
    print("="*60)

    # The Blind Test Case
    blind_code = """package Test_System_Blind {
    
    port def AxlePort;
    port def FuelPort;
    port def WheelHubIF;

    part def AxlePort_Def {
        port p : AxlePort;
    }
    
    part def FuelPort_Def {
        port p : FuelPort;
    }
    
    part def WheelHubIF_Def {
        port p : WheelHubIF;
    }
    
    part def SubSystem_Context {
        part comp_axle : AxlePort_Def;
        part comp_tank : FuelPort_Def;
        part comp_wheel : WheelHubIF_Def;
        
        connect comp_axle.p to comp_tank.p;
    }
}"""

    fix, context = ask_model(model, tokenizer, blind_code)
    
    print(f"\n[INJECTED CONTEXT]:\n{context}")
    print("-" * 30)
    print(f"[MODEL OUTPUT]:\n{fix}")