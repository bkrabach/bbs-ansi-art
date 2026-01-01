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


def clean_bytes(data: bytes, optimize: bool = True, add_safety: bool = True) -> tuple[bytes, CleanResult]:
    """
    Clean problematic escape sequences from ANSI art data.
    
    Works at byte level to preserve CP437 encoding.
    Preserves SAUCE metadata.
    
    Args:
        data: Raw bytes of ANSI art file
        optimize: If True, also apply size optimizations
        add_safety: If True, add safety sequences (reset at end)
        
    Returns:
        Tuple of (cleaned_bytes, CleanResult)
    """
    # Separate SAUCE metadata (preserve it exactly)
    sauce_idx = data.find(b'\x1aSAUCE')
    if sauce_idx >= 0:
        art_data = data[:sauce_idx]
        sauce_data = data[sauce_idx:]
    else:
        art_data = data
        sauce_data = b''
    
    # First pass: remove problematic sequences
    cleaned, removed_count, details = _remove_problematic_sequences(art_data)
    
    # Second pass: optimizations
    if optimize:
        cleaned, opt_details = _optimize(cleaned)
        details.update(opt_details)
    
    # Third pass: add safety sequences
    if add_safety:
        cleaned, safety_details = _add_safety(cleaned)
        details.update(safety_details)
    
    # Recombine with SAUCE
    final = cleaned + sauce_data
    
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
) -> tuple[Path, CleanResult]:
    """
    Clean a single ANSI file.
    
    Args:
        input_path: Path to input file
        output_path: Path to output file (default: input_clean.ans)
        optimize: If True, also apply size optimizations
        
    Returns:
        Tuple of (output_path, CleanResult)
    """
    input_path = Path(input_path)
    
    if output_path is None:
        output_path = input_path.with_stem(input_path.stem + "_clean")
    else:
        output_path = Path(output_path)
    
    data = input_path.read_bytes()
    cleaned, result = clean_bytes(data, optimize=optimize)
    
    output_path.write_bytes(cleaned)
    
    return output_path, result
