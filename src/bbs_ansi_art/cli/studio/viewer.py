"""Interactive studio viewer for ANSI art files."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional

import bbs_ansi_art as ansi
from bbs_ansi_art.cli.core.terminal import Terminal
from bbs_ansi_art.cli.core.input import InputReader, Key
from bbs_ansi_art.cli.core.layout import LayoutManager, LayoutMode
from bbs_ansi_art.cli.widgets.base import Rect
from bbs_ansi_art.cli.widgets.file_list import FileListWidget, FileItem
from bbs_ansi_art.cli.widgets.art_canvas import ArtCanvasWidget
from bbs_ansi_art.cli.widgets.status_bar import StatusBarWidget, Shortcut


def _visible_len(s: str) -> int:
    """Get visible length of string (excluding ANSI codes)."""
    return len(re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', s))


class ViewerApp:
    """
    Interactive ANSI art viewer with responsive layout.
    
    Layout modes:
    - NARROW (<80): Art only, truncated
    - COMPACT (80-99): Art only, full width
    - SPLIT (100-139): Browser + Art side by side
    - WIDE (140+): Comfortable spacing
    
    Keyboard:
    - Tab: Switch focus between panels
    - b: Toggle browser panel visibility
    - q/Esc: Quit
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
            on_open=self._on_file_open,
        )
        self.art_canvas = ArtCanvasWidget()
        self.status_bar = StatusBarWidget()
        
        # State
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
        
        with Terminal.managed_mode():
            while self.running:
                self._render()
                self._handle_input()

    def _render(self) -> None:
        """Render the full screen with responsive layout."""
        size = Terminal.size()
        layout = self.layout_mgr.calculate(size.cols, size.rows)
        
        # Update widget focus states
        self.file_list.focused = self.layout_mgr.browser_focused
        self.art_canvas.focused = self.layout_mgr.art_focused
        
        Terminal.clear()
        
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
                
                # Pad file line to exact width
                file_vis_len = _visible_len(file_line)
                if file_vis_len < layout.browser_width:
                    file_line += " " * (layout.browser_width - file_vis_len)
                
                # Separator
                sep = "\x1b[90m│\x1b[0m"
                
                # Truncate combined line to terminal width
                combined = f"{file_line}{sep}{art_line}"
                output_lines.append(combined)
        else:
            # Art-only layout
            art_bounds = Rect(0, 0, layout.art_width, layout.art_height)
            art_lines = self._render_art_panel(art_bounds)
            output_lines.extend(art_lines)
        
        # Render status bar
        self._update_status_bar(layout)
        status_bounds = Rect(0, 0, layout.term_width, 1)
        status_lines = self.status_bar.render(status_bounds)
        output_lines.extend(status_lines)
        
        # Output everything
        Terminal.move_to(1, 1)
        sys.stdout.write('\n'.join(output_lines))
        sys.stdout.flush()

    def _render_art_panel(self, bounds: Rect) -> list[str]:
        """Render art or SAUCE info panel."""
        if self._show_sauce and self.art_canvas.document:
            return self._render_sauce_info(bounds)
        return self.art_canvas.render(bounds)

    def _render_sauce_info(self, bounds: Rect) -> list[str]:
        """Render SAUCE metadata panel."""
        lines: list[str] = []
        doc = self.art_canvas.document
        
        if not doc or not doc.sauce:
            lines.append("\x1b[33mNo SAUCE metadata\x1b[0m")
        else:
            s = doc.sauce
            lines.append(f"\x1b[1;36m{'═' * min(40, bounds.width)}\x1b[0m")
            lines.append(f"\x1b[1;36m  SAUCE Metadata\x1b[0m")
            lines.append(f"\x1b[1;36m{'═' * min(40, bounds.width)}\x1b[0m")
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
        
        # Toggle browser (b key)
        if event.char == 'b':
            self.layout_mgr.toggle_browser()
            return
        
        # Toggle SAUCE info
        if event.char == 's':
            self._show_sauce = not self._show_sauce
            return
        
        # Switch focus (Tab)
        if event.key == Key.TAB:
            self.layout_mgr.cycle_focus()
            return
        
        # Route to focused widget
        if self.layout_mgr.browser_focused and self.layout_mgr.layout and self.layout_mgr.layout.browser_visible:
            self.file_list.handle_input(event)
        else:
            self.art_canvas.handle_input(event)

    def _on_file_select(self, item: FileItem) -> None:
        """Called when file selection changes."""
        if not item.is_dir:
            self._load_file(item.path)

    def _on_file_open(self, item: FileItem) -> None:
        """Called when file is opened (Enter pressed)."""
        if not item.is_dir:
            self._load_file(item.path)

    def _load_file(self, path: Path) -> None:
        """Load an ANSI file into the viewer."""
        try:
            doc = ansi.load(path)
            self.art_canvas.load(doc)
            self._current_file = path
            self._show_sauce = False
            # Update layout manager with art width
            if doc.canvas:
                self.layout_mgr.set_art_width(doc.canvas.width)
        except Exception:
            self.art_canvas.clear()
            self._current_file = None

    def _update_status_bar(self, layout) -> None:
        """Update status bar based on current state and layout."""
        shortcuts: list[Shortcut] = []
        
        # Context-aware shortcuts based on layout mode
        if layout.browser_visible:
            if self.layout_mgr.browser_focused:
                shortcuts.append(Shortcut("↑↓", "Nav"))
                shortcuts.append(Shortcut("Enter", "Open"))
                shortcuts.append(Shortcut("←", "Up"))
            else:
                shortcuts.append(Shortcut("↑↓", "Scroll"))
            shortcuts.append(Shortcut("Tab", "Switch"))
            shortcuts.append(Shortcut("b", "Hide"))
        else:
            shortcuts.append(Shortcut("↑↓", "Scroll"))
            if layout.mode in (LayoutMode.SPLIT, LayoutMode.WIDE):
                shortcuts.append(Shortcut("b", "Browser"))
        
        shortcuts.append(Shortcut("s", "Info" if not self._show_sauce else "Art"))
        shortcuts.append(Shortcut("q", "Quit"))
        
        self.status_bar.set_shortcuts(shortcuts)
        
        # Left text: filename
        if self._current_file:
            self.status_bar.set_left(self._current_file.name)
        else:
            self.status_bar.set_left("")
        
        # Center text: art info
        if self.art_canvas.document and not self._show_sauce:
            total = self.art_canvas.total_lines
            pct = self.art_canvas.scroll_percent
            mode_indicator = f"[{layout.mode.value}]" if layout.mode != LayoutMode.WIDE else ""
            self.status_bar.set_center(f"{total}L {pct:.0f}% {mode_indicator}")
        else:
            self.status_bar.set_center("")


def run_viewer(path: Optional[Path] = None) -> None:
    """Launch the viewer application."""
    app = ViewerApp(path)
    app.run()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    run_viewer(path)
