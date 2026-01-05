"""Interactive ANSI art editor application.

This module provides the main EditorApp that integrates:
- ArtEditorWidget: Main canvas for editing ANSI art
- SwatchPaletteWidget: Color picker with document colors, saved swatches, and editor
- StatusBarWidget: Information display and keyboard shortcuts
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from bbs_ansi_art.cli.core.terminal import Terminal
from bbs_ansi_art.cli.core.input import InputReader, Key, KeyEvent
from bbs_ansi_art.cli.core.ansi_text import visible_len, truncate, pad_to_width
from bbs_ansi_art.cli.core.shortcuts import get_shortcut_registry, ShortcutContext
from bbs_ansi_art.cli.widgets.base import Rect
from bbs_ansi_art.cli.widgets.art_editor import ArtEditorWidget, ANSI_16_RGB
from bbs_ansi_art.cli.widgets.swatch_palette import SwatchPaletteWidget, ANSI_16_PALETTE
from bbs_ansi_art.cli.widgets.status_bar import StatusBarWidget, Shortcut
from bbs_ansi_art.edit.document import EditableDocument, DocumentFormat
from bbs_ansi_art.edit.editable import EditMode, ColorMode


# Layout constants
PALETTE_WIDTH = 40
MIN_EDITOR_WIDTH = 40
STATUS_BAR_HEIGHT = 1


class EditorApp:
    """Interactive ANSI art editor.
    
    Provides a full-featured terminal-based editor for creating and
    editing ANSI art files (.ans and .art formats).
    
    Layout:
        +---------------------------+------------+
        |                           |  Palette   |
        |      Art Editor           |  (colors)  |
        |      (main canvas)        |            |
        |                           +------------+
        +------------------------------------------+
        | Status Bar (info + shortcuts)            |
        +------------------------------------------+
    
    Keyboard Controls:
        Global:
            S: Save file
            Q: Quit (with confirmation if unsaved)
            P: Toggle palette visibility
            I: Enter eyedropper mode
            ?: Toggle help overlay
            
        Editor (when focused):
            Arrow keys / hjkl: Move cursor
            Space / Enter: Draw at cursor
            d: Draw and advance
            x: Erase (transparent)
            1-9: Quick color select
            [ / ]: Cycle colors
            
        Palette (when focused):
            Arrow keys: Navigate swatches
            1-9: Select document color
            a-z: Select saved swatch
            Tab: Switch sections
            E: Edit current color
            +: Add current to saved
            -: Remove from saved
            
        Eyedropper Mode:
            Arrow keys: Move cursor on canvas
            Enter/Space: Pick color
            +: Pick and save to swatches
            Esc/I: Cancel
    """

    def __init__(self, path: Optional[Path] = None) -> None:
        """Initialize the editor.
        
        Args:
            path: Optional file path to load on startup
        """
        self.running = False
        self.input = InputReader()
        
        # Widgets
        self.editor = ArtEditorWidget()
        self.palette = SwatchPaletteWidget()
        self.status_bar = StatusBarWidget()
        
        # Shortcut registry
        self._shortcuts = get_shortcut_registry()
        
        # Document state
        self._document: EditableDocument | None = None
        self._file_path: Path | None = path
        
        # UI state
        self._palette_visible = True
        self._palette_focused = False
        self._eyedropper_mode = False
        self._needs_redraw = True
        self._last_size: tuple[int, int] | None = None
        self._message: str | None = None  # Temporary message for status bar
        
        # Save prompt state
        self._save_prompt_active = False
        self._save_prompt_text = ""
        self._save_prompt_cursor = 0
        
        # Quit confirmation state
        self._quit_confirm_pending = False
        
        # Set up swatches file in user's home directory
        swatches_path = Path.home() / ".config" / "bbs-ansi-art" / "swatches.json"
        self.palette.set_swatches_file(swatches_path)
        
        # Connect widget callbacks
        self._setup_callbacks()
        
        # Load initial file or create new document
        if path and path.exists():
            self._load_file(path)
        else:
            self._new_document()

    def _setup_callbacks(self) -> None:
        """Set up inter-widget communication callbacks."""
        # Sync colors from palette to editor
        def on_palette_color_change(color: tuple[int, int, int]) -> None:
            # Set the RGB color directly on the editor (supports full color range)
            self.editor.set_fg_color_rgb(color)
            self._needs_redraw = True
        
        self.palette.set_on_color_change(on_palette_color_change)
        
        # Eyedropper callbacks
        def on_eyedropper_start() -> None:
            self._eyedropper_mode = True
            self._message = "EYEDROPPER: Move to pick color, Enter=Pick, Esc=Cancel"
            self._needs_redraw = True
        
        def on_eyedropper_end(picked: bool) -> None:
            self._eyedropper_mode = False
            if picked:
                self._message = "Color picked"
            else:
                self._message = "Eyedropper cancelled"
            self._needs_redraw = True
        
        def get_color_at_cursor() -> tuple[int, int, int] | None:
            """Get color at current cursor position."""
            if self._document and self._document.canvas:
                canvas = self._document.canvas
                x, y = self.editor._cursor_x, self.editor._cursor_y
                if hasattr(canvas, 'get_pixel'):
                    pixel = canvas.get_pixel(x, y)
                    if pixel and not pixel.transparent:
                        return (pixel.r, pixel.g, pixel.b)
            return None
        
        self.palette.set_on_eyedropper_start(on_eyedropper_start)
        self.palette.set_on_eyedropper_end(on_eyedropper_end)
        self.palette.set_eyedropper_callback(get_color_at_cursor)
        
        # Sync colors from editor to palette
        def on_editor_color_change(fg_idx: int, bg_idx: int) -> None:
            # Use set_color_from_index to update both color and visual selection
            self.palette.set_color_from_index(fg_idx)
            self._needs_redraw = True
        
        self.editor.on_color_change(on_editor_color_change)
        
        # Track modifications
        def on_modified() -> None:
            self._needs_redraw = True
            # Update document colors in palette
            self._update_document_colors()
        
        self.editor.on_modified(on_modified)

    def _find_closest_color(self, rgb: tuple[int, int, int]) -> int:
        """Find the closest 16-color palette index to an RGB color."""
        r, g, b = rgb
        best_idx = 0
        best_dist = float('inf')
        
        for idx, (pr, pg, pb) in enumerate(ANSI_16_RGB):
            dist = (r - pr) ** 2 + (g - pg) ** 2 + (b - pb) ** 2
            if dist < best_dist:
                best_dist = dist
                best_idx = idx
        
        return best_idx
    
    def _get_color_at_cursor(self) -> tuple[int, int, int] | None:
        """Get color at current cursor position."""
        if self._document and self._document.canvas:
            canvas = self._document.canvas
            x, y = self.editor._cursor_x, self.editor._cursor_y
            if hasattr(canvas, 'get_pixel'):
                pixel = canvas.get_pixel(x, y)
                if pixel and not pixel.transparent:
                    return (pixel.r, pixel.g, pixel.b)
        return None
    
    def _update_document_colors(self) -> None:
        """Update palette with colors from the current document, sorted by frequency."""
        if self._document and self._document.canvas:
            canvas = self._document.canvas
            if hasattr(canvas, '_pixels'):
                # Count color frequencies
                color_counts: dict[tuple[int, int, int], int] = {}
                for row in canvas._pixels:
                    for pixel in row:
                        if pixel and not pixel.transparent:
                            rgb = (pixel.r, pixel.g, pixel.b)
                            color_counts[rgb] = color_counts.get(rgb, 0) + 1
                
                # Sort by frequency (most used first)
                sorted_colors = sorted(color_counts.keys(), key=lambda c: color_counts[c], reverse=True)
                self.palette.set_document_colors(sorted_colors)

    # -------------------------------------------------------------------------
    # Document Management
    # -------------------------------------------------------------------------

    def _new_document(self, width: int = 80, height: int = 50) -> None:
        """Create a new empty document.
        
        Args:
            width: Canvas width in columns
            height: Canvas height in rows (in pixels, so 50 = 25 terminal rows)
        """
        self._document = EditableDocument.new_ans(width, height)
        self._file_path = None
        self.editor.load(self._document.canvas)
        # Sync palette with editor's initial colors
        self.palette.current_color = ANSI_16_RGB[self.editor._fg_index]
        self._update_document_colors()
        self._message = f"New document ({width}x{height})"
        self._needs_redraw = True

    def _load_file(self, path: Path) -> None:
        """Load a file for editing.
        
        Args:
            path: Path to the file to load
        """
        try:
            self._document = EditableDocument.load(path)
            self._file_path = path
            self.editor.load(self._document.canvas)
            
            # Sync palette with editor's initial colors
            self.palette.current_color = ANSI_16_RGB[self.editor._fg_index]
            self._update_document_colors()
            
            self._message = f"Loaded: {path.name}"
        except Exception as e:
            self._message = f"Error loading {path.name}: {e}"
            self._new_document()
        
        self._needs_redraw = True

    def _open_save_prompt(self) -> None:
        """Open the save filename prompt."""
        if self._document is None:
            self._message = "No document to save"
            self._needs_redraw = True
            return
        
        # Pre-populate with current filename or default
        if self._file_path:
            self._save_prompt_text = str(self._file_path)
        else:
            self._save_prompt_text = "untitled.ans"
        self._save_prompt_cursor = len(self._save_prompt_text)
        self._save_prompt_active = True
        self._needs_redraw = True
    
    def _handle_save_prompt_input(self, event: KeyEvent) -> bool:
        """Handle input while save prompt is active."""
        if event.key == Key.ESCAPE:
            # Cancel save
            self._save_prompt_active = False
            self._message = "Save cancelled"
            self._needs_redraw = True
            return True
        
        if event.key == Key.ENTER:
            # Perform save
            self._save_prompt_active = False
            path = Path(self._save_prompt_text.strip())
            if path.name:
                self._save_to_path(path)
            else:
                self._message = "Invalid filename"
            self._needs_redraw = True
            return True
        
        if event.key == Key.BACKSPACE:
            if self._save_prompt_cursor > 0:
                self._save_prompt_text = (
                    self._save_prompt_text[:self._save_prompt_cursor - 1] +
                    self._save_prompt_text[self._save_prompt_cursor:]
                )
                self._save_prompt_cursor -= 1
            self._needs_redraw = True
            return True
        
        if event.key == Key.LEFT:
            if self._save_prompt_cursor > 0:
                self._save_prompt_cursor -= 1
            self._needs_redraw = True
            return True
        
        if event.key == Key.RIGHT:
            if self._save_prompt_cursor < len(self._save_prompt_text):
                self._save_prompt_cursor += 1
            self._needs_redraw = True
            return True
        
        if event.key == Key.HOME:
            self._save_prompt_cursor = 0
            self._needs_redraw = True
            return True
        
        if event.key == Key.END:
            self._save_prompt_cursor = len(self._save_prompt_text)
            self._needs_redraw = True
            return True
        
        # Typing characters
        if event.char and len(event.char) == 1 and event.char.isprintable():
            self._save_prompt_text = (
                self._save_prompt_text[:self._save_prompt_cursor] +
                event.char +
                self._save_prompt_text[self._save_prompt_cursor:]
            )
            self._save_prompt_cursor += 1
            self._needs_redraw = True
            return True
        
        return True  # Consume all input while prompt is active
    
    def _save_to_path(self, path: Path) -> None:
        """Save the document to the specified path."""
        if self._document is None:
            self._message = "No document to save"
            return
        
        try:
            # Resolve to absolute path to avoid saving in wrong directory
            abs_path = path.resolve()
            self._document.save(abs_path)
            self._file_path = abs_path
            self._message = f"Saved: {abs_path}"
        except Exception as e:
            self._message = f"Error saving: {e}"
        
        self._needs_redraw = True

    def _save_as(self, path: Path) -> None:
        """Save the document to a new path.
        
        Args:
            path: New path to save to
        """
        if self._document is None:
            return
        
        try:
            self._document.save(path)
            self._file_path = path
            self._message = f"Saved: {path.name}"
        except Exception as e:
            self._message = f"Error saving: {e}"
        
        self._needs_redraw = True

    # -------------------------------------------------------------------------
    # Main Loop
    # -------------------------------------------------------------------------

    def run(self) -> None:
        """Run the editor main loop."""
        self.running = True
        
        # Initial focus state
        self.editor.focused = True
        self.palette.focused = False
        
        with Terminal.managed_mode():
            Terminal.clear()
            
            while self.running:
                # Check for terminal resize
                size = Terminal.size()
                current_size = (size.cols, size.rows)
                if current_size != self._last_size:
                    self._last_size = current_size
                    self._needs_redraw = True
                
                # Render if needed
                if self._needs_redraw:
                    self._render()
                    self._needs_redraw = False
                
                # Handle input
                self._handle_input()

    # -------------------------------------------------------------------------
    # Input Handling
    # -------------------------------------------------------------------------

    def _handle_input(self) -> None:
        """Process keyboard input."""
        event = self.input.read(timeout=0.1)
        if event is None:
            return
        
        # Handle save prompt input first if active
        if self._save_prompt_active:
            self._handle_save_prompt_input(event)
            return
        
        # Handle quit confirmation
        if self._quit_confirm_pending:
            if event.char == 'q' or event.char == 'Q':
                # Confirmed quit
                self.running = False
                return
            elif event.char == 's' or event.char == 'S':
                # Save instead
                self._quit_confirm_pending = False
                self._open_save_prompt()
                return
            else:
                # Any other key cancels quit
                self._quit_confirm_pending = False
                self._message = None
                self._needs_redraw = True
                # Don't return - let the key be processed normally
        
        # Handle eyedropper mode
        if self._eyedropper_mode:
            if self._handle_eyedropper_input(event):
                return
        
        # Handle color editor if open
        if self.palette.editor_open:
            if self.palette.handle_input(event):
                self._needs_redraw = True
                return
        
        # Global shortcuts (always active)
        if self._handle_global_shortcuts(event):
            return
        
        # Route to focused widget
        if self._palette_focused and self._palette_visible:
            handled = self.palette.handle_input(event)
        else:
            handled = self.editor.handle_input(event)
        
        if handled:
            self._needs_redraw = True
    
    def _handle_eyedropper_input(self, event: KeyEvent) -> bool:
        """Handle input in eyedropper mode."""
        # Navigation - move cursor on canvas
        if event.key == Key.UP or event.char == 'k':
            self.editor.move_cursor(0, -1)
            self._needs_redraw = True
            return True
        if event.key == Key.DOWN or event.char == 'j':
            self.editor.move_cursor(0, 1)
            self._needs_redraw = True
            return True
        if event.key == Key.LEFT or event.char == 'h':
            self.editor.move_cursor(-1, 0)
            self._needs_redraw = True
            return True
        if event.key == Key.RIGHT or event.char == 'l':
            self.editor.move_cursor(1, 0)
            self._needs_redraw = True
            return True
        
        # Pick color
        if event.key == Key.ENTER or event.char == ' ':
            if self.palette.pick_eyedropper_color():
                self.palette.exit_eyedropper(picked=True)
            else:
                self._message = "No color at cursor"
            self._needs_redraw = True
            return True
        
        # Pick and save
        if event.char == '+':
            if self.palette.pick_eyedropper_color():
                self.palette.add_to_saved()
                self.palette.exit_eyedropper(picked=True)
                self._message = "Color picked and saved"
            else:
                self._message = "No color at cursor"
            self._needs_redraw = True
            return True
        
        # Cancel
        if event.key == Key.ESCAPE or event.char == 'i':
            self.palette.exit_eyedropper(picked=False)
            self._needs_redraw = True
            return True
        
        return True  # Consume all input in eyedropper mode

    def _handle_global_shortcuts(self, event: KeyEvent) -> bool:
        """Handle global keyboard shortcuts.
        
        Args:
            event: Key event to process
            
        Returns:
            True if the event was consumed
        """
        # 's' - Open save prompt
        if event.char == 's':
            self._open_save_prompt()
            return True
        
        # 'q' - Quit (always)
        if event.char == 'q':
            self._confirm_quit()
            return True
        
        # Escape - Exit mode first, then quit if no mode active
        if event.key == Key.ESCAPE:
            # Try to exit any active mode in the editor first
            if self.editor.exit_mode():
                self._needs_redraw = True
                return True
            # No mode was active, so quit
            self._confirm_quit()
            return True
        
        # Ctrl+Q - Also quit
        if event.raw == '\x11':  # Ctrl+Q
            self._confirm_quit()
            return True
        
        # Ctrl+N - New document
        if event.raw == '\x0e':  # Ctrl+N
            if self._confirm_discard_changes():
                self._new_document()
            return True
        
        # 'i' - Instant color pick from cursor position
        if event.char == 'i' and not self._palette_focused:
            color = self._get_color_at_cursor()
            if color:
                self.palette.select_color(color)
                # Also update editor's color
                idx = self._find_closest_color(color)
                self.editor.set_fg_color(idx)
                self._message = f"Picked #{color[0]:02X}{color[1]:02X}{color[2]:02X}"
            else:
                self._message = "No color at cursor"
            self._needs_redraw = True
            return True
        
        # 'e' - Open color editor (works from editor or palette)
        if event.char == 'e' and not self._palette_focused:
            self.palette.open_editor()
            self._needs_redraw = True
            return True
        
        # 'p' or 'P' - Toggle palette visibility
        if event.char and event.char.lower() == 'p' and not self._palette_focused:
            self._palette_visible = not self._palette_visible
            self._needs_redraw = True
            return True
        
        # '?' - Toggle help overlay
        if event.char == '?':
            self.editor._show_help = not self.editor._show_help
            self._needs_redraw = True
            return True
        
        # F1 - Help
        if event.key == Key.F1:
            self.editor._show_help = not self.editor._show_help
            self._needs_redraw = True
            return True
        
        # Tab is no longer used for focus switching - it was confusing
        # All shortcuts work directly from the editor now
        
        return False

    def _confirm_quit(self) -> None:
        """Quit with confirmation if there are unsaved changes."""
        if self._document and self._document.is_modified():
            # Show quit confirmation prompt
            self._quit_confirm_pending = True
            self._message = "Unsaved changes! Press Q again to quit, or S to save"
            self._needs_redraw = True
        else:
            self.running = False

    def _confirm_discard_changes(self) -> bool:
        """Check if it's OK to discard unsaved changes.
        
        Returns:
            True if OK to proceed, False to cancel
        """
        if self._document and self._document.is_modified():
            # For now, always allow (a full impl would show a dialog)
            return True
        return True

    def _show_help(self) -> None:
        """Show help screen (placeholder)."""
        self._message = "Help: Arrow=Move, Space=Draw, P=Palette, Q=Quit"
        self._needs_redraw = True

    # -------------------------------------------------------------------------
    # Rendering
    # -------------------------------------------------------------------------

    def _render(self) -> None:
        """Render all widgets to the screen."""
        size = Terminal.size()
        
        # Calculate layout
        palette_width = PALETTE_WIDTH if self._palette_visible else 0
        editor_width = max(MIN_EDITOR_WIDTH, size.cols - palette_width - 1)  # -1 for separator
        content_height = size.rows - STATUS_BAR_HEIGHT
        
        # If terminal is too small, adjust
        if editor_width + palette_width + 1 > size.cols:
            palette_width = max(0, size.cols - MIN_EDITOR_WIDTH - 1)
            editor_width = size.cols - palette_width - (1 if palette_width > 0 else 0)
        
        # Render widgets
        output_lines: list[str] = []
        
        # Editor bounds
        editor_bounds = Rect(0, 0, editor_width, content_height)
        editor_lines = self.editor.render(editor_bounds)
        
        # Palette bounds (if visible)
        palette_lines: list[str] = []
        if self._palette_visible and palette_width > 0:
            palette_bounds = Rect(0, 0, palette_width, content_height)
            palette_lines = self.palette.render(palette_bounds)
        
        # Compose each row: editor | separator | palette
        for y in range(content_height):
            editor_line = editor_lines[y] if y < len(editor_lines) else ""
            
            # Ensure editor line has exact width
            editor_line = pad_to_width(truncate(editor_line, editor_width), editor_width)
            
            if self._palette_visible and palette_width > 0:
                palette_line = palette_lines[y] if y < len(palette_lines) else ""
                palette_line = truncate(palette_line, palette_width)
                
                # Separator character
                sep = "\x1b[90m\u2502\x1b[0m"
                combined = f"{editor_line}{sep}{palette_line}\x1b[K"
            else:
                combined = f"{editor_line}\x1b[K"
            
            output_lines.append(combined)
        
        # Overlay help modal at the FULL SCREEN level (after composition)
        if self.editor._show_help:
            output_lines = self._overlay_help_fullscreen(output_lines, size.cols, content_height)
        
        # Update and render status bar (or save prompt)
        if self._save_prompt_active:
            # Show save prompt instead of status bar
            prompt_line = self._render_save_prompt(size.cols)
            output_lines.append(prompt_line)
        else:
            self._update_status_bar()
            status_bounds = Rect(0, 0, size.cols, STATUS_BAR_HEIGHT)
            status_lines = self.status_bar.render(status_bounds)
            output_lines.extend(status_lines)
        
        # Output all at once to minimize flicker
        Terminal.move_to(1, 1)
        sys.stdout.write('\r\n'.join(output_lines))
        sys.stdout.flush()
        
        # Clear temporary message after display
        self._message = None
    
    def _render_save_prompt(self, width: int) -> str:
        """Render the save filename prompt."""
        prompt = "Save as: "
        text = self._save_prompt_text
        cursor_pos = self._save_prompt_cursor
        
        # Use TRUE COLOR to override any terminal theme
        # Dark blue background (30, 60, 120), bright white text (255, 255, 255)
        style = "\x1b[38;2;255;255;255m\x1b[48;2;30;60;120m"
        cursor_style = "\x1b[38;2;0;0;0m\x1b[48;2;255;255;100m"
        reset = "\x1b[0m"
        
        # Build the prompt with cursor
        before_cursor = text[:cursor_pos]
        cursor_char = text[cursor_pos] if cursor_pos < len(text) else " "
        after_cursor = text[cursor_pos + 1:] if cursor_pos < len(text) else ""
        
        # Calculate visible width exactly:
        # " Save as: " (10) + text + cursor(1) + "  " (2) + hint + " " (1)
        hint = "[Enter] [Esc]"  # Shorter hint
        fixed_chars = 1 + len(prompt) + 1 + 2 + len(hint) + 1  # = 1+9+1+2+13+1 = 27
        max_text_len = width - fixed_chars - 2  # Safety margin
        
        # Truncate filename if needed to fit
        if len(text) > max_text_len and max_text_len > 10:
            # Truncate with ellipsis at start (show end of path)
            text = "…" + text[-(max_text_len - 1):]
            before_cursor = text[:min(cursor_pos, len(text) - 1)]
            cursor_char = text[min(cursor_pos, len(text) - 1)] if text else " "
            after_cursor = text[min(cursor_pos, len(text) - 1) + 1:] if cursor_pos < len(text) else ""
        
        # Calculate padding to fill exact width
        visible_used = 1 + len(prompt) + len(text) + 1 + 2 + len(hint) + 1
        padding_needed = max(0, width - visible_used - 1)
        
        # Construct the line - use exact width, no overflow
        text_display = f"{before_cursor}{cursor_style}{cursor_char}{style}{after_cursor}"
        padding = " " * padding_needed
        line = f"{style} {prompt}{text_display}  {padding}{hint} {reset}"
        
        return line
    
    def _ansi_slice(self, s: str, start: int, end: int) -> str:
        """Slice a string by visual position, preserving ANSI escape codes.
        
        Args:
            s: String potentially containing ANSI escape codes
            start: Visual start position (inclusive)
            end: Visual end position (exclusive)
            
        Returns:
            Substring from visual position start to end, with ANSI codes intact
        """
        import re
        # Pattern matches ANSI escape sequences
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        
        result = []
        visual_pos = 0
        i = 0
        active_codes = []  # Track active ANSI codes to reapply
        
        while i < len(s):
            # Check for ANSI escape sequence
            match = ansi_pattern.match(s, i)
            if match:
                code = match.group()
                # Track the code (reset clears all)
                if code == '\x1b[0m':
                    active_codes = []
                else:
                    active_codes.append(code)
                # Include codes that appear before or within our slice
                if visual_pos <= end:
                    if visual_pos >= start or (result and visual_pos < start):
                        pass  # Will be handled below
                    if visual_pos < start:
                        pass  # Keep tracking but don't add yet
                    else:
                        result.append(code)
                i = match.end()
            else:
                # Regular character
                if start <= visual_pos < end:
                    # First char? Prepend active codes
                    if not result and active_codes:
                        result.extend(active_codes)
                    result.append(s[i])
                visual_pos += 1
                i += 1
                
                if visual_pos >= end:
                    break
        
        return ''.join(result)

    def _ansi_visual_len(self, s: str) -> int:
        """Get visual length of string (excluding ANSI codes)."""
        import re
        return len(re.sub(r'\x1b\[[0-9;]*m', '', s))

    def _overlay_help_fullscreen(self, lines: list[str], width: int, height: int) -> list[str]:
        """Overlay help modal centered on full screen.
        
        This renders the help at the full-screen level after composition,
        so it displays correctly over editor + palette.
        """
        # Style: bold white on dark gray background
        style = "\x1b[1;97;48;5;236m"
        reset = "\x1b[0m"
        
        help_content = [
            "╭───────────────────────────────────────╮",
            "│         EDITOR HELP  (? to close)     │",
            "├───────────────────────────────────────┤",
            "│  NAVIGATION                           │",
            "│    Arrow keys / hjkl    Move cursor   │",
            "│    Shift+Arrow          Move fast     │",
            "│    Home / End           Line start    │",
            "│    PgUp / PgDn          Scroll page   │",
            "│                                       │",
            "│  DRAWING                              │",
            "│    d                    Draw pixel    │",
            "│    D                    Draw mode     │",
            "│    x                    Erase pixel   │",
            "│    X                    Erase mode    │",
            "│    Esc                  Exit mode     │",
            "│                                       │",
            "│  COLORS                               │",
            "│    i                    Pick color    │",
            "│    [ / ]                Cycle color   │",
            "│    p                    Palette       │",
            "│                                       │",
            "│  FILE                                 │",
            "│    s                    Save          │",
            "│    q                    Quit          │",
            "╰───────────────────────────────────────╯",
        ]
        
        # Calculate centered position
        help_width = 41  # Width of the box
        help_height = len(help_content)
        
        start_x = max(0, (width - help_width) // 2)
        start_y = max(0, (height - help_height) // 2)
        
        result = list(lines)
        
        # Ensure we have enough lines
        while len(result) < height:
            result.append(" " * width)
        
        for i, help_line in enumerate(help_content):
            line_y = start_y + i
            if 0 <= line_y < len(result):
                existing = result[line_y]
                
                # Get content before and after the modal using ANSI-aware slicing
                before = self._ansi_slice(existing, 0, start_x)
                after_start = start_x + help_width
                after = self._ansi_slice(existing, after_start, width)
                
                # Pad 'before' if it's visually shorter than start_x
                before_visual_len = self._ansi_visual_len(before)
                if before_visual_len < start_x:
                    before = before + " " * (start_x - before_visual_len)
                
                # Compose: before + styled help + reset + after
                result[line_y] = f"{before}{style}{help_line}{reset}{after}"
        
        return result

    def _update_status_bar(self) -> None:
        """Update status bar content based on current state."""
        shortcuts: list[Shortcut] = []
        
        if self._eyedropper_mode:
            # Eyedropper mode shortcuts
            shortcuts.append(Shortcut("↑↓←→", "Move"))
            shortcuts.append(Shortcut("Enter", "Pick"))
            shortcuts.append(Shortcut("+", "Pick+Save"))
            shortcuts.append(Shortcut("Esc", "Cancel"))
        else:
            # Normal mode shortcuts
            shortcuts.append(Shortcut("↑↓←→", "Move"))
            shortcuts.append(Shortcut("d", "Draw"))
            shortcuts.append(Shortcut("x", "Erase"))
            shortcuts.append(Shortcut("[]", "Color"))
            shortcuts.append(Shortcut("i", "Pick color"))
            
            if self._palette_visible:
                shortcuts.append(Shortcut("p", "Hide palette"))
            else:
                shortcuts.append(Shortcut("p", "Show palette"))
            
            shortcuts.append(Shortcut("s", "Save"))
            shortcuts.append(Shortcut("?", "Help"))
        
        self.status_bar.set_shortcuts(shortcuts)
        
        # Left: temporary message or editor status
        if self._message:
            self.status_bar.set_left(self._message)
            # Clear center when showing a message to avoid stale content
            self.status_bar.set_center("")
        else:
            status = self.editor.get_status()
            # Add modified indicator
            if self._document and self._document.is_modified():
                status = "[*] " + status
            
            # Add mode indicator with high contrast (unified for all modes)
            active_mode = self.editor.active_mode
            if self._eyedropper_mode:
                # High contrast: black on yellow
                status = "\x1b[1;30;103m PICK \x1b[0m\x1b[100;97m " + status
            elif active_mode:
                # High contrast: black on bright color (green for draw, red for erase)
                if active_mode == "DRAW":
                    status = "\x1b[1;30;102m DRAW \x1b[22;90m[Esc]\x1b[0m\x1b[100;97m " + status
                elif active_mode == "ERASE":
                    status = "\x1b[1;30;101m ERASE \x1b[22;90m[Esc]\x1b[0m\x1b[100;97m " + status
            
            self.status_bar.set_left(status)
            
            # Center: filename and focus indicator (only when no message)
            center_parts: list[str] = []
            if self._file_path:
                center_parts.append(self._file_path.name)
            else:
                center_parts.append("(untitled)")
            
            # Show focus indicator
            if self._eyedropper_mode:
                center_parts.append("[PICK]")
            elif self._palette_focused:
                center_parts.append("[PALETTE]")
            else:
                center_parts.append("[EDITOR]")
            
            self.status_bar.set_center(" ".join(center_parts))


def run_editor(path: Optional[Path] = None) -> None:
    """Launch the editor application.
    
    Args:
        path: Optional file path to open
    """
    app = EditorApp(path)
    app.run()


if __name__ == "__main__":
    file_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_editor(file_path)
