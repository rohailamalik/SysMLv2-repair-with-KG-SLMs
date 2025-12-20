from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS
from typing import List, Dict, Tuple, Set
from datasets import Dataset
import re, random
from collections import defaultdict
from patching import create_fixes, create_patches, remove_comments

SOLUTION_MAP = {
    "Type mismatch": "To solve this, the attribute declaration should be renamed correctly based on semantic meaning.",
    "Domain violation": "To solve this, we need to reroute this connection to a compatible port as per the rules.",
    "Quantity mismatch": "To solve this, we need to assign correct units to this attribute.",
    "Unit expression corruption": "To solve this, the unit must be corrected to valid form."
}

def fetch_domain_rules(code: str) -> str:
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
    
    rules = "\n".join(context_lines)

    return (
        "\nUse these relevant domain rules to identify and fix any potential mistakes.\n"
        "### Domain Rules:\n"
        f"{rules}\n"
        "\n"
    )



def _parse_error_message(error: str) -> Tuple[str, str]:
    """Parses an error message into error type and description."""

    error = error.replace("ERROR:", "").strip()
    
    if " (line : " in error:
        error = error.split(" (line : ")[0].strip()
    
    parts = error.split(":", 1)
    err_type = parts[0].strip()
    err_desc = parts[1].strip() if len(parts) > 1 else ""
    
    return err_type, err_desc


def _create_thought(error_message: str, mutation_category: str) -> str:
    """Generates analysis thought process based on error type."""
    
    if mutation_category == "none":
        thought = (
            "Let's think step-by-step.\n"
            "Checking the rules, reading the code.\n"
            "The code seems to be in-line with all the presented rules and does not have any syntax errors."
        )
    
    elif mutation_category == "domain":
        error_type, error_desc = _parse_error_message(error_message)
        solution = SOLUTION_MAP.get(error_type, "")
        thought = (
            "Let's think step-by-step.\n"
            "Checking the rules, reading the code.\n"
            f"{error_desc}\n"
            f"{solution}"
        )
    
    elif mutation_category == "syntax":
        thought = (
            "Let's think step-by-step.\n"
            "The compiler reports syntax errors.\n"
            "To solve this, we need to fix the syntax issues in the code at the reported lines."
        )
    else:
        raise ValueError(f"Unknown mutation category: {mutation_category}")

    return f"<THINK>\n{thought}\n</THINK>\n"
    
    


def _create_prompt(error_message: str, mutation_category: str, bad_code: str) -> str:
    """Creates a prompt for the LLM based on error type."""

    if mutation_category == "syntax":
        return (
            "Analyze and repair the following SysML v2 code for errors reported by the compiler.\n"
            "\n"
            "### Compiler Error:\n"
            f"{error_message}\n"
            "\n"
            "### Code:\n"
            "```\n"
            f"{bad_code}\n"
            "```"
        )
    
    else:  # for domain and correct examples
        return (
            "Analyze the following SysML v2 code for any potential domain inconsistencies or mistakes, and repair accordingly.\n"
            "\n"
            "### Code:\n"
            "```\n"
            f"{bad_code}\n"
            "```"
        )


def _create_response(fixes: str) -> str:
    """Creates the completion response with fix."""

    if not fixes:
        response = "\n<NO_CHANGE>\n"
    else:
        fixes = [f"<FIX>\n{fix}\n</FIX>" for fix in fixes]
        response = "\n".join(fixes)
    
    return response



def processing_function(example, tokenizer) -> Dict:
    """Create patches, fix, prompts, fix responses, chat and its length for an entry"""
    try:
        error_msg = example["error_message"]
        category = example["mutation_category"]
        bad_code = remove_comments(example["bad_code"])
        good_code = remove_comments(example["good_code"]) 
        # comments are removed due to them being leftover during dataset synthesis

        prompt = _create_prompt(error_msg, category, bad_code)
        rules = fetch_domain_rules(bad_code)
        
        thought = _create_thought(error_msg, category)
        patches = create_patches(bad_code, good_code)
        fixes = create_fixes(patches)
        response = _create_response(fixes)
        
        chat = [
            {"role": "user", "content": prompt + rules},
            {"role": "assistant", "content": thought + response + tokenizer.eos_token},
        ]

        ids = tokenizer.apply_chat_template(
            chat,
            tokenize=True,
            add_generation_prompt=False,
        ) # this is only for length computation here since internally template is applied anyways

        return {
            "bad_code": bad_code,
            "good_code": good_code,
            "patches": patches,
            "prompt": prompt,
            "rules": rules,
            "thought": thought,
            "response": response,
            "length": len(ids),
        }

    except Exception as e:
        raise RuntimeError(f"Error encountered at entry id {example["id"]}")


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

    # Calculate how many we need BEFORE updating
    val_needed = max(0, n_val - len(val_sources))
    val_sources.update(remaining[:val_needed])
    remaining = remaining[val_needed:]  # ← Use stored value

    test_needed = max(0, n_test - len(test_sources))
    test_sources.update(remaining[:test_needed])

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
    overlap_val_test = val_ids & test_ids
    
    # Val-Test overlap doesnt really matter since model is not being trained on val
    if overlap_train_val or overlap_train_test:
        raise ValueError(f"Data leakage detected! "
                        f"train-val: {len(overlap_train_val)}, "
                        f"train-test: {len(overlap_train_test)}, "
                        f"val-test: {len(overlap_val_test)}")
        
    print(f"Split sizes: train={len(train)}, val={len(val)}, test={len(test)}")
    
    return train, val, test