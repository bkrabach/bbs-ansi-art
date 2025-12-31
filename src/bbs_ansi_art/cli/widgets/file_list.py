"""Scrollable file browser widget with directory tree navigation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from bbs_ansi_art.cli.core.input import Key, KeyEvent
from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect


@dataclass
class FileItem:
    """Represents a file or directory in the list."""
    path: Path
    name: str
    is_dir: bool
    size: int = 0

    @classmethod
    def from_path(cls, path: Path) -> FileItem:
        try:
            size = path.stat().st_size if path.is_file() else 0
        except OSError:
            size = 0
        return cls(
            path=path,
            name=path.name,
            is_dir=path.is_dir(),
            size=size,
        )


class FileListWidget(BaseWidget):
    """
    Scrollable file browser with full directory tree navigation.
    
    Keyboard shortcuts:
        Navigation:
            ↑/k         Move selection up
            ↓/j         Move selection down
            PgUp/PgDn   Page up/down
            Home/End    Jump to first/last
        
        Directory:
            Enter/l/→   Enter directory / open file
            Backspace/h/← Go up to parent directory
            ~           Go to home directory
            /           Go to root directory
            .           Toggle hidden files
        
        Selection:
            Space       Select/deselect for batch operations
    """

    EXTENSIONS = {'.ans', '.asc', '.diz', '.nfo', '.txt'}

    def __init__(
        self,
        extensions: Optional[set[str]] = None,
        on_select: Optional[Callable[[FileItem], None]] = None,
        on_open: Optional[Callable[[FileItem], None]] = None,
        on_directory_change: Optional[Callable[[Path], None]] = None,
        show_hidden: bool = False,
    ):
        super().__init__()
        self.extensions = extensions or self.EXTENSIONS
        self.on_select = on_select
        self.on_open = on_open
        self.on_directory_change = on_directory_change
        self.show_hidden = show_hidden

        self._items: list[FileItem] = []
        self._selected: int = 0
        self._scroll_offset: int = 0
        self._current_dir: Path = Path.cwd()
        self._default_visible_height: int = 20  # Default, actual height comes from render bounds
        self._history: list[Path] = []  # For potential back/forward navigation
        self._dir_count: int = 0
        self._file_count: int = 0

    def load_directory(self, path: Path, push_history: bool = True) -> None:
        """Load files from directory."""
        new_dir = path.resolve()
        
        # Don't reload if same directory
        if new_dir == self._current_dir and self._items:
            return
        
        # Push to history for back navigation
        if push_history and self._current_dir != new_dir:
            self._history.append(self._current_dir)
            # Limit history size
            if len(self._history) > 50:
                self._history.pop(0)
        
        self._current_dir = new_dir
        self._refresh_items()
        
        # Fire directory change callback
        if self.on_directory_change:
            self.on_directory_change(self._current_dir)

    def _refresh_items(self) -> None:
        """Refresh the file list for current directory."""
        self._items = []
        self._dir_count = 0
        self._file_count = 0

        # Add parent directory navigation (unless at root)
        if self._current_dir.parent != self._current_dir:
            self._items.append(FileItem(self._current_dir.parent, "..", is_dir=True))

        # Collect and sort entries
        try:
            entries = sorted(
                self._current_dir.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            entries = []

        for entry in entries:
            # Handle hidden files
            if entry.name.startswith('.') and not self.show_hidden:
                continue
            
            if entry.is_dir():
                self._items.append(FileItem.from_path(entry))
                self._dir_count += 1
            elif entry.suffix.lower() in self.extensions:
                self._items.append(FileItem.from_path(entry))
                self._file_count += 1

        self._selected = 0
        self._scroll_offset = 0
        self._fire_select()

    def go_up(self) -> bool:
        """Navigate to parent directory. Returns True if successful."""
        if self._current_dir.parent != self._current_dir:
            # Remember current dir name to re-select it after going up
            current_name = self._current_dir.name
            self.load_directory(self._current_dir.parent)
            # Try to select the directory we just came from
            self._select_by_name(current_name)
            return True
        return False

    def go_home(self) -> None:
        """Navigate to home directory."""
        self.load_directory(Path.home())

    def go_root(self) -> None:
        """Navigate to root directory."""
        self.load_directory(Path("/"))

    def go_back(self) -> bool:
        """Navigate to previous directory in history."""
        if self._history:
            prev = self._history.pop()
            self.load_directory(prev, push_history=False)
            return True
        return False

    def toggle_hidden(self) -> None:
        """Toggle visibility of hidden files."""
        self.show_hidden = not self.show_hidden
        self._refresh_items()

    def _select_by_name(self, name: str) -> bool:
        """Select item by name. Returns True if found."""
        for i, item in enumerate(self._items):
            if item.name == name:
                self._selected = i
                self._adjust_scroll()
                self._fire_select()
                return True
        return False

    def handle_input(self, event: KeyEvent) -> bool:
        if not self._items:
            return False

        # Movement (with wrap-around)
        if event.key == Key.UP or event.char == 'k':
            self._move_selection_wrap(-1)
            return True
        elif event.key == Key.DOWN or event.char == 'j':
            self._move_selection_wrap(1)
            return True
        elif event.key == Key.PAGE_UP:
            self._move_selection(-self._default_visible_height)
            return True
        elif event.key == Key.PAGE_DOWN:
            self._move_selection(self._default_visible_height)
            return True
        # Ctrl+U / Ctrl+D for half-page scroll (vim style)
        elif event.raw == '\x15':  # Ctrl+U
            self._move_selection(-self._default_visible_height // 2)
            return True
        elif event.raw == '\x04':  # Ctrl+D
            self._move_selection(self._default_visible_height // 2)
            return True
        # g/G for top/bottom (vim style)
        elif event.char == 'g':
            self._selected = 0
            self._scroll_offset = 0
            self._fire_select()
            return True
        elif event.char == 'G':
            self._selected = len(self._items) - 1
            self._adjust_scroll()
            self._fire_select()
            return True
        elif event.key == Key.HOME:
            self._selected = 0
            self._scroll_offset = 0
            self._fire_select()
            return True
        elif event.key == Key.END:
            self._selected = len(self._items) - 1
            self._adjust_scroll()
            self._fire_select()
            return True
        
        # Directory navigation
        elif event.key == Key.ENTER or event.key == Key.RIGHT or event.char == 'l':
            item = self._items[self._selected]
            if item.is_dir:
                self.load_directory(item.path)
            elif self.on_open:
                self.on_open(item)
            return True
        elif event.key == Key.BACKSPACE or event.key == Key.LEFT or event.char == 'h':
            # Only go up if we're not in a file (h/left could be for other purposes)
            if event.key == Key.BACKSPACE or self._items[self._selected].is_dir or event.char == 'h':
                self.go_up()
            return True
        elif event.char == '~':
            self.go_home()
            return True
        elif event.char == '/':
            self.go_root()
            return True
        elif event.char == '.':
            self.toggle_hidden()
            return True
        elif event.char == '-':
            # Go back in history
            self.go_back()
            return True

        return False

    def _move_selection(self, delta: int) -> None:
        """Move selection by delta, clamping to bounds."""
        self._selected = max(0, min(len(self._items) - 1, self._selected + delta))
        self._fire_select()

    def _move_selection_wrap(self, delta: int) -> None:
        """Move selection by delta, wrapping around at ends."""
        if not self._items:
            return
        self._selected = (self._selected + delta) % len(self._items)
        self._fire_select()

    def _adjust_scroll(self) -> None:
        """Adjust scroll using default visible height (for input handling)."""
        self._adjust_scroll_for_height(self._default_visible_height)

    def _adjust_scroll_for_height(self, visible_height: int) -> None:
        """Ensure selected item is visible for given viewport height."""
        if visible_height <= 0:
            return
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + visible_height:
            self._scroll_offset = self._selected - visible_height + 1

    def _fire_select(self) -> None:
        if self.on_select and self._items:
            self.on_select(self._items[self._selected])

    def render(self, bounds: Rect) -> list[str]:
        """Render the file list."""
        # Calculate visible height for this render (don't store as side effect)
        visible_height = bounds.height - 2  # Reserve for header + counts
        lines: list[str] = []

        # Adjust scroll based on current visible height
        self._adjust_scroll_for_height(visible_height)

        # Header: breadcrumb path
        lines.append(self._render_breadcrumb(bounds.width))
        
        # Subheader: counts
        counts = f"{self._dir_count} dirs, {self._file_count} files"
        hidden_indicator = " [+hidden]" if self.show_hidden else ""
        counts_line = f"\x1b[90m{counts}{hidden_indicator}\x1b[0m"
        lines.append(counts_line)

        # File list
        visible_start = self._scroll_offset
        visible_end = min(visible_start + visible_height, len(self._items))

        for i in range(visible_start, visible_end):
            item = self._items[i]
            is_selected = i == self._selected

            # Icon
            if item.name == "..":
                icon = "↑"
            elif item.is_dir:
                icon = "▸"  # Simpler, more compatible
            else:
                icon = " "

            # Format name with directory indicator
            name = item.name
            if item.is_dir and item.name != "..":
                name += "/"
            
            max_name_len = bounds.width - 4
            if len(name) > max_name_len:
                name = name[:max_name_len - 3] + "..."

            # Color: directories in blue, files in default
            if item.is_dir:
                color = "34"  # Blue
            else:
                color = "0"   # Default
            
            # Selection styling - always visible, brighter when focused
            if is_selected:
                # Bright cyan background when focused, dimmer when not
                if self.focused:
                    # Focused: bright inverse with cyan highlight
                    line = f"\x1b[30;46m▶{icon} {name:<{max_name_len}} \x1b[0m"
                else:
                    # Unfocused: still visible but dimmer
                    line = f"\x1b[30;106m {icon} {name:<{max_name_len}} \x1b[0m"
            else:
                line = f"\x1b[{color}m {icon} {name}\x1b[0m"

            lines.append(line)

        # Pad to fill height
        while len(lines) < bounds.height:
            lines.append("")

        return lines

    def _render_breadcrumb(self, width: int) -> str:
        """Render path as clickable-style breadcrumb."""
        parts = self._current_dir.parts
        
        # Build from right, truncating left if needed
        if len(parts) <= 3:
            # Short path - show full
            path_str = "/".join(parts) if parts[0] != "/" else "/".join([""] + list(parts[1:]))
        else:
            # Long path - show first, ellipsis, last 2
            path_str = f"{parts[0]}/…/{'/'.join(parts[-2:])}"
        
        # Ensure it fits
        if len(path_str) > width - 2:
            path_str = "…" + path_str[-(width - 3):]
        
        return f"\x1b[1;36m{path_str}\x1b[0m"

    @property
    def selected_item(self) -> Optional[FileItem]:
        if self._items and 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    @property
    def current_directory(self) -> Path:
        return self._current_dir
    
    @property
    def has_history(self) -> bool:
        return len(self._history) > 0
