import subprocess, re
from difflib import SequenceMatcher
from pathlib import Path

HUNK_RE = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

DIFF = r"C:\Program Files\Git\usr\bin\diff.exe"
PATCH = r"C:\Program Files\Git\usr\bin\patch.exe"

OLD = Path("__old.txt")
NEW = Path("__new.txt")
TARGET = OLD


def create_diff_patch(old_code: str, new_code: str) -> str:
    """Creates a diff patch between old and new code, using DIFF"""
    
    try:
        with open(OLD, "w", newline="\n", encoding="utf-8") as f:
            f.write(old_code if old_code.endswith("\n") else old_code + "\n")


        with open(NEW, "w", newline="\n", encoding="utf-8") as f:
            f.write(new_code if new_code.endswith("\n") else new_code + "\n")

        result = subprocess.run(
            [DIFF, "-u", OLD, NEW],
            text=True,
            capture_output=True,
        )

        if result.returncode not in (0, 1):
            raise RuntimeError(result.stderr)

        return result.stdout
    
    except Exception:
        raise

    finally:
        OLD.unlink(missing_ok=True)
        NEW.unlink(missing_ok=True)
        

def apply_diff_patch(code: str, patch: str) -> tuple[str, bool]:
    """Applies a diff patch to given code through PATCH"""

    try:
        with open(TARGET, "w", newline="\n", encoding="utf-8") as f:
            f.write(code if code.endswith("\n") else code + "\n")

        result = subprocess.run(
            [PATCH, "-p0", TARGET],
            input=patch,
            text=True,
            capture_output=True,
        )

        # GNU patch semantics:
        # 0 = clean
        # 1 = applied with fuzz/offsets
        # 2 = failed

        if result.returncode == 2:
            return code, False

        with open(TARGET) as f:
            return f.read(), True
    
    except Exception:
        raise

    finally: 
        TARGET.unlink(missing_ok=True)


def remove_comments(code: str) -> str:
    """Remove all // commments from SysML v2 code"""
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


def remove_file_headers(patch: str) -> str:
    """Remove any +++ or --- file headers from the diff patch"""

    newlines = []
    lines = patch.splitlines()

    for line in lines:
        if not (line.startswith("+++") or line.startswith("---")):
            newlines.append(line)

    return "\n".join(newlines)


def fix_file_headers(patch: str) -> str:
    """Add a generic file header to the diff patch"""
    patch = remove_file_headers(patch) # just to be safe
    return "--- __old.txt	2025-12-21 16:19:42.829747600 +0500\n+++ __new.txt	2025-12-21 16:19:42.830746100 +0500\n"+patch


def fix_patch_line_counts(patch: str) -> str:
    """Check if the line number counts in each diff header are actually correct, and fix if not"""
    lines = patch.splitlines()
    out = []
    i = 0

    while i < len(lines):
        line = lines[i]
        m = HUNK_RE.match(line)

        if not m:
            out.append(line)
            i += 1
            continue

        old_start, old_cnt, new_start, new_cnt = map(int, m.groups())

        old_actual = 0
        new_actual = 0
        hunk_lines = []
        i += 1

        while i < len(lines):
            l = lines[i]
            if l.startswith('@@ '):
                break
            if l.startswith(' '):
                old_actual += 1
                new_actual += 1
            elif l.startswith('-'):
                old_actual += 1
            elif l.startswith('+'):
                new_actual += 1
            hunk_lines.append(l)
            i += 1

        if old_actual != old_cnt or new_actual != new_cnt:
            line = f"@@ -{old_start},{old_actual} +{new_start},{new_actual} @@"

        out.append(line)
        out.extend(hunk_lines)

    return "\n".join(out)


def apply_generated_patch(code: str, patch: str) -> tuple[str, bool]:
    """Applies an LLM generated patch to given code by first validating and fixing it"""
    
    patch = remove_comments(patch) # llm may add comments
    patch = fix_file_headers(patch) # add a dummy header
    patch = fix_patch_line_counts(patch) # check and fix line counts
    
    fixed_code, status = apply_diff_patch(code, patch) 
    return fixed_code, status


def extract_code_blocks(text: str) -> list[str]:
    """Extracts all code blocks present in a text, using the ``` and then optionally some language identifier"""
    return re.findall(r'```(?:\w+\n?)?(.*?)```', text, re.DOTALL)


def normalize_code(code: str, remove_indents: bool=False) -> str:
    """Normalize code by removing all whitespaces and optionally indents"""
    
    code = code.replace("\r\n", "\n")
    
    code = code.strip()
    #code = re.sub(r"\s+", " ", code)
    return code


def remove_line_headers(patch: str) -> str:
    """Removes @@ line headers from the patch to compare"""
    return "\n".join([line for line in patch.splitlines() if not line.startswith("@@")])


def get_patch_similarity(patch: str, true_patch: str) -> str:
    """Process LLM generated patch for comparing with ground truth"""
    #patch = remove_comments(patch) # llm may add comments
    
    patch = remove_line_headers(patch)
    true_patch = remove_line_headers(patch)

    return SequenceMatcher(None, patch, true_patch).ratio()


def remove_empty_lines(s: str) -> str:
    return "\n".join(line for line in s.splitlines() if line.strip())


def get_code_similarity(good_code: str, fixed_code: str, remove_indents: bool=False) -> float:
    """Computes similarity between a model-fixed code and ground truth"""

    #fixed_code = remove_comments(fixed_code) # llm may add comments

    #fixed_code = normalize_code(fixed_code, remove_indents)
    #good_code = normalize_code(good_code, remove_indents)

    fixed_code = remove_empty_lines(fixed_code)
    good_code = remove_empty_lines(good_code)

    return SequenceMatcher(None, good_code, fixed_code).ratio()


