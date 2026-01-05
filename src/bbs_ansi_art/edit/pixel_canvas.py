"""PixelEditableCanvas - Editable canvas for .art files (pixel-based, true color).

This implements the EditableCanvas interface for pixel-level editing of .art files.
Each terminal cell can represent two pixels vertically using half-block characters.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator

from bbs_ansi_art.core.pixel import Pixel


# Half-block characters for pixel rendering
UPPER_HALF = "▀"  # FG = top pixel, BG = bottom pixel
LOWER_HALF = "▄"  # FG = bottom pixel, BG = top pixel

# ANSI escape sequence patterns
ESC = "\x1b"
CSI = f"{ESC}["

# Regex for parsing ANSI SGR sequences
SGR_PATTERN = re.compile(r'\x1b\[([0-9;]*)m')


@dataclass
class EditContext:
    """Context for edit operations (current color, tool, etc.)."""
    fg_color: tuple[int, int, int] = (255, 255, 255)
    bg_color: tuple[int, int, int] = (0, 0, 0)
    tool: str = "pencil"


class EditableCanvas(ABC):
    """Abstract base class for editable canvases."""
    
    @property
    @abstractmethod
    def width(self) -> int:
        """Width in columns."""
        ...
    
    @property
    @abstractmethod
    def height(self) -> int:
        """Height in the canvas's native unit (pixels for pixel canvas, rows for cell canvas)."""
        ...
    
    @abstractmethod
    def get_pixel(self, x: int, y: int) -> Pixel:
        """Get pixel at position."""
        ...
    
    @abstractmethod
    def set_pixel(self, x: int, y: int, pixel: Pixel) -> None:
        """Set pixel at position."""
        ...
    
    @abstractmethod
    def render(self) -> str:
        """Render to ANSI string for display/saving."""
        ...
    
    @property
    @abstractmethod
    def modified(self) -> bool:
        """Whether the canvas has been modified since last save."""
        ...
    
    @abstractmethod
    def clear_modified(self) -> None:
        """Clear the modified flag."""
        ...


class PixelEditableCanvas(EditableCanvas):
    """
    Editable canvas for .art files (pixel-based, true color).
    
    Stores a 2D grid of Pixel objects where pixel_height = 2 * terminal rows.
    Each terminal cell uses a half-block character to represent two vertical pixels.
    
    In half-block rendering:
    - UPPER_HALF (▀): foreground = top pixel, background = bottom pixel
    - LOWER_HALF (▄): foreground = bottom pixel, background = top pixel
    - Space: both pixels = background (transparent)
    """
    
    def __init__(self, width: int, pixel_height: int):
        """
        Initialize an empty pixel canvas.
        
        Args:
            width: Width in columns (characters)
            pixel_height: Height in pixels (2x terminal rows)
        """
        self._width = width
        self._pixel_height = pixel_height
        self._pixels: list[list[Pixel]] = [
            [Pixel(0, 0, 0) for _ in range(width)]
            for _ in range(pixel_height)
        ]
        self._modified = False
    
    @property
    def width(self) -> int:
        """Width in columns."""
        return self._width
    
    @property
    def height(self) -> int:
        """Height in pixels."""
        return self._pixel_height
    
    @property
    def terminal_height(self) -> int:
        """Height in terminal rows (half of pixel height)."""
        return (self._pixel_height + 1) // 2
    
    @property
    def pixel_height(self) -> int:
        """Height in pixels (alias for height)."""
        return self._pixel_height
    
    @property
    def modified(self) -> bool:
        """Whether the canvas has been modified since last save."""
        return self._modified
    
    @modified.setter
    def modified(self, value: bool) -> None:
        """Set the modified flag."""
        self._modified = value
    
    def clear_modified(self) -> None:
        """Clear the modified flag."""
        self._modified = False
    
    def get_pixel(self, x: int, y: int) -> Pixel:
        """
        Get pixel at position.
        
        Args:
            x: Column (0 to width-1)
            y: Pixel row (0 to pixel_height-1)
            
        Returns:
            Pixel at the specified position
            
        Raises:
            IndexError: If position is out of bounds
        """
        if not (0 <= x < self._width and 0 <= y < self._pixel_height):
            raise IndexError(f"Position ({x}, {y}) out of bounds ({self._width}x{self._pixel_height})")
        return self._pixels[y][x]
    
    def set_pixel(self, x: int, y: int, pixel: Pixel) -> None:
        """
        Set pixel at position.
        
        Args:
            x: Column (0 to width-1)
            y: Pixel row (0 to pixel_height-1)
            pixel: Pixel to set
            
        Raises:
            IndexError: If position is out of bounds
        """
        if not (0 <= x < self._width and 0 <= y < self._pixel_height):
            raise IndexError(f"Position ({x}, {y}) out of bounds ({self._width}x{self._pixel_height})")
        self._pixels[y][x] = pixel
        self._modified = True
    
    def fill(self, pixel: Pixel) -> None:
        """Fill entire canvas with a single pixel color."""
        for y in range(self._pixel_height):
            for x in range(self._width):
                self._pixels[y][x] = pixel
        self._modified = True
    
    def fill_rect(self, x: int, y: int, w: int, h: int, pixel: Pixel) -> None:
        """Fill a rectangular region with a pixel color."""
        for py in range(max(0, y), min(self._pixel_height, y + h)):
            for px in range(max(0, x), min(self._width, x + w)):
                self._pixels[py][px] = pixel
        self._modified = True
    
    def draw_point(self, x: int, y: int, color, context=None) -> None:
        """Draw a point at the specified position.
        
        Args:
            x: X coordinate (column)
            y: Y coordinate (pixel row)
            color: Color as RGB tuple (r, g, b) or object with rgb/value attribute
            context: Edit context (optional, for compatibility)
        """
        # Convert color to RGB tuple
        if isinstance(color, tuple):
            rgb = color
        elif hasattr(color, 'rgb'):
            rgb = color.rgb
        elif hasattr(color, 'value') and isinstance(color.value, tuple):
            rgb = color.value
        else:
            rgb = (255, 255, 255)  # Default white
        
        # Bounds check
        if not (0 <= x < self._width and 0 <= y < self._pixel_height):
            return
        
        self._pixels[y][x] = Pixel(r=rgb[0], g=rgb[1], b=rgb[2])
        self._modified = True
    
    def erase_point(self, x: int, y: int) -> None:
        """Erase a point (set to transparent).
        
        Args:
            x: X coordinate (column)
            y: Y coordinate (pixel row)
        """
        # Bounds check
        if not (0 <= x < self._width and 0 <= y < self._pixel_height):
            return
        
        self._pixels[y][x] = Pixel.transparent_pixel()
        self._modified = True
    
    def pixels(self) -> Iterator[tuple[int, int, Pixel]]:
        """Iterate over all pixels as (x, y, pixel) tuples."""
        for y, row in enumerate(self._pixels):
            for x, pixel in enumerate(row):
                yield x, y, pixel
    
    @classmethod
    def from_raw_text(cls, raw_text: str) -> PixelEditableCanvas:
        """
        Parse .art ANSI text into pixel grid.
        
        Handles:
        - \\x1b[38;2;R;G;Bm - true color foreground
        - \\x1b[48;2;R;G;Bm - true color background
        - \\x1b[49m - default/transparent background
        - \\x1b[0m - reset
        
        Args:
            raw_text: The raw ANSI text from a .art file
            
        Returns:
            PixelEditableCanvas with parsed pixel data
        """
        lines = raw_text.split('\n')
        
        # Remove trailing empty lines
        while lines and not lines[-1].strip():
            lines.pop()
        
        if not lines:
            return cls(80, 2)  # Empty canvas with minimal size
        
        # First pass: determine dimensions
        max_width = 0
        for line in lines:
            visible_width = len(_strip_ansi(line))
            max_width = max(max_width, visible_width)
        
        width = max_width or 80
        terminal_height = len(lines)
        pixel_height = terminal_height * 2
        
        # Create canvas
        canvas = cls(width, pixel_height)
        
        # Second pass: parse each line into pixels
        for term_y, line in enumerate(lines):
            canvas._parse_line(line, term_y)
        
        canvas._modified = False  # Fresh from file, not modified
        return canvas
    
    def _parse_line(self, line: str, term_y: int) -> None:
        """
        Parse a single line of ANSI text into pixels.
        
        Args:
            line: The ANSI-encoded line
            term_y: Terminal row (0-indexed)
        """
        # Current state
        fg_rgb: tuple[int, int, int] | None = None
        bg_rgb: tuple[int, int, int] | None = None
        bg_transparent = True
        
        # Pixel rows for this terminal row
        top_y = term_y * 2
        bottom_y = term_y * 2 + 1
        
        x = 0
        i = 0
        
        while i < len(line):
            if line[i] == ESC and i + 1 < len(line) and line[i + 1] == '[':
                # Parse escape sequence
                i += 2  # Skip ESC[
                params_str = ""
                
                while i < len(line):
                    ch = line[i]
                    if ch.isdigit() or ch == ';':
                        params_str += ch
                        i += 1
                    elif ch.isalpha():
                        i += 1  # Skip command character
                        if ch == 'm':
                            # Process SGR parameters
                            fg_rgb, bg_rgb, bg_transparent = self._process_sgr_params(
                                params_str, fg_rgb, bg_rgb, bg_transparent
                            )
                        break
                    else:
                        i += 1
                        break
            else:
                # Regular character - interpret based on half-block logic
                char = line[i]
                
                if x < self._width:
                    if char == UPPER_HALF:
                        # FG = top pixel, BG = bottom pixel
                        if fg_rgb is not None:
                            self._pixels[top_y][x] = Pixel(*fg_rgb)
                        else:
                            # Default foreground (white)
                            self._pixels[top_y][x] = Pixel(255, 255, 255)
                        
                        if bottom_y < self._pixel_height:
                            if bg_transparent:
                                self._pixels[bottom_y][x] = Pixel.transparent_pixel()
                            elif bg_rgb is not None:
                                self._pixels[bottom_y][x] = Pixel(*bg_rgb)
                            else:
                                self._pixels[bottom_y][x] = Pixel(0, 0, 0)
                    
                    elif char == LOWER_HALF:
                        # FG = bottom pixel, BG = top pixel
                        if bg_transparent:
                            self._pixels[top_y][x] = Pixel.transparent_pixel()
                        elif bg_rgb is not None:
                            self._pixels[top_y][x] = Pixel(*bg_rgb)
                        else:
                            self._pixels[top_y][x] = Pixel(0, 0, 0)
                        
                        if bottom_y < self._pixel_height:
                            if fg_rgb is not None:
                                self._pixels[bottom_y][x] = Pixel(*fg_rgb)
                            else:
                                self._pixels[bottom_y][x] = Pixel(255, 255, 255)
                    
                    elif char == ' ':
                        # Space: both pixels = background
                        if bg_transparent:
                            self._pixels[top_y][x] = Pixel.transparent_pixel()
                            if bottom_y < self._pixel_height:
                                self._pixels[bottom_y][x] = Pixel.transparent_pixel()
                        elif bg_rgb is not None:
                            self._pixels[top_y][x] = Pixel(*bg_rgb)
                            if bottom_y < self._pixel_height:
                                self._pixels[bottom_y][x] = Pixel(*bg_rgb)
                        else:
                            self._pixels[top_y][x] = Pixel(0, 0, 0)
                            if bottom_y < self._pixel_height:
                                self._pixels[bottom_y][x] = Pixel(0, 0, 0)
                    
                    else:
                        # Other characters - treat like upper half block
                        # (best effort for non-standard .art content)
                        if fg_rgb is not None:
                            self._pixels[top_y][x] = Pixel(*fg_rgb)
                        else:
                            self._pixels[top_y][x] = Pixel(255, 255, 255)
                        
                        if bottom_y < self._pixel_height:
                            if bg_transparent:
                                self._pixels[bottom_y][x] = Pixel.transparent_pixel()
                            elif bg_rgb is not None:
                                self._pixels[bottom_y][x] = Pixel(*bg_rgb)
                            else:
                                self._pixels[bottom_y][x] = Pixel(0, 0, 0)
                    
                    x += 1
                
                i += 1
    
    def _process_sgr_params(
        self,
        params_str: str,
        fg_rgb: tuple[int, int, int] | None,
        bg_rgb: tuple[int, int, int] | None,
        bg_transparent: bool,
    ) -> tuple[tuple[int, int, int] | None, tuple[int, int, int] | None, bool]:
        """
        Process SGR (Select Graphic Rendition) parameters.
        
        Args:
            params_str: Semicolon-separated parameter string
            fg_rgb: Current foreground RGB
            bg_rgb: Current background RGB
            bg_transparent: Current background transparency state
            
        Returns:
            Updated (fg_rgb, bg_rgb, bg_transparent)
        """
        if not params_str:
            # Empty params = reset
            return None, None, True
        
        params = []
        for p in params_str.split(';'):
            try:
                params.append(int(p) if p else 0)
            except ValueError:
                params.append(0)
        
        i = 0
        while i < len(params):
            p = params[i]
            
            if p == 0:
                # Reset
                fg_rgb = None
                bg_rgb = None
                bg_transparent = True
            
            elif p == 38:
                # Extended foreground color
                if i + 4 < len(params) and params[i + 1] == 2:
                    # True color: 38;2;R;G;B
                    r = _clamp(params[i + 2], 0, 255)
                    g = _clamp(params[i + 3], 0, 255)
                    b = _clamp(params[i + 4], 0, 255)
                    fg_rgb = (r, g, b)
                    i += 4
                elif i + 2 < len(params) and params[i + 1] == 5:
                    # 256-color: 38;5;N - convert to approximate RGB
                    fg_rgb = _color256_to_rgb(params[i + 2])
                    i += 2
            
            elif p == 39:
                # Default foreground
                fg_rgb = None
            
            elif p == 48:
                # Extended background color
                if i + 4 < len(params) and params[i + 1] == 2:
                    # True color: 48;2;R;G;B
                    r = _clamp(params[i + 2], 0, 255)
                    g = _clamp(params[i + 3], 0, 255)
                    b = _clamp(params[i + 4], 0, 255)
                    bg_rgb = (r, g, b)
                    bg_transparent = False
                    i += 4
                elif i + 2 < len(params) and params[i + 1] == 5:
                    # 256-color: 48;5;N - convert to approximate RGB
                    bg_rgb = _color256_to_rgb(params[i + 2])
                    bg_transparent = False
                    i += 2
            
            elif p == 49:
                # Default/transparent background
                bg_rgb = None
                bg_transparent = True
            
            elif 30 <= p <= 37:
                # Standard foreground colors
                fg_rgb = _ansi_color_to_rgb(p - 30)
            
            elif 40 <= p <= 47:
                # Standard background colors
                bg_rgb = _ansi_color_to_rgb(p - 40)
                bg_transparent = False
            
            elif 90 <= p <= 97:
                # Bright foreground colors
                fg_rgb = _ansi_color_to_rgb(p - 90 + 8)
            
            elif 100 <= p <= 107:
                # Bright background colors
                bg_rgb = _ansi_color_to_rgb(p - 100 + 8)
                bg_transparent = False
            
            i += 1
        
        return fg_rgb, bg_rgb, bg_transparent
    
    def render(self) -> str:
        """
        Render pixel grid back to true-color ANSI.
        
        Uses UPPER_HALF character consistently:
        - foreground (38;2;R;G;B) = top pixel
        - background (48;2;R;G;B) = bottom pixel
        
        Returns:
            ANSI-encoded string suitable for display or saving
        """
        lines: list[str] = []
        
        for term_y in range(self.terminal_height):
            top_y = term_y * 2
            bottom_y = term_y * 2 + 1
            
            line_parts: list[str] = []
            last_fg: tuple[int, int, int] | None = None
            last_bg: tuple[int, int, int] | None = None
            last_bg_transparent = False
            
            for x in range(self._width):
                top_pixel = self._pixels[top_y][x]
                
                # Get bottom pixel (may be out of bounds for odd pixel heights)
                if bottom_y < self._pixel_height:
                    bottom_pixel = self._pixels[bottom_y][x]
                else:
                    bottom_pixel = Pixel.transparent_pixel()
                
                # Determine character and colors based on transparency
                top_transparent = top_pixel.transparent
                bottom_transparent = bottom_pixel.transparent
                
                if top_transparent and bottom_transparent:
                    # Both transparent - space with transparent BG
                    char = " "
                    fg = None
                    bg_transparent = True
                elif top_transparent:
                    # Top transparent, bottom opaque - use lower half
                    char = LOWER_HALF
                    fg = bottom_pixel.rgb
                    bg_transparent = True
                elif bottom_transparent:
                    # Top opaque, bottom transparent - use upper half
                    char = UPPER_HALF
                    fg = top_pixel.rgb
                    bg_transparent = True
                else:
                    # Both opaque - use upper half with both colors
                    char = UPPER_HALF
                    fg = top_pixel.rgb
                    bg_transparent = False
                
                # Emit foreground color if changed
                if fg is not None and fg != last_fg:
                    line_parts.append(f"{CSI}38;2;{fg[0]};{fg[1]};{fg[2]}m")
                    last_fg = fg
                
                # Emit background color if changed
                if bg_transparent:
                    if not last_bg_transparent:
                        line_parts.append(f"{CSI}49m")
                        last_bg_transparent = True
                else:
                    bg = bottom_pixel.rgb
                    if bg != last_bg or last_bg_transparent:
                        line_parts.append(f"{CSI}48;2;{bg[0]};{bg[1]};{bg[2]}m")
                        last_bg = bg
                        last_bg_transparent = False
                
                line_parts.append(char)
            
            # Reset at end of line
            line_parts.append(f"{CSI}0m")
            lines.append("".join(line_parts))
        
        return "\n".join(lines) + "\n"
    
    def to_bytes(self) -> bytes:
        """Convert canvas to bytes for saving.
        
        Returns:
            UTF-8 encoded bytes of the rendered ANSI content
        """
        return self.render().encode('utf-8')
    
    def resize(self, new_width: int, new_pixel_height: int) -> None:
        """
        Resize the canvas, preserving existing content where possible.
        
        Args:
            new_width: New width in columns
            new_pixel_height: New height in pixels
        """
        new_pixels: list[list[Pixel]] = [
            [Pixel(0, 0, 0) for _ in range(new_width)]
            for _ in range(new_pixel_height)
        ]
        
        # Copy existing pixels
        for y in range(min(self._pixel_height, new_pixel_height)):
            for x in range(min(self._width, new_width)):
                new_pixels[y][x] = self._pixels[y][x]
        
        self._pixels = new_pixels
        self._width = new_width
        self._pixel_height = new_pixel_height
        self._modified = True
    
    def copy_region(
        self, x: int, y: int, w: int, h: int
    ) -> list[list[Pixel]]:
        """
        Copy a rectangular region of pixels.
        
        Args:
            x: Left column
            y: Top pixel row
            w: Width in columns
            h: Height in pixels
            
        Returns:
            2D list of Pixel copies
        """
        result: list[list[Pixel]] = []
        for py in range(max(0, y), min(self._pixel_height, y + h)):
            row: list[Pixel] = []
            for px in range(max(0, x), min(self._width, x + w)):
                p = self._pixels[py][px]
                row.append(Pixel(p.r, p.g, p.b, p.transparent))
            result.append(row)
        return result
    
    def paste_region(
        self, x: int, y: int, pixels: list[list[Pixel]]
    ) -> None:
        """
        Paste a rectangular region of pixels.
        
        Args:
            x: Left column to paste at
            y: Top pixel row to paste at
            pixels: 2D list of Pixels to paste
        """
        for dy, row in enumerate(pixels):
            py = y + dy
            if 0 <= py < self._pixel_height:
                for dx, pixel in enumerate(row):
                    px = x + dx
                    if 0 <= px < self._width:
                        self._pixels[py][px] = pixel
        self._modified = True


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences from text."""
    return re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)


def _clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp value to range [min_val, max_val]."""
    return max(min_val, min(max_val, value))


def _ansi_color_to_rgb(color_index: int) -> tuple[int, int, int]:
    """
    Convert ANSI 16-color index to RGB.
    
    Args:
        color_index: 0-15 color index
        
    Returns:
        RGB tuple
    """
    # Standard 16-color ANSI palette
    palette = [
        (0, 0, 0),        # 0: Black
        (128, 0, 0),      # 1: Red
        (0, 128, 0),      # 2: Green
        (128, 128, 0),    # 3: Yellow
        (0, 0, 128),      # 4: Blue
        (128, 0, 128),    # 5: Magenta
        (0, 128, 128),    # 6: Cyan
        (192, 192, 192),  # 7: White
        (128, 128, 128),  # 8: Bright Black (Gray)
        (255, 0, 0),      # 9: Bright Red
        (0, 255, 0),      # 10: Bright Green
        (255, 255, 0),    # 11: Bright Yellow
        (0, 0, 255),      # 12: Bright Blue
        (255, 0, 255),    # 13: Bright Magenta
        (0, 255, 255),    # 14: Bright Cyan
        (255, 255, 255),  # 15: Bright White
    ]
    if 0 <= color_index < len(palette):
        return palette[color_index]
    return (255, 255, 255)


def _color256_to_rgb(color_index: int) -> tuple[int, int, int]:
    """
    Convert 256-color index to RGB.
    
    Args:
        color_index: 0-255 color index
        
    Returns:
        RGB tuple
    """
    if color_index < 16:
        # Standard colors
        return _ansi_color_to_rgb(color_index)
    elif color_index < 232:
        # 216-color cube (6x6x6)
        color_index -= 16
        r = (color_index // 36) % 6
        g = (color_index // 6) % 6
        b = color_index % 6
        return (
            0 if r == 0 else 55 + r * 40,
            0 if g == 0 else 55 + g * 40,
            0 if b == 0 else 55 + b * 40,
        )
    else:
        # Grayscale (24 shades)
        gray = 8 + (color_index - 232) * 10
        return (gray, gray, gray)
