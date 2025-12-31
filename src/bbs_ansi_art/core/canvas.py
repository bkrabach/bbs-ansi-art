"""Canvas - 2D grid of cells representing ANSI artwork."""

from dataclasses import dataclass, field
from typing import Iterator

from bbs_ansi_art.core.cell import Cell


@dataclass
class Canvas:
    """
    A 2D grid of Cells representing ANSI artwork.
    
    This is the central data structure for ANSI art. It provides
    methods for accessing and manipulating cells, as well as
    iteration over rows and cells.
    """
    width: int = 80
    height: int | None = None  # None = auto-expand
    _buffer: list[list[Cell]] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        """Initialize the buffer."""
        if not self._buffer:
            self._ensure_row(0)
    
    def ensure_row(self, row: int) -> None:
        """Ensure the buffer has at least this many rows (0-indexed)."""
        while len(self._buffer) <= row:
            self._buffer.append([Cell() for _ in range(self.width)])
    
    # Alias for backwards compatibility
    _ensure_row = ensure_row
    
    def get(self, x: int, y: int) -> Cell:
        """Get the cell at position (x, y)."""
        if x < 0 or x >= self.width:
            raise IndexError(f"x={x} out of bounds (width={self.width})")
        self._ensure_row(y)
        return self._buffer[y][x]
    
    def set(self, x: int, y: int, cell: Cell) -> None:
        """Set the cell at position (x, y)."""
        if x < 0 or x >= self.width:
            raise IndexError(f"x={x} out of bounds (width={self.width})")
        self._ensure_row(y)
        self._buffer[y][x] = cell
    
    def __getitem__(self, pos: tuple[int, int]) -> Cell:
        """Get cell using indexing: canvas[x, y]."""
        x, y = pos
        return self.get(x, y)
    
    def __setitem__(self, pos: tuple[int, int], cell: Cell) -> None:
        """Set cell using indexing: canvas[x, y] = cell."""
        x, y = pos
        self.set(x, y, cell)
    
    def put_char(
        self, 
        x: int, 
        y: int, 
        char: str,
        fg: int | None = None,
        bg: int | None = None,
        bold: bool | None = None,
    ) -> None:
        """Put a character at position with optional styling."""
        self._ensure_row(y)
        cell = self._buffer[y][x]
        cell.char = char
        if fg is not None:
            cell.fg = fg
        if bg is not None:
            cell.bg = bg
        if bold is not None:
            cell.bold = bold
    
    def put_text(
        self,
        x: int,
        y: int,
        text: str,
        fg: int | None = None,
        bg: int | None = None,
        bold: bool | None = None,
    ) -> None:
        """Put a string of text starting at position."""
        for i, char in enumerate(text):
            if x + i >= self.width:
                break
            self.put_char(x + i, y, char, fg, bg, bold)
    
    def fill_rect(
        self,
        x: int,
        y: int,
        w: int,
        h: int,
        cell: Cell,
    ) -> None:
        """Fill a rectangle with copies of a cell."""
        for row in range(y, y + h):
            self._ensure_row(row)
            for col in range(x, min(x + w, self.width)):
                self._buffer[row][col] = cell.copy()
    
    @property
    def current_height(self) -> int:
        """Get the current number of rows in the buffer."""
        return len(self._buffer)
    
    def rows(self) -> Iterator[list[Cell]]:
        """Iterate over rows."""
        yield from self._buffer
    
    def cells(self) -> Iterator[tuple[int, int, Cell]]:
        """Iterate over all cells as (x, y, cell) tuples."""
        for y, row in enumerate(self._buffer):
            for x, cell in enumerate(row):
                yield x, y, cell
    
    def trim(self) -> "Canvas":
        """
        Return a new canvas trimmed to content bounds.
        
        Removes empty rows from top and bottom, and adjusts width
        to the rightmost non-empty cell.
        """
        if not self._buffer:
            return Canvas(width=self.width)
        
        # Find content bounds
        min_y = len(self._buffer)
        max_y = 0
        max_x = 0
        
        for y, row in enumerate(self._buffer):
            for x, cell in enumerate(row):
                if not cell.is_default():
                    min_y = min(min_y, y)
                    max_y = max(max_y, y)
                    max_x = max(max_x, x)
        
        if min_y > max_y:
            # No content
            return Canvas(width=self.width)
        
        # Create trimmed canvas
        new_canvas = Canvas(width=self.width)
        for y in range(min_y, max_y + 1):
            new_canvas._ensure_row(y - min_y)
            for x in range(self.width):
                new_canvas._buffer[y - min_y][x] = self._buffer[y][x].copy()
        
        return new_canvas
