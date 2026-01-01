"""
Clean ANSI art files for use as LLM training examples.

Removes sequences that don't affect visual output:
- Window manipulation (ESC[...t) - causes flicker/resize
- Mode set/reset (ESC[?...h/l) - terminal modes, not visual
- Scrolling regions (ESC[...r) - breaks modern display
- Clear screen (ESC[2J) - just clears before drawing
- Cursor save/restore (ESC[s/u) - can be "baked in" to positioning

Optimizations:
- Normalize line endings to LF only (remove CR)
- Remove redundant resets (multiple ESC[0m in a row)
- Remove trailing ESC[0m before line endings

Preserves:
- All SGR color/attribute codes (ESC[...m)
- Cursor positioning (ESC[...H, ESC[...C, ESC[...A/B/D)
- SAUCE metadata (everything after 0x1A)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Union


@dataclass
class CleanResult:
    """Result of cleaning operation."""
    original_size: int
    cleaned_size: int
    sequences_removed: int
    details: dict = field(default_factory=dict)
    
    @property
    def was_modified(self) -> bool:
        """True if any changes were made."""
        return self.original_size != self.cleaned_size

    def summary(self) -> str:
        """Human-readable summary."""
        if not self.was_modified:
            return "No changes needed"
        
        parts = []
        if self.sequences_removed:
            parts.append(f"{self.sequences_removed} sequences removed")
        for key, count in self.details.items():
            if count:
                parts.append(f"{count} {key}")
        
        saved = self.original_size - self.cleaned_size
        parts.append(f"saved {saved} bytes ({100*saved/self.original_size:.1f}%)")
        return ", ".join(parts)


# CP437 graphical characters (block drawing, box drawing, etc.) - bytes that should be kept
# These are the non-text visual characters used in ANSI art
CP437_GRAPHICAL = set(range(0x01, 0x20)) | {  # Control chars that render as symbols in CP437
    0xB0, 0xB1, 0xB2,  # ░▒▓ shading
    0xDB, 0xDC, 0xDD, 0xDE, 0xDF,  # █▄▌▐▀ blocks
    0xC0, 0xC1, 0xC2, 0xC3, 0xC4, 0xC5,  # └┴┬├─┼ box drawing
    0xC6, 0xC7, 0xC8, 0xC9, 0xCA, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
    0xD0, 0xD1, 0xD2, 0xD3, 0xD4, 0xD5, 0xD6, 0xD7, 0xD8, 0xD9, 0xDA,
    0xB3, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9, 0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF,
    0xFE,  # ■ small block
}

# Text characters to strip (ASCII alphanumerics and common punctuation)
TEXT_CHARS = set(range(0x30, 0x3A)) | set(range(0x41, 0x5B)) | set(range(0x61, 0x7B))  # 0-9, A-Z, a-z
TEXT_CHARS |= {ord(c) for c in "!\"#$%&'()*+,-./:;<=>?@[\\]^_`{|}~"}  # punctuation


def strip_text(data: bytes) -> tuple[bytes, dict]:
    """
    Strip text characters from ANSI art, replacing with spaces.
    
    Preserves:
    - Escape sequences (colors, cursor movement)
    - Block drawing and graphical characters
    - Spaces and structure
    
    Replaces with space:
    - Letters (A-Z, a-z)
    - Numbers (0-9)  
    - Punctuation
    
    Args:
        data: Raw bytes of ANSI art
        
    Returns:
        Tuple of (stripped_bytes, details_dict)
    """
    result = bytearray()
    details = {'text_chars_stripped': 0}
    i = 0
    
    while i < len(data):
        b = data[i]
        
        # Escape sequence - copy entirely (ESC [ ... <letter>)
        if b == 0x1B and i + 1 < len(data) and data[i + 1] == ord('['):
            result.append(b)  # ESC
            result.append(data[i + 1])  # [
            i += 2
            # Copy params and command - sequence ends at letter (A-Z, a-z) or ~
            while i < len(data):
                b = data[i]
                result.append(b)
                i += 1
                # Command letters end the sequence (but NOT '[' which is 0x5B)
                if (b >= 0x41 and b <= 0x5A) or (b >= 0x61 and b <= 0x7A) or b == ord('~'):
                    break
            continue
        
        # Text character - replace with space
        if b in TEXT_CHARS:
            result.append(0x20)  # space
            details['text_chars_stripped'] += 1
            i += 1
            continue
        
        # Everything else (graphical chars, spaces, newlines) - keep
        result.append(b)
        i += 1
    
    return bytes(result), details


def strip_sauce(data: bytes) -> tuple[bytes, bytes]:
    """
    Strip SAUCE metadata from ANSI art data.
    
    Args:
        data: Raw bytes of ANSI art file
        
    Returns:
        Tuple of (art_data, sauce_data) - sauce_data is empty if none found
    """
    sauce_idx = data.find(b'\x1aSAUCE')
    if sauce_idx >= 0:
        return data[:sauce_idx], data[sauce_idx:]
    return data, b''


def clean_bytes(
    data: bytes,
    optimize: bool = True,
    add_safety: bool = True,
    strip_sauce_data: bool = False,
    strip_text_data: bool = False,
) -> tuple[bytes, CleanResult]:
    """
    Clean problematic escape sequences from ANSI art data.
    
    Works at byte level to preserve CP437 encoding.
    
    Args:
        data: Raw bytes of ANSI art file
        optimize: If True, also apply size optimizations
        add_safety: If True, add safety sequences (reset at end)
        strip_sauce_data: If True, remove SAUCE metadata from output
        strip_text_data: If True, replace text characters with spaces
        
    Returns:
        Tuple of (cleaned_bytes, CleanResult)
    """
    # Separate SAUCE metadata
    art_data, sauce_data = strip_sauce(data)
    
    # First pass: remove problematic sequences
    cleaned, removed_count, details = _remove_problematic_sequences(art_data)
    
    # Second pass: optimizations
    if optimize:
        cleaned, opt_details = _optimize(cleaned)
        details.update(opt_details)
    
    # Strip text if requested
    if strip_text_data:
        cleaned, text_details = strip_text(cleaned)
        details.update(text_details)
    
    # Third pass: add safety sequences
    if add_safety:
        cleaned, safety_details = _add_safety(cleaned)
        details.update(safety_details)
    
    # Track SAUCE stripping
    if strip_sauce_data and sauce_data:
        details['sauce_stripped'] = len(sauce_data)
    
    # Recombine with SAUCE (unless stripping)
    final = cleaned if strip_sauce_data else cleaned + sauce_data
    
    return final, CleanResult(
        original_size=len(data),
        cleaned_size=len(final),
        sequences_removed=removed_count,
        details=details,
    )


def _remove_problematic_sequences(data: bytes) -> tuple[bytes, int, dict]:
    """Remove sequences that cause terminal issues."""
    result = bytearray()
    i = 0
    removed_count = 0
    # Only track sequences we KNOW don't affect visual output
    details = {
        'window_manip': 0,
        'mode_changes': 0,
    }
    
    while i < len(data):
        if data[i] == 0x1B and i + 1 < len(data) and data[i + 1] == 0x5B:
            # CSI sequence (ESC[)
            j = i + 2
            
            # Check for private sequence (ESC[?)
            is_private = j < len(data) and data[j] == 0x3F
            if is_private:
                j += 1
            
            # Read parameters
            param_start = j
            while j < len(data) and (0x30 <= data[j] <= 0x39 or data[j] == 0x3B):
                j += 1
            params = data[param_start:j]
            
            # Get command character
            if j < len(data):
                cmd = data[j]
                seq_end = j + 1
                
                should_remove = False
                
                # Window manipulation
                if cmd == ord('t'):
                    should_remove = True
                    details['window_manip'] += 1
                
                # Mode set/reset (private sequences only)
                elif is_private and cmd in (ord('h'), ord('l')):
                    should_remove = True
                    details['mode_changes'] += 1
                
                # NOTE: We ONLY remove sequences that truly don't affect visual output
                # Scrolling region, clear screen, cursor save/restore all affect layout!
                
                if should_remove:
                    removed_count += 1
                    i = seq_end
                    continue
                else:
                    result.extend(data[i:seq_end])
                    i = seq_end
                    continue
        
        result.append(data[i])
        i += 1
    
    return bytes(result), removed_count, details


def _optimize(data: bytes) -> tuple[bytes, dict]:
    """Apply size optimizations while preserving visual output.
    
    NOTE: We do NOT remove CR characters - the parser uses them for cursor positioning.
    Only safe optimizations are applied.
    """
    details = {
        'redundant_resets': 0,
    }
    
    result = bytearray()
    i = 0
    last_was_reset = False
    
    while i < len(data):
        # Track ESC[0m to detect redundant resets
        if (data[i] == 0x1B and 
            i + 3 < len(data) and 
            data[i+1:i+4] == b'[0m'):
            
            if last_was_reset:
                # Skip redundant reset
                details['redundant_resets'] += 1
                i += 4
                continue
            else:
                last_was_reset = True
                result.extend(data[i:i+4])
                i += 4
                continue
        
        # Any non-reset, non-whitespace content clears the flag
        if data[i] not in (0x0A, 0x0D, 0x20, 0x09):
            last_was_reset = False
        
        result.append(data[i])
        i += 1
    
    return bytes(result), details


def _add_safety(data: bytes) -> tuple[bytes, dict]:
    """Add safety sequences that don't change visual output but ensure clean state.
    
    Only adds reset if the file doesn't already end with one.
    Preserves existing line ending structure.
    """
    details = {
        'reset_added': 0,
    }
    
    # Don't modify if empty
    if not data:
        return data, details
    
    # Check if file already ends with reset (possibly followed by whitespace/newlines)
    # Find the last non-whitespace content
    i = len(data) - 1
    while i >= 0 and data[i] in (0x20, 0x0A, 0x0D, 0x09):
        i -= 1
    
    # Check if last meaningful content is a reset
    if i >= 3 and data[i-3:i+1] == b'\x1b[0m':
        # Already ends with reset
        return data, details
    
    # Need to add reset - insert before trailing whitespace/newlines
    trailing = data[i+1:]
    content = data[:i+1]
    
    result = content + b'\x1b[0m' + trailing
    details['reset_added'] = 1
    
    return result, details


def normalize_for_llm(data: bytes, width: int = 80) -> tuple[bytes, dict]:
    """
    Normalize ANSI art for LLM training by adding explicit line endings.
    
    ANSI art often relies on 80-column auto-wrap with no explicit newlines.
    This makes it hard for LLMs to understand the structure. This function:
    1. Parses the art to a canvas (like the viewer does)
    2. Re-renders with explicit newlines after each line
    3. Preserves all colors and visual content
    
    Args:
        data: Raw bytes of ANSI art file
        width: Expected canvas width (default 80)
        
    Returns:
        Tuple of (normalized_bytes, details_dict)
    """
    import bbs_ansi_art as ansi
    from io import BytesIO
    
    details = {
        'lines_added': 0,
        'original_lines': 0,
        'normalized_lines': 0,
    }
    
    # Count original newlines
    details['original_lines'] = data.count(b'\n')
    
    # Separate SAUCE metadata
    sauce_idx = data.find(b'\x1aSAUCE')
    if sauce_idx >= 0:
        art_data = data[:sauce_idx]
        sauce_data = data[sauce_idx:]
    else:
        art_data = data
        sauce_data = b''
    
    # Parse to document using the library
    try:
        # Write to temp file and load
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.ans', delete=False) as f:
            f.write(art_data)
            temp_path = f.name
        
        from pathlib import Path
        doc = ansi.load(Path(temp_path))
        Path(temp_path).unlink()  # Clean up
        if not doc.canvas:
            return data, details
        
        # Get actual height from buffer
        canvas = doc.canvas
        height = len(canvas._buffer) if hasattr(canvas, '_buffer') else (canvas.height or 25)
        
        # Re-render with explicit line endings
        lines = []
        
        # Track state for efficient output
        last_fg = 37
        last_bg = 40
        last_bold = False
        
        for y in range(height):
            line_parts = []
            
            # Find last non-empty cell in this row
            last_col = canvas.width - 1
            while last_col >= 0:
                cell = canvas.get(last_col, y)
                if cell.char != ' ' or cell.bg != 40:
                    break
                last_col -= 1
            
            for x in range(last_col + 1):
                cell = canvas.get(x, y)
                
                # Build SGR if attributes changed
                sgr_parts = []
                
                if cell.bold != last_bold:
                    sgr_parts.append(b'1' if cell.bold else b'22')
                    last_bold = cell.bold
                
                if cell.fg != last_fg:
                    sgr_parts.append(str(cell.fg).encode())
                    last_fg = cell.fg
                
                if cell.bg != last_bg:
                    sgr_parts.append(b'49' if cell.bg == 40 else str(cell.bg).encode())
                    last_bg = cell.bg
                
                if sgr_parts:
                    line_parts.append(b'\x1b[' + b';'.join(sgr_parts) + b'm')
                
                # Add character (encode to CP437)
                char = cell.char
                if ord(char) < 128:
                    line_parts.append(char.encode('ascii'))
                else:
                    # Find CP437 byte for this Unicode char
                    from bbs_ansi_art.codec.cp437 import UNICODE_TO_CP437
                    cp437_byte = UNICODE_TO_CP437.get(char, ord('?'))
                    line_parts.append(bytes([cp437_byte]))
            
            lines.append(b''.join(line_parts))
        
        # Join with CRLF (standard for ANSI art)
        normalized = b'\r\n'.join(lines)
        
        # Add reset at end
        if not normalized.endswith(b'\x1b[0m'):
            normalized += b'\x1b[0m'
        
        # Add final newline
        normalized += b'\r\n'
        
        details['normalized_lines'] = len(lines)
        details['lines_added'] = len(lines) - details['original_lines']
        
        return normalized + sauce_data, details
        
    except Exception as e:
        # If parsing fails, return original
        details['error'] = str(e)
        return data, details


def clean_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path, None] = None,
    optimize: bool = True,
    strip_sauce_data: bool = False,
    strip_text_data: bool = False,
) -> tuple[Path, CleanResult]:
    """
    Clean a single ANSI file.
    
    Args:
        input_path: Path to input file
        output_path: Path to output file (default: input_clean.ans)
        optimize: If True, also apply size optimizations
        strip_sauce_data: If True, remove SAUCE metadata from output
        strip_text_data: If True, replace text characters with spaces
        
    Returns:
        Tuple of (output_path, CleanResult)
    """
    input_path = Path(input_path)
    
    if output_path is None:
        output_path = input_path.with_stem(input_path.stem + "_clean")
    else:
        output_path = Path(output_path)
    
    data = input_path.read_bytes()
    cleaned, result = clean_bytes(
        data,
        optimize=optimize,
        strip_sauce_data=strip_sauce_data,
        strip_text_data=strip_text_data,
    )
    
    output_path.write_bytes(cleaned)
    
    return output_path, result
