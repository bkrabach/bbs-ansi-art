"""Render ANSI art to LLM-friendly annotated text format.

This format is designed for LLM training and generation:
- Row-by-row sequential structure (no cursor movements)
- Human-readable color names instead of escape codes
- Explicit row markers for clear structure
- Character-color binding preserved (critical for ANSI art)

Example output:
    ROW 0: [red]██[yellow]▄▄[reset]
    ROW 1: [bright_cyan/blue]▀▀[white]HELLO[reset]

The format uses [color] for foreground-only and [fg/bg] for both colors.
"""

from bbs_ansi_art.core.canvas import Canvas


# SGR code to human-readable color name mapping
COLOR_NAMES = {
    30: "black",
    31: "red",
    32: "green",
    33: "yellow",
    34: "blue",
    35: "magenta",
    36: "cyan",
    37: "white",
    # Background colors (same names, used contextually)
    40: "black",
    41: "red",
    42: "green",
    43: "yellow",
    44: "blue",
    45: "magenta",
    46: "cyan",
    47: "white",
}

# Bright/bold variants (when bold=True)
BRIGHT_COLOR_NAMES = {
    30: "bright_black",  # aka dark gray
    31: "bright_red",
    32: "bright_green",
    33: "bright_yellow",
    34: "bright_blue",
    35: "bright_magenta",
    36: "bright_cyan",
    37: "bright_white",
}


class LlmTextRenderer:
    """
    Render a Canvas to LLM-friendly annotated text format.
    
    This format uses human-readable color annotations instead of
    escape codes, making it easier for LLMs to understand and generate.
    """
    
    def __init__(
        self,
        include_row_markers: bool = True,
        compact: bool = False,
        include_reset: bool = True,
    ):
        """
        Args:
            include_row_markers: Add "ROW N:" prefix to each line
            compact: Omit colors that match defaults (black bg, white fg)
            include_reset: Add [reset] at end of rows with non-default colors
        """
        self.include_row_markers = include_row_markers
        self.compact = compact
        self.include_reset = include_reset
    
    def render(self, canvas: Canvas) -> str:
        """Render canvas to annotated text string."""
        lines: list[str] = []
        
        for y, row in enumerate(canvas.rows()):
            line_parts: list[str] = []
            
            if self.include_row_markers:
                line_parts.append(f"ROW {y}: ")
            
            # Track current style for run-length encoding
            current_fg = None
            current_bg = None
            current_bold = None
            current_chars: list[str] = []
            had_non_default = False
            
            # Find last non-empty cell
            last_col = -1
            for x, cell in enumerate(row):
                if cell.char != ' ' or cell.bg != 40:
                    last_col = x
            
            def flush_run():
                nonlocal current_chars, had_non_default
                if not current_chars:
                    return
                
                # Build color annotation
                fg_name = self._get_fg_name(current_fg, current_bold)
                bg_name = self._get_bg_name(current_bg)
                
                is_default = (fg_name == "white" and bg_name == "black" and not current_bold)
                
                if self.compact and is_default:
                    # No annotation for default colors in compact mode
                    line_parts.append(''.join(current_chars))
                else:
                    had_non_default = True
                    if bg_name != "black":
                        line_parts.append(f"[{fg_name}/{bg_name}]")
                    else:
                        line_parts.append(f"[{fg_name}]")
                    line_parts.append(''.join(current_chars))
                
                current_chars.clear()
            
            for x, cell in enumerate(row):
                if x > last_col:
                    break
                
                # Check if style changed
                if (cell.fg != current_fg or 
                    cell.bg != current_bg or 
                    cell.bold != current_bold):
                    flush_run()
                    current_fg = cell.fg
                    current_bg = cell.bg
                    current_bold = cell.bold
                
                current_chars.append(cell.char)
            
            flush_run()
            
            # Add reset marker at end of row if needed
            if self.include_reset and had_non_default:
                line_parts.append("[reset]")
            
            lines.append(''.join(line_parts))
        
        return '\n'.join(lines)
    
    def _get_fg_name(self, fg: int, bold: bool) -> str:
        """Get foreground color name."""
        if bold and fg in BRIGHT_COLOR_NAMES:
            return BRIGHT_COLOR_NAMES[fg]
        return COLOR_NAMES.get(fg, f"fg{fg}")
    
    def _get_bg_name(self, bg: int) -> str:
        """Get background color name."""
        # Background codes are 40-47, map to names
        return COLOR_NAMES.get(bg, f"bg{bg}")


class LlmTextParser:
    """
    Parse LLM-generated annotated text back to a Canvas.
    
    This enables round-trip: ANSI -> LlmText -> LLM generates -> parse -> ANSI
    """
    
    # Reverse mappings
    NAME_TO_FG = {v: k for k, v in COLOR_NAMES.items() if k < 40}
    NAME_TO_BG = {v: k + 10 for k, v in COLOR_NAMES.items() if k < 40}  # 30->40, etc.
    BRIGHT_TO_FG = {v: k for k, v in BRIGHT_COLOR_NAMES.items()}
    
    def parse(self, text: str, width: int = 80) -> Canvas:
        """Parse annotated text to a Canvas."""
        from bbs_ansi_art.core.canvas import Canvas
        import re
        
        canvas = Canvas(width=width)
        
        lines = text.strip().split('\n')
        
        for line in lines:
            # Strip row marker if present
            match = re.match(r'ROW\s+(\d+):\s*', line)
            if match:
                y = int(match.group(1))
                line = line[match.end():]
            else:
                y = canvas.current_height
            
            # Ensure canvas has enough rows
            while canvas.current_height <= y:
                canvas._ensure_row(canvas.current_height)
            
            # Parse color annotations and text
            x = 0
            fg, bg, bold = 37, 40, False  # Defaults
            
            i = 0
            while i < len(line):
                if line[i] == '[':
                    # Find closing bracket
                    end = line.find(']', i)
                    if end == -1:
                        # No closing bracket, treat as literal
                        canvas.put_char(x, y, line[i], fg, bg, bold)
                        x += 1
                        i += 1
                        continue
                    
                    annotation = line[i+1:end].lower()
                    i = end + 1
                    
                    if annotation == 'reset':
                        fg, bg, bold = 37, 40, False
                        continue
                    
                    # Parse color(s)
                    if '/' in annotation:
                        fg_name, bg_name = annotation.split('/', 1)
                    else:
                        fg_name = annotation
                        bg_name = None
                    
                    # Handle bright variants
                    if fg_name.startswith('bright_'):
                        bold = True
                        if fg_name in self.BRIGHT_TO_FG:
                            fg = self.BRIGHT_TO_FG[fg_name]
                    elif fg_name in self.NAME_TO_FG:
                        fg = self.NAME_TO_FG[fg_name]
                        bold = False
                    
                    if bg_name and bg_name in self.NAME_TO_BG:
                        bg = self.NAME_TO_BG[bg_name]
                else:
                    # Regular character
                    canvas.put_char(x, y, line[i], fg, bg, bold)
                    x += 1
                    i += 1
            
            canvas._cursor_y = y + 1
        
        return canvas
