"""Cell - atomic unit of the ANSI art canvas."""

from __future__ import annotations

from dataclasses import dataclass

# Standard 16-color ANSI palette RGB values for quantization
_ANSI_16_PALETTE: list[tuple[int, int, int]] = [
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

# Mapping from palette index to ANSI foreground codes
_PALETTE_TO_FG: list[int] = [30, 31, 32, 33, 34, 35, 36, 37, 90, 91, 92, 93, 94, 95, 96, 97]

# Mapping from palette index to ANSI background codes
_PALETTE_TO_BG: list[int] = [40, 41, 42, 43, 44, 45, 46, 47, 100, 101, 102, 103, 104, 105, 106, 107]


def _rgb_distance_squared(c1: tuple[int, int, int], c2: tuple[int, int, int]) -> int:
    """Calculate squared Euclidean distance between two RGB colors."""
    return (c1[0] - c2[0]) ** 2 + (c1[1] - c2[1]) ** 2 + (c1[2] - c2[2]) ** 2


def _find_nearest_ansi_16(rgb: tuple[int, int, int]) -> int:
    """Find the nearest ANSI 16-color palette index for an RGB color."""
    min_distance = float('inf')
    best_index = 0
    for i, palette_color in enumerate(_ANSI_16_PALETTE):
        distance = _rgb_distance_squared(rgb, palette_color)
        if distance < min_distance:
            min_distance = distance
            best_index = i
    return best_index


@dataclass(slots=True)
class Cell:
    """
    A single character cell with styling attributes.
    
    Represents one position in the terminal grid with its character
    and associated color/style information. Supports both traditional
    16-color ANSI codes and true color RGB values.
    """
    char: str = ' '
    fg: int = 37   # Default foreground (white)
    bg: int = 40   # Default background (black)
    bold: bool = False
    blink: bool = False
    reverse: bool = False
    fg_rgb: tuple[int, int, int] | None = None  # Optional RGB foreground
    bg_rgb: tuple[int, int, int] | None = None  # Optional RGB background
    
    @property
    def is_true_color(self) -> bool:
        """Return True if either RGB field is set."""
        return self.fg_rgb is not None or self.bg_rgb is not None
    
    @property
    def effective_fg(self) -> tuple[int, int, int] | int:
        """Return fg_rgb if set, else fg."""
        return self.fg_rgb if self.fg_rgb is not None else self.fg
    
    @property
    def effective_bg(self) -> tuple[int, int, int] | int:
        """Return bg_rgb if set, else bg."""
        return self.bg_rgb if self.bg_rgb is not None else self.bg
    
    def copy(self) -> Cell:
        """Create a copy of this cell."""
        return Cell(
            char=self.char,
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            blink=self.blink,
            reverse=self.reverse,
            fg_rgb=self.fg_rgb,
            bg_rgb=self.bg_rgb,
        )
    
    def to_ansi_16(self) -> Cell:
        """
        Return a new Cell with RGB colors quantized to 16-color ANSI.
        
        If RGB colors are set, they are converted to the nearest ANSI 16-color
        code. The RGB fields in the returned Cell are set to None.
        """
        new_fg = self.fg
        new_bg = self.bg
        
        if self.fg_rgb is not None:
            palette_index = _find_nearest_ansi_16(self.fg_rgb)
            new_fg = _PALETTE_TO_FG[palette_index]
        
        if self.bg_rgb is not None:
            palette_index = _find_nearest_ansi_16(self.bg_rgb)
            new_bg = _PALETTE_TO_BG[palette_index]
        
        return Cell(
            char=self.char,
            fg=new_fg,
            bg=new_bg,
            bold=self.bold,
            blink=self.blink,
            reverse=self.reverse,
            fg_rgb=None,
            bg_rgb=None,
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
            and self.fg_rgb is None
            and self.bg_rgb is None
        )
