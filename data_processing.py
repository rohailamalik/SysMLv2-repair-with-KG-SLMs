from transformers import AutoTokenizer
from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS
from typing import List, Dict, Tuple, Set
from datasets import Dataset
import re, textwrap, random
import pandas as pd
import random
from collections import defaultdict
from pathlib import Path

MODEL_NAME = "Qwen/Qwen2.5-Coder-1.5B-Instruct"
MAX_LEN = 2048
DATASET_PATH = "dataset/complete_sysmlv2_dataset.jsonl"

SOLUTION_MAP = {
    "Type mismatch": "To solve this, the attribute declaration should be renamed correctly based on semantic meaning",
    "Domain violation": "To solve this, we need to reroute this connection to a compatible port as per the rules",
    "Quantity mismatch": "To solve this, we need to assign correct units to this attribute",
    "Unit expression corruption": "To solve this, the unit must be corrected to valid form"
}

SYSTEM_PROMPT = """
You are a SysML v2 expert. Your task is to analyse a given SysML v2 code and fix it if it has issues.
The code may be accompanied by an error from the compiler. 
Or if the compiler did not report any errors, a set of relevant domain rules.
Use the error description or domain rules to find the mistakes in the code. 
Note that presence of domain rules does not guarentee that the code is broken.
Think step by step, and instead of rewriting the entire code correctly, tell the precise fixes.
These include telling the user which code part should be replaced by which one, or which part should be deleted or inserted, etc.
Make sure to tell the user where exactly the changes are to be made, by using previous code lines as context.
Adhere to the following templates in your answer. First think, and then for each fix:

If it's about replacing code:
```
// AFTER THIS CODE (OPTIONAL)
previous code lines indicating where to make changes

// REPLACE
put old code snipper here

// WITH 
put new code snippet here
```

If it's about deleting some code:
```
// AFTER THIS CODE 
previous code lines to indicate where to make changes

// DELETE
put old code snipper here, which is to be deleted
```

If it's about adding new code:
```
// AFTER THIS CODE
previous code lines to indicate where to make changes

// INSERT
put the new code snippet here which is to be inserted
```
"""

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
if tokenizer.pad_token is None:
    tokenizer.pad_token = tokenizer.eos_token


def get_kg_context(code: str) -> str:
    """Scans code and retrieves relevant domain rules."""

    found_domains: Set[str] = set()
    context_lines: List[str] = []
    
    # Find all matching types and their domains
    for type_name, domain in TYPE_TO_DOMAIN.items():
        if re.search(rf'\b{re.escape(type_name)}\b', code):
            context_lines.append(f"- '{type_name}' belongs to Domain: {domain}")
            found_domains.add(domain)
    
    # Add connection rules if domains were found
    if found_domains:
        context_lines.append("\nValid Connections Rules:")
        for domain in sorted(found_domains):  # Sort for consistency
            allowed = VALID_CONNECTIONS.get(domain, [])
            context_lines.append(f"- {domain} can ONLY connect to: {allowed}")
    
    return "\n".join(context_lines)


def parse_error_message(error_string: str) -> Tuple[str, str]:
    """Parses an error message into error type and description."""

    cleaned = error_string.replace("ERROR:", "").strip()
    
    if " (line : " in cleaned:
        cleaned = cleaned.split(" (line : ")[0].strip()
    
    parts = cleaned.split(":", 1)
    error_type = parts[0].strip()
    message = parts[1].strip() if len(parts) > 1 else ""
    
    return error_type, message


def create_thought(error_message: str, mutation_category: str) -> str:
    """Generates analysis thought process based on error type."""
    
    if mutation_category == "domain":
        error_type, error_desc = parse_error_message(error_message)
        solution = SOLUTION_MAP.get(error_type, "")
        return (
            f"<think>Let's think step-by-step.\n"
            f"Checking the rules, reading the code.\n"
            f"{error_desc}.\n"
            f"{solution}<think>."
        )
    elif mutation_category == "syntax":
        return (
            "<think>Let's think step-by-step.\n"
            "The compiler reports syntax errors.\n"
            "To solve this, we need to fix the syntax issues in the code at the reported lines.<think>"
        )
    
    return ""


def create_fix(patches: List[Dict[str, str]]) -> str:
    """Formats patch instructions into a readable fix description."""
    
    fixes: List[str] = ["Fix: \n"]
    
    for patch in patches:
        context = patch.get("context", "")
        before = patch.get("before", "")
        after = patch.get("after", "")
        
        parts: List[str] = []

        # one block per patch
        
        # Add separator for subsequent patches
        #parts.append("\n\n## AND " if i > 0 else "### ")
        parts.append("```") # start
        
        # Add context if present
        if context:
            #parts.append(f"AFTER THIS CODE:\n{context}\n\n")
            parts.append(f"// AFTER THIS CODE:\n{context}\n")
        
        # Determine and format operation type
        if before and after:
            #parts.append(f"## REPLACE:\n{before}\n\n## WITH:\n{after}")
            parts.append(f"// REPLACE\n{before}\n// WITH\n{after}")
        elif before:
            parts.append(f"// DELETE\n{before}")
        elif after:
            #parts.append(f"## INSERT:\n{after}")
            parts.append(f"// INSERT:\n{after}")

        parts.append("```") # end
        
        fixes.append("".join(parts))
    
    return "".join(fixes)


def create_prompt(error_message: str, mutation_category: str, bad_code: str) -> str:
    """Creates a prompt for the LLM based on error type."""

    if mutation_category == "syntax":
        return textwrap.dedent(f"""\
            Analyze the following SysML v2 code for errors reported by the compiler. 
            Think step by step, and then provide fixes.
            
            ### Compiler Error:
            {error_message}
            
            ### Code:
            ```
            {bad_code}
            ```
        """)
    
    elif mutation_category == "domain":
        rules = get_kg_context(bad_code)
        return textwrap.dedent(f"""\
            Analyze the SysML v2 code for potential semantic domain inconsistencies using the provided relevant rules. 
            Think step by step, and then give fixes if any.
            
            ### Domain Rules:
            {rules}
            
            ### Code:
            ```
            {bad_code}
            ```
        """)
    
    return ""


def create_completion(error_message: str, mutation_category: str, patches: List[Dict[str, str]]) -> str:
    """Creates the completion response containing analysis and fix."""

    thought = create_thought(error_message, mutation_category)
    fix = create_fix(patches)

    return f"### ANALYSIS:\n{thought}\n\n### FIX:\n{fix}"


def processing_function(examples):
    """Processes the dataset to create complete messages and their lengths"""
    texts, lengths = [], []
    
    for err, cat, code, patch in zip(
        examples["error_message"],
        examples["mutation_category"],
        examples["bad_code"],
        examples["fix_patches"]
    ):
        
        question = create_prompt(err, cat, code)
        answer = create_completion(err, cat, patch) + tokenizer.eos_token

        chat = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
            {"role": "assistant", "content": answer}
        ]

        text = tokenizer.apply_chat_template( # here only done for computing lengths, internally done automatically so just pass dict chats
            chat,
            tokenize=False,
            add_generation_prompt=False
        )

        texts.append(chat)
        lengths.append(len(tokenizer(text)["input_ids"]))
       
    return {"messages": texts, "length": lengths}


def split_dataset(
    dataset: Dataset,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42
    ) -> Tuple[Dataset, Dataset, Dataset]:
    
    """
    Split dataset into train/val/test ensuring no source_id leakage.
    Stratifies by (mutation_category, mutation_type) to ensure rare heuristics
    are represented in all splits.
    
    Args:
        dataset: HuggingFace Dataset with 'source_id', 'mutation_category', 'mutation_type'
        val_ratio: Fraction for validation set
        test_ratio: Fraction for test set
        seed: Random seed
    
    Returns:
        (train_dataset, val_dataset, test_dataset)
    """

    random.seed(seed)
    
    # Build mappings
    source_to_heuristics = defaultdict(set)
    heuristic_to_sources = defaultdict(set)
    
    for i in range(len(dataset)):
        src_id = dataset[i]['source_id']
        key = (dataset[i]['mutation_category'], dataset[i]['mutation_type'])
        source_to_heuristics[src_id].add(key)
        heuristic_to_sources[key].add(src_id)
    
    all_sources = set(source_to_heuristics.keys())
    n_val = int(len(all_sources) * val_ratio)
    n_test = int(len(all_sources) * test_ratio)
    
    # Sort heuristics by rarity
    heuristics_sorted = sorted(heuristic_to_sources.keys(), 
                               key=lambda h: len(heuristic_to_sources[h]))
    
    val_sources = set()
    test_sources = set()
    covered_val = set()
    covered_test = set()
    
    # Ensure rare heuristics in validation
    for heuristic in heuristics_sorted:
        if heuristic in covered_val or len(val_sources) >= n_val:
            continue
        
        sources = heuristic_to_sources[heuristic]
        if not any(s in val_sources for s in sources):
            best = max((s for s in sources if s not in val_sources | test_sources),
                      key=lambda s: len(source_to_heuristics[s] - covered_val),
                      default=None)
            if best:
                val_sources.add(best)
                covered_val.update(source_to_heuristics[best])
    
    # Ensure rare heuristics in test
    for heuristic in heuristics_sorted:
        if heuristic in covered_test or len(test_sources) >= n_test:
            continue
        
        sources = heuristic_to_sources[heuristic]
        if not any(s in test_sources for s in sources):
            best = max((s for s in sources if s not in val_sources | test_sources),
                      key=lambda s: len(source_to_heuristics[s] - covered_test),
                      default=None)
            if best:
                test_sources.add(best)
                covered_test.update(source_to_heuristics[best])
    
    # Fill remaining quotas randomly
    remaining = list(all_sources - val_sources - test_sources)
    random.shuffle(remaining)
    
    val_sources.update(remaining[:max(0, n_val - len(val_sources))])
    remaining = remaining[max(0, n_val - len(val_sources)):]
    
    test_sources.update(remaining[:max(0, n_test - len(test_sources))])
    
    train_sources = all_sources - val_sources - test_sources
    
    # Split dataset using filter
    train_indices = [i for i in range(len(dataset)) if dataset[i]['source_id'] in train_sources]
    val_indices = [i for i in range(len(dataset)) if dataset[i]['source_id'] in val_sources]
    test_indices = [i for i in range(len(dataset)) if dataset[i]['source_id'] in test_sources]
    
    train = dataset.select(train_indices)
    val = dataset.select(val_indices)
    test = dataset.select(test_indices)
    
    # Verify no leakage
    train_ids = set(train['source_id'])
    val_ids = set(val['source_id'])
    test_ids = set(test['source_id'])
    
    overlap_train_val = train_ids & val_ids
    overlap_train_test = train_ids & test_ids
    
    # Val-Test overlap doesnt really matter since model is not being trained on val
    if overlap_train_val or overlap_train_test:
        raise ValueError(f"Data leakage detected! "
                        f"train-val: {len(overlap_train_val)}, "
                        f"train-test: {len(overlap_train_test)}")
        
    print(f"Split sizes: train={len(train)}, val={len(val)}, test={len(test)}")
    
    return train, val, test


def process_dataset(path: str = DATASET_PATH):
    path = Path(path).resolve()
    parent = path.parent
    
    df = pd.read_json(path, lines=True)
    ds = Dataset.from_pandas(df).map(processing_function, batched=True)
    ds = ds.filter(lambda x: x["length"] <= MAX_LEN)

    ds.to_json(parent / "dataset_with_limit_length.jsonl", lines=True)
    
    train_ds, val_ds, test_ds = split_dataset(ds)
    
    train_ds.to_json(parent / "training_dataset.jsonl", lines=True)
    val_ds.to_json(parent / "validation_dataset.jsonl", lines=True)
    test_ds.to_json(parent / "test_dataset.jsonl", lines=True)

    print(f"Split datasets saved to {parent}")


if __name__ == "__main__":
    process_dataset()