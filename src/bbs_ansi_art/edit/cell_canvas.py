"""CellEditableCanvas - Editable canvas for .ANS files (cell-based, 16-color)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bbs_ansi_art.edit.editable import EditableCanvas, EditContext, EditMode, ColorMode
from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.core.cell import Cell
from bbs_ansi_art.core.pixel import Pixel
from bbs_ansi_art.render.terminal import TerminalRenderer

if TYPE_CHECKING:
    from bbs_ansi_art.core.color import Color

# 16-color ANSI palette RGB values for conversion
# These match classic DOS/BBS terminal colors
ANSI_16_RGB: list[tuple[int, int, int]] = [
    (0, 0, 0),        # 0: Black
    (170, 0, 0),      # 1: Red
    (0, 170, 0),      # 2: Green
    (170, 85, 0),     # 3: Yellow/Brown
    (0, 0, 170),      # 4: Blue
    (170, 0, 170),    # 5: Magenta
    (0, 170, 170),    # 6: Cyan
    (170, 170, 170),  # 7: White (Light Gray)
    (85, 85, 85),     # 8: Bright Black (Dark Gray)
    (255, 85, 85),    # 9: Bright Red
    (85, 255, 85),    # 10: Bright Green
    (255, 255, 85),   # 11: Bright Yellow
    (85, 85, 255),    # 12: Bright Blue
    (255, 85, 255),   # 13: Bright Magenta
    (85, 255, 255),   # 14: Bright Cyan
    (255, 255, 255),  # 15: Bright White
]

# Half-block characters for pixel-level rendering
UPPER_HALF_BLOCK = '▀'  # U+2580
LOWER_HALF_BLOCK = '▄'  # U+2584
FULL_BLOCK = '█'        # U+2588


def sgr_to_rgb(code: int) -> tuple[int, int, int]:
    """Convert SGR color code to RGB.
    
    Args:
        code: SGR color code (30-37 for fg, 40-47 for bg, 90-97/100-107 for bright)
        
    Returns:
        RGB tuple (r, g, b)
    """
    if 30 <= code <= 37:
        return ANSI_16_RGB[code - 30]
    elif 90 <= code <= 97:
        return ANSI_16_RGB[code - 90 + 8]
    elif 40 <= code <= 47:
        return ANSI_16_RGB[code - 40]
    elif 100 <= code <= 107:
        return ANSI_16_RGB[code - 100 + 8]
    return (170, 170, 170)  # Default gray


def rgb_to_ansi_16(rgb: tuple[int, int, int]) -> int:
    """Find nearest ANSI 16-color palette index for an RGB color.
    
    Args:
        rgb: RGB tuple (r, g, b)
        
    Returns:
        Palette index 0-15
    """
    min_distance = float('inf')
    best_index = 0
    for i, palette_color in enumerate(ANSI_16_RGB):
        distance = (
            (rgb[0] - palette_color[0]) ** 2 +
            (rgb[1] - palette_color[1]) ** 2 +
            (rgb[2] - palette_color[2]) ** 2
        )
        if distance < min_distance:
            min_distance = distance
            best_index = i
    return best_index


def palette_index_to_fg(index: int) -> int:
    """Convert palette index (0-15) to SGR foreground code."""
    if index < 8:
        return 30 + index
    return 90 + index - 8


def palette_index_to_bg(index: int) -> int:
    """Convert palette index (0-15) to SGR background code."""
    if index < 8:
        return 40 + index
    return 100 + index - 8


class CellEditableCanvas(EditableCanvas):
    """Editable canvas for .ANS files - cell level with 16 colors.
    
    This canvas operates at the cell level (one character per cell) and
    supports the standard 16-color ANSI palette. For pixel-level operations,
    it maps pixels to cells using half-block characters where each cell
    contains 2 vertical pixels.
    
    Attributes:
        _canvas: The underlying Canvas data structure
        _modified: Whether the canvas has been modified since last save
        _renderer: Terminal renderer for generating ANSI output
    """
    
    def __init__(self, canvas: Canvas) -> None:
        """Initialize with an existing Canvas.
        
        Args:
            canvas: The Canvas to wrap for editing
        """
        self._canvas = canvas
        self._modified = False
        self._renderer = TerminalRenderer(reset_at_end=True)
    
    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    
    @property
    def width(self) -> int:
        """Width in cells (columns)."""
        return self._canvas.width
    
    @property
    def height(self) -> int:
        """Height in cells (rows)."""
        return self._canvas.current_height
    
    @property
    def pixel_height(self) -> int:
        """Height in pixels (2x cell height for half-block mode)."""
        return self._canvas.current_height * 2
    
    @property
    def color_mode(self) -> ColorMode:
        """Color mode for this canvas (always 16-color for .ANS)."""
        return ColorMode.INDEXED_16
    
    @property
    def modified(self) -> bool:
        """Whether canvas has unsaved changes."""
        return self._modified
    
    @modified.setter
    def modified(self, value: bool) -> None:
        """Set the modified flag."""
        self._modified = value
    
    # -------------------------------------------------------------------------
    # Cell Operations
    # -------------------------------------------------------------------------
    
    def get_cell(self, x: int, y: int) -> Cell:
        """Get the cell at position (x, y).
        
        Args:
            x: Column (0-indexed)
            y: Row (0-indexed)
            
        Returns:
            Cell at the specified position
            
        Raises:
            IndexError: If x is out of bounds
        """
        return self._canvas.get(x, y)
    
    def set_cell(self, x: int, y: int, cell: Cell) -> None:
        """Set the cell at position (x, y).
        
        Args:
            x: Column (0-indexed)
            y: Row (0-indexed)
            cell: Cell to place at position
            
        Raises:
            IndexError: If x is out of bounds
        """
        self._canvas.set(x, y, cell)
        self._modified = True
    
    # -------------------------------------------------------------------------
    # Pixel Operations (half-block mapping)
    # -------------------------------------------------------------------------
    
    def get_pixel(self, x: int, y: int) -> Pixel:
        """Get pixel at position using half-block mapping.
        
        Each cell contains 2 vertical pixels:
        - pixel_y // 2 = cell row
        - pixel_y % 2 == 0: top pixel (foreground color with upper half block)
        - pixel_y % 2 == 1: bottom pixel (background color with lower half block)
        
        Args:
            x: Pixel column (same as cell column)
            y: Pixel row (0-indexed, 2 pixels per cell row)
            
        Returns:
            Pixel with RGB color from the cell
        """
        cell_row = y // 2
        is_top = (y % 2) == 0
        
        cell = self._canvas.get(x, cell_row)
        char = cell.char
        
        # Determine pixel color based on character and position
        if char == FULL_BLOCK:
            # Both pixels use foreground color
            rgb = sgr_to_rgb(cell.fg)
        elif char == UPPER_HALF_BLOCK:
            # Top = fg, Bottom = bg
            rgb = sgr_to_rgb(cell.fg) if is_top else sgr_to_rgb(cell.bg)
        elif char == LOWER_HALF_BLOCK:
            # Top = bg, Bottom = fg
            rgb = sgr_to_rgb(cell.bg) if is_top else sgr_to_rgb(cell.fg)
        elif char == ' ':
            # Both pixels use background color
            rgb = sgr_to_rgb(cell.bg)
        else:
            # Non-block character: use foreground for top, background for bottom
            rgb = sgr_to_rgb(cell.fg) if is_top else sgr_to_rgb(cell.bg)
        
        return Pixel(r=rgb[0], g=rgb[1], b=rgb[2])
    
    def set_pixel(self, x: int, y: int, pixel: Pixel) -> None:
        """Set pixel at position using half-block mapping.
        
        Modifies the cell to represent the pixel color using half-block
        characters. The cell character and colors are adjusted to correctly
        display both top and bottom pixels.
        
        Args:
            x: Pixel column
            y: Pixel row (0-indexed, 2 pixels per cell row)
            pixel: Pixel with RGB color to set
        """
        if pixel.transparent:
            return
            
        cell_row = y // 2
        is_top = (y % 2) == 0
        
        # Get current cell and determine current pixel colors
        cell = self._canvas.get(x, cell_row)
        
        # Get current top and bottom colors from cell
        top_rgb, bottom_rgb = self._get_cell_pixel_colors(cell)
        
        # Update the appropriate pixel
        new_rgb = (pixel.r, pixel.g, pixel.b)
        if is_top:
            top_rgb = new_rgb
        else:
            bottom_rgb = new_rgb
        
        # Convert RGB to nearest ANSI colors
        top_idx = rgb_to_ansi_16(top_rgb)
        bottom_idx = rgb_to_ansi_16(bottom_rgb)
        
        # Create new cell with appropriate character and colors
        new_cell = self._create_half_block_cell(top_idx, bottom_idx)
        self._canvas.set(x, cell_row, new_cell)
        self._modified = True
    
    def _get_cell_pixel_colors(self, cell: Cell) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
        """Extract top and bottom pixel RGB colors from a cell.
        
        Args:
            cell: Cell to extract colors from
            
        Returns:
            Tuple of (top_rgb, bottom_rgb)
        """
        char = cell.char
        fg_rgb = sgr_to_rgb(cell.fg)
        bg_rgb = sgr_to_rgb(cell.bg)
        
        if char == FULL_BLOCK:
            return (fg_rgb, fg_rgb)
        elif char == UPPER_HALF_BLOCK:
            return (fg_rgb, bg_rgb)
        elif char == LOWER_HALF_BLOCK:
            return (bg_rgb, fg_rgb)
        elif char == ' ':
            return (bg_rgb, bg_rgb)
        else:
            # Non-block: treat as upper half block
            return (fg_rgb, bg_rgb)
    
    def _create_half_block_cell(self, top_idx: int, bottom_idx: int) -> Cell:
        """Create a cell from top and bottom palette indices.
        
        Chooses the optimal character and color assignment to represent
        two vertically stacked pixels.
        
        Args:
            top_idx: Palette index for top pixel (0-15)
            bottom_idx: Palette index for bottom pixel (0-15)
            
        Returns:
            Cell configured to display the two pixels
        """
        if top_idx == bottom_idx:
            # Same color: use full block with fg = color
            return Cell(
                char=FULL_BLOCK,
                fg=palette_index_to_fg(top_idx),
                bg=40,  # Black background (won't be visible)
            )
        else:
            # Different colors: use upper half block
            # Top pixel = foreground, Bottom pixel = background
            return Cell(
                char=UPPER_HALF_BLOCK,
                fg=palette_index_to_fg(top_idx),
                bg=palette_index_to_bg(bottom_idx),
            )
    
    # -------------------------------------------------------------------------
    # Drawing Operations
    # -------------------------------------------------------------------------
    
    def draw_point(self, x: int, y: int, color: Color | tuple[int, int, int], context: EditContext) -> None:
        """Draw a point at the specified position.
        
        Behavior depends on the edit mode in context:
        - CELL mode: Sets cell foreground/background at (x, y)
        - PIXEL mode: Sets pixel at (x, y) using half-block mapping
        
        Args:
            x: X coordinate
            y: Y coordinate
            color: Color to draw (Color object or RGB tuple)
            context: Edit context with mode and other settings
        """
        # Convert color to RGB tuple if needed
        if hasattr(color, 'value'):
            # It's a Color object
            if isinstance(color.value, tuple):
                rgb = color.value
            else:
                # It's a palette index
                rgb = ANSI_16_RGB[color.value] if color.value < 16 else (170, 170, 170)
        else:
            rgb = color
        
        if context.mode == EditMode.PIXEL:
            # Pixel mode: use half-block mapping
            self.set_pixel(x, y, Pixel(r=rgb[0], g=rgb[1], b=rgb[2]))
        else:
            # Cell mode: set cell character and color
            cell = self._canvas.get(x, y)
            palette_idx = rgb_to_ansi_16(rgb)
            
            if context.affect_foreground:
                cell.fg = palette_index_to_fg(palette_idx)
                if context.brush_char is not None:
                    cell.char = context.brush_char
            if context.affect_background:
                cell.bg = palette_index_to_bg(palette_idx)
            
            self._canvas.set(x, y, cell)
            self._modified = True
    
    def draw_line(self, x0: int, y0: int, x1: int, y1: int, 
                  color: Color | tuple[int, int, int], context: EditContext) -> None:
        """Draw a line using Bresenham's algorithm.
        
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
        
        Args:
            x, y: Top-left corner
            w, h: Width and height
            color: Fill color
            context: Edit context
        """
        for py in range(y, y + h):
            for px in range(x, x + w):
                if 0 <= px < self.width:
                    if context.mode == EditMode.PIXEL:
                        if 0 <= py < self.pixel_height:
                            self.draw_point(px, py, color, context)
                    else:
                        if 0 <= py < self.height:
                            self.draw_point(px, py, color, context)
    
    def put_char(self, x: int, y: int, char: str, 
                 fg: int | None = None, bg: int | None = None) -> None:
        """Put a character at cell position with optional colors.
        
        Args:
            x: Column
            y: Row
            char: Character to place
            fg: Optional foreground SGR code
            bg: Optional background SGR code
        """
        self._canvas.put_char(x, y, char, fg=fg, bg=bg)
        self._modified = True
    
    def put_text(self, x: int, y: int, text: str,
                 fg: int | None = None, bg: int | None = None) -> None:
        """Put text starting at cell position.
        
        Args:
            x: Starting column
            y: Row
            text: Text string to place
            fg: Optional foreground SGR code
            bg: Optional background SGR code
        """
        self._canvas.put_text(x, y, text, fg=fg, bg=bg)
        self._modified = True
    
    # -------------------------------------------------------------------------
    # Canvas Management
    # -------------------------------------------------------------------------
    
    def clear(self) -> None:
        """Clear the entire canvas to default cells."""
        for y in range(self._canvas.current_height):
            for x in range(self._canvas.width):
                self._canvas.set(x, y, Cell())
        self._modified = True
    
    def resize(self, width: int, height: int) -> None:
        """Resize the canvas.
        
        Content is preserved where possible. New cells are initialized
        to defaults.
        
        Args:
            width: New width in cells
            height: New height in cells
        """
        # Create new canvas
        new_canvas = Canvas(width=width, height=height)
        
        # Copy existing content
        for y in range(min(self._canvas.current_height, height)):
            for x in range(min(self._canvas.width, width)):
                cell = self._canvas.get(x, y)
                new_canvas.set(x, y, cell.copy())
        
        self._canvas = new_canvas
        self._modified = True
    
    def ensure_height(self, height: int) -> None:
        """Ensure canvas has at least the specified height.
        
        Args:
            height: Minimum height in cells
        """
        if height > 0:
            self._canvas.ensure_row(height - 1)
    
    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------
    
    def render(self) -> str:
        """Render canvas to ANSI escape sequence string.
        
        Returns:
            String with ANSI escape sequences for terminal display
        """
        return self._renderer.render(self._canvas)
    
    def render_region(self, x: int, y: int, w: int, h: int) -> str:
        """Render a rectangular region of the canvas.
        
        Args:
            x, y: Top-left corner
            w, h: Width and height
            
        Returns:
            ANSI string for the region
        """
        # Create temporary canvas for the region
        region = Canvas(width=w, height=h)
        for ry in range(h):
            for rx in range(w):
                src_x = x + rx
                src_y = y + ry
                if 0 <= src_x < self.width and 0 <= src_y < self.height:
                    region.set(rx, ry, self._canvas.get(src_x, src_y).copy())
        
        return self._renderer.render(region)
    
    # -------------------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------------------
    
    def to_bytes(self) -> bytes:
        """Convert canvas to .ANS file bytes.
        
        Generates ANSI escape sequences with CP437 encoding suitable
        for saving as a .ANS file.
        
        Returns:
            Bytes in .ANS format (CP437 encoded with ANSI escapes)
        """
        lines: list[bytes] = []
        
        last_fg = 37
        last_bg = 40
        last_bold = False
        
        for row in self._canvas.rows():
            line_parts: list[bytes] = []
            
            for cell in row:
                # Build SGR sequence if attributes changed
                sgr_parts: list[str] = []
                
                if cell.bold != last_bold:
                    sgr_parts.append('1' if cell.bold else '22')
                    last_bold = cell.bold
                
                if cell.fg != last_fg:
                    sgr_parts.append(str(cell.fg))
                    last_fg = cell.fg
                
                if cell.bg != last_bg:
                    sgr_parts.append(str(cell.bg))
                    last_bg = cell.bg
                
                if sgr_parts:
                    line_parts.append(f"\x1b[{';'.join(sgr_parts)}m".encode('cp437', errors='replace'))
                
                # Encode character
                try:
                    line_parts.append(cell.char.encode('cp437'))
                except UnicodeEncodeError:
                    # Fallback for characters not in CP437
                    line_parts.append(b'?')
            
            lines.append(b''.join(line_parts))
        
        # Join with CRLF (standard for .ANS files)
        result = b'\r\n'.join(lines)
        
        # Add reset at end
        result += b'\x1b[0m'
        
        return result
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def get_canvas(self) -> Canvas:
        """Get the underlying Canvas object.
        
        Returns:
            The wrapped Canvas instance
        """
        return self._canvas
    
    def copy(self) -> CellEditableCanvas:
        """Create a deep copy of this editable canvas.
        
        Returns:
            New CellEditableCanvas with copied data
        """
        new_canvas = Canvas(width=self._canvas.width)
        for y in range(self._canvas.current_height):
            for x in range(self._canvas.width):
                new_canvas.set(x, y, self._canvas.get(x, y).copy())
        
        result = CellEditableCanvas(new_canvas)
        result._modified = self._modified
        return result
    
    def __repr__(self) -> str:
        return f"CellEditableCanvas(width={self.width}, height={self.height}, modified={self.modified})"
