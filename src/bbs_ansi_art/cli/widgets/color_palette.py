"""Color palette widget supporting 16-color and RGB modes."""

from __future__ import annotations

from typing import Callable

from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect
from bbs_ansi_art.cli.core.input import KeyEvent, Key
from bbs_ansi_art.edit.editable import ColorMode


# Standard 16-color ANSI palette RGB values
ANSI_16_PALETTE = [
    (0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0),
    (0, 0, 170), (170, 0, 170), (0, 170, 170), (170, 170, 170),
    (85, 85, 85), (255, 85, 85), (85, 255, 85), (255, 255, 85),
    (85, 85, 255), (255, 85, 255), (85, 255, 255), (255, 255, 255),
]

# Color names for display
ANSI_16_NAMES = [
    "Black", "Red", "Green", "Brown",
    "Blue", "Magenta", "Cyan", "White",
    "Dk Gray", "Lt Red", "Lt Green", "Yellow",
    "Lt Blue", "Lt Magenta", "Lt Cyan", "Bright White",
]


class ColorPaletteWidget(BaseWidget):
    """Color palette supporting 16-color and RGB modes."""

    def __init__(self) -> None:
        super().__init__()
        self._mode = ColorMode.INDEXED_16
        self._selected_fg: int = 7  # White
        self._selected_bg: int = 0  # Black
        self._custom_fg_rgb: tuple[int, int, int] = (170, 170, 170)
        self._custom_bg_rgb: tuple[int, int, int] = (0, 0, 0)
        self._rgb_component: int = 0  # 0=R, 1=G, 2=B for RGB editing
        self._editing_fg: bool = True  # True=FG, False=BG

        # Callbacks
        self._on_fg_change: Callable[[tuple[int, int, int] | int], None] | None = None
        self._on_bg_change: Callable[[tuple[int, int, int] | int], None] | None = None

    @property
    def mode(self) -> ColorMode:
        """Get current color mode."""
        return self._mode

    @mode.setter
    def mode(self, value: ColorMode) -> None:
        """Set color mode."""
        self._mode = value

    @property
    def current_fg(self) -> tuple[int, int, int] | int:
        """Get current FG color (index for 16-color, RGB tuple for true color)."""
        if self._mode == ColorMode.TRUE_COLOR:
            return self._custom_fg_rgb
        return self._selected_fg

    @property
    def current_bg(self) -> tuple[int, int, int] | int:
        """Get current BG color (index for 16-color, RGB tuple for true color)."""
        if self._mode == ColorMode.TRUE_COLOR:
            return self._custom_bg_rgb
        return self._selected_bg

    @property
    def current_fg_rgb(self) -> tuple[int, int, int]:
        """Get current FG color as RGB tuple."""
        if self._mode == ColorMode.TRUE_COLOR:
            return self._custom_fg_rgb
        return ANSI_16_PALETTE[self._selected_fg]

    @property
    def current_bg_rgb(self) -> tuple[int, int, int]:
        """Get current BG color as RGB tuple."""
        if self._mode == ColorMode.TRUE_COLOR:
            return self._custom_bg_rgb
        return ANSI_16_PALETTE[self._selected_bg]

    @property
    def editing_fg(self) -> bool:
        """Whether currently editing foreground (True) or background (False)."""
        return self._editing_fg

    @editing_fg.setter
    def editing_fg(self, value: bool) -> None:
        """Set whether editing foreground or background."""
        self._editing_fg = value

    def set_on_fg_change(self, callback: Callable[[tuple[int, int, int] | int], None] | None) -> None:
        """Set callback for FG color changes."""
        self._on_fg_change = callback

    def set_on_bg_change(self, callback: Callable[[tuple[int, int, int] | int], None] | None) -> None:
        """Set callback for BG color changes."""
        self._on_bg_change = callback

    def _notify_fg_change(self) -> None:
        """Notify callback of FG change."""
        if self._on_fg_change:
            self._on_fg_change(self.current_fg)

    def _notify_bg_change(self) -> None:
        """Notify callback of BG change."""
        if self._on_bg_change:
            self._on_bg_change(self.current_bg)

    def handle_input(self, event: KeyEvent) -> bool:
        """Handle palette navigation."""
        if not self._focused:
            return False

        # Handle mode-specific input
        if self._mode == ColorMode.TRUE_COLOR:
            return self._handle_rgb_input(event)
        else:
            return self._handle_indexed_input(event)

    def _handle_indexed_input(self, event: KeyEvent) -> bool:
        """Handle input in 16-color indexed mode."""
        # 0-9: quick color select (0-9)
        if event.char and event.char in '0123456789':
            idx = int(event.char)
            if idx < 16:
                self._set_indexed_color(idx)
                return True

        # a-f: quick color select (10-15)
        if event.char and event.char.lower() in 'abcdef':
            idx = 10 + ord(event.char.lower()) - ord('a')
            self._set_indexed_color(idx)
            return True

        # Arrow navigation
        if event.key == Key.LEFT:
            self._navigate_indexed(-1)
            return True
        if event.key == Key.RIGHT:
            self._navigate_indexed(1)
            return True
        if event.key == Key.UP:
            self._navigate_indexed(-8)
            return True
        if event.key == Key.DOWN:
            self._navigate_indexed(8)
            return True

        # x: swap FG/BG
        if event.char and event.char.lower() == 'x':
            self._swap_colors()
            return True

        # Tab or f/b: switch between FG and BG editing
        if event.key == Key.TAB:
            self._editing_fg = not self._editing_fg
            return True
        if event.char and event.char.lower() == 'f':
            self._editing_fg = True
            return True
        if event.char and event.char.lower() == 'b':
            self._editing_fg = False
            return True

        return False

    def _handle_rgb_input(self, event: KeyEvent) -> bool:
        """Handle input in RGB true color mode."""
        # Tab: cycle through R/G/B components
        if event.key == Key.TAB:
            self._rgb_component = (self._rgb_component + 1) % 3
            return True

        # Up/Down: adjust current component value
        if event.key == Key.UP:
            self._adjust_rgb_component(1)
            return True
        if event.key == Key.DOWN:
            self._adjust_rgb_component(-1)
            return True

        # Page Up/Down: adjust by larger increments
        if event.key == Key.PAGE_UP:
            self._adjust_rgb_component(16)
            return True
        if event.key == Key.PAGE_DOWN:
            self._adjust_rgb_component(-16)
            return True

        # Left/Right: fine adjust
        if event.key == Key.LEFT:
            self._adjust_rgb_component(-1)
            return True
        if event.key == Key.RIGHT:
            self._adjust_rgb_component(1)
            return True

        # r/g/b: quick component select
        if event.char and event.char.lower() == 'r':
            self._rgb_component = 0
            return True
        if event.char and event.char.lower() == 'g':
            self._rgb_component = 1
            return True
        if event.char and event.char.lower() == 'b':
            self._rgb_component = 2
            return True

        # f/b: switch between FG and BG editing
        if event.char and event.char.lower() == 'f':
            self._editing_fg = True
            return True
        if event.char and event.char == 'B':  # Capital B to avoid conflict with 'b' for blue
            self._editing_fg = False
            return True

        # x: swap FG/BG
        if event.char and event.char.lower() == 'x':
            self._swap_colors()
            return True

        # 0-9: quick value input for current component
        if event.char and event.char in '0123456789':
            digit = int(event.char)
            # Set component to digit * 28 (roughly maps 0-9 to 0-252)
            value = min(255, digit * 28)
            self._set_rgb_component(value)
            return True

        return False

    def _set_indexed_color(self, idx: int) -> None:
        """Set indexed color for current target (FG or BG)."""
        idx = max(0, min(15, idx))
        if self._editing_fg:
            self._selected_fg = idx
            self._notify_fg_change()
        else:
            self._selected_bg = idx
            self._notify_bg_change()

    def _navigate_indexed(self, delta: int) -> None:
        """Navigate indexed palette by delta."""
        if self._editing_fg:
            self._selected_fg = (self._selected_fg + delta) % 16
            self._notify_fg_change()
        else:
            self._selected_bg = (self._selected_bg + delta) % 16
            self._notify_bg_change()

    def _adjust_rgb_component(self, delta: int) -> None:
        """Adjust current RGB component by delta."""
        if self._editing_fg:
            r, g, b = self._custom_fg_rgb
            values = [r, g, b]
            values[self._rgb_component] = max(0, min(255, values[self._rgb_component] + delta))
            self._custom_fg_rgb = (values[0], values[1], values[2])
            self._notify_fg_change()
        else:
            r, g, b = self._custom_bg_rgb
            values = [r, g, b]
            values[self._rgb_component] = max(0, min(255, values[self._rgb_component] + delta))
            self._custom_bg_rgb = (values[0], values[1], values[2])
            self._notify_bg_change()

    def _set_rgb_component(self, value: int) -> None:
        """Set current RGB component to specific value."""
        value = max(0, min(255, value))
        if self._editing_fg:
            r, g, b = self._custom_fg_rgb
            values = [r, g, b]
            values[self._rgb_component] = value
            self._custom_fg_rgb = (values[0], values[1], values[2])
            self._notify_fg_change()
        else:
            r, g, b = self._custom_bg_rgb
            values = [r, g, b]
            values[self._rgb_component] = value
            self._custom_bg_rgb = (values[0], values[1], values[2])
            self._notify_bg_change()

    def _swap_colors(self) -> None:
        """Swap FG and BG colors."""
        if self._mode == ColorMode.TRUE_COLOR:
            self._custom_fg_rgb, self._custom_bg_rgb = self._custom_bg_rgb, self._custom_fg_rgb
        else:
            self._selected_fg, self._selected_bg = self._selected_bg, self._selected_fg
        self._notify_fg_change()
        self._notify_bg_change()

    def render(self, bounds: Rect) -> list[str]:
        """Render palette."""
        if not self._visible:
            return []

        if self._mode == ColorMode.TRUE_COLOR:
            return self._render_rgb(bounds)
        else:
            return self._render_indexed(bounds)

    def _render_indexed(self, bounds: Rect) -> list[str]:
        """Render 16-color indexed palette."""
        lines: list[str] = []

        # Header showing current selection
        fg_name = ANSI_16_NAMES[self._selected_fg]
        bg_name = ANSI_16_NAMES[self._selected_bg]
        target = "FG" if self._editing_fg else "BG"
        
        # Color preview with current FG on current BG
        fg_r, fg_g, fg_b = ANSI_16_PALETTE[self._selected_fg]
        bg_r, bg_g, bg_b = ANSI_16_PALETTE[self._selected_bg]
        preview = f"\x1b[38;2;{fg_r};{fg_g};{fg_b}m\x1b[48;2;{bg_r};{bg_g};{bg_b}m Sample \x1b[0m"
        
        header = f"{preview} FG:{fg_name} BG:{bg_name} [{target}]"
        lines.append(header[:bounds.width] if len(header) > bounds.width else header)

        if bounds.height < 3:
            return lines

        # Render two rows of 8 color swatches
        for row in range(2):
            row_str = ""
            for col in range(8):
                idx = row * 8 + col
                r, g, b = ANSI_16_PALETTE[idx]
                
                # Determine if this is selected FG, BG, or both
                is_fg = idx == self._selected_fg
                is_bg = idx == self._selected_bg
                
                # Create color swatch using true color for accurate preview
                swatch = f"\x1b[48;2;{r};{g};{b}m"
                
                # Show marker inside swatch
                if is_fg and is_bg:
                    marker = "FB"
                elif is_fg:
                    marker = "F "
                elif is_bg:
                    marker = " B"
                else:
                    marker = "  "
                
                # Add selection bracket if this cell is being edited
                current_sel = self._selected_fg if self._editing_fg else self._selected_bg
                if idx == current_sel and self._focused:
                    # Highlighted selection
                    text_color = "\x1b[38;2;255;255;0m" if (r + g + b) < 384 else "\x1b[38;2;0;0;0m"
                    swatch += f"{text_color}[{marker}]\x1b[0m"
                else:
                    # Normal swatch
                    text_color = "\x1b[38;2;255;255;255m" if (r + g + b) < 384 else "\x1b[38;2;0;0;0m"
                    swatch += f"{text_color} {marker} \x1b[0m"
                
                row_str += swatch
            
            lines.append(row_str)

        # Add help text if there's room
        if bounds.height >= 5:
            lines.append("")
            help_text = "0-9,A-F:select  Tab:FG/BG  X:swap"
            lines.append(help_text[:bounds.width])

        return lines[:bounds.height]

    def _render_rgb(self, bounds: Rect) -> list[str]:
        """Render RGB true color palette with sliders."""
        lines: list[str] = []

        # Current colors
        fg_r, fg_g, fg_b = self._custom_fg_rgb
        bg_r, bg_g, bg_b = self._custom_bg_rgb
        target = "FG" if self._editing_fg else "BG"

        # Color preview
        preview = f"\x1b[38;2;{fg_r};{fg_g};{fg_b}m\x1b[48;2;{bg_r};{bg_g};{bg_b}m Sample \x1b[0m"
        header = f"{preview} FG:({fg_r},{fg_g},{fg_b}) BG:({bg_r},{bg_g},{bg_b}) [{target}]"
        lines.append(header[:bounds.width] if len(header) > bounds.width else header)

        if bounds.height < 5:
            return lines

        lines.append("")

        # Get current editing color
        current_rgb = self._custom_fg_rgb if self._editing_fg else self._custom_bg_rgb
        component_names = ["R", "G", "B"]
        component_colors = [
            (255, 100, 100),  # Red tint
            (100, 255, 100),  # Green tint
            (100, 100, 255),  # Blue tint
        ]

        # Render RGB sliders
        slider_width = min(32, bounds.width - 12)
        for i, (name, value) in enumerate(zip(component_names, current_rgb)):
            # Highlight current component
            is_selected = i == self._rgb_component and self._focused
            
            # Calculate filled portion
            filled = int((value / 255) * slider_width)
            
            # Component color for the slider
            cr, cg, cb = component_colors[i]
            
            # Build slider
            if is_selected:
                prefix = f"\x1b[1m>{name}:\x1b[0m"
            else:
                prefix = f" {name}:"
            
            slider = f"\x1b[48;2;{cr};{cg};{cb}m"
            slider += "█" * filled
            slider += "\x1b[0m\x1b[48;2;60;60;60m"
            slider += "░" * (slider_width - filled)
            slider += f"\x1b[0m {value:3d}"
            
            lines.append(f"{prefix} {slider}")

        # Large color preview swatch
        if bounds.height >= 8:
            lines.append("")
            cr, cg, cb = current_rgb
            swatch = f"\x1b[48;2;{cr};{cg};{cb}m" + " " * min(20, bounds.width - 2) + "\x1b[0m"
            lines.append(f" {swatch}")

        # Help text
        if bounds.height >= 10:
            lines.append("")
            help_text = "R/G/B:component  ↑↓:adjust  X:swap  Tab:cycle"
            lines.append(help_text[:bounds.width])

        return lines[:bounds.height]

    def set_fg_color(self, color: tuple[int, int, int] | int) -> None:
        """Set foreground color programmatically."""
        if isinstance(color, int):
            self._selected_fg = max(0, min(15, color))
        else:
            self._custom_fg_rgb = (
                max(0, min(255, color[0])),
                max(0, min(255, color[1])),
                max(0, min(255, color[2])),
            )
            # Also update indexed selection to closest match
            self._selected_fg = self._find_closest_indexed(color)

    def set_bg_color(self, color: tuple[int, int, int] | int) -> None:
        """Set background color programmatically."""
        if isinstance(color, int):
            self._selected_bg = max(0, min(15, color))
        else:
            self._custom_bg_rgb = (
                max(0, min(255, color[0])),
                max(0, min(255, color[1])),
                max(0, min(255, color[2])),
            )
            # Also update indexed selection to closest match
            self._selected_bg = self._find_closest_indexed(color)

    def _find_closest_indexed(self, rgb: tuple[int, int, int]) -> int:
        """Find closest color in 16-color palette."""
        r, g, b = rgb
        best_idx = 0
        best_dist = float('inf')
        
        for idx, (pr, pg, pb) in enumerate(ANSI_16_PALETTE):
            # Simple Euclidean distance in RGB space
            dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        
        return best_idx
