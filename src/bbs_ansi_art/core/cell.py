"""Cell - atomic unit of the ANSI art canvas."""

from dataclasses import dataclass


@dataclass(slots=True)
class Cell:
    """
    A single character cell with styling attributes.
    
    Represents one position in the terminal grid with its character
    and associated color/style information.
    """
    char: str = ' '
    fg: int = 37   # Default foreground (white)
    bg: int = 40   # Default background (black)
    bold: bool = False
    blink: bool = False
    reverse: bool = False
    
    def copy(self) -> "Cell":
        """Create a copy of this cell."""
        return Cell(
            char=self.char,
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            blink=self.blink,
            reverse=self.reverse,
        )
    
    def is_default(self) -> bool:
        """Check if this cell has default values (empty space, default colors)."""
        return (
            self.char == ' ' 
            and self.fg == 37 
            and self.bg == 40
            and not self.bold
            and not self.blink
            and not self.reverse
        )
