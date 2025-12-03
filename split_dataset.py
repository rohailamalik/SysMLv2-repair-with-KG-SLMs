#!/usr/bin/env python3
"""
Dataset Splitter for SysML v2 Debugging Research
-------------------------------------------------
Splits syntax and domain-aware error datasets into train/validation sets.

Key principles:
- Split by source_id to prevent data leakage (no file appears in both train and val)
- Stratify to ensure rare heuristics are represented in validation
- Combine both datasets with category labels

Usage:
    python split_dataset.py --syntax <syntax_file> --domain <domain_file> --output_dir <dir> --val_ratio 0.2
"""

import json
import argparse
import random
from pathlib import Path
from collections import defaultdict
from typing import Dict, Set, List, Tuple

def load_jsonl(filepath: str) -> List[dict]:
    """Load a JSONL file and return list of records."""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"Warning: Skipping malformed JSON at line {line_num}: {e}")
    return records

def save_jsonl(records: List[dict], filepath: str):
    """Save records to a JSONL file."""
    with open(filepath, 'w', encoding='utf-8') as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')

def analyze_datasets(syntax_records: List[dict], domain_records: List[dict]) -> dict:
    """
    Analyze both datasets and build mappings for stratified splitting.
    
    Returns a dict with:
    - all_source_ids: set of all unique source_ids
    - source_to_heuristics: mapping of source_id -> set of (category, mutation_type)
    - heuristic_to_sources: mapping of (category, mutation_type) -> set of source_ids
    - heuristic_counts: mapping of (category, mutation_type) -> sample count
    """
    all_source_ids = set()
    source_to_heuristics = defaultdict(set)  # source_id -> set of (category, mutation_type)
    heuristic_to_sources = defaultdict(set)  # (category, mutation_type) -> set of source_ids
    heuristic_counts = defaultdict(int)       # (category, mutation_type) -> count
    
    # Process syntax records
    for record in syntax_records:
        src_id = record['source_id']
        mut_type = record['mutation_type']
        key = ('syntax', mut_type)
        
        all_source_ids.add(src_id)
        source_to_heuristics[src_id].add(key)
        heuristic_to_sources[key].add(src_id)
        heuristic_counts[key] += 1
    
    # Process domain records
    for record in domain_records:
        src_id = record['source_id']
        mut_type = record['mutation_type']
        key = ('domain', mut_type)
        
        all_source_ids.add(src_id)
        source_to_heuristics[src_id].add(key)
        heuristic_to_sources[key].add(src_id)
        heuristic_counts[key] += 1
    
    return {
        'all_source_ids': all_source_ids,
        'source_to_heuristics': dict(source_to_heuristics),
        'heuristic_to_sources': {k: v for k, v in heuristic_to_sources.items()},
        'heuristic_counts': dict(heuristic_counts)
    }

def stratified_source_split(
    analysis: dict,
    val_ratio: float = 0.2,
    seed: int = 42
) -> Tuple[Set[str], Set[str]]:
    """
    Split source_ids into train and validation sets with stratification.
    
    Strategy:
    1. Sort heuristics by rarity (fewest sources first)
    2. For each rare heuristic, ensure at least one contributing source is in validation
    3. Fill remaining validation quota with random sampling
    """
    random.seed(seed)
    
    all_source_ids = analysis['all_source_ids']
    heuristic_to_sources = analysis['heuristic_to_sources']
    heuristic_counts = analysis['heuristic_counts']
    
    n_total = len(all_source_ids)
    n_val_target = int(n_total * val_ratio)
    
    print(f"\n{'='*70}")
    print("STRATIFIED SPLITTING")
    print(f"{'='*70}")
    print(f"Total unique source_ids: {n_total}")
    print(f"Target validation source_ids: {n_val_target} ({val_ratio*100:.0f}%)")
    
    # Sort heuristics by number of contributing sources (rarest first)
    heuristics_by_rarity = sorted(
        heuristic_to_sources.keys(),
        key=lambda h: len(heuristic_to_sources[h])
    )
    
    val_source_ids = set()
    covered_heuristics = set()
    
    print(f"\nEnsuring rare heuristics are covered in validation:")
    
    # Phase 1: Ensure coverage of rare heuristics
    for heuristic in heuristics_by_rarity:
        if heuristic in covered_heuristics:
            continue
            
        sources_for_heuristic = heuristic_to_sources[heuristic]
        n_sources = len(sources_for_heuristic)
        
        # Check if any source already in validation covers this heuristic
        already_covered = any(src in val_source_ids for src in sources_for_heuristic)
        
        if not already_covered and len(val_source_ids) < n_val_target:
            # Pick a source that covers the most uncovered heuristics
            # This greedy approach helps with efficiency
            best_source = None
            best_coverage = 0
            
            for src in sources_for_heuristic:
                if src in val_source_ids:
                    continue
                # Count how many uncovered heuristics this source would cover
                src_heuristics = analysis['source_to_heuristics'][src]
                new_coverage = len(src_heuristics - covered_heuristics)
                if new_coverage > best_coverage:
                    best_coverage = new_coverage
                    best_source = src
            
            if best_source:
                val_source_ids.add(best_source)
                newly_covered = analysis['source_to_heuristics'][best_source]
                covered_heuristics.update(newly_covered)
                
                category, mut_type = heuristic
                print(f"  - Added {best_source} for [{category}] {mut_type} "
                      f"(covers {best_coverage} heuristics, {n_sources} sources available)")
    
    # Phase 2: Fill remaining validation quota randomly
    remaining_sources = list(all_source_ids - val_source_ids)
    random.shuffle(remaining_sources)
    
    n_to_add = n_val_target - len(val_source_ids)
    if n_to_add > 0:
        additional = remaining_sources[:n_to_add]
        val_source_ids.update(additional)
        print(f"\nAdded {len(additional)} additional random source_ids to reach target")
    
    train_source_ids = all_source_ids - val_source_ids
    
    return train_source_ids, val_source_ids

def apply_split(
    syntax_records: List[dict],
    domain_records: List[dict],
    train_source_ids: Set[str],
    val_source_ids: Set[str]
) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    """
    Apply the source_id split to both datasets.
    Returns (train_syntax, val_syntax, train_domain, val_domain).
    """
    train_syntax = []
    val_syntax = []
    train_domain = []
    val_domain = []
    
    # Process syntax records
    for record in syntax_records:
        if record['source_id'] in train_source_ids:
            train_syntax.append(record)
        else:
            val_syntax.append(record)
    
    # Process domain records
    for record in domain_records:
        if record['source_id'] in train_source_ids:
            train_domain.append(record)
        else:
            val_domain.append(record)
    
    return train_syntax, val_syntax, train_domain, val_domain

def print_split_statistics(
    train_syntax: List[dict],
    val_syntax: List[dict],
    train_domain: List[dict],
    val_domain: List[dict],
    train_source_ids: Set[str],
    val_source_ids: Set[str]
):
    """Print detailed statistics about the split."""
    print(f"\n{'='*70}")
    print("SPLIT STATISTICS")
    print(f"{'='*70}")
    
    # Overall counts
    print(f"\n--- Source ID Split ---")
    print(f"Training source_ids:   {len(train_source_ids):>6}")
    print(f"Validation source_ids: {len(val_source_ids):>6}")
    print(f"Total:                 {len(train_source_ids) + len(val_source_ids):>6}")
    
    total_train = len(train_syntax) + len(train_domain)
    total_val = len(val_syntax) + len(val_domain)
    total_all = total_train + total_val
    
    print(f"\n--- Sample Split ---")
    print(f"Training samples:   {total_train:>6}")
    print(f"Validation samples: {total_val:>6}")
    print(f"Total:              {total_all:>6}")
    print(f"Actual val ratio:   {total_val / total_all * 100:.1f}%")
    
    # By category
    print(f"\n--- By Category ---")
    print(f"{'Category':<12} {'Train':>8} {'Val':>8} {'Val%':>8}")
    print(f"{'-'*40}")
    
    syntax_total = len(train_syntax) + len(val_syntax)
    domain_total = len(train_domain) + len(val_domain)
    
    print(f"{'Syntax':<12} {len(train_syntax):>8} {len(val_syntax):>8} {len(val_syntax)/syntax_total*100 if syntax_total > 0 else 0:>7.1f}%")
    print(f"{'Domain':<12} {len(train_domain):>8} {len(val_domain):>8} {len(val_domain)/domain_total*100 if domain_total > 0 else 0:>7.1f}%")
    
    # By heuristic
    print(f"\n--- By Heuristic (Mutation Type) ---")
    
    heuristic_stats = defaultdict(lambda: {'train': 0, 'val': 0})
    
    for r in train_syntax:
        key = ('syntax', r['mutation_type'])
        heuristic_stats[key]['train'] += 1
    for r in val_syntax:
        key = ('syntax', r['mutation_type'])
        heuristic_stats[key]['val'] += 1
    for r in train_domain:
        key = ('domain', r['mutation_type'])
        heuristic_stats[key]['train'] += 1
    for r in val_domain:
        key = ('domain', r['mutation_type'])
        heuristic_stats[key]['val'] += 1
    
    # Sort by category then by total count descending
    sorted_heuristics = sorted(
        heuristic_stats.keys(),
        key=lambda k: (k[0], -(heuristic_stats[k]['train'] + heuristic_stats[k]['val']))
    )
    
    current_category = None
    for category, mut_type in sorted_heuristics:
        if category != current_category:
            print(f"\n  [{category.upper()}]")
            print(f"  {'Heuristic':<45} {'Train':>7} {'Val':>7} {'Val%':>7}")
            print(f"  {'-'*70}")
            current_category = category
        
        stats = heuristic_stats[(category, mut_type)]
        total = stats['train'] + stats['val']
        val_pct = stats['val'] / total * 100 if total > 0 else 0
        
        # Flag if validation has 0 samples
        flag = " ⚠️" if stats['val'] == 0 else ""
        print(f"  {mut_type:<45} {stats['train']:>7} {stats['val']:>7} {val_pct:>6.1f}%{flag}")

def verify_no_leakage(
    train_syntax: List[dict],
    val_syntax: List[dict],
    train_domain: List[dict],
    val_domain: List[dict]
) -> bool:
    """Verify there's no source_id overlap between train and validation."""
    train_sources = {r['source_id'] for r in train_syntax + train_domain}
    val_sources = {r['source_id'] for r in val_syntax + val_domain}
    
    overlap = train_sources & val_sources
    
    if overlap:
        print(f"\n⚠️  WARNING: Data leakage detected!")
        print(f"   {len(overlap)} source_ids appear in both train and validation:")
        for src in sorted(overlap)[:10]:
            print(f"     - {src}")
        if len(overlap) > 10:
            print(f"     ... and {len(overlap) - 10} more")
        return False
    else:
        print(f"\n✓ No data leakage: train and validation source_ids are disjoint")
        return True

def main():
    parser = argparse.ArgumentParser(
        description='Split SysML debugging datasets by source_id with stratification'
    )
    parser.add_argument('--syntax', required=True, help='Path to syntax error JSONL file')
    parser.add_argument('--domain', required=True, help='Path to domain error JSONL file')
    parser.add_argument('--output_dir', default='.', help='Output directory for split files')
    parser.add_argument('--val_ratio', type=float, default=0.2, help='Validation set ratio (default: 0.2)')
    parser.add_argument('--seed', type=int, default=42, help='Random seed for reproducibility')
    
    args = parser.parse_args()
    
    print(f"{'='*70}")
    print("SysML Dataset Splitter")
    print(f"{'='*70}")
    print(f"Syntax file:  {args.syntax}")
    print(f"Domain file:  {args.domain}")
    print(f"Output dir:   {args.output_dir}")
    print(f"Val ratio:    {args.val_ratio}")
    print(f"Random seed:  {args.seed}")
    
    # Load datasets
    print(f"\nLoading datasets...")
    syntax_records = load_jsonl(args.syntax)
    domain_records = load_jsonl(args.domain)
    print(f"  Syntax records: {len(syntax_records)}")
    print(f"  Domain records: {len(domain_records)}")
    
    # Analyze
    print(f"\nAnalyzing datasets...")
    analysis = analyze_datasets(syntax_records, domain_records)
    print(f"  Unique source_ids: {len(analysis['all_source_ids'])}")
    print(f"  Unique heuristics: {len(analysis['heuristic_counts'])}")
    
    # Split
    train_source_ids, val_source_ids = stratified_source_split(
        analysis,
        val_ratio=args.val_ratio,
        seed=args.seed
    )
    
    # Apply split
    train_syntax, val_syntax, train_domain, val_domain = apply_split(
        syntax_records, domain_records,
        train_source_ids, val_source_ids
    )
    
    # Statistics
    print_split_statistics(
        train_syntax, val_syntax, train_domain, val_domain,
        train_source_ids, val_source_ids
    )
    
    # Verify no leakage
    verify_no_leakage(train_syntax, val_syntax, train_domain, val_domain)
    
    # Save
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    train_syntax_path = output_dir / 'train_syntax.jsonl'
    val_syntax_path = output_dir / 'val_syntax.jsonl'
    train_domain_path = output_dir / 'train_domain.jsonl'
    val_domain_path = output_dir / 'val_domain.jsonl'
    
    print(f"\nSaving split datasets...")
    save_jsonl(train_syntax, str(train_syntax_path))
    save_jsonl(val_syntax, str(val_syntax_path))
    save_jsonl(train_domain, str(train_domain_path))
    save_jsonl(val_domain, str(val_domain_path))
    
    print(f"  train_syntax.jsonl:  {len(train_syntax):>5} samples")
    print(f"  val_syntax.jsonl:    {len(val_syntax):>5} samples")
    print(f"  train_domain.jsonl:  {len(train_domain):>5} samples")
    print(f"  val_domain.jsonl:    {len(val_domain):>5} samples")
    
    # Also save the source_id assignments for reproducibility
    split_info = {
        'train_source_ids': sorted(train_source_ids),
        'val_source_ids': sorted(val_source_ids),
        'val_ratio': args.val_ratio,
        'seed': args.seed,
        'counts': {
            'train_syntax': len(train_syntax),
            'val_syntax': len(val_syntax),
            'train_domain': len(train_domain),
            'val_domain': len(val_domain)
        }
    }
    split_info_path = output_dir / 'split_info.json'
    with open(split_info_path, 'w') as f:
        json.dump(split_info, f, indent=2)
    print(f"  split_info.json:     (source_id assignments)")
    
    print(f"\n{'='*70}")
    print("Done!")
    print(f"{'='*70}")

if __name__ == '__main__':
    main()