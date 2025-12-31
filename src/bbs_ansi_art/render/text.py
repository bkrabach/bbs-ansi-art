"""Render ANSI art to plain text (strip colors)."""

from bbs_ansi_art.core.canvas import Canvas


class TextRenderer:
    """Render a Canvas to plain text without any styling."""
    
    def __init__(self, preserve_whitespace: bool = False):
        self.preserve_whitespace = preserve_whitespace
    
    def render(self, canvas: Canvas) -> str:
        """Render canvas to plain text."""
        lines: list[str] = []
        
        for row in canvas.rows():
            line = ''.join(cell.char for cell in row)
            if not self.preserve_whitespace:
                line = line.rstrip()
            lines.append(line)
        
        result = '\n'.join(lines)
        
        if not self.preserve_whitespace:
            # Remove trailing empty lines
            result = result.rstrip('\n')
        
        return result
