import subprocess, re
from pathlib import Path
from dataclasses import dataclass

HUNK_RE = re.compile(r'^@@ -(\d+),(\d+) \+(\d+),(\d+) @@')

DIFF = r"C:\Program Files\Git\usr\bin\diff.exe"
PATCH = r"C:\Program Files\Git\usr\bin\patch.exe"

OLD = Path("__old.txt")
NEW = Path("__new.txt")
TARGET = OLD

@dataclass
class Hunk:
    lines: list[tuple[str, str]]  # (prefix, content)


def remove_comments(code: str) -> str:
    """Normalize code by removing all comments and empty lines"""
    out = []
    in_string = False

    for line in code.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        i = 0
        while i < len(line) - 1:
            c = line[i]
            if c == '"':
                in_string = not in_string
            if not in_string and line[i:i+2] == '//':
                line = line[:i]
                break
            i += 1
        out.append(line.rstrip())

    return '\n'.join(l for l in out if l.strip())


def build_diff_patch(old_code: str, new_code: str) -> str:
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


def remove_file_headers(patch: str) -> str:
    """Remove any +++ or --- file headers from the diff patch"""

    newlines = []
    lines = patch.splitlines()

    for line in lines:
        if not (line.startswith("+++") or line.startswith("---")):
            newlines.append(line)

    return "\n".join(newlines)   


def create_diff_patch(bad_code: str, good_code: str) -> str:
    """Create a diff patch between bad and good code for dataset"""
    return remove_file_headers(build_diff_patch(bad_code, good_code))


def parse_unified_diff(diff_text: str) -> list[Hunk]:
    hunks = []
    current = None

    for line in diff_text.splitlines():
        if line.startswith('@@'):
            if current:
                hunks.append(Hunk(current))
            current = []
        elif current is not None and line[:1] in {' ', '+', '-'}:
            current.append((line[0], line[1:]))

    if current:
        hunks.append(Hunk(current))

    return hunks


def hunk_to_match_lines(hunk: Hunk) -> list[str]:
    return [text for prefix, text in hunk.lines if prefix in {' ', '-'}]


def hunk_to_replacement_lines(hunk: Hunk) -> list[str]:
    return [text for prefix, text in hunk.lines if prefix in {' ', '+'}]


def find_subsequence(haystack: list[str], needle: list[str]) -> int:
    n = len(needle)
    for i in range(len(haystack) - n + 1):
        if haystack[i:i+n] == needle:
            return i
    return -1


def apply_diff_patch(source: str, diff_text: str) -> tuple[str, bool]:
    lines = source.splitlines()
    hunks = parse_unified_diff(diff_text)

    for hunk in hunks:
        match_lines = hunk_to_match_lines(hunk)
        replacement = hunk_to_replacement_lines(hunk)

        idx = find_subsequence(lines, match_lines)
        if idx == -1:
            return source, False

        lines[idx:idx + len(match_lines)] = replacement

    return "\n".join(lines), True