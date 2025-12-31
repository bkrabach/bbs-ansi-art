"""Render ANSI art to terminal-compatible escape sequences."""

from bbs_ansi_art.core.canvas import Canvas


class TerminalRenderer:
    """
    Render a Canvas to ANSI escape sequences for terminal display.
    
    Optimizes output by only emitting SGR codes when attributes change.
    """
    
    def __init__(self, reset_at_end: bool = True):
        self.reset_at_end = reset_at_end
    
    def render(self, canvas: Canvas) -> str:
        """Render canvas to ANSI string."""
        lines: list[str] = []
        
        last_fg = 37
        last_bg = 40
        last_bold = False
        
        for row in canvas.rows():
            line_parts: list[str] = []
            
            # Find last non-empty cell to avoid trailing spaces
            last_col = -1
            for x, cell in enumerate(row):
                if cell.char != ' ' or cell.bg != 40:
                    last_col = x
            
            for x, cell in enumerate(row):
                if x > last_col:
                    break
                
                # Build SGR sequence if attributes changed
                sgr_parts: list[str] = []
                
                if cell.bold != last_bold:
                    sgr_parts.append('1' if cell.bold else '22')
                    last_bold = cell.bold
                
                if cell.fg != last_fg:
                    sgr_parts.append(str(cell.fg))
                    last_fg = cell.fg
                
                if cell.bg != last_bg:
                    # Use default bg (49) for black to match terminal background
                    # True black (40) can appear as dark gray on modern terminals
                    sgr_parts.append('49' if cell.bg == 40 else str(cell.bg))
                    last_bg = cell.bg
                
                if sgr_parts:
                    line_parts.append(f"\x1b[{';'.join(sgr_parts)}m")
                
                line_parts.append(cell.char)
            
            # Reset at end of each line to prevent color bleeding into clear-to-EOL
            if last_bg != 40 or last_bold:
                line_parts.append('\x1b[0m')
                last_fg = 37
                last_bg = 40
                last_bold = False
            
            lines.append(''.join(line_parts))
        
        result = '\n'.join(lines)
        
        if self.reset_at_end:
            result += '\x1b[0m'
        
        return result
