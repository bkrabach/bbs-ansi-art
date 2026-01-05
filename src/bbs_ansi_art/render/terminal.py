"""Render ANSI art to terminal-compatible escape sequences."""

from bbs_ansi_art.core.canvas import Canvas


class TerminalRenderer:
    """
    Render a Canvas to ANSI escape sequences for terminal display.
    
    Optimizes output by only emitting SGR codes when attributes change.
    Supports true color RGB via 38;2;r;g;b and 48;2;r;g;b sequences.
    """
    
    def __init__(self, reset_at_end: bool = True):
        self.reset_at_end = reset_at_end
    
    def render(self, canvas: Canvas) -> str:
        """Render canvas to ANSI string."""
        lines: list[str] = []
        
        last_fg = 37
        last_bg = 40
        last_bold = False
        last_fg_rgb: tuple[int, int, int] | None = None
        last_bg_rgb: tuple[int, int, int] | None = None
        
        for row in canvas.rows():
            line_parts: list[str] = []
            
            # Find last non-empty cell to avoid trailing spaces
            last_col = -1
            for x, cell in enumerate(row):
                if cell.char != ' ' or cell.bg != 40 or getattr(cell, 'bg_rgb', None) is not None:
                    last_col = x
            
            for x, cell in enumerate(row):
                if x > last_col:
                    break
                
                # Build SGR sequence if attributes changed
                sgr_parts: list[str] = []
                
                if cell.bold != last_bold:
                    sgr_parts.append('1' if cell.bold else '22')
                    last_bold = cell.bold
                
                # Handle foreground color (with RGB support)
                cell_fg_rgb = getattr(cell, 'fg_rgb', None)
                fg_changed = False
                if cell_fg_rgb is not None:
                    # Cell wants RGB mode
                    if cell_fg_rgb != last_fg_rgb:
                        fg_changed = True
                else:
                    # Cell wants int mode
                    if last_fg_rgb is not None or cell.fg != last_fg:
                        fg_changed = True
                
                if fg_changed:
                    if cell_fg_rgb is not None:
                        r, g, b = cell_fg_rgb
                        sgr_parts.append(f"38;2;{r};{g};{b}")
                        last_fg_rgb = cell_fg_rgb
                    else:
                        sgr_parts.append(str(cell.fg))
                        last_fg = cell.fg
                        last_fg_rgb = None
                
                # Handle background color (with RGB support)
                cell_bg_rgb = getattr(cell, 'bg_rgb', None)
                bg_changed = False
                if cell_bg_rgb is not None:
                    # Cell wants RGB mode
                    if cell_bg_rgb != last_bg_rgb:
                        bg_changed = True
                else:
                    # Cell wants int mode
                    if last_bg_rgb is not None or cell.bg != last_bg:
                        bg_changed = True
                
                if bg_changed:
                    if cell_bg_rgb is not None:
                        r, g, b = cell_bg_rgb
                        sgr_parts.append(f"48;2;{r};{g};{b}")
                        last_bg_rgb = cell_bg_rgb
                    else:
                        # Use default bg (49) for black to match terminal background
                        # True black (40) can appear as dark gray on modern terminals
                        sgr_parts.append('49' if cell.bg == 40 else str(cell.bg))
                        last_bg = cell.bg
                        last_bg_rgb = None
                
                if sgr_parts:
                    line_parts.append(f"\x1b[{';'.join(sgr_parts)}m")
                
                line_parts.append(cell.char)
            
            # Reset at end of each line to prevent color bleeding into clear-to-EOL
            if last_bg != 40 or last_bold or last_bg_rgb is not None:
                line_parts.append('\x1b[0m')
                last_fg = 37
                last_bg = 40
                last_bold = False
                last_fg_rgb = None
                last_bg_rgb = None
            
            lines.append(''.join(line_parts))
        
        result = '\n'.join(lines)
        
        if self.reset_at_end:
            result += '\x1b[0m'
        
        return result
