"""ANSI text utilities - measuring and truncating strings with escape codes."""

from __future__ import annotations

import re

# Pattern to match ANSI escape sequences (including ~ terminator for F-keys, etc.)
_ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*[A-Za-z~]')


def visible_len(s: str) -> int:
    """Get visible length of string (excluding ANSI escape codes)."""
    return len(_ANSI_ESCAPE.sub('', s))


def truncate(s: str, max_width: int, reset: bool = True) -> str:
    """
    Truncate an ANSI-escaped string to max visible width.
    
    Preserves ANSI codes but counts only visible characters.
    Ensures the result displays in exactly max_width columns or less.
    
    Args:
        s: String to truncate
        max_width: Maximum visible width
        reset: If True, append reset sequence to prevent color bleed
    """
    if max_width <= 0:
        return ""
    
    result: list[str] = []
    vis_len = 0
    i = 0
    was_truncated = False
    
    while i < len(s) and vis_len < max_width:
        if s[i] == '\x1b' and i + 1 < len(s) and s[i + 1] == '[':
            # ANSI escape sequence - include whole thing
            j = i + 2
            while j < len(s) and s[j] not in 'ABCDEFGHJKSTfmsu~':
                j += 1
            if j < len(s):
                j += 1  # Include terminator
            result.append(s[i:j])
            i = j
        else:
            result.append(s[i])
            vis_len += 1
            i += 1
    
    # Check if we truncated
    was_truncated = i < len(s)
    
    output = ''.join(result)
    
    # Append reset if truncated to prevent color bleed
    if reset and was_truncated:
        output += '\x1b[0m'
    
    return output


def pad_to_width(s: str, width: int, char: str = ' ') -> str:
    """Pad string with char to reach exactly width visible characters."""
    current = visible_len(s)
    if current >= width:
        return s
    return s + char * (width - current)


def truncate_and_pad(s: str, width: int) -> str:
    """Truncate if too long, pad if too short. Always returns exactly width visible chars."""
    vlen = visible_len(s)
    if vlen > width:
        return truncate(s, width)
    elif vlen < width:
        return s + ' ' * (width - vlen)
    return s
