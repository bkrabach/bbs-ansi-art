"""Color representation for ANSI art."""

from dataclasses import dataclass
from enum import Enum
from typing import ClassVar


class ColorMode(Enum):
    """Color mode for ANSI sequences."""
    STANDARD_16 = "16"      # Standard 16-color (SGR 30-37, 40-47, 90-97, 100-107)
    EXTENDED_256 = "256"    # Extended 256-color (SGR 38;5;n, 48;5;n)
    TRUE_COLOR = "rgb"      # 24-bit true color (SGR 38;2;r;g;b, 48;2;r;g;b)


@dataclass(frozen=True)
class Color:
    """
    Represents a color value for ANSI art.
    
    Supports 16-color, 256-color, and true color modes.
    """
    mode: ColorMode
    value: int | tuple[int, int, int]
    
    # Standard 16 colors (index 0-15)
    BLACK: ClassVar["Color"]
    RED: ClassVar["Color"]
    GREEN: ClassVar["Color"]
    YELLOW: ClassVar["Color"]
    BLUE: ClassVar["Color"]
    MAGENTA: ClassVar["Color"]
    CYAN: ClassVar["Color"]
    WHITE: ClassVar["Color"]
    BRIGHT_BLACK: ClassVar["Color"]
    BRIGHT_RED: ClassVar["Color"]
    BRIGHT_GREEN: ClassVar["Color"]
    BRIGHT_YELLOW: ClassVar["Color"]
    BRIGHT_BLUE: ClassVar["Color"]
    BRIGHT_MAGENTA: ClassVar["Color"]
    BRIGHT_CYAN: ClassVar["Color"]
    BRIGHT_WHITE: ClassVar["Color"]
    
    # Default colors
    DEFAULT_FG: ClassVar["Color"]
    DEFAULT_BG: ClassVar["Color"]
    
    @classmethod
    def from_sgr(cls, code: int) -> "Color":
        """Create a Color from an SGR code (30-37, 40-47, 90-97, 100-107)."""
        # Map SGR to color index
        if 30 <= code <= 37:
            return cls(ColorMode.STANDARD_16, code - 30)
        elif 40 <= code <= 47:
            return cls(ColorMode.STANDARD_16, code - 40)
        elif 90 <= code <= 97:
            return cls(ColorMode.STANDARD_16, code - 90 + 8)
        elif 100 <= code <= 107:
            return cls(ColorMode.STANDARD_16, code - 100 + 8)
        else:
            raise ValueError(f"Invalid SGR color code: {code}")
    
    @classmethod
    def from_256(cls, index: int) -> "Color":
        """Create a Color from a 256-color index."""
        if not 0 <= index <= 255:
            raise ValueError(f"256-color index must be 0-255, got {index}")
        return cls(ColorMode.EXTENDED_256, index)
    
    @classmethod
    def from_rgb(cls, r: int, g: int, b: int) -> "Color":
        """Create a Color from RGB values."""
        if not all(0 <= c <= 255 for c in (r, g, b)):
            raise ValueError(f"RGB values must be 0-255, got ({r}, {g}, {b})")
        return cls(ColorMode.TRUE_COLOR, (r, g, b))
    
    def to_sgr_fg(self) -> str:
        """Return SGR sequence for foreground color."""
        if self.mode == ColorMode.STANDARD_16:
            assert isinstance(self.value, int)
            if self.value < 8:
                return str(30 + self.value)
            else:
                return str(90 + self.value - 8)
        elif self.mode == ColorMode.EXTENDED_256:
            return f"38;5;{self.value}"
        else:  # TRUE_COLOR
            assert isinstance(self.value, tuple)
            r, g, b = self.value
            return f"38;2;{r};{g};{b}"
    
    def to_sgr_bg(self) -> str:
        """Return SGR sequence for background color."""
        if self.mode == ColorMode.STANDARD_16:
            assert isinstance(self.value, int)
            if self.value < 8:
                return str(40 + self.value)
            else:
                return str(100 + self.value - 8)
        elif self.mode == ColorMode.EXTENDED_256:
            return f"48;5;{self.value}"
        else:  # TRUE_COLOR
            assert isinstance(self.value, tuple)
            r, g, b = self.value
            return f"48;2;{r};{g};{b}"


# Initialize class-level color constants
Color.BLACK = Color(ColorMode.STANDARD_16, 0)
Color.RED = Color(ColorMode.STANDARD_16, 1)
Color.GREEN = Color(ColorMode.STANDARD_16, 2)
Color.YELLOW = Color(ColorMode.STANDARD_16, 3)
Color.BLUE = Color(ColorMode.STANDARD_16, 4)
Color.MAGENTA = Color(ColorMode.STANDARD_16, 5)
Color.CYAN = Color(ColorMode.STANDARD_16, 6)
Color.WHITE = Color(ColorMode.STANDARD_16, 7)
Color.BRIGHT_BLACK = Color(ColorMode.STANDARD_16, 8)
Color.BRIGHT_RED = Color(ColorMode.STANDARD_16, 9)
Color.BRIGHT_GREEN = Color(ColorMode.STANDARD_16, 10)
Color.BRIGHT_YELLOW = Color(ColorMode.STANDARD_16, 11)
Color.BRIGHT_BLUE = Color(ColorMode.STANDARD_16, 12)
Color.BRIGHT_MAGENTA = Color(ColorMode.STANDARD_16, 13)
Color.BRIGHT_CYAN = Color(ColorMode.STANDARD_16, 14)
Color.BRIGHT_WHITE = Color(ColorMode.STANDARD_16, 15)
Color.DEFAULT_FG = Color.WHITE
Color.DEFAULT_BG = Color.BLACK
