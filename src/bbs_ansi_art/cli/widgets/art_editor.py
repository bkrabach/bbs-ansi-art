"""Interactive editor widget for ANSI art."""

from __future__ import annotations

import re
from typing import Callable, Optional

from bbs_ansi_art.cli.core.input import Key, KeyEvent
from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect
from bbs_ansi_art.edit.editable import EditableCanvas, EditContext, EditMode, ColorMode

# 16-color ANSI palette for quick color selection
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


def _visible_length(s: str) -> int:
    """Calculate visible length of a string, ignoring ANSI escape sequences."""
    # Remove all ANSI escape sequences
    ansi_pattern = re.compile(r'\x1b\[[0-9;]*[A-Za-z]')
    return len(ansi_pattern.sub('', s))


def _truncate_ansi(s: str, max_width: int) -> str:
    """Truncate an ANSI-escaped string to max visible width.
    
    Preserves ANSI codes but counts only visible characters.
    """
    if max_width <= 0:
        return ""
    
    result = []
    visible_len = 0
    i = 0
    
    while i < len(s) and visible_len < max_width:
        if s[i] == '\x1b' and i + 1 < len(s) and s[i + 1] == '[':
            # Start of ANSI escape sequence - include the whole thing
            j = i + 2
            while j < len(s) and s[j] not in 'ABCDEFGHJKSTfmsu':
                j += 1
            if j < len(s):
                j += 1  # Include the terminating character
            result.append(s[i:j])
            i = j
        else:
            result.append(s[i])
            visible_len += 1
            i += 1
    
    return ''.join(result)


def _slice_ansi(s: str, start: int, end: int) -> str:
    """Extract a visible slice from an ANSI string.
    
    Args:
        s: String potentially containing ANSI escape codes
        start: Start visible character index (inclusive)
        end: End visible character index (exclusive)
        
    Returns:
        Substring with ANSI codes preserved
    """
    if start >= end:
        return ""
    
    result = []
    visible_idx = 0
    i = 0
    active_codes: list[str] = []  # Track active ANSI codes for prefix
    
    while i < len(s):
        if s[i] == '\x1b' and i + 1 < len(s) and s[i + 1] == '[':
            # ANSI escape sequence
            j = i + 2
            while j < len(s) and s[j] not in 'ABCDEFGHJKSTfmsu':
                j += 1
            if j < len(s):
                j += 1
            seq = s[i:j]
            
            # Track active codes
            if visible_idx < start:
                active_codes.append(seq)
            elif visible_idx < end:
                result.append(seq)
            
            i = j
        else:
            if start <= visible_idx < end:
                # Add active codes prefix on first visible char
                if visible_idx == start and active_codes:
                    result.extend(active_codes)
                result.append(s[i])
            visible_idx += 1
            if visible_idx >= end:
                break
            i += 1
    
    return ''.join(result)


def _insert_at_visible_pos(s: str, pos: int, insert_str: str) -> str:
    """Insert a string at a visible character position in an ANSI string.
    
    Args:
        s: Original string with potential ANSI codes
        pos: Visible character position to insert at
        insert_str: String to insert (may contain ANSI codes)
        
    Returns:
        New string with insertion
    """
    result = []
    visible_idx = 0
    i = 0
    inserted = False
    
    while i < len(s):
        if visible_idx == pos and not inserted:
            result.append(insert_str)
            inserted = True
        
        if s[i] == '\x1b' and i + 1 < len(s) and s[i + 1] == '[':
            # ANSI escape sequence
            j = i + 2
            while j < len(s) and s[j] not in 'ABCDEFGHJKSTfmsu':
                j += 1
            if j < len(s):
                j += 1
            result.append(s[i:j])
            i = j
        else:
            result.append(s[i])
            visible_idx += 1
            i += 1
    
    # Insert at end if position is at or past the end
    if not inserted:
        result.append(insert_str)
    
    return ''.join(result)


class ArtEditorWidget(BaseWidget):
    """Interactive editor for ANSI art.
    
    Provides a full-featured editor with cursor navigation, drawing,
    scrolling, and color selection. Supports both cell mode (character-level)
    and pixel mode (half-block) editing.
    
    Keyboard Controls:
        Navigation:
            Arrow keys / hjkl: Move cursor
            Home / 0: Move to start of line
            End / $: Move to end of line
            PgUp / Ctrl+U: Scroll up one page
            PgDn / Ctrl+D: Scroll down one page
            g: Go to top
            G: Go to bottom
            
        Drawing:
            d: Draw at cursor with current color
            D: Enter draw mode (draws while moving, Esc to exit)
            x: Erase at cursor (draw transparent)
            X: Enter erase mode (erases while moving, Esc to exit)
            
        Colors:
            0-9: Quick select color (0-9 from palette)
            Shift+0-5: Select color 10-15
            [ / ]: Cycle foreground color
            { / }: Cycle background color
            
        Modes:
            Tab: Toggle between cell/pixel mode
            f: Toggle foreground affect
            b: Toggle background affect
    """
    
    def __init__(self) -> None:
        super().__init__()
        self._canvas: EditableCanvas | None = None
        self._rendered_lines: list[str] = []
        
        # Cursor state
        self._cursor_x: int = 0
        self._cursor_y: int = 0  # Cell row for CELL mode, pixel row for PIXEL mode
        
        # Scroll state
        self._scroll_x: int = 0
        self._scroll_y: int = 0
        
        # Viewport size (updated during render)
        self._viewport_width: int = 80
        self._viewport_height: int = 24
        
        # Edit context (current colors/brush)
        self._context = EditContext()
        
        # Current drawing color (RGB tuple)
        self._fg_color: tuple[int, int, int] = ANSI_16_RGB[15]  # Bright white
        self._bg_color: tuple[int, int, int] = ANSI_16_RGB[0]   # Black
        self._fg_index: int = 15  # Palette index for cycling
        self._bg_index: int = 0
        
        # Help overlay
        self._show_help: bool = False
        
        # Continuous draw/erase mode (hold while moving)
        self._draw_mode: bool = False  # True when holding space
        self._erase_mode: bool = False  # True when holding x
        
        # Callbacks
        self._on_cursor_move: Callable[[int, int], None] | None = None
        self._on_modified: Callable[[], None] | None = None
        self._on_mode_change: Callable[[EditMode], None] | None = None
    
    @property
    def active_mode(self) -> str | None:
        """Get the current active mode name, if any.
        
        Returns:
            'DRAW' if draw mode, 'ERASE' if erase mode, None otherwise
        """
        if self._draw_mode:
            return "DRAW"
        elif self._erase_mode:
            return "ERASE"
        return None
    
    def exit_mode(self) -> bool:
        """Exit any active mode (draw/erase).
        
        Returns:
            True if a mode was exited, False if no mode was active
        """
        if self._draw_mode or self._erase_mode:
            self._draw_mode = False
            self._erase_mode = False
            return True
        return False
        self._on_modified: Callable[[], None] | None = None
        self._on_mode_change: Callable[[EditMode], None] | None = None
        self._on_color_change: Callable[[int, int], None] | None = None
    
    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    
    @property
    def cursor_x(self) -> int:
        """Current cursor X position (column)."""
        return self._cursor_x
    
    @property
    def cursor_y(self) -> int:
        """Current cursor Y position (row)."""
        return self._cursor_y
    
    @property
    def scroll_x(self) -> int:
        """Current horizontal scroll offset."""
        return self._scroll_x
    
    @property
    def scroll_y(self) -> int:
        """Current vertical scroll offset."""
        return self._scroll_y
    
    @property
    def context(self) -> EditContext:
        """Current edit context."""
        return self._context
    
    @property
    def fg_color(self) -> tuple[int, int, int]:
        """Current foreground color (RGB)."""
        return self._fg_color
    
    @property
    def bg_color(self) -> tuple[int, int, int]:
        """Current background color (RGB)."""
        return self._bg_color
    
    @property
    def fg_index(self) -> int:
        """Current foreground palette index."""
        return self._fg_index
    
    @property
    def bg_index(self) -> int:
        """Current background palette index."""
        return self._bg_index
    
    @property
    def canvas(self) -> EditableCanvas | None:
        """The canvas being edited."""
        return self._canvas
    
    # -------------------------------------------------------------------------
    # Callback Registration
    # -------------------------------------------------------------------------
    
    def on_cursor_move(self, callback: Callable[[int, int], None] | None) -> None:
        """Register callback for cursor movement. Receives (x, y)."""
        self._on_cursor_move = callback
    
    def on_modified(self, callback: Callable[[], None] | None) -> None:
        """Register callback for document modification."""
        self._on_modified = callback
    
    def on_mode_change(self, callback: Callable[[EditMode], None] | None) -> None:
        """Register callback for edit mode changes."""
        self._on_mode_change = callback
    
    def on_color_change(self, callback: Callable[[int, int], None] | None) -> None:
        """Register callback for color changes. Receives (fg_index, bg_index)."""
        self._on_color_change = callback
    
    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------
    
    def load(self, canvas: EditableCanvas) -> None:
        """Load a canvas for editing.
        
        Args:
            canvas: The EditableCanvas to edit
        """
        from bbs_ansi_art.edit.pixel_canvas import PixelEditableCanvas
        
        self._canvas = canvas
        
        # Set mode based on canvas type
        if isinstance(canvas, PixelEditableCanvas):
            self._context.mode = EditMode.PIXEL
        else:
            self._context.mode = EditMode.CELL
        
        self._cursor_x = 0
        self._cursor_y = 0
        self._scroll_x = 0
        self._scroll_y = 0
        self._refresh_render()
    
    def unload(self) -> None:
        """Unload the current canvas."""
        self._canvas = None
        self._rendered_lines = []
        self._cursor_x = 0
        self._cursor_y = 0
        self._scroll_x = 0
        self._scroll_y = 0
    
    def _refresh_render(self) -> None:
        """Re-render the canvas to cached lines."""
        if self._canvas is None:
            self._rendered_lines = []
            return
        
        rendered = self._canvas.render()
        self._rendered_lines = rendered.split('\n')
    
    # -------------------------------------------------------------------------
    # Color Management
    # -------------------------------------------------------------------------
    
    def set_fg_color(self, index: int) -> None:
        """Set foreground color by palette index.
        
        Args:
            index: Palette index 0-15
        """
        if 0 <= index < 16:
            self._fg_index = index
            self._fg_color = ANSI_16_RGB[index]
            if self._on_color_change:
                self._on_color_change(self._fg_index, self._bg_index)

    def set_fg_color_rgb(self, color: tuple[int, int, int]) -> None:
        """Set foreground color by RGB value directly.

        This allows setting arbitrary colors not in the ANSI-16 palette.

        Args:
            color: RGB tuple (r, g, b)
        """
        self._fg_color = color
        # Set index to -1 to indicate custom color (not in palette)
        self._fg_index = -1
    
    def set_bg_color(self, index: int) -> None:
        """Set background color by palette index.
        
        Args:
            index: Palette index 0-15
        """
        if 0 <= index < 16:
            self._bg_index = index
            self._bg_color = ANSI_16_RGB[index]
            if self._on_color_change:
                self._on_color_change(self._fg_index, self._bg_index)
    
    def cycle_fg_color(self, delta: int) -> None:
        """Cycle foreground color.
        
        Args:
            delta: Direction to cycle (+1 or -1)
        """
        self.set_fg_color((self._fg_index + delta) % 16)
    
    def cycle_bg_color(self, delta: int) -> None:
        """Cycle background color.
        
        Args:
            delta: Direction to cycle (+1 or -1)
        """
        self.set_bg_color((self._bg_index + delta) % 16)
    
    # -------------------------------------------------------------------------
    # Mode Management
    # -------------------------------------------------------------------------
    
    def toggle_mode(self) -> None:
        """Toggle between CELL and PIXEL edit modes."""
        if self._context.mode == EditMode.CELL:
            self._context.mode = EditMode.PIXEL
            # Convert cursor position: cell Y -> pixel Y (multiply by 2)
            self._cursor_y = self._cursor_y * 2
        else:
            self._context.mode = EditMode.CELL
            # Convert cursor position: pixel Y -> cell Y (divide by 2)
            self._cursor_y = self._cursor_y // 2
        
        self._ensure_cursor_bounds()
        
        if self._on_mode_change:
            self._on_mode_change(self._context.mode)
    
    def toggle_affect_foreground(self) -> None:
        """Toggle whether drawing affects foreground."""
        self._context.affect_foreground = not self._context.affect_foreground
    
    def toggle_affect_background(self) -> None:
        """Toggle whether drawing affects background."""
        self._context.affect_background = not self._context.affect_background
    
    # -------------------------------------------------------------------------
    # Cursor Movement
    # -------------------------------------------------------------------------
    
    def _get_max_y(self) -> int:
        """Get maximum Y coordinate based on current mode."""
        if self._canvas is None:
            return 0
        if self._context.mode == EditMode.PIXEL:
            return max(0, self._canvas.pixel_height - 1)
        return max(0, self._canvas.height - 1)
    
    def _get_max_x(self) -> int:
        """Get maximum X coordinate."""
        if self._canvas is None:
            return 0
        return max(0, self._canvas.width - 1)
    
    def _ensure_cursor_bounds(self) -> None:
        """Ensure cursor is within valid bounds."""
        self._cursor_x = max(0, min(self._cursor_x, self._get_max_x()))
        self._cursor_y = max(0, min(self._cursor_y, self._get_max_y()))
    
    def move_cursor(self, dx: int, dy: int) -> None:
        """Move cursor with bounds checking (public API).
        
        Args:
            dx: Horizontal movement (positive = right)
            dy: Vertical movement (positive = down)
        """
        self._move_cursor(dx, dy)
    
    def _move_cursor(self, dx: int, dy: int) -> None:
        """Move cursor with bounds checking.
        
        Args:
            dx: Horizontal movement (positive = right)
            dy: Vertical movement (positive = down)
        """
        old_x, old_y = self._cursor_x, self._cursor_y
        
        self._cursor_x = max(0, min(self._cursor_x + dx, self._get_max_x()))
        self._cursor_y = max(0, min(self._cursor_y + dy, self._get_max_y()))
        
        # Update scroll to keep cursor visible
        self._ensure_cursor_visible()
        
        if (self._cursor_x, self._cursor_y) != (old_x, old_y):
            if self._on_cursor_move:
                self._on_cursor_move(self._cursor_x, self._cursor_y)
    
    def _set_cursor(self, x: int, y: int) -> None:
        """Set cursor to absolute position.
        
        Args:
            x: X coordinate
            y: Y coordinate
        """
        old_x, old_y = self._cursor_x, self._cursor_y
        
        self._cursor_x = max(0, min(x, self._get_max_x()))
        self._cursor_y = max(0, min(y, self._get_max_y()))
        
        self._ensure_cursor_visible()
        
        if (self._cursor_x, self._cursor_y) != (old_x, old_y):
            if self._on_cursor_move:
                self._on_cursor_move(self._cursor_x, self._cursor_y)
    
    def _ensure_cursor_visible(self) -> None:
        """Adjust scroll to keep cursor within viewport."""
        # Horizontal scrolling
        if self._cursor_x < self._scroll_x:
            self._scroll_x = self._cursor_x
        elif self._cursor_x >= self._scroll_x + self._viewport_width:
            self._scroll_x = self._cursor_x - self._viewport_width + 1
        
        # Vertical scrolling
        # In pixel mode, we need to convert to display rows
        display_y = self._cursor_y
        if self._context.mode == EditMode.PIXEL:
            display_y = self._cursor_y // 2
        
        if display_y < self._scroll_y:
            self._scroll_y = display_y
        elif display_y >= self._scroll_y + self._viewport_height:
            self._scroll_y = display_y - self._viewport_height + 1
    
    def _page_up(self) -> None:
        """Move cursor up one page."""
        page_size = max(1, self._viewport_height - 2)
        if self._context.mode == EditMode.PIXEL:
            page_size *= 2
        self._move_cursor(0, -page_size)
    
    def _page_down(self) -> None:
        """Move cursor down one page."""
        page_size = max(1, self._viewport_height - 2)
        if self._context.mode == EditMode.PIXEL:
            page_size *= 2
        self._move_cursor(0, page_size)
    
    def _go_to_start_of_line(self) -> None:
        """Move cursor to start of current line."""
        self._set_cursor(0, self._cursor_y)
    
    def _go_to_end_of_line(self) -> None:
        """Move cursor to end of current line."""
        self._set_cursor(self._get_max_x(), self._cursor_y)
    
    def _go_to_top(self) -> None:
        """Move cursor to top of canvas."""
        self._set_cursor(self._cursor_x, 0)
    
    def _go_to_bottom(self) -> None:
        """Move cursor to bottom of canvas."""
        self._set_cursor(self._cursor_x, self._get_max_y())
    
    # -------------------------------------------------------------------------
    # Drawing Operations
    # -------------------------------------------------------------------------
    
    def _draw_at_cursor(self) -> None:
        """Draw using current context at cursor position."""
        if self._canvas is None:
            return
        
        self._canvas.draw_point(
            self._cursor_x,
            self._cursor_y,
            self._fg_color,
            self._context,
        )
        
        self._refresh_render()
        
        if self._on_modified:
            self._on_modified()
    
    def _draw_and_advance(self) -> None:
        """Draw at cursor and move right."""
        self._draw_at_cursor()
        self._move_cursor(1, 0)
    
    def _erase_at_cursor(self) -> None:
        """Erase at cursor (transparent for pixel mode, bg color for cell mode)."""
        if self._canvas is None:
            return
        
        if self._context.mode == EditMode.PIXEL:
            # Pixel mode: erase to transparent
            if hasattr(self._canvas, 'erase_point'):
                self._canvas.erase_point(self._cursor_x, self._cursor_y)
            else:
                # Fallback to black if no erase_point method
                self._canvas.draw_point(
                    self._cursor_x,
                    self._cursor_y,
                    (0, 0, 0),
                    self._context,
                )
        else:
            # Cell mode: erase with background color
            self._canvas.draw_point(
                self._cursor_x,
                self._cursor_y,
                self._bg_color,
                self._context,
            )
        
        self._refresh_render()
        
        if self._on_modified:
            self._on_modified()
    
    # -------------------------------------------------------------------------
    # Input Handling
    # -------------------------------------------------------------------------
    
    def handle_input(self, event: KeyEvent) -> bool:
        """Handle keyboard input.
        
        Args:
            event: Key event to handle
            
        Returns:
            True if the event was consumed, False otherwise
        """
        if self._canvas is None:
            return False
        
        # Arrow key navigation (Shift = fast move: 10 pixels or 5 cells)
        fast_x = 10
        fast_y = 5 if self._context.mode == EditMode.CELL else 10
        
        if event.key == Key.UP:
            dy = -fast_y if event.shift else -1
            self._move_cursor(0, dy)
            if self._draw_mode:
                self._draw_at_cursor()
            elif self._erase_mode:
                self._erase_at_cursor()
            return True
        elif event.key == Key.DOWN:
            dy = fast_y if event.shift else 1
            self._move_cursor(0, dy)
            if self._draw_mode:
                self._draw_at_cursor()
            elif self._erase_mode:
                self._erase_at_cursor()
            return True
        elif event.key == Key.LEFT:
            dx = -fast_x if event.shift else -1
            self._move_cursor(dx, 0)
            if self._draw_mode:
                self._draw_at_cursor()
            elif self._erase_mode:
                self._erase_at_cursor()
            return True
        elif event.key == Key.RIGHT:
            dx = fast_x if event.shift else 1
            self._move_cursor(dx, 0)
            if self._draw_mode:
                self._draw_at_cursor()
            elif self._erase_mode:
                self._erase_at_cursor()
            return True
        
        # Vi-style navigation (hjkl)
        if event.char == 'h':
            self._move_cursor(-1, 0)
            return True
        elif event.char == 'j':
            dy = 1 if self._context.mode == EditMode.CELL else 1
            self._move_cursor(0, dy)
            return True
        elif event.char == 'k':
            dy = -1 if self._context.mode == EditMode.CELL else -1
            self._move_cursor(0, dy)
            return True
        elif event.char == 'l':
            self._move_cursor(1, 0)
            return True
        
        # Page navigation
        if event.key == Key.PAGE_UP:
            self._page_up()
            return True
        elif event.key == Key.PAGE_DOWN:
            self._page_down()
            return True
        
        # Home/End navigation
        if event.key == Key.HOME or event.char == '0':
            self._go_to_start_of_line()
            return True
        elif event.key == Key.END or event.char == '$':
            self._go_to_end_of_line()
            return True
        
        # Top/Bottom navigation (vi-style)
        if event.char == 'g':
            self._go_to_top()
            return True
        elif event.char == 'G':
            self._go_to_bottom()
            return True
        
        # Ctrl+U/D for page up/down
        if event.raw == '\x15':  # Ctrl+U
            self._page_up()
            return True
        elif event.raw == '\x04':  # Ctrl+D
            self._page_down()
            return True
        
        # Drawing: d = single draw, D = draw mode, x = single erase, X = erase mode
        if event.char == 'd':
            self._draw_at_cursor()
            return True
        elif event.char == 'x':
            self._erase_at_cursor()
            return True
        
        # Toggle continuous draw mode (capital D) - draws on entry + while moving
        elif event.char == 'D':
            self._draw_mode = not self._draw_mode
            self._erase_mode = False  # Can't have both
            if self._draw_mode:
                # Draw at current position when entering draw mode
                self._draw_at_cursor()
            return True
        
        # Toggle continuous erase mode (capital X) - erases on entry + while moving
        elif event.char == 'X':
            self._erase_mode = not self._erase_mode
            self._draw_mode = False  # Can't have both
            if self._erase_mode:
                # Erase at current position when entering erase mode
                self._erase_at_cursor()
            return True
        
        # Escape exits any active mode first, then propagates
        elif event.key == Key.ESCAPE:
            if self.exit_mode():
                return True
            # Let escape propagate for other uses (quit, etc.)
            return False
        
        # Color selection (number keys 1-9, 0 handled above for home)
        if event.char and event.char in '123456789':
            self.set_fg_color(int(event.char))
            return True
        
        # Shift+number for colors 10-15 (symbols on US keyboard)
        color_shift_map = {
            '!': 10,  # Shift+1 -> Bright Green
            '@': 11,  # Shift+2 -> Bright Yellow  
            '#': 12,  # Shift+3 -> Bright Blue
            '%': 13,  # Shift+5 -> Bright Magenta
            '^': 14,  # Shift+6 -> Bright Cyan
            '&': 15,  # Shift+7 -> Bright White
        }
        if event.char in color_shift_map:
            self.set_fg_color(color_shift_map[event.char])
            return True
        
        # Color cycling
        if event.char == ']':
            self.cycle_fg_color(1)
            return True
        elif event.char == '[':
            self.cycle_fg_color(-1)
            return True
        # BG color cycling only in cell mode (not useful in pixel mode)
        elif event.char == '}' and self._context.mode == EditMode.CELL:
            self.cycle_bg_color(1)
            return True
        elif event.char == '{' and self._context.mode == EditMode.CELL:
            self.cycle_bg_color(-1)
            return True
        
        # Mode toggles
        if event.key == Key.TAB:
            self.toggle_mode()
            return True
        elif event.char == 'f':
            self.toggle_affect_foreground()
            return True
        elif event.char == 'b':
            self.toggle_affect_background()
            return True
        
        # Help overlay
        if event.char == '?':
            self._show_help = not self._show_help
            return True
        
        # Any key dismisses help if showing
        if self._show_help:
            self._show_help = False
            return True
        
        return False
    
    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------
    
    def render(self, bounds: Rect) -> list[str]:
        """Render the editor with cursor overlay.
        
        Args:
            bounds: Rectangle defining the render area
            
        Returns:
            List of strings (one per line) for display
        """
        self._viewport_width = bounds.width
        self._viewport_height = bounds.height
        
        if self._canvas is None or not self._rendered_lines:
            # Empty state
            lines = [""] * bounds.height
            msg = "(No canvas loaded)"
            if bounds.height > 2 and bounds.width > len(msg):
                lines[bounds.height // 2] = f"\x1b[90m{msg:^{bounds.width}}\x1b[0m"
            return lines
        
        # Get visible slice of rendered lines
        visible_lines = []
        for i in range(bounds.height):
            line_idx = self._scroll_y + i
            if line_idx < len(self._rendered_lines):
                line = self._rendered_lines[line_idx]
                # Apply horizontal scroll and truncate
                if self._scroll_x > 0:
                    line = _slice_ansi(line, self._scroll_x, self._scroll_x + bounds.width)
                else:
                    line = _truncate_ansi(line, bounds.width)
                visible_lines.append(line)
            else:
                visible_lines.append("")
        
        # Overlay cursor
        visible_lines = self._overlay_cursor(visible_lines, bounds)
        
        # Note: Help overlay is now handled at the studio level (EditorApp)
        # to ensure proper full-screen centering over editor + palette
        
        return visible_lines
    
    def _overlay_cursor(self, lines: list[str], bounds: Rect) -> list[str]:
        """Add cursor highlight to output.
        
        The cursor is rendered using reverse video (swap fg/bg colors).
        
        Args:
            lines: List of rendered lines
            bounds: Viewport bounds
            
        Returns:
            Lines with cursor overlay applied
        """
        # Calculate cursor position in viewport
        cursor_view_x = self._cursor_x - self._scroll_x
        
        # In pixel mode, cursor_y is pixel position; display row = cursor_y // 2
        if self._context.mode == EditMode.PIXEL:
            cursor_view_y = (self._cursor_y // 2) - self._scroll_y
        else:
            cursor_view_y = self._cursor_y - self._scroll_y
        
        # Check if cursor is visible
        if not (0 <= cursor_view_x < bounds.width and 0 <= cursor_view_y < bounds.height):
            return lines
        
        if cursor_view_y >= len(lines):
            return lines
        
        line = lines[cursor_view_y]
        visible_len = _visible_length(line)
        
        # Build the cursor-overlaid line
        r, g, b = self._fg_color
        
        if self._context.mode == EditMode.PIXEL:
            # Pixel mode: show cursor with both halves visible
            # - The half being edited shows the cursor/selected color
            # - The other half shows its actual pixel color from the canvas
            is_top_pixel = (self._cursor_y % 2) == 0
            
            # Get the OTHER pixel's color (the one not being edited)
            other_color: tuple[int, int, int] | None = None
            if self._canvas is not None:
                if is_top_pixel:
                    # Editing top pixel, get bottom pixel's color
                    other_y = self._cursor_y + 1
                else:
                    # Editing bottom pixel, get top pixel's color
                    other_y = self._cursor_y - 1
                
                if 0 <= other_y < self._canvas.pixel_height:
                    other_pixel = self._canvas.get_pixel(self._cursor_x, other_y)
                    if not other_pixel.transparent:
                        other_color = other_pixel.rgb
            
            col = cursor_view_x + 1  # 1-indexed for ANSI
            
            if cursor_view_x < visible_len:
                # Build cursor character with both halves
                # Upper half block (▀): FG = top color, BG = bottom color
                if is_top_pixel:
                    # Editing TOP pixel: FG = cursor color, BG = other (bottom) pixel
                    fg_part = f"\x1b[38;2;{r};{g};{b}m"
                    if other_color:
                        bg_part = f"\x1b[48;2;{other_color[0]};{other_color[1]};{other_color[2]}m"
                    else:
                        bg_part = "\x1b[49m"  # Default/transparent background
                    cursor_char = f"{fg_part}{bg_part}\u2580\x1b[0m"
                else:
                    # Editing BOTTOM pixel: use lower half block
                    # Lower half block (▄): FG = bottom color, BG = top color
                    fg_part = f"\x1b[38;2;{r};{g};{b}m"
                    if other_color:
                        bg_part = f"\x1b[48;2;{other_color[0]};{other_color[1]};{other_color[2]}m"
                    else:
                        bg_part = "\x1b[49m"
                    cursor_char = f"{fg_part}{bg_part}\u2584\x1b[0m"
                
                cursor_overlay = f"\x1b[s\x1b[{col}G{cursor_char}\x1b[u"
                lines[cursor_view_y] = f"{line}{cursor_overlay}"
            else:
                # Cursor past content - show half-block on empty space
                padding = " " * (cursor_view_x - visible_len)
                if is_top_pixel:
                    fg_part = f"\x1b[38;2;{r};{g};{b}m"
                    if other_color:
                        bg_part = f"\x1b[48;2;{other_color[0]};{other_color[1]};{other_color[2]}m"
                    else:
                        bg_part = "\x1b[49m"
                    cursor_char = f"{fg_part}{bg_part}\u2580\x1b[0m"
                else:
                    fg_part = f"\x1b[38;2;{r};{g};{b}m"
                    if other_color:
                        bg_part = f"\x1b[48;2;{other_color[0]};{other_color[1]};{other_color[2]}m"
                    else:
                        bg_part = "\x1b[49m"
                    cursor_char = f"{fg_part}{bg_part}\u2584\x1b[0m"
                lines[cursor_view_y] = f"{line}{padding}{cursor_char}"
        else:
            # Cell mode: use reverse video for full-cell cursor
            cursor_on = "\x1b[7m"   # Reverse video
            cursor_off = "\x1b[27m\x1b[0m"  # Reverse off + full reset
            
            if cursor_view_x < visible_len:
                before = _slice_ansi(line, 0, cursor_view_x)
                cursor_content = _slice_ansi(line, cursor_view_x, cursor_view_x + 1)
                after = _slice_ansi(line, cursor_view_x + 1, visible_len)
                lines[cursor_view_y] = f"{before}{cursor_on}{cursor_content}{cursor_off}{after}"
            else:
                padding = " " * (cursor_view_x - visible_len)
                cursor_char = f"\x1b[48;2;{r};{g};{b}m \x1b[0m"
                lines[cursor_view_y] = f"{line}{padding}{cursor_char}"
        
        return lines
    
    def _overlay_help(self, lines: list[str], bounds: Rect) -> list[str]:
        """Overlay help panel on the editor.
        
        Args:
            lines: Current rendered lines
            bounds: Viewport bounds
            
        Returns:
            Lines with help overlay
        """
        # Style: bold white on dark gray background
        style = "\x1b[1;97;48;5;236m"
        reset = "\x1b[0m"
        
        help_content = [
            "╭─────────────────────────────────────╮",
            "│         EDITOR HELP  (? to close)  │",
            "├─────────────────────────────────────┤",
            "│  NAVIGATION                        │",
            "│    Arrow keys / hjkl   Move cursor │",
            "│    Home / End          Line start  │",
            "│    PgUp / PgDn         Scroll page │",
            "│                                    │",
            "│  DRAWING                           │",
            "│    d                   Draw pixel  │",
            "│    D                   Draw mode   │",
            "│    x                   Erase pixel │",
            "│    X                   Erase mode  │",
            "│                                    │",
            "│  COLORS                            │",
            "│    1-9                 Pick color  │",
            "│    [ / ]               Cycle color │",
            "│    i                   Eyedropper  │",
            "│    p                   Palette     │",
            "│                                    │",
            "│  FILE                              │",
            "│    s                   Save        │",
            "│    q                   Quit        │",
            "╰─────────────────────────────────────╯",
        ]
        
        # Center the help overlay
        help_width = 39  # Width of the box content
        help_height = len(help_content)
        
        start_x = max(0, (bounds.width - help_width) // 2)
        start_y = max(0, (bounds.height - help_height) // 2)
        
        result = list(lines)
        
        # Ensure we have enough lines
        while len(result) < bounds.height:
            result.append(" " * bounds.width)
        
        for i, help_line in enumerate(help_content):
            line_y = start_y + i
            if 0 <= line_y < len(result):
                existing = result[line_y]
                existing_vis_len = _visible_length(existing)
                
                # Get content before the help box
                if start_x > 0:
                    before = _truncate_ansi(existing, start_x)
                else:
                    before = ""
                
                # Get content after the help box
                after_start = start_x + help_width
                if after_start < existing_vis_len:
                    after = _slice_ansi(existing, after_start, existing_vis_len)
                else:
                    after = ""
                
                # Combine: before + styled help + reset + after
                result[line_y] = f"{before}{style}{help_line}{reset}{after}"
        
        return result
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def get_status(self) -> str:
        """Get a status string describing current editor state.
        
        Returns:
            Status string suitable for display in a status bar
        """
        if self._canvas is None:
            return "No canvas"
        
        mode_str = "CELL" if self._context.mode == EditMode.CELL else "PIXEL"
        
        # Include color swatch for visual feedback
        fg_r, fg_g, fg_b = self._fg_color
        fg_swatch = f"\x1b[48;2;{fg_r};{fg_g};{fg_b}m  \x1b[0m"
        
        if self._context.mode == EditMode.PIXEL:
            # Pixel mode: only show FG color (BG not used)
            return (
                f"({self._cursor_x},{self._cursor_y}) "
                f"{mode_str} "
                f"Color:{self._fg_index}{fg_swatch}"
            )
        else:
            # Cell mode: show FG/BG and affect flags
            affect = []
            if self._context.affect_foreground:
                affect.append("FG")
            if self._context.affect_background:
                affect.append("BG")
            affect_str = "+".join(affect) if affect else "NONE"
            
            bg_r, bg_g, bg_b = self._bg_color
            bg_swatch = f"\x1b[48;2;{bg_r};{bg_g};{bg_b}m  \x1b[0m"
            
            return (
                f"({self._cursor_x},{self._cursor_y}) "
                f"{mode_str} {affect_str} "
                f"FG:{self._fg_index}{fg_swatch} BG:{self._bg_index}{bg_swatch}"
            )
    
    def get_scroll_percent(self) -> float:
        """Get vertical scroll position as percentage.
        
        Returns:
            Scroll percentage (0-100)
        """
        if not self._rendered_lines or len(self._rendered_lines) <= self._viewport_height:
            return 0.0
        max_scroll = len(self._rendered_lines) - self._viewport_height
        if max_scroll <= 0:
            return 0.0
        return (self._scroll_y / max_scroll) * 100
