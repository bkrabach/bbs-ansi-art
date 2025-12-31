"""Interactive studio viewer for ANSI art files."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

import bbs_ansi_art as ansi
from bbs_ansi_art.cli.core.terminal import Terminal
from bbs_ansi_art.cli.core.input import InputReader, Key
from bbs_ansi_art.cli.core.layout import LayoutManager, LayoutMode
from bbs_ansi_art.cli.core.ansi_text import visible_len, truncate, pad_to_width
from bbs_ansi_art.cli.widgets.base import Rect
from bbs_ansi_art.cli.widgets.file_list import FileListWidget, FileItem
from bbs_ansi_art.cli.widgets.art_canvas import ArtCanvasWidget
from bbs_ansi_art.cli.widgets.status_bar import StatusBarWidget, Shortcut


class ViewerApp:
    """
    Interactive ANSI art viewer.
    
    Simple design:
    - Arrow keys navigate file browser
    - Preview updates automatically on selection
    - Commands: s=SAUCE info, b=toggle browser, q=quit
    """

    def __init__(self, initial_path: Optional[Path] = None) -> None:
        self.running = False
        self.initial_path = initial_path
        
        # Input handling
        self.input = InputReader()
        
        # Layout manager
        self.layout_mgr = LayoutManager()
        
        # Widgets
        self.file_list = FileListWidget(
            on_select=self._on_file_select,
        )
        self.file_list.focused = True  # Always focused
        self.art_canvas = ArtCanvasWidget()
        self.status_bar = StatusBarWidget()
        
        # State
        self._show_sauce = False
        self._current_file: Optional[Path] = None
        self._load_error: Optional[str] = None

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
        
        with Terminal.managed_mode():
            while self.running:
                self._render()
                self._handle_input()

    def _render(self) -> None:
        """Render the full screen without flicker."""
        size = Terminal.size()
        layout = self.layout_mgr.calculate(size.cols, size.rows)
        
        # Move to home instead of clearing - prevents flicker
        # Each line ends with \x1b[K to clear any leftover content
        Terminal.move_to(1, 1)
        
        output_lines: list[str] = []
        
        if layout.browser_visible:
            # Split layout: browser | separator | art
            file_bounds = Rect(0, 0, layout.browser_width, layout.browser_height)
            file_lines = self.file_list.render(file_bounds)
            
            art_bounds = Rect(0, 0, layout.art_width, layout.art_height)
            art_lines = self._render_art_panel(art_bounds)
            
            # Compose each row
            for y in range(layout.content_height):
                file_line = file_lines[y] if y < len(file_lines) else ""
                art_line = art_lines[y] if y < len(art_lines) else ""
                
                # Ensure exact widths
                file_line = pad_to_width(truncate(file_line, layout.browser_width), layout.browser_width)
                art_line = truncate(art_line, layout.art_width)
                
                sep = "\x1b[90m│\x1b[0m"
                combined = f"{file_line}{sep}{art_line}\x1b[K"
                output_lines.append(combined)
        else:
            # Art-only layout
            art_bounds = Rect(0, 0, layout.art_width, layout.art_height)
            art_lines = self._render_art_panel(art_bounds)
            for line in art_lines:
                output_lines.append(truncate(line, layout.art_width) + "\x1b[K")
        
        # Render status bar
        self._update_status_bar(layout)
        status_bounds = Rect(0, 0, layout.term_width, 1)
        status_lines = self.status_bar.render(status_bounds)
        for line in status_lines:
            output_lines.append(truncate(line, layout.term_width))
        
        # Output
        Terminal.move_to(1, 1)
        sys.stdout.write('\r\n'.join(output_lines))
        sys.stdout.flush()

    def _render_art_panel(self, bounds: Rect) -> list[str]:
        """Render art, SAUCE info, or error message."""
        if self._load_error:
            return self._render_error(bounds)
        if self._show_sauce and self.art_canvas.document:
            return self._render_sauce_info(bounds)
        return self.art_canvas.render(bounds)

    def _render_error(self, bounds: Rect) -> list[str]:
        """Render error message panel."""
        lines: list[str] = []
        lines.append("")
        lines.append(f"\x1b[1;31m  Error loading file:\x1b[0m")
        lines.append(f"\x1b[31m  {self._load_error}\x1b[0m")
        lines.append("")
        lines.append("\x1b[90m  The file may be corrupted or in an unsupported format.\x1b[0m")
        
        while len(lines) < bounds.height:
            lines.append("")
        return lines[:bounds.height]

    def _render_sauce_info(self, bounds: Rect) -> list[str]:
        """Render SAUCE metadata panel."""
        lines: list[str] = []
        doc = self.art_canvas.document
        
        if not doc or not doc.sauce:
            lines.append("\x1b[33mNo SAUCE metadata\x1b[0m")
        else:
            s = doc.sauce
            bar_width = min(40, bounds.width)
            lines.append(f"\x1b[1;36m{'═' * bar_width}\x1b[0m")
            lines.append(f"\x1b[1;36m  SAUCE Metadata\x1b[0m")
            lines.append(f"\x1b[1;36m{'═' * bar_width}\x1b[0m")
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
        
        while len(lines) < bounds.height:
            lines.append("")
        
        return lines[:bounds.height]

    def _handle_input(self) -> None:
        """Handle keyboard input."""
        event = self.input.read(timeout=0.05)
        if event is None:
            return
        
        # Quit
        if event.char == 'q' or event.key == Key.ESCAPE:
            self.running = False
            return
        
        # Toggle browser visibility
        if event.char == 'b':
            self.layout_mgr.toggle_browser()
            return
        
        # Toggle SAUCE info
        if event.char == 's':
            self._show_sauce = not self._show_sauce
            return
        
        # All other input goes to file browser
        self.file_list.handle_input(event)

    def _on_file_select(self, item: FileItem) -> None:
        """Called when file selection changes - load preview."""
        if not item.is_dir:
            self._load_file(item.path)
        else:
            # Clear preview when on a directory
            self.art_canvas.clear()
            self._current_file = None
            self._show_sauce = False

    def _load_file(self, path: Path) -> None:
        """Load an ANSI file for preview."""
        try:
            doc = ansi.load(path)
            self.art_canvas.load(doc)
            self._current_file = path
            self._load_error = None
            self._show_sauce = False
            if doc.canvas:
                self.layout_mgr.set_art_width(doc.canvas.width)
        except Exception as e:
            self.art_canvas.clear()
            self._current_file = path  # Keep filename for error display
            self._load_error = str(e) or type(e).__name__

    def _update_status_bar(self, layout) -> None:
        """Update status bar."""
        shortcuts: list[Shortcut] = []
        
        shortcuts.append(Shortcut("↑↓", "Navigate"))
        shortcuts.append(Shortcut("⏎", "Enter dir"))
        
        if layout.browser_visible:
            shortcuts.append(Shortcut("b", "Hide browser"))
        else:
            shortcuts.append(Shortcut("b", "Show browser"))
        
        if self._show_sauce:
            shortcuts.append(Shortcut("s", "Show art"))
        else:
            shortcuts.append(Shortcut("s", "SAUCE info"))
        
        shortcuts.append(Shortcut("q", "Quit"))
        
        self.status_bar.set_shortcuts(shortcuts)
        
        # Left: current file
        if self._current_file:
            self.status_bar.set_left(self._current_file.name)
        else:
            self.status_bar.set_left("")
        
        # Center: directory info
        dir_path = self.file_list.current_directory
        self.status_bar.set_center(str(dir_path))


def run_viewer(path: Optional[Path] = None) -> None:
    """Launch the viewer application."""
    app = ViewerApp(path)
    app.run()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_viewer(path)
