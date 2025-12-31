"""Scrollable file browser widget."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from bbs_ansi_art.cli.core.input import Key, KeyEvent
from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect


@dataclass
class FileItem:
    """Represents a file in the list."""
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
    """Scrollable, filterable file list with keyboard navigation."""

    EXTENSIONS = {'.ans', '.asc', '.diz', '.nfo', '.txt'}

    def __init__(
        self,
        extensions: Optional[set[str]] = None,
        on_select: Optional[Callable[[FileItem], None]] = None,
        on_open: Optional[Callable[[FileItem], None]] = None,
    ):
        super().__init__()
        self.extensions = extensions or self.EXTENSIONS
        self.on_select = on_select
        self.on_open = on_open

        self._items: list[FileItem] = []
        self._selected: int = 0
        self._scroll_offset: int = 0
        self._current_dir: Path = Path.cwd()
        self._visible_height: int = 20

    def load_directory(self, path: Path) -> None:
        """Load files from directory."""
        self._current_dir = path.resolve()
        self._items = []

        # Add parent directory navigation
        if self._current_dir.parent != self._current_dir:
            self._items.append(FileItem(self._current_dir.parent, "..", is_dir=True))

        # Add directories first, then matching files
        try:
            entries = sorted(
                self._current_dir.iterdir(),
                key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except PermissionError:
            entries = []

        for entry in entries:
            if entry.name.startswith('.'):
                continue  # Skip hidden files
            if entry.is_dir():
                self._items.append(FileItem.from_path(entry))
            elif entry.suffix.lower() in self.extensions:
                self._items.append(FileItem.from_path(entry))

        self._selected = 0
        self._scroll_offset = 0
        self._fire_select()

    def handle_input(self, event: KeyEvent) -> bool:
        if not self._items:
            return False

        if event.key == Key.UP or event.char == 'k':
            self._move_selection(-1)
            return True
        elif event.key == Key.DOWN or event.char == 'j':
            self._move_selection(1)
            return True
        elif event.key == Key.PAGE_UP:
            self._move_selection(-self._visible_height)
            return True
        elif event.key == Key.PAGE_DOWN:
            self._move_selection(self._visible_height)
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
        elif event.key == Key.ENTER:
            item = self._items[self._selected]
            if item.is_dir:
                self.load_directory(item.path)
            elif self.on_open:
                self.on_open(item)
            return True

        return False

    def _move_selection(self, delta: int) -> None:
        self._selected = max(0, min(len(self._items) - 1, self._selected + delta))
        self._adjust_scroll()
        self._fire_select()

    def _adjust_scroll(self) -> None:
        """Ensure selected item is visible."""
        if self._selected < self._scroll_offset:
            self._scroll_offset = self._selected
        elif self._selected >= self._scroll_offset + self._visible_height:
            self._scroll_offset = self._selected - self._visible_height + 1

    def _fire_select(self) -> None:
        if self.on_select and self._items:
            self.on_select(self._items[self._selected])

    def render(self, bounds: Rect) -> list[str]:
        """Render the file list."""
        self._visible_height = bounds.height
        lines: list[str] = []

        # Adjust scroll
        self._adjust_scroll()

        # Header: current directory
        dir_str = str(self._current_dir)
        if len(dir_str) > bounds.width - 2:
            dir_str = "..." + dir_str[-(bounds.width - 5):]
        lines.append(f"\x1b[1;36m{dir_str}\x1b[0m")

        # File list
        visible_start = self._scroll_offset
        visible_end = min(visible_start + bounds.height - 1, len(self._items))

        for i in range(visible_start, visible_end):
            item = self._items[i]
            is_selected = i == self._selected

            # Icon
            if item.name == "..":
                icon = "⬆"
            elif item.is_dir:
                icon = "📁"
            else:
                icon = "📄"

            # Format name
            name = item.name
            max_name_len = bounds.width - 4
            if len(name) > max_name_len:
                name = name[:max_name_len - 3] + "..."

            if is_selected and self.focused:
                line = f"\x1b[7m {icon} {name:<{max_name_len}} \x1b[0m"
            elif is_selected:
                line = f"\x1b[100m {icon} {name:<{max_name_len}} \x1b[0m"
            else:
                line = f" {icon} {name}"

            lines.append(line)

        # Pad to fill height
        while len(lines) < bounds.height:
            lines.append("")

        return lines

    @property
    def selected_item(self) -> Optional[FileItem]:
        if self._items and 0 <= self._selected < len(self._items):
            return self._items[self._selected]
        return None

    @property
    def current_directory(self) -> Path:
        return self._current_dir
