"""Interactive studio viewer for ANSI art files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import bbs_ansi_art as ansi
from bbs_ansi_art.cli.core.terminal import Terminal, TerminalSize
from bbs_ansi_art.cli.core.input import InputReader, Key, KeyEvent
from bbs_ansi_art.cli.widgets.base import Rect
from bbs_ansi_art.cli.widgets.file_list import FileListWidget, FileItem
from bbs_ansi_art.cli.widgets.art_canvas import ArtCanvasWidget
from bbs_ansi_art.cli.widgets.status_bar import StatusBarWidget, Shortcut


class ViewerApp:
    """
    Interactive ANSI art viewer with file browser.
    
    Features:
    - File browser with directory navigation
    - Scrollable art display
    - SAUCE metadata viewing
    - Keyboard navigation (vim-style and arrows)
    """

    def __init__(self, initial_path: Optional[Path] = None) -> None:
        self.running = False
        self.initial_path = initial_path
        
        # Input handling
        self.input = InputReader()
        
        # Widgets
        self.file_list = FileListWidget(
            on_select=self._on_file_select,
            on_open=self._on_file_open,
        )
        self.art_canvas = ArtCanvasWidget()
        self.status_bar = StatusBarWidget()
        
        # State
        self._focus_file_list = True  # True = file list, False = art canvas
        self._show_sauce = False
        self._current_file: Optional[Path] = None

    def run(self) -> None:
        """Main application loop."""
        self.running = True
        
        # Initialize file list
        if self.initial_path:
            path = self.initial_path.resolve()
            if path.is_file():
                self.file_list.load_directory(path.parent)
                self._load_file(path)
            elif path.is_dir():
                self.file_list.load_directory(path)
        else:
            self.file_list.load_directory(Path.cwd())
        
        # Set initial focus
        self.file_list.focused = True
        self.art_canvas.focused = False
        
        # Update shortcuts
        self._update_shortcuts()
        
        with Terminal.managed_mode():
            while self.running:
                self._render()
                self._handle_input()

    def _render(self) -> None:
        """Render the full screen."""
        size = Terminal.size()
        Terminal.clear()
        
        # Layout: file list on left (30 cols), art on right, status at bottom
        file_list_width = min(35, size.cols // 3)
        art_width = size.cols - file_list_width - 1  # -1 for separator
        content_height = size.rows - 1  # -1 for status bar
        
        # Render file list
        file_bounds = Rect(0, 0, file_list_width, content_height)
        file_lines = self.file_list.render(file_bounds)
        
        # Render art canvas
        art_bounds = Rect(file_list_width + 1, 0, art_width, content_height)
        if self._show_sauce and self.art_canvas.document:
            art_lines = self._render_sauce_info(art_bounds)
        else:
            art_lines = self.art_canvas.render(art_bounds)
        
        # Compose screen
        output_lines = []
        for y in range(content_height):
            file_line = file_lines[y] if y < len(file_lines) else ""
            art_line = art_lines[y] if y < len(art_lines) else ""
            
            # Pad file line to width
            import re
            def visible_len(s: str) -> int:
                return len(re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', s))
            
            file_visible_len = visible_len(file_line)
            if file_visible_len < file_list_width:
                file_line += " " * (file_list_width - file_visible_len)
            
            # Separator
            sep = "\x1b[90m│\x1b[0m"
            
            output_lines.append(f"{file_line}{sep}{art_line}")
        
        # Render status bar
        status_bounds = Rect(0, size.rows - 1, size.cols, 1)
        self._update_status()
        status_lines = self.status_bar.render(status_bounds)
        output_lines.extend(status_lines)
        
        # Output
        Terminal.move_to(1, 1)
        sys.stdout.write('\n'.join(output_lines))
        sys.stdout.flush()

    def _render_sauce_info(self, bounds: Rect) -> list[str]:
        """Render SAUCE metadata panel."""
        lines: list[str] = []
        doc = self.art_canvas.document
        
        if not doc or not doc.sauce:
            lines.append("\x1b[33mNo SAUCE metadata\x1b[0m")
        else:
            s = doc.sauce
            lines.append(f"\x1b[1;36m{'═' * 40}\x1b[0m")
            lines.append(f"\x1b[1;36m  SAUCE Metadata\x1b[0m")
            lines.append(f"\x1b[1;36m{'═' * 40}\x1b[0m")
            lines.append("")
            lines.append(f"\x1b[1mTitle:\x1b[0m  {s.title or '(none)'}")
            lines.append(f"\x1b[1mAuthor:\x1b[0m {s.author or '(none)'}")
            lines.append(f"\x1b[1mGroup:\x1b[0m  {s.group or '(none)'}")
            if s.date:
                lines.append(f"\x1b[1mDate:\x1b[0m   {s.date.strftime('%Y-%m-%d')}")
            lines.append(f"\x1b[1mSize:\x1b[0m   {s.tinfo1}x{s.tinfo2}")
            
            if s.comments:
                lines.append("")
                lines.append(f"\x1b[1mComments:\x1b[0m")
                for comment in s.comments:
                    lines.append(f"  {comment}")
        
        # Pad to height
        while len(lines) < bounds.height:
            lines.append("")
        
        return lines[:bounds.height]

    def _handle_input(self) -> None:
        """Handle keyboard input."""
        event = self.input.read(timeout=0.05)
        if event is None:
            return
        
        # Global shortcuts
        if event.char == 'q':
            self.running = False
            return
        
        if event.key == Key.ESCAPE:
            if self._show_sauce:
                self._show_sauce = False
            else:
                self.running = False
            return
        
        if event.char == 's':
            self._show_sauce = not self._show_sauce
            self._update_shortcuts()
            return
        
        if event.key == Key.TAB:
            self._toggle_focus()
            return
        
        # Route to focused widget
        if self._focus_file_list:
            self.file_list.handle_input(event)
        else:
            self.art_canvas.handle_input(event)

    def _toggle_focus(self) -> None:
        """Toggle focus between file list and art canvas."""
        self._focus_file_list = not self._focus_file_list
        self.file_list.focused = self._focus_file_list
        self.art_canvas.focused = not self._focus_file_list
        self._update_shortcuts()

    def _on_file_select(self, item: FileItem) -> None:
        """Called when file selection changes."""
        if not item.is_dir:
            self._load_file(item.path)

    def _on_file_open(self, item: FileItem) -> None:
        """Called when file is opened (Enter pressed)."""
        if not item.is_dir:
            self._load_file(item.path)
            # Optionally switch focus to canvas
            # self._toggle_focus()

    def _load_file(self, path: Path) -> None:
        """Load an ANSI file into the viewer."""
        try:
            doc = ansi.load(path)
            self.art_canvas.load(doc)
            self._current_file = path
            self._show_sauce = False
        except Exception as e:
            # Could show error in status bar
            self.art_canvas.clear()
            self._current_file = None

    def _update_shortcuts(self) -> None:
        """Update status bar shortcuts based on current state."""
        shortcuts = [
            Shortcut("Tab", "Switch"),
            Shortcut("↑↓", "Navigate"),
        ]
        
        if not self._focus_file_list:
            shortcuts.append(Shortcut("PgUp/Dn", "Scroll"))
        
        if self._show_sauce:
            shortcuts.append(Shortcut("s", "Hide SAUCE"))
        else:
            shortcuts.append(Shortcut("s", "SAUCE"))
        
        shortcuts.append(Shortcut("q", "Quit"))
        
        self.status_bar.set_shortcuts(shortcuts)

    def _update_status(self) -> None:
        """Update status bar text."""
        if self._current_file:
            self.status_bar.set_left(self._current_file.name)
        else:
            self.status_bar.set_left("")
        
        if self.art_canvas.document and not self._show_sauce:
            total = self.art_canvas.total_lines
            pct = self.art_canvas.scroll_percent
            self.status_bar.set_center(f"{total} lines ({pct:.0f}%)")
        else:
            self.status_bar.set_center("")


def run_viewer(path: Optional[Path] = None) -> None:
    """Launch the viewer application."""
    app = ViewerApp(path)
    app.run()


if __name__ == "__main__":
    # Allow running directly: python -m bbs_ansi_art.cli.studio.viewer [path]
    import sys
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_viewer(path)
