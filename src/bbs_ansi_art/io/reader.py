"""Load ANSI art files."""

from pathlib import Path
from typing import Union

from bbs_ansi_art.core.document import AnsiDocument
from bbs_ansi_art.codec.ansi_parser import AnsiParser
from bbs_ansi_art.sauce.reader import parse_sauce


# File extensions for each format
ANS_EXTENSIONS = {".ans", ".asc", ".diz", ".nfo", ".ice"}
ART_EXTENSIONS = {".art"}


def load(path: Union[str, Path]) -> AnsiDocument:
    """
    Load an ANSI art file from disk.
    
    Supports:
    - .ans, .asc, .diz, .nfo, .ice - Classic CP437/16-color BBS format
    - .art - Modern UTF-8/true-color terminal art
    
    Automatically detects format by extension and parses accordingly.
    """
    path = Path(path)
    ext = path.suffix.lower()
    
    if ext in ART_EXTENSIONS:
        return load_art(path)
    else:
        return load_ans(path)


def load_ans(path: Union[str, Path]) -> AnsiDocument:
    """
    Load a classic .ANS file (CP437 encoding, 16-color).
    
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


def load_art(path: Union[str, Path]) -> AnsiDocument:
    """
    Load a .art file (UTF-8 encoding, true-color).
    
    The .art format is modern terminal art with:
    - UTF-8 text encoding
    - True color (24-bit RGB) via SGR escape sequences
    - Half-block characters for 2x vertical resolution
    
    Note: True color is preserved for display but Canvas stores
    a 16-color approximation for compatibility with other renderers.
    """
    from bbs_ansi_art.core.canvas import Canvas
    from bbs_ansi_art.core.cell import Cell
    
    path = Path(path)
    
    # Read as UTF-8 text
    text = path.read_text(encoding="utf-8")
    
    # Parse to extract dimensions and create canvas
    lines = text.split("\n")
    
    # Determine width from longest line (excluding escape sequences)
    max_width = 0
    for line in lines:
        # Strip ANSI escape sequences to count visible characters
        visible = _strip_ansi(line)
        max_width = max(max_width, len(visible))
    
    width = max_width or 80
    canvas = Canvas(width=width)
    
    # Parse each line
    for y, line in enumerate(lines):
        if not line:
            continue
        canvas.ensure_row(y)
        _parse_art_line(line, y, canvas)
    
    return AnsiDocument(
        canvas=canvas,
        source_path=path,
        encoding="utf-8",
        raw_text=text,  # Store original for true-color display
    )


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    import re
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


def _parse_art_line(line: str, y: int, canvas: "Canvas") -> None:
    """Parse a line of .art format into canvas cells."""
    from bbs_ansi_art.core.cell import Cell
    
    x = 0
    i = 0
    fg = 37  # Default white
    bg = 40  # Default black
    bold = False
    
    # Track true color for potential future use
    fg_rgb: tuple[int, int, int] | None = None
    bg_rgb: tuple[int, int, int] | None = None
    
    while i < len(line):
        if line[i] == '\x1b' and i + 1 < len(line) and line[i + 1] == '[':
            # Parse escape sequence
            i += 2
            params = []
            current = ""
            
            while i < len(line):
                ch = line[i]
                if ch.isdigit():
                    current += ch
                elif ch == ';':
                    params.append(int(current) if current else 0)
                    current = ""
                elif ch.isalpha():
                    if current:
                        params.append(int(current))
                    # Process command
                    if ch == 'm':
                        fg, bg, bold, fg_rgb, bg_rgb = _process_sgr(
                            params, fg, bg, bold, fg_rgb, bg_rgb
                        )
                    i += 1
                    break
                else:
                    i += 1
                    break
                i += 1
        else:
            # Regular character
            if x < canvas.width:
                cell = canvas._buffer[y][x]
                cell.char = line[i]
                cell.fg = fg
                cell.bg = bg
                cell.bold = bold
                x += 1
            i += 1


def _process_sgr(
    params: list[int],
    fg: int,
    bg: int, 
    bold: bool,
    fg_rgb: tuple[int, int, int] | None,
    bg_rgb: tuple[int, int, int] | None,
) -> tuple[int, int, bool, tuple[int, int, int] | None, tuple[int, int, int] | None]:
    """Process SGR (Select Graphic Rendition) parameters."""
    if not params:
        params = [0]
    
    i = 0
    while i < len(params):
        p = params[i]
        
        if p == 0:
            fg, bg, bold = 37, 40, False
            fg_rgb, bg_rgb = None, None
        elif p == 1:
            bold = True
        elif p == 22:
            bold = False
        elif 30 <= p <= 37:
            fg = p
            fg_rgb = None
        elif p == 38:
            # Extended foreground
            if i + 2 < len(params) and params[i + 1] == 2:
                # True color: 38;2;R;G;B
                if i + 4 < len(params):
                    r, g, b = params[i + 2], params[i + 3], params[i + 4]
                    fg_rgb = (r, g, b)
                    fg = _rgb_to_ansi16(r, g, b)
                    i += 4
            elif i + 2 < len(params) and params[i + 1] == 5:
                # 256-color: 38;5;N
                fg = params[i + 2]
                fg_rgb = None
                i += 2
        elif p == 39:
            fg = 37
            fg_rgb = None
        elif 40 <= p <= 47:
            bg = p
            bg_rgb = None
        elif p == 48:
            # Extended background
            if i + 2 < len(params) and params[i + 1] == 2:
                # True color: 48;2;R;G;B
                if i + 4 < len(params):
                    r, g, b = params[i + 2], params[i + 3], params[i + 4]
                    bg_rgb = (r, g, b)
                    bg = _rgb_to_ansi16(r, g, b) + 10  # Convert FG code to BG
                    i += 4
            elif i + 2 < len(params) and params[i + 1] == 5:
                # 256-color: 48;5;N
                bg = params[i + 2]
                bg_rgb = None
                i += 2
        elif p == 49:
            bg = 40
            bg_rgb = None
        elif 90 <= p <= 97:
            fg = p
            fg_rgb = None
        elif 100 <= p <= 107:
            bg = p
            bg_rgb = None
        
        i += 1
    
    return fg, bg, bold, fg_rgb, bg_rgb


def _rgb_to_ansi16(r: int, g: int, b: int) -> int:
    """Convert RGB to nearest ANSI 16-color code (30-37, 90-97)."""
    threshold = 128
    bright_threshold = 192
    
    red = r >= threshold
    green = g >= threshold
    blue = b >= threshold
    
    is_bright = r >= bright_threshold or g >= bright_threshold or b >= bright_threshold
    
    code = 30
    if red:
        code += 1
    if green:
        code += 2
    if blue:
        code += 4
    
    if is_bright and code > 30:
        code += 60
    
    return code


def load_bytes(data: bytes, width: int = 80) -> AnsiDocument:
    """Load ANSI art from raw bytes."""
    parser = AnsiParser(width=width)
    parser.feed(data)
    
    return AnsiDocument(
        canvas=parser.get_canvas(),
        encoding="cp437",
    )
