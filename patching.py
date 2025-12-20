from typing import List, Dict, Optional
import difflib, re
from difflib import SequenceMatcher


def remove_comments(code: str) -> str:
    """Remove all // commments from code"""
    lines = code.split('\n')
    cleaned_lines = []
    
    for line in lines:
        # Find // and remove everything from that point onward
        comment_index = line.find('//')
        if comment_index != -1:
            line = line[:comment_index]
        
        if line.strip():
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _compare_code_lines(bad_lines: List[str], good_lines: List[str], merge_threshold: int = 3) -> Optional[List[tuple]]:
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


def _is_all_empty(strings: List[str]) -> bool:
    """Check if all strings are empty or whitespace-only."""
    return all(not s.strip() for s in strings)


def _occurs_exactly_once(haystack: List[str], needle: List[str]) -> bool:
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


def _strip_lines(lines: List[str]) -> List[str]:
    """Remove leading and trailing whitespace from each line."""
    return [line.strip() for line in lines]


def _find_sublist(haystack: List[str], needle: List[str]) -> int:
    """Find needle in haystack, ignoring leading/trailing whitespace on each line."""
    if not needle:
        return -1
    
    # Strip whitespace for comparison
    needle_stripped = _strip_lines(needle)
    haystack_stripped = _strip_lines(haystack)
    
    needle_len = len(needle)
    haystack_len = len(haystack)

    # Early exit if needle is longer than haystack
    if needle_len > haystack_len:
        return -1

    for i in range(haystack_len - needle_len + 1):
        if haystack_stripped[i : i + needle_len] == needle_stripped:
            return i

    return -1


def _get_indent(line: str) -> str:
    """Get the leading whitespace of a line."""
    return line[:len(line) - len(line.lstrip())]


def _add_indent(code_snippet: str, indent: str) -> str:
    """Add the given indent to each line of the code snippet."""
    if not code_snippet:
        return code_snippet
    
    lines = code_snippet.splitlines()
    indented_lines = [indent + line for line in lines]
    return '\n'.join(indented_lines)


def _normalize_indent(lines: list[str]) -> str:
    """Remove smallest indent from all lines"""
    if not lines:
        return ""
    
    non_empty_lines = [line for line in lines if line.strip()]
    if not non_empty_lines:
        return '\n'.join(lines)
    
    min_indent = min((_get_indent(line) for line in non_empty_lines), key=len)
    
    return '\n'.join(
        line[len(min_indent):] if line.startswith(min_indent) else line
        for line in lines
    )


def create_patches(
        bad_code: str,
        good_code: str,
        merge_threshold: int = 3, 
        max_context: int = 50
    ) -> List[Dict[str, str]]:
    
    """Generate contextual patches to transform bad_code into good_code."""
    
    bad_lines = bad_code.splitlines()
    good_lines = good_code.splitlines()

    diff_lines = _compare_code_lines(bad_lines, good_lines, merge_threshold)

    if not diff_lines:
        return []

    patches = []

    for i1, i2, j1, j2 in diff_lines:
        before_block = bad_lines[i1:i2]
        after_block = good_lines[j1:j2]

        # If before_block is non-empty and unique, no context is needed
        if not _is_all_empty(before_block) and _occurs_exactly_once(bad_lines, before_block):
            patches.append({
                "context_before": "",
                "before": "\n".join(before_block),
                "after": "\n".join(after_block),
                "context_after": ""
            })
            continue
        
        # Need to find unique context
        found_unique = False
        context_size = 0
        
        # Try expanding context backwards
        while context_size < max_context and context_size < i1:
            context_size += 1
            context_before = bad_lines[i1 - context_size : i1]
            
            # Skip if context is all empty lines
            if _is_all_empty(context_before):
                #context_size -= 1 # to not count empty lines # dont do this it somehow makes the code get stuck
                continue
            
            # Check if context + before_block is unique
            candidate = context_before + before_block
            if _occurs_exactly_once(bad_lines, candidate):
                patches.append({
                    "context_before": "\n".join(context_before),
                    "before": "\n".join(before_block),
                    "after": "\n".join(after_block),
                    "context_after": ""
                })
                found_unique = True
                break
        
        # If not found with context_before, try context_after
        if not found_unique:
            context_size = 0
            lines_left = len(bad_lines) - i2
            
            while context_size < max_context and context_size < lines_left:
                context_size += 1
                context_after = bad_lines[i2 : i2 + context_size]
                
                # Skip if context is all empty lines
                if _is_all_empty(context_after):
                    #context_size -= 1 # to not count empty lines # dont do this it somehow makes the code get stuck
                    continue
                
                # Check if before_block + context is unique
                candidate = before_block + context_after
                if _occurs_exactly_once(bad_lines, candidate):
                    patches.append({
                        "context_before": "",
                        "before": "\n".join(before_block),
                        "after": "\n".join(after_block),
                        "context_after": "\n".join(context_after),
                    })
                    found_unique = True
                    break
        
        if context_size >= max_context:
            print("limit breached")
        
        # If still not unique after max_context, raise an error
        if not found_unique:
            raise ValueError("Could not find sufficient unique context.")

    return patches


def create_fixes(patches: List[Dict[str, str]]) -> List[str]:
    """Formats patch instructions into readable fixes description."""
    
    if not patches:  # code is correct
        return ""
    
    fixes = []  
    
    for patch in patches:
        context_before = patch.get("context_before", "").splitlines()
        context_after = patch.get("context_after", "").splitlines()
        before = patch.get("before", "").splitlines()
        after = patch.get("after", "").splitlines()
        
        parts = [] 
        
        if not _is_all_empty(context_before):
            indent = _get_indent(context_before[0])
            parts.append(f"{indent}// AFTER THIS CODE")
            parts.extend(context_before)
        
        if not _is_all_empty(before) and not _is_all_empty(after): 
            indent = _get_indent(before[0])  
            parts.append(f"{indent}// REPLACE")
            parts.extend(before)
            
            indent = _get_indent(after[0])
            parts.append(f"{indent}// WITH")
            parts.extend(after)
        elif not _is_all_empty(before):
            indent = _get_indent(before[0])
            parts.append(f"{indent}// DELETE")
            parts.extend(before)
        elif not _is_all_empty(after):
            indent = _get_indent(after[0])
            parts.append(f"{indent}// INSERT")
            parts.extend(after)
            
        if not _is_all_empty(context_after):
            indent = _get_indent(context_after[0])
            parts.append(f"{indent}// BEFORE THIS CODE")
            parts.extend(context_after)
        
        fix = _normalize_indent(parts)
        fixes.append(fix)
    
    return fixes


def extract_code_blocks(text: str) -> List[str]:
    """Extracts all code blocks present in a text, using the ``` and then some language identifier"""
    return re.findall(r'```(?:\w+\n?)?(.*?)```', text, re.DOTALL)


def extract_fixes(text: str) -> List[str]:
    """Extracts all <FIX>...</FIX> blocks from the text."""
    return re.findall(r'<FIX>\s*(.*?)\s*</FIX>', text, re.DOTALL)

        
def extract_patches_from_fixes(fixes: List[str]) -> List[Dict[str, str]]:
    """Extracts patch instructions from fix code blocks into patch dictionaries."""
    
    patches: List[Dict[str, str]] = []
    
    if not fixes:
        return []
    
    for fix in fixes:
        if not "// INSERT" or "// REPLACE" or "// DELETE" in fix:
            # this is not a fix, some other code
            continue

        lines = fix.splitlines()
        patch: Dict[str, str] = {}
        current_section = None
        current_content: List[str] = []

        for line in lines:
            if "// AFTER THIS CODE:" in line:
                if current_section and current_content:
                    patch[current_section] = '\n'.join(current_content)
                current_section = "context_before"
                current_content = []
            elif "// BEFORE THIS CODE:" in line:
                if current_section and current_content:
                    patch[current_section] = '\n'.join(current_content)
                current_section = "context_after"
                current_content = []
            elif "// REPLACE" in line:
                if current_section and current_content:
                    patch[current_section] = '\n'.join(current_content)
                current_section = "before"  
                current_content = []
            elif "// WITH" in line:
                if current_section and current_content:
                    patch[current_section] = '\n'.join(current_content)
                current_section = "after"
                current_content = []
            elif "// DELETE" in line:
                if current_section and current_content:
                    patch[current_section] = '\n'.join(current_content)
                current_section = "before"
                current_content = []
            elif "// INSERT" in line:
                if current_section and current_content:
                    patch[current_section] = '\n'.join(current_content)
                current_section = "after"
                current_content = []
            else:
                current_content.append(line)

        if current_section and current_content:
            patch[current_section] = '\n'.join(current_content)
        
        if patch:
            before = patch.get("before", None)
            after = patch.get("after", None)
            if not before:
                patch["before"] = ""
            if not after:
                patch["after"] = ""
            
            patches.append(patch)
    
    return patches


def apply_patches(bad_code: str, patches: List[Dict[str, str]]) -> str:
    """Apply context-aware BEFORE/AFTER patches to code."""
    
    lines = bad_code.splitlines()

    for i, patch in enumerate(patches):
        context_before_lines = patch.get("context_before", "").splitlines()
        context_after_lines = patch.get("context_after", "").splitlines() 
        before_lines = patch.get("before", "").splitlines()
        after_lines = patch.get("after", "").splitlines()

        # Build target block to find
        if context_before_lines:
            target_block = context_before_lines + before_lines
        elif context_after_lines:
            target_block = before_lines + context_after_lines
        else:
            target_block = before_lines

        # Find the target block
        idx = _find_sublist(lines, target_block)

        if idx == -1:
            raise RuntimeError(
                f"Could not locate patch {i + 1}/{len(patches)} in code.\n"
                f"Looking for {len(target_block)} lines starting with: "
                f"{target_block[0].strip() if target_block else '(empty)'}..."
            )

        # Get the indent from line of the match
        if idx == len(lines)-1:
            match_indent = _get_indent(lines[idx])
        else:
            match_indent = _get_indent(lines[idx+1])

        # Build replacement block with proper indentation
        if context_before_lines:
            # Combine context_before + after, then indent everything
            combined = '\n'.join(context_before_lines + after_lines) if after_lines else '\n'.join(context_before_lines)
            replacement_block = _add_indent(combined, match_indent).splitlines()
        elif context_after_lines:
            # Combine after + context_after, then indent everything
            combined = '\n'.join(after_lines + context_after_lines) if after_lines else '\n'.join(context_after_lines)
            replacement_block = _add_indent(combined, match_indent).splitlines()
        else:
            # No context, just replace with proper indentation
            replacement_block = _add_indent('\n'.join(after_lines), match_indent).splitlines() if after_lines else []

        # Apply replacement
        end_idx = idx + len(target_block)
        lines = lines[:idx] + replacement_block + lines[end_idx:]

    return "\n".join(lines)


def fix_code(bad_code: str, fix: str) -> str:
    """Apply model-generated template compliant fixes to code."""
    if "<NO_CHANGE>" in fix:
        return bad_code
    fixes = extract_fixes(fix)
    patches = extract_patches_from_fixes(fixes)
    return apply_patches(bad_code, patches)


def _normalize(s: str) -> str:
    """Normalize code by removing all whitespaces and indents etc"""
    s = s.strip()
    s = re.sub(r"\s+", " ", s)  # collapse all whitespace sequences
    return s


def get_similarity(good_code: str, fixed_code: str) -> float:
    """Computes similarity between a model-fixed code and ground truth"""

    fc = _normalize(remove_comments(fixed_code))
    gc = _normalize(good_code)

    return SequenceMatcher(None, gc, fc).ratio()