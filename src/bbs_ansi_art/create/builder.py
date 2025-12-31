"""Fluent builder API for creating ANSI art."""

from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.core.document import AnsiDocument
from bbs_ansi_art.sauce.record import SauceRecord


class ArtBuilder:
    """
    Fluent API for creating ANSI art programmatically.
    
    Example:
        >>> art = (ArtBuilder(80)
        ...     .fg(36)  # Cyan
        ...     .text("Hello, ")
        ...     .fg(33)  # Yellow
        ...     .bold()
        ...     .text("World!")
        ...     .build())
    """
    
    def __init__(self, width: int = 80):
        self.canvas = Canvas(width=width)
        self.cursor_x = 0
        self.cursor_y = 0
        self._fg = 37
        self._bg = 40
        self._bold = False
        self._blink = False
    
    def fg(self, color: int) -> "ArtBuilder":
        """Set foreground color (SGR code, e.g., 31 for red)."""
        self._fg = color
        return self
    
    def bg(self, color: int) -> "ArtBuilder":
        """Set background color (SGR code, e.g., 44 for blue)."""
        self._bg = color
        return self
    
    def bold(self, on: bool = True) -> "ArtBuilder":
        """Enable or disable bold."""
        self._bold = on
        return self
    
    def blink(self, on: bool = True) -> "ArtBuilder":
        """Enable or disable blink."""
        self._blink = on
        return self
    
    def reset(self) -> "ArtBuilder":
        """Reset all attributes to defaults."""
        self._fg = 37
        self._bg = 40
        self._bold = False
        self._blink = False
        return self
    
    def move_to(self, x: int, y: int) -> "ArtBuilder":
        """Move cursor to absolute position."""
        self.cursor_x = max(0, min(x, self.canvas.width - 1))
        self.cursor_y = max(0, y)
        return self
    
    def newline(self) -> "ArtBuilder":
        """Move to beginning of next line."""
        self.cursor_x = 0
        self.cursor_y += 1
        return self
    
    def text(self, text: str) -> "ArtBuilder":
        """Write text at current position with current style."""
        for char in text:
            if char == '\n':
                self.newline()
                continue
            
            if self.cursor_x >= self.canvas.width:
                self.newline()
            
            self.canvas._ensure_row(self.cursor_y)
            cell = self.canvas._buffer[self.cursor_y][self.cursor_x]
            cell.char = char
            cell.fg = self._fg
            cell.bg = self._bg
            cell.bold = self._bold
            cell.blink = self._blink
            
            self.cursor_x += 1
        
        return self
    
    def fill(self, char: str, count: int) -> "ArtBuilder":
        """Fill with a character repeated count times."""
        return self.text(char * count)
    
    def center(self, text: str, width: int | None = None) -> "ArtBuilder":
        """Write centered text."""
        width = width or self.canvas.width
        padding = (width - len(text)) // 2
        self.cursor_x = max(0, padding)
        return self.text(text)
    
    def box(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        style: str = "single",
    ) -> "ArtBuilder":
        """Draw a box with border characters."""
        # Box drawing characters
        if style == "double":
            tl, tr, bl, br = '╔', '╗', '╚', '╝'
            h, v = '═', '║'
        else:  # single
            tl, tr, bl, br = '┌', '┐', '└', '┘'
            h, v = '─', '│'
        
        # Top border
        self.move_to(x, y).text(tl + h * (width - 2) + tr)
        
        # Sides
        for row in range(1, height - 1):
            self.move_to(x, y + row).text(v)
            self.move_to(x + width - 1, y + row).text(v)
        
        # Bottom border
        self.move_to(x, y + height - 1).text(bl + h * (width - 2) + br)
        
        return self
    
    def build(self) -> Canvas:
        """Build and return the canvas."""
        return self.canvas
    
    def to_document(
        self,
        title: str = "",
        author: str = "",
        group: str = "",
    ) -> AnsiDocument:
        """Build and wrap in an AnsiDocument with optional SAUCE metadata."""
        sauce = SauceRecord(
            title=title,
            author=author,
            group=group,
            tinfo1=self.canvas.width,
            tinfo2=self.canvas.current_height,
        )
        return AnsiDocument(canvas=self.canvas, sauce=sauce)
