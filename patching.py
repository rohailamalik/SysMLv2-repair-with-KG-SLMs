from typing import List, Dict, Optional
import difflib

# Used in one time preprocessing mainly. For creating patches from good and bad code comparison
def compare_code_lines(bad_lines: list[str], good_lines: list[str], merge_threshold: int) -> Optional[list[tuple]]:
    """Compare two lists of code lines and return merged diff hunks."""
    matcher = difflib.SequenceMatcher(a=bad_lines, b=good_lines)
    raw_hunks = [
        (i1, i2, j1, j2)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes()
        if tag != "equal"
    ]

    if not raw_hunks:
        return None

    merged = []
    current = list(raw_hunks[0])

    for i1, i2, j1, j2 in raw_hunks[1:]:
        if i1 - current[1] <= merge_threshold:
            current[1] = i2  # extend bad-region end
            current[3] = j2  # extend good-region end
        else:
            merged.append(tuple(current))
            current = [i1, i2, j1, j2]

    merged.append(tuple(current))
    return merged


def is_all_empty(strings: list[str]) -> bool:
    """Check if all strings are empty or whitespace-only."""
    return all(not s.strip() for s in strings)


def occurs_exactly_once(haystack: list[str], needle: list[str]) -> bool:
    """Check if needle appears exactly once in haystack."""
    if not needle:
        return False
    
    needle_len = len(needle)
    haystack_len = len(haystack)
    count = 0
    
    for i in range(haystack_len - needle_len + 1):
        if haystack[i : i + needle_len] == needle:
            count += 1
            if count > 1:  # Early exit optimization
                return False
    
    return count == 1


def generate_contextual_patches(
        bad_code: str,
        good_code: str,
        merge_threshold: int = 3, 
        max_context: int = 50
    ) -> List[Dict[str, str]]:

    """Generate contextual patches to transform bad_code into good_code."""
    bad_lines = bad_code.splitlines()
    good_lines = good_code.splitlines()

    merged = compare_code_lines(bad_lines, good_lines, merge_threshold)

    if not merged:
        return []

    patches = []

    for i1, i2, j1, j2 in merged:
        before_block = bad_lines[i1:i2]
        after_block = good_lines[j1:j2]

        # If before_block is non-empty and unique, no context needed
        if not is_all_empty(before_block) and occurs_exactly_once(bad_lines, before_block):
            
            patches.append({
                "context": "",
                "before": "\n".join(before_block),
                "after": "\n".join(after_block),
            })
        
        else:
            # Need to find unique context
            context_size = 0
            context_before = []

            while context_size < max_context:
                # Expand context backwards until we hit a non-empty line
                while context_size < i1:
                    context_size += 1
                    context_before = bad_lines[i1 - context_size : i1]
                    if not is_all_empty(context_before):
                        break
                
                # Check if context + before_block is unique
                candidate = context_before + before_block
                if occurs_exactly_once(bad_lines, candidate) or context_size >= i1:
                    break

                # Need more context - increment and continue
                if context_size < i1:
                    context_size += 1
                    context_before = bad_lines[i1 - context_size : i1]
                else:
                    break

            patches.append({
                "context": "\n".join(context_before),
                "before": "\n".join(before_block),
                "after": "\n".join(after_block),
            })

    return patches


def apply_patches(bad_code: str, patches: List[Dict[str, str]]) -> str:
    """
    Apply context-aware BEFORE/AFTER patches to code.
    
    Patches have keys:
        "context": str  (may be empty)
        "before": str
        "after": str
    
    Returns updated code after all patches are applied.
    
    Raises:
        RuntimeError: If a patch cannot be located in the code.
    """
    lines = bad_code.splitlines()

    for i, patch in enumerate(patches):
        context = patch["context"].splitlines() if patch["context"] else []
        before = patch["before"].splitlines()
        after = patch["after"].splitlines()

        target_block = context + before
        replacement_block = context + after

        # Find the target block
        idx = find_exact_sublist(lines, target_block)

        if idx == -1:
            raise RuntimeError(
                f"Could not locate patch {i + 1}/{len(patches)} in code. "
                f"Target block: {target_block[:2]}..."  # Show first 2 lines for debugging
            )

        # Apply replacement
        end_idx = idx + len(target_block)
        lines = lines[:idx] + replacement_block + lines[end_idx:]

    return "\n".join(lines)


def find_exact_sublist(haystack: List[str], needle: List[str]) -> int:
    """
    Find the first exact consecutive match of needle in haystack.
    
    Args:
        haystack: List to search in
        needle: List to search for
    
    Returns:
        Starting index of the match, or -1 if not found.
    """
    if not needle:
        return -1

    needle_len = len(needle)
    haystack_len = len(haystack)

    # Early exit if needle is longer than haystack
    if needle_len > haystack_len:
        return -1

    for i in range(haystack_len - needle_len + 1):
        if haystack[i : i + needle_len] == needle:
            return i

    return -1


def process_errors(text: str) -> str:
    return text.replace("ERROR:", "\nERROR:").lstrip()