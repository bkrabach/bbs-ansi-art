"""Load ANSI art files."""

from pathlib import Path

from bbs_ansi_art.core.document import AnsiDocument
from bbs_ansi_art.codec.ansi_parser import AnsiParser
from bbs_ansi_art.sauce.reader import parse_sauce


def load(path: str | Path) -> AnsiDocument:
    """
    Load an ANSI art file from disk.
    
    Supports .ans, .asc, .diz, and other text-mode art files.
    Automatically detects and parses SAUCE metadata if present.
    """
    path = Path(path)
    
    # Parse SAUCE first to get width
    sauce = parse_sauce(path)
    width = sauce.tinfo1 if sauce and sauce.tinfo1 > 0 else 80
    
    # Read raw bytes
    with open(path, 'rb') as f:
        data = f.read()
    
    # Remove SAUCE record and EOF marker from data for parsing
    if sauce:
        # Find EOF marker (0x1A) before SAUCE
        eof_pos = data.rfind(b'\x1a')
        if eof_pos != -1:
            data = data[:eof_pos]
    
    # Parse ANSI sequences
    parser = AnsiParser(width=width)
    parser.feed(data)
    
    return AnsiDocument(
        canvas=parser.get_canvas(),
        sauce=sauce,
        source_path=path,
        encoding="cp437",
    )


def load_bytes(data: bytes, width: int = 80) -> AnsiDocument:
    """Load ANSI art from raw bytes."""
    parser = AnsiParser(width=width)
    parser.feed(data)
    
    return AnsiDocument(
        canvas=parser.get_canvas(),
        encoding="cp437",
    )
