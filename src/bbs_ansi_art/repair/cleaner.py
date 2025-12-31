"""
Clean ANSI art files by removing problematic escape sequences.

Removes sequences that cause issues on modern terminals:
- Window manipulation (ESC[...t) - causes flicker/resize
- Mode set/reset (ESC[?...h/l) - not needed for display
- Scrolling regions (ESC[...r) - breaks display

Preserves all visual content and color sequences.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Union


@dataclass
class CleanResult:
    """Result of cleaning operation."""
    original_size: int
    cleaned_size: int
    sequences_removed: int
    
    @property
    def was_modified(self) -> bool:
        """True if any sequences were removed."""
        return self.sequences_removed > 0


def clean_bytes(data: bytes) -> tuple[bytes, CleanResult]:
    """
    Clean problematic escape sequences from ANSI art data.
    
    Works at byte level to preserve CP437 encoding.
    
    Args:
        data: Raw bytes of ANSI art file
        
    Returns:
        Tuple of (cleaned_bytes, CleanResult)
    """
    result = bytearray()
    i = 0
    removed_count = 0
    
    while i < len(data):
        # Check for ESC
        if data[i] == 0x1B:
            # Look ahead for CSI sequence (ESC[)
            if i + 1 < len(data) and data[i + 1] == 0x5B:  # '['
                # Parse the sequence
                j = i + 2
                
                # Check for private sequence (ESC[?)
                is_private = j < len(data) and data[j] == 0x3F  # '?'
                if is_private:
                    j += 1
                
                # Read parameters (digits and semicolons)
                while j < len(data) and (0x30 <= data[j] <= 0x39 or data[j] == 0x3B):
                    j += 1
                
                # Get the command character
                if j < len(data):
                    cmd = data[j]
                    seq_end = j + 1
                    
                    # Check if this is a problematic sequence
                    should_remove = False
                    
                    if cmd == ord('t'):
                        # Window manipulation - REMOVE
                        should_remove = True
                    elif is_private and cmd in (ord('h'), ord('l')):
                        # Mode set/reset - REMOVE
                        should_remove = True
                    elif cmd == ord('r'):
                        # Scrolling region - REMOVE
                        should_remove = True
                    
                    if should_remove:
                        removed_count += 1
                        i = seq_end
                        continue
                    else:
                        # Keep this sequence
                        result.extend(data[i:seq_end])
                        i = seq_end
                        continue
            
            # Not a CSI sequence, keep the ESC
            result.append(data[i])
            i += 1
        else:
            # Regular byte, keep it
            result.append(data[i])
            i += 1
    
    cleaned = bytes(result)
    return cleaned, CleanResult(
        original_size=len(data),
        cleaned_size=len(cleaned),
        sequences_removed=removed_count,
    )


def clean_file(
    input_path: Union[str, Path],
    output_path: Union[str, Path, None] = None,
) -> tuple[Path, CleanResult]:
    """
    Clean a single ANSI file.
    
    Args:
        input_path: Path to input file
        output_path: Path to output file (default: input_clean.ans)
        
    Returns:
        Tuple of (output_path, CleanResult)
    """
    input_path = Path(input_path)
    
    if output_path is None:
        output_path = input_path.with_stem(input_path.stem + "_clean")
    else:
        output_path = Path(output_path)
    
    data = input_path.read_bytes()
    cleaned, result = clean_bytes(data)
    
    output_path.write_bytes(cleaned)
    
    return output_path, result
