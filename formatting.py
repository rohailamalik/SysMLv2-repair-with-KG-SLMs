from knowledge import get_domain_rules
from datasets import Dataset
import random
from collections import defaultdict
from patching import create_diff_patch
from utils import remove_comments


def create_prompt(error_message: str, mutation_category: str, bad_code: str, add_rules: bool = True) -> str:

    if mutation_category == "syntax":
        prompt = (
            "The following SysML v2 code contains compiler-reported syntax errors.\n"
            "Repair the code so that it compiles successfully.\n"
            "\n"
            "Compiler Error:\n"
            f"{error_message}\n"
        )

    else:
        prompt = (
            "Check the SysML v2 code below for correctness with respect to the given domain constraints.\n"
            "Repair the code if it is incorrect.\n"
            "If the code is correct, simply report it as correct without rewriting it again.\n"
            "\n"
        )

        if add_rules:
            domain_rules = get_domain_rules(bad_code)
            prompt += f"{domain_rules}\n"

    prompt += (
        "\nCode:\n"
        "```sysml\n"
        f"{bad_code}\n"
        "```"
    )

    return prompt


def create_response(mutation_category: str, answer: str | None) -> str:

    if mutation_category == "none":
        return (
            "CODE STATUS = CORRECT\n"
            "NO CHANGES REQUIRED"
        )

    return (
        "CODE STATUS = INCORRECT\n"
        "```sysml\n"
        f"{answer}\n"
        "```"
    )


def processing_function(example, tokenizer) -> dict:
    """Create patches, fix, prompts, fix responses, chat and its length for an entry"""
  
    error_msg = example["error_message"]
    category = example["mutation_category"]
    
    # comments are removed due to them being leftover during dataset synthesis
    bad_code = remove_comments(example["bad_code"])
    good_code = remove_comments(example["good_code"])

    diff_patch = create_diff_patch(bad_code, good_code)

    base_prompt = create_prompt(error_msg, category, bad_code, add_rules=False) # without rules 
    prompt = create_prompt(error_msg, category, bad_code, add_rules=True) 

    code_resp = create_response(category, good_code)
    patch_resp = create_response(category, diff_patch)
    
    # this is only for length computation 
    chat = [
        {"role": "user", "content": "You are a SysML v2 expert."},
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": patch_resp + tokenizer.eos_token}
    ]

    # when training, chat template is applied automatically
    ids = tokenizer.apply_chat_template(
        chat,
        tokenize=True,
        add_generation_prompt=False,
    )

    return {
        "bad_code": bad_code,
        "good_code": good_code,
        "diff_patch": diff_patch,
        "base_prompt": base_prompt,
        "prompt": prompt,
        "code_response": code_resp,
        "patch_response": patch_resp,
        "length": len(ids),
    }


def split_dataset(
    dataset: Dataset,
    val_ratio: float = 0.15,
    test_ratio: float = 0.15,
    seed: int = 42
    ) -> tuple[Dataset, Dataset, Dataset]:
    
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
        
    print(f"Split sizes: train={len(train)}, val={len(val)}, test={len(test)}")
    print(f"Data Overlap: "
              f"train-val: {len(overlap_train_val)}, "
              f"train-test: {len(overlap_train_test)}, "
              f"val-test: {len(overlap_val_test)}")
    
    # Val-Test overlap doesnt really matter since model is not being trained on val
    if overlap_train_val or overlap_train_test:
        print("Data leakage detected!!")
    
    return train, val, test