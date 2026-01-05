"""EditableCanvas - Abstract base class for editable ANSI art canvases."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bbs_ansi_art.core.cell import Cell
    from bbs_ansi_art.core.pixel import Pixel
    from bbs_ansi_art.core.color import Color


class EditMode(Enum):
    """Editing mode determining coordinate granularity."""
    CELL = auto()   # Edit at cell level (1 char = 1 unit)
    PIXEL = auto()  # Edit at pixel level (2 pixels per cell height)


class ColorMode(Enum):
    """Color mode for the canvas."""
    INDEXED_16 = auto()    # 16-color ANSI palette (.ANS files)
    INDEXED_256 = auto()   # 256-color extended palette
    TRUE_COLOR = auto()    # 24-bit RGB (.XB files)


@dataclass
class EditContext:
    """Context for editing operations.
    
    Holds settings that affect how drawing operations are applied.
    
    Attributes:
        mode: Current edit mode (CELL or PIXEL)
        affect_foreground: Whether to modify foreground color
        affect_background: Whether to modify background color
        brush_char: Character to use when drawing in cell mode
        brush_size: Size of brush (1 = single point)
        blend_mode: How colors are combined (for future use)
    """
    mode: EditMode = EditMode.CELL
    affect_foreground: bool = True
    affect_background: bool = False
    brush_char: str | None = None
    brush_size: int = 1
    blend_mode: str = "replace"
    
    @classmethod
    def cell_mode(cls, brush_char: str = '█') -> EditContext:
        """Create context for cell-mode editing."""
        return cls(
            mode=EditMode.CELL,
            affect_foreground=True,
            affect_background=False,
            brush_char=brush_char,
        )
    
    @classmethod
    def pixel_mode(cls) -> EditContext:
        """Create context for pixel-mode editing."""
        return cls(
            mode=EditMode.PIXEL,
            affect_foreground=True,
            affect_background=True,
        )
    
    @classmethod
    def background_mode(cls) -> EditContext:
        """Create context for background-only editing."""
        return cls(
            mode=EditMode.CELL,
            affect_foreground=False,
            affect_background=True,
        )


class EditableCanvas(ABC):
    """Abstract base class for editable ANSI art canvases.
    
    Defines the interface for canvases that support editing operations.
    Implementations handle the specifics of different file formats
    (e.g., .ANS with 16 colors vs .XB with true color).
    """
    
    # -------------------------------------------------------------------------
    # Abstract Properties
    # -------------------------------------------------------------------------
    
    @property
    @abstractmethod
    def width(self) -> int:
        """Width in cells (columns)."""
        ...
    
    @property
    @abstractmethod
    def height(self) -> int:
        """Height in cells (rows)."""
        ...
    
    @property
    @abstractmethod
    def pixel_height(self) -> int:
        """Height in pixels (may differ from cell height)."""
        ...
    
    @property
    @abstractmethod
    def color_mode(self) -> ColorMode:
        """Color mode for this canvas."""
        ...
    
    @property
    @abstractmethod
    def modified(self) -> bool:
        """Whether canvas has unsaved changes."""
        ...
    
    @modified.setter
    @abstractmethod
    def modified(self, value: bool) -> None:
        """Set the modified flag."""
        ...
    
    # -------------------------------------------------------------------------
    # Abstract Cell Operations
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def get_cell(self, x: int, y: int) -> Cell:
        """Get the cell at position (x, y).
        
        Args:
            x: Column (0-indexed)
            y: Row (0-indexed)
            
        Returns:
            Cell at the specified position
        """
        ...
    
    @abstractmethod
    def set_cell(self, x: int, y: int, cell: Cell) -> None:
        """Set the cell at position (x, y).
        
        Args:
            x: Column (0-indexed)
            y: Row (0-indexed)
            cell: Cell to place at position
        """
        ...
    
    # -------------------------------------------------------------------------
    # Abstract Pixel Operations
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def get_pixel(self, x: int, y: int) -> Pixel:
        """Get pixel at position.
        
        Args:
            x: Pixel column
            y: Pixel row
            
        Returns:
            Pixel with color information
        """
        ...
    
    @abstractmethod
    def set_pixel(self, x: int, y: int, pixel: Pixel) -> None:
        """Set pixel at position.
        
        Args:
            x: Pixel column
            y: Pixel row
            pixel: Pixel with color to set
        """
        ...
    
    # -------------------------------------------------------------------------
    # Abstract Drawing Operations
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def draw_point(self, x: int, y: int, color: Color | tuple[int, int, int], 
                   context: EditContext) -> None:
        """Draw a point at the specified position.
        
        Args:
            x: X coordinate
            y: Y coordinate
            color: Color to draw
            context: Edit context with mode and settings
        """
        ...
    
    # -------------------------------------------------------------------------
    # Abstract Canvas Management
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def clear(self) -> None:
        """Clear the entire canvas to default state."""
        ...
    
    @abstractmethod
    def resize(self, width: int, height: int) -> None:
        """Resize the canvas.
        
        Args:
            width: New width in cells
            height: New height in cells
        """
        ...
    
    # -------------------------------------------------------------------------
    # Abstract Rendering
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def render(self) -> str:
        """Render canvas to ANSI escape sequence string.
        
        Returns:
            String with ANSI escape sequences for terminal display
        """
        ...
    
    # -------------------------------------------------------------------------
    # Abstract Serialization
    # -------------------------------------------------------------------------
    
    @abstractmethod
    def to_bytes(self) -> bytes:
        """Convert canvas to file bytes.
        
        Returns:
            Bytes suitable for saving to file
        """
        ...
    
    # -------------------------------------------------------------------------
    # Optional Methods (with default implementations)
    # -------------------------------------------------------------------------
    
    def draw_line(self, x0: int, y0: int, x1: int, y1: int,
                  color: Color | tuple[int, int, int], context: EditContext) -> None:
        """Draw a line between two points.
        
        Default implementation uses Bresenham's algorithm.
        Subclasses may override for optimization.
        
        Args:
            x0, y0: Start point
            x1, y1: End point
            color: Line color
            context: Edit context
        """
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        
        x, y = x0, y0
        while True:
            self.draw_point(x, y, color, context)
            
            if x == x1 and y == y1:
                break
                
            e2 = 2 * err
            if e2 > -dy:
                err -= dy
                x += sx
            if e2 < dx:
                err += dx
                y += sy
    
    def fill_rect(self, x: int, y: int, w: int, h: int,
                  color: Color | tuple[int, int, int], context: EditContext) -> None:
        """Fill a rectangle with color.
        
        Default implementation draws point by point.
        Subclasses may override for optimization.
        
        Args:
            x, y: Top-left corner
            w, h: Width and height
            color: Fill color
            context: Edit context
        """
        max_y = self.pixel_height if context.mode == EditMode.PIXEL else self.height
        for py in range(y, min(y + h, max_y)):
            for px in range(x, min(x + w, self.width)):
                if px >= 0 and py >= 0:
                    self.draw_point(px, py, color, context)
    
    def copy(self) -> EditableCanvas:
        """Create a deep copy of this canvas.
        
        Subclasses should override this method.
        
        Returns:
            New EditableCanvas with copied data
        """
        raise NotImplementedError("Subclasses must implement copy()")
