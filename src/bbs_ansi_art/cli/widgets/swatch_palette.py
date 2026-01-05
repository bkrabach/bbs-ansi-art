"""Enhanced color palette widget with document swatches, saved colors, and color editor.

This widget provides a professional swatch-based palette similar to design tools:
- Current color display
- Document swatches (colors extracted from artwork)
- Saved swatches (user favorites, persisted)
- Standard ANSI-16 palette
- Color editor modal (RGB/HSL/Hex)
- Color history ring
"""

from __future__ import annotations

import colorsys
import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Callable, Optional

from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect
from bbs_ansi_art.cli.core.input import KeyEvent, Key


# Standard 16-color ANSI palette RGB values
ANSI_16_PALETTE = [
    (0, 0, 0), (170, 0, 0), (0, 170, 0), (170, 85, 0),
    (0, 0, 170), (170, 0, 170), (0, 170, 170), (170, 170, 170),
    (85, 85, 85), (255, 85, 85), (85, 255, 85), (255, 255, 85),
    (85, 85, 255), (255, 85, 255), (85, 255, 255), (255, 255, 255),
]

ANSI_16_NAMES = [
    "Black", "Red", "Green", "Brown",
    "Blue", "Magenta", "Cyan", "White",
    "Dk Gray", "Lt Red", "Lt Green", "Yellow",
    "Lt Blue", "Lt Magenta", "Lt Cyan", "Bright White",
]


class PaletteSection(Enum):
    """Sections in the palette widget."""
    CURRENT = auto()
    DOCUMENT = auto()
    SAVED = auto()
    STANDARD = auto()


class ColorEditorMode(Enum):
    """Mode for color editor."""
    RGB = auto()
    HSL = auto()
    HEX = auto()


@dataclass
class ColorSwatch:
    """A color swatch with optional name."""
    rgb: tuple[int, int, int]
    name: str = ""
    
    @property
    def hex(self) -> str:
        """Get hex representation."""
        return f"#{self.rgb[0]:02X}{self.rgb[1]:02X}{self.rgb[2]:02X}"
    
    @property
    def hsl(self) -> tuple[float, float, float]:
        """Get HSL representation (h: 0-360, s: 0-100, l: 0-100)."""
        r, g, b = self.rgb[0] / 255, self.rgb[1] / 255, self.rgb[2] / 255
        h, l, s = colorsys.rgb_to_hls(r, g, b)
        return (h * 360, s * 100, l * 100)
    
    @classmethod
    def from_hex(cls, hex_str: str, name: str = "") -> Optional[ColorSwatch]:
        """Create swatch from hex string."""
        hex_str = hex_str.strip().lstrip('#')
        if len(hex_str) == 6:
            try:
                r = int(hex_str[0:2], 16)
                g = int(hex_str[2:4], 16)
                b = int(hex_str[4:6], 16)
                return cls((r, g, b), name)
            except ValueError:
                return None
        return None
    
    @classmethod
    def from_hsl(cls, h: float, s: float, l: float, name: str = "") -> ColorSwatch:
        """Create swatch from HSL values (h: 0-360, s: 0-100, l: 0-100)."""
        h_norm = (h % 360) / 360
        s_norm = max(0, min(100, s)) / 100
        l_norm = max(0, min(100, l)) / 100
        r, g, b = colorsys.hls_to_rgb(h_norm, l_norm, s_norm)
        return cls((int(r * 255), int(g * 255), int(b * 255)), name)


@dataclass
class ColorHistory:
    """Ring buffer for color history."""
    colors: list[tuple[int, int, int]] = field(default_factory=list)
    max_size: int = 20
    position: int = 0  # Current position in history
    
    def add(self, color: tuple[int, int, int]) -> None:
        """Add color to history (at current position, truncating future)."""
        # Don't add duplicates of the current color
        if self.colors and self.position < len(self.colors):
            if self.colors[self.position] == color:
                return
        
        # Truncate any "future" history if we're not at the end
        if self.position < len(self.colors) - 1:
            self.colors = self.colors[:self.position + 1]
        
        self.colors.append(color)
        if len(self.colors) > self.max_size:
            self.colors.pop(0)
        self.position = len(self.colors) - 1
    
    def previous(self) -> Optional[tuple[int, int, int]]:
        """Go to previous color in history."""
        if self.colors and self.position > 0:
            self.position -= 1
            return self.colors[self.position]
        return None
    
    def next(self) -> Optional[tuple[int, int, int]]:
        """Go to next color in history."""
        if self.colors and self.position < len(self.colors) - 1:
            self.position += 1
            return self.colors[self.position]
        return None
    
    def current(self) -> Optional[tuple[int, int, int]]:
        """Get current color in history."""
        if self.colors and 0 <= self.position < len(self.colors):
            return self.colors[self.position]
        return None


class SwatchPaletteWidget(BaseWidget):
    """Enhanced color palette with document swatches, saved colors, and editor."""
    
    def __init__(self) -> None:
        super().__init__()
        
        # Current color
        self._current_color: tuple[int, int, int] = (255, 255, 255)
        
        # Document colors (extracted from artwork)
        self._document_colors: list[ColorSwatch] = []
        
        # Saved swatches (user favorites)
        self._saved_swatches: list[ColorSwatch] = []
        self._swatches_file: Optional[Path] = None
        
        # Standard palette
        self._standard_palette = [ColorSwatch(rgb, name) for rgb, name in zip(ANSI_16_PALETTE, ANSI_16_NAMES)]
        
        # Color history
        self._history = ColorHistory()
        
        # UI State
        self._active_section = PaletteSection.DOCUMENT
        self._section_index = 0  # Selection within current section
        self._section_collapsed: dict[PaletteSection, bool] = {
            PaletteSection.CURRENT: False,
            PaletteSection.DOCUMENT: False,
            PaletteSection.SAVED: False,
            PaletteSection.STANDARD: True,  # Collapsed by default
        }
        self._section_scroll: dict[PaletteSection, int] = {
            PaletteSection.DOCUMENT: 0,
            PaletteSection.SAVED: 0,
            PaletteSection.STANDARD: 0,
        }
        
        # Color editor state
        self._editor_open = False
        self._editor_mode = ColorEditorMode.RGB
        self._editor_channel = 0  # 0=R/H, 1=G/S, 2=B/L
        self._editor_color: tuple[int, int, int] = (255, 255, 255)
        self._editor_hex_input = ""
        self._editor_original_color: tuple[int, int, int] = (255, 255, 255)
        
        # Eyedropper mode
        self._eyedropper_mode = False
        self._eyedropper_callback: Optional[Callable[[], tuple[int, int, int] | None]] = None
        
        # Callbacks
        self._on_color_change: Optional[Callable[[tuple[int, int, int]], None]] = None
        self._on_eyedropper_start: Optional[Callable[[], None]] = None
        self._on_eyedropper_end: Optional[Callable[[bool], None]] = None
    
    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    
    @property
    def current_color(self) -> tuple[int, int, int]:
        """Get current selected color."""
        return self._current_color
    
    @current_color.setter
    def current_color(self, color: tuple[int, int, int]) -> None:
        """Set current color."""
        self._current_color = color
        self._history.add(color)
    
    @property
    def editor_open(self) -> bool:
        """Whether color editor modal is open."""
        return self._editor_open
    
    @property
    def eyedropper_mode(self) -> bool:
        """Whether in eyedropper mode."""
        return self._eyedropper_mode
    
    # -------------------------------------------------------------------------
    # Callbacks
    # -------------------------------------------------------------------------
    
    def set_on_color_change(self, callback: Optional[Callable[[tuple[int, int, int]], None]]) -> None:
        """Set callback for color changes."""
        self._on_color_change = callback
    
    def set_on_eyedropper_start(self, callback: Optional[Callable[[], None]]) -> None:
        """Set callback when eyedropper mode starts."""
        self._on_eyedropper_start = callback
    
    def set_on_eyedropper_end(self, callback: Optional[Callable[[bool], None]]) -> None:
        """Set callback when eyedropper mode ends (bool = picked color)."""
        self._on_eyedropper_end = callback
    
    def set_eyedropper_callback(self, callback: Optional[Callable[[], tuple[int, int, int] | None]]) -> None:
        """Set callback to get color at cursor position."""
        self._eyedropper_callback = callback
    
    def _notify_color_change(self) -> None:
        """Notify callback of color change."""
        if self._on_color_change:
            self._on_color_change(self._current_color)
    
    # -------------------------------------------------------------------------
    # Document Colors
    # -------------------------------------------------------------------------
    
    def set_document_colors(self, colors: list[tuple[int, int, int]]) -> None:
        """Set document colors (extracted from artwork)."""
        # Deduplicate and convert to swatches
        seen = set()
        self._document_colors = []
        for rgb in colors:
            if rgb not in seen:
                seen.add(rgb)
                self._document_colors.append(ColorSwatch(rgb))
        # Reset scroll/selection if needed
        if self._section_index >= len(self._document_colors):
            self._section_index = max(0, len(self._document_colors) - 1)
    
    def extract_colors_from_pixels(self, pixels: list[list[tuple[int, int, int] | None]]) -> None:
        """Extract unique colors from pixel data."""
        color_counts: dict[tuple[int, int, int], int] = {}
        for row in pixels:
            for pixel in row:
                if pixel is not None:
                    color_counts[pixel] = color_counts.get(pixel, 0) + 1
        
        # Sort by frequency (most used first)
        sorted_colors = sorted(color_counts.keys(), key=lambda c: color_counts[c], reverse=True)
        self.set_document_colors(sorted_colors)
    
    # -------------------------------------------------------------------------
    # Saved Swatches
    # -------------------------------------------------------------------------
    
    def set_swatches_file(self, path: Path) -> None:
        """Set file for persisting swatches."""
        self._swatches_file = path
        self._load_swatches()
    
    def _load_swatches(self) -> None:
        """Load saved swatches from file."""
        if not self._swatches_file or not self._swatches_file.exists():
            return
        try:
            with open(self._swatches_file, 'r') as f:
                data = json.load(f)
            self._saved_swatches = []
            for item in data.get('swatches', []):
                rgb = tuple(item['rgb'])
                name = item.get('name', '')
                self._saved_swatches.append(ColorSwatch(rgb, name))  # type: ignore
        except (json.JSONDecodeError, KeyError, TypeError):
            pass
    
    def _save_swatches(self) -> None:
        """Save swatches to file."""
        if not self._swatches_file:
            return
        try:
            self._swatches_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'swatches': [
                    {'rgb': list(s.rgb), 'name': s.name}
                    for s in self._saved_swatches
                ]
            }
            with open(self._swatches_file, 'w') as f:
                json.dump(data, f, indent=2)
        except (OSError, IOError):
            pass
    
    def add_to_saved(self, color: Optional[tuple[int, int, int]] = None, name: str = "") -> None:
        """Add a color to saved swatches."""
        if color is None:
            color = self._current_color
        # Don't add duplicates
        for swatch in self._saved_swatches:
            if swatch.rgb == color:
                return
        self._saved_swatches.append(ColorSwatch(color, name))
        self._save_swatches()
    
    def remove_from_saved(self, index: int) -> None:
        """Remove a color from saved swatches."""
        if 0 <= index < len(self._saved_swatches):
            del self._saved_swatches[index]
            self._save_swatches()
    
    # -------------------------------------------------------------------------
    # Color Selection
    # -------------------------------------------------------------------------
    
    def select_color(self, color: tuple[int, int, int]) -> None:
        """Select a color as current."""
        self._current_color = color
        self._history.add(color)
        self._notify_color_change()
    
    def set_color_from_index(self, index: int) -> None:
        """Set color from standard palette index and update visual selection.
        
        This is used to sync the palette when the editor changes color via brackets.
        """
        if 0 <= index < 16:
            self._current_color = ANSI_16_PALETTE[index]
            self._history.add(self._current_color)
            # Update visual selection to show in standard palette
            self._active_section = PaletteSection.STANDARD
            self._section_index = index
            # Make sure standard section is visible
            self._section_collapsed[PaletteSection.STANDARD] = False
    
    def _select_from_section(self) -> None:
        """Select color from current section at current index."""
        swatches = self._get_section_swatches(self._active_section)
        if swatches and 0 <= self._section_index < len(swatches):
            self.select_color(swatches[self._section_index].rgb)
    
    def _get_section_swatches(self, section: PaletteSection) -> list[ColorSwatch]:
        """Get swatches for a section."""
        if section == PaletteSection.DOCUMENT:
            return self._document_colors
        elif section == PaletteSection.SAVED:
            return self._saved_swatches
        elif section == PaletteSection.STANDARD:
            return self._standard_palette
        return []
    
    # -------------------------------------------------------------------------
    # Color History
    # -------------------------------------------------------------------------
    
    def history_previous(self) -> None:
        """Go to previous color in history."""
        color = self._history.previous()
        if color:
            self._current_color = color
            self._notify_color_change()
    
    def history_next(self) -> None:
        """Go to next color in history."""
        color = self._history.next()
        if color:
            self._current_color = color
            self._notify_color_change()
    
    # -------------------------------------------------------------------------
    # Color Editor
    # -------------------------------------------------------------------------
    
    def open_editor(self, color: Optional[tuple[int, int, int]] = None) -> None:
        """Open color editor modal."""
        self._editor_open = True
        self._editor_original_color = color or self._current_color
        self._editor_color = self._editor_original_color
        self._editor_hex_input = ""
        self._editor_channel = 0
    
    def close_editor(self, apply: bool = False) -> None:
        """Close color editor modal."""
        if apply:
            self.select_color(self._editor_color)
        self._editor_open = False
    
    def _editor_adjust_channel(self, delta: int) -> None:
        """Adjust current channel in editor."""
        if self._editor_mode == ColorEditorMode.HEX:
            return  # No adjustment in hex mode
        
        r, g, b = self._editor_color
        
        if self._editor_mode == ColorEditorMode.RGB:
            values = [r, g, b]
            values[self._editor_channel] = max(0, min(255, values[self._editor_channel] + delta))
            self._editor_color = (values[0], values[1], values[2])
        else:  # HSL
            h, s, l = ColorSwatch(self._editor_color).hsl
            if self._editor_channel == 0:  # Hue
                h = (h + delta) % 360
            elif self._editor_channel == 1:  # Saturation
                s = max(0, min(100, s + delta))
            else:  # Lightness
                l = max(0, min(100, l + delta))
            swatch = ColorSwatch.from_hsl(h, s, l)
            self._editor_color = swatch.rgb
    
    def _editor_handle_hex_input(self, char: str) -> None:
        """Handle hex input in editor."""
        if char.upper() in '0123456789ABCDEF':
            if len(self._editor_hex_input) < 6:
                self._editor_hex_input += char.upper()
                if len(self._editor_hex_input) == 6:
                    swatch = ColorSwatch.from_hex(self._editor_hex_input)
                    if swatch:
                        self._editor_color = swatch.rgb
        elif char == '\x7f' or char == '\b':  # Backspace
            self._editor_hex_input = self._editor_hex_input[:-1]
    
    # -------------------------------------------------------------------------
    # Eyedropper Mode
    # -------------------------------------------------------------------------
    
    def enter_eyedropper(self) -> None:
        """Enter eyedropper/sampling mode."""
        self._eyedropper_mode = True
        if self._on_eyedropper_start:
            self._on_eyedropper_start()
    
    def exit_eyedropper(self, picked: bool = False) -> None:
        """Exit eyedropper mode."""
        self._eyedropper_mode = False
        if self._on_eyedropper_end:
            self._on_eyedropper_end(picked)
    
    def pick_eyedropper_color(self) -> bool:
        """Pick color at current cursor position."""
        if self._eyedropper_callback:
            color = self._eyedropper_callback()
            if color:
                self.select_color(color)
                return True
        return False
    
    # -------------------------------------------------------------------------
    # Input Handling
    # -------------------------------------------------------------------------
    
    def handle_input(self, event: KeyEvent) -> bool:
        """Handle keyboard input."""
        if not self._focused and not self._editor_open:
            return False
        
        # Color editor takes priority
        if self._editor_open:
            return self._handle_editor_input(event)
        
        # Quick color selection by number (1-9 for document, 0 for 10th)
        if event.char and event.char in '1234567890':
            idx = int(event.char) - 1 if event.char != '0' else 9
            if self._active_section == PaletteSection.DOCUMENT:
                if idx < len(self._document_colors):
                    self._section_index = idx
                    self._select_from_section()
                    return True
            elif self._active_section == PaletteSection.STANDARD:
                if idx < 16:
                    self._section_index = idx
                    self._select_from_section()
                    return True
        
        # Letter selection for saved swatches (a-z)
        if event.char and event.char.lower() in 'abcdefghijklmnopqrstuvwxyz':
            if self._active_section == PaletteSection.SAVED:
                idx = ord(event.char.lower()) - ord('a')
                if idx < len(self._saved_swatches):
                    self._section_index = idx
                    self._select_from_section()
                    return True
        
        # Section navigation
        if event.key == Key.TAB:
            self._next_section()
            return True
        
        # Collapse/expand section
        if event.char == ' ' and self._active_section != PaletteSection.CURRENT:
            self._section_collapsed[self._active_section] = not self._section_collapsed[self._active_section]
            return True
        
        # Navigation within section
        if event.key == Key.LEFT:
            self._navigate_section(-1)
            return True
        if event.key == Key.RIGHT:
            self._navigate_section(1)
            return True
        if event.key == Key.UP:
            swatches_per_row = 12  # Approximate
            self._navigate_section(-swatches_per_row)
            return True
        if event.key == Key.DOWN:
            swatches_per_row = 12
            self._navigate_section(swatches_per_row)
            return True
        
        # Select current
        if event.key == Key.ENTER:
            self._select_from_section()
            return True
        
        # Open color editor
        if event.char == 'e' or event.char == 'E':
            self.open_editor()
            return True
        
        # Add to saved
        if event.char == '+' or event.char == 'a':
            self.add_to_saved()
            return True
        
        # Remove from saved
        if event.key == Key.DELETE or event.char == '-':
            if self._active_section == PaletteSection.SAVED:
                self.remove_from_saved(self._section_index)
                if self._section_index >= len(self._saved_swatches):
                    self._section_index = max(0, len(self._saved_swatches) - 1)
                return True
        
        # Eyedropper
        if event.char == 'i':
            self.enter_eyedropper()
            return True
        
        # History navigation
        if event.char == '[':
            self.history_previous()
            return True
        if event.char == ']':
            self.history_next()
            return True
        
        return False
    
    def _handle_editor_input(self, event: KeyEvent) -> bool:
        """Handle input in color editor modal."""
        # Cancel
        if event.key == Key.ESCAPE:
            self.close_editor(apply=False)
            return True
        
        # Apply
        if event.key == Key.ENTER and self._editor_mode != ColorEditorMode.HEX:
            self.close_editor(apply=True)
            return True
        if event.key == Key.ENTER and self._editor_mode == ColorEditorMode.HEX:
            if len(self._editor_hex_input) == 6:
                self.close_editor(apply=True)
            return True
        
        # Switch mode
        if event.key == Key.TAB:
            modes = list(ColorEditorMode)
            current_idx = modes.index(self._editor_mode)
            self._editor_mode = modes[(current_idx + 1) % len(modes)]
            self._editor_hex_input = ""
            self._editor_channel = 0
            return True
        
        # Hex input mode
        if self._editor_mode == ColorEditorMode.HEX:
            if event.char:
                self._editor_handle_hex_input(event.char)
                return True
            if event.key == Key.BACKSPACE:
                self._editor_hex_input = self._editor_hex_input[:-1]
                return True
            return True
        
        # Channel navigation
        if event.key == Key.UP:
            self._editor_channel = (self._editor_channel - 1) % 3
            return True
        if event.key == Key.DOWN:
            self._editor_channel = (self._editor_channel + 1) % 3
            return True
        
        # Value adjustment
        if event.key == Key.LEFT:
            step = 10 if self._editor_mode == ColorEditorMode.HSL and self._editor_channel == 0 else 1
            self._editor_adjust_channel(-step)
            return True
        if event.key == Key.RIGHT:
            step = 10 if self._editor_mode == ColorEditorMode.HSL and self._editor_channel == 0 else 1
            self._editor_adjust_channel(step)
            return True
        if event.key == Key.PAGE_DOWN:
            step = 10
            self._editor_adjust_channel(-step)
            return True
        if event.key == Key.PAGE_UP:
            step = 10
            self._editor_adjust_channel(step)
            return True
        
        return True  # Consume all input while editor is open
    
    def _next_section(self) -> None:
        """Move to next section."""
        sections = [PaletteSection.DOCUMENT, PaletteSection.SAVED, PaletteSection.STANDARD]
        try:
            idx = sections.index(self._active_section)
            self._active_section = sections[(idx + 1) % len(sections)]
        except ValueError:
            self._active_section = PaletteSection.DOCUMENT
        self._section_index = 0
    
    def _navigate_section(self, delta: int) -> None:
        """Navigate within current section."""
        swatches = self._get_section_swatches(self._active_section)
        if not swatches:
            return
        self._section_index = max(0, min(len(swatches) - 1, self._section_index + delta))
    
    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------
    
    def render(self, bounds: Rect) -> list[str]:
        """Render the palette widget."""
        if not self._visible:
            return []
        
        lines: list[str] = []
        width = bounds.width
        
        # If editor is open, render it as overlay
        if self._editor_open:
            return self._render_editor(bounds)
        
        # Current color section
        lines.extend(self._render_current_section(width))
        
        # Document colors section
        if len(lines) < bounds.height - 2:
            remaining = bounds.height - len(lines) - 2
            lines.extend(self._render_section(
                PaletteSection.DOCUMENT,
                "DOCUMENT",
                self._document_colors,
                width,
                max_rows=min(4, remaining // 2) if not self._section_collapsed[PaletteSection.DOCUMENT] else 0
            ))
        
        # Saved swatches section
        if len(lines) < bounds.height - 2:
            remaining = bounds.height - len(lines) - 2
            lines.extend(self._render_section(
                PaletteSection.SAVED,
                "SAVED",
                self._saved_swatches,
                width,
                max_rows=min(3, remaining // 2) if not self._section_collapsed[PaletteSection.SAVED] else 0,
                show_add=True
            ))
        
        # Standard palette section
        if len(lines) < bounds.height - 1:
            remaining = bounds.height - len(lines) - 1
            lines.extend(self._render_section(
                PaletteSection.STANDARD,
                "ANSI-16",
                self._standard_palette,
                width,
                max_rows=min(2, remaining) if not self._section_collapsed[PaletteSection.STANDARD] else 0
            ))
        
        return lines[:bounds.height]
    
    def _render_current_section(self, width: int) -> list[str]:
        """Render current color section."""
        lines = []
        r, g, b = self._current_color
        
        # Color swatch and info
        swatch = f"\x1b[48;2;{r};{g};{b}m        \x1b[0m"
        hex_str = f"#{r:02X}{g:02X}{b:02X}"
        
        # Header line with swatch
        header = f" {swatch} {hex_str}"
        lines.append(header)
        
        # RGB values
        rgb_info = f" RGB({r},{g},{b})"
        if len(rgb_info) < width - 10:
            rgb_info += f"  [E]dit [I]nspect"
        lines.append(rgb_info[:width])
        
        lines.append("─" * width)
        
        return lines
    
    def _render_section(
        self,
        section: PaletteSection,
        title: str,
        swatches: list[ColorSwatch],
        width: int,
        max_rows: int = 2,
        show_add: bool = False
    ) -> list[str]:
        """Render a swatch section."""
        lines = []
        is_active = self._active_section == section and self._focused
        is_collapsed = self._section_collapsed.get(section, False)
        
        # Section header
        arrow = "▸" if is_collapsed else "▶"
        count = f"({len(swatches)})"
        add_hint = " [+]" if show_add else ""
        
        if is_active:
            header = f"\x1b[1m {arrow} {title} {count}{add_hint}\x1b[0m"
        else:
            header = f" {arrow} {title} {count}{add_hint}"
        
        lines.append(header[:width])
        
        if is_collapsed or max_rows == 0:
            return lines
        
        if not swatches:
            lines.append("   (empty)")
            return lines
        
        # Calculate swatches per row (2 chars each + 1 space)
        swatches_per_row = max(1, (width - 2) // 3)
        
        # Render swatch rows
        for row in range(max_rows):
            start_idx = row * swatches_per_row
            if start_idx >= len(swatches):
                break
            
            row_str = " "
            for i in range(swatches_per_row):
                idx = start_idx + i
                if idx >= len(swatches):
                    break
                
                swatch = swatches[idx]
                r, g, b = swatch.rgb
                
                # Determine if selected (cursor here)
                is_selected = is_active and idx == self._section_index
                # Determine if this matches the current color
                is_current = swatch.rgb == self._current_color
                
                if is_selected:
                    # Highlighted selection with brackets
                    text_color = "\x1b[38;2;255;255;0m" if (r + g + b) < 384 else "\x1b[38;2;0;0;0m"
                    row_str += f"\x1b[48;2;{r};{g};{b}m{text_color}[]\x1b[0m"
                elif is_current:
                    # Current color indicator (diamond or dot)
                    text_color = "\x1b[38;2;255;255;255m" if (r + g + b) < 384 else "\x1b[38;2;0;0;0m"
                    row_str += f"\x1b[48;2;{r};{g};{b}m{text_color}◆ \x1b[0m"
                else:
                    row_str += f"\x1b[48;2;{r};{g};{b}m  \x1b[0m"
                
                row_str += " "
            
            lines.append(row_str)
        
        # Show overflow indicator
        total_shown = max_rows * swatches_per_row
        if len(swatches) > total_shown:
            overflow = len(swatches) - total_shown
            lines.append(f"   +{overflow} more")
        
        return lines
    
    def _render_editor(self, bounds: Rect) -> list[str]:
        """Render color editor modal."""
        lines = []
        width = min(bounds.width, 36)
        
        r, g, b = self._editor_color
        orig_r, orig_g, orig_b = self._editor_original_color
        
        # Title
        lines.append("┌" + "─" * (width - 2) + "┐")
        title = " COLOR EDITOR "
        padding = (width - 2 - len(title)) // 2
        lines.append("│" + " " * padding + title + " " * (width - 2 - padding - len(title)) + "│")
        lines.append("├" + "─" * (width - 2) + "┤")
        
        # Color preview (original → new)
        orig_swatch = f"\x1b[48;2;{orig_r};{orig_g};{orig_b}m    \x1b[0m"
        new_swatch = f"\x1b[48;2;{r};{g};{b}m    \x1b[0m"
        preview_line = f"│ {orig_swatch} → {new_swatch}"
        preview_line += " " * (width - len(preview_line) - 1 + 22) + "│"  # Adjust for ANSI codes
        lines.append(preview_line)
        
        lines.append("├" + "─" * (width - 2) + "┤")
        
        # Mode indicator
        mode_names = {ColorEditorMode.RGB: "RGB", ColorEditorMode.HSL: "HSL", ColorEditorMode.HEX: "HEX"}
        mode_str = f" Mode: {mode_names[self._editor_mode]} [Tab]"
        lines.append("│" + mode_str + " " * (width - 2 - len(mode_str)) + "│")
        
        lines.append("│" + " " * (width - 2) + "│")
        
        # Mode-specific content
        if self._editor_mode == ColorEditorMode.HEX:
            hex_display = self._editor_hex_input or ColorSwatch(self._editor_color).hex[1:]
            cursor = "│" if len(self._editor_hex_input) < 6 else ""
            hex_line = f" HEX: #{hex_display}{cursor}"
            lines.append("│" + hex_line + " " * (width - 2 - len(hex_line)) + "│")
            lines.append("│" + " " * (width - 2) + "│")
            hint = " Type 6 hex digits"
            lines.append("│" + hint + " " * (width - 2 - len(hint)) + "│")
        else:
            # Sliders
            slider_width = width - 14
            
            if self._editor_mode == ColorEditorMode.RGB:
                channels = [("R", r, 255, (255, 100, 100)), 
                           ("G", g, 255, (100, 255, 100)), 
                           ("B", b, 255, (100, 100, 255))]
            else:  # HSL
                h, s, l = ColorSwatch(self._editor_color).hsl
                channels = [("H", h, 360, (255, 200, 100)), 
                           ("S", s, 100, (200, 200, 200)), 
                           ("L", l, 100, (255, 255, 200))]
            
            for i, (name, value, max_val, color) in enumerate(channels):
                is_selected = i == self._editor_channel
                prefix = ">" if is_selected else " "
                
                filled = int((value / max_val) * slider_width)
                cr, cg, cb = color
                
                slider = f"\x1b[48;2;{cr};{cg};{cb}m" + "█" * filled
                slider += f"\x1b[0m\x1b[48;2;60;60;60m" + "░" * (slider_width - filled) + "\x1b[0m"
                
                if self._editor_mode == ColorEditorMode.HSL and i == 0:
                    val_str = f"{int(value)}°"
                elif self._editor_mode == ColorEditorMode.HSL:
                    val_str = f"{int(value)}%"
                else:
                    val_str = f"{int(value)}"
                
                line = f"{prefix}{name}: {slider} {val_str:>4}"
                # Account for ANSI escape codes in length calculation
                visible_len = len(f"{prefix}{name}:  {val_str:>4}") + slider_width
                padding = width - 2 - visible_len
                lines.append("│" + f" {prefix}{name}: " + slider + f" {val_str:>4}" + " " * max(0, padding - 4) + "│")
        
        lines.append("│" + " " * (width - 2) + "│")
        lines.append("├" + "─" * (width - 2) + "┤")
        
        # Footer with actions
        footer = " [Esc]Cancel  [Enter]Apply"
        lines.append("│" + footer + " " * (width - 2 - len(footer)) + "│")
        lines.append("└" + "─" * (width - 2) + "┘")
        
        return lines
    
    # -------------------------------------------------------------------------
    # Quick Access Methods
    # -------------------------------------------------------------------------
    
    def quick_select_standard(self, index: int) -> None:
        """Quick select from standard palette by index (0-15)."""
        if 0 <= index < 16:
            self.select_color(ANSI_16_PALETTE[index])
    
    def get_color_at_index(self, index: int) -> Optional[tuple[int, int, int]]:
        """Get color at index in current active section."""
        swatches = self._get_section_swatches(self._active_section)
        if 0 <= index < len(swatches):
            return swatches[index].rgb
        return None
