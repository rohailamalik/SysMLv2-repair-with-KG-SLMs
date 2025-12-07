import re
from typing import List

# NOT USED

def extract_last_error_location(error: str) -> List[int]:
    """Extract last error line number based on "line : number" format"""
    
    pattern = r'line : (\d+)'
    matches = re.findall(pattern, error)
    nums = [int(num) for num in matches]

    if not nums:
        raise ValueError("No line numbers found in the error string.")

    return max(nums)


def truncate_beyond_last_error(code: str, error: str) -> str:
    """Truncate code, keeping everything up to the line after the error."""
    
    err_line = extract_last_error_location(error)
    lines = code.splitlines()
    
    return "\n".join(lines[:err_line+1])