"""ANSI art display widget with scrolling support."""

from __future__ import annotations

import re
from typing import Optional

from bbs_ansi_art.core.document import AnsiDocument
from bbs_ansi_art.cli.core.input import Key, KeyEvent
from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect


def _truncate_ansi(s: str, max_width: int) -> str:
    """
    Truncate an ANSI-escaped string to max visible width.
    
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


class ArtCanvasWidget(BaseWidget):
    """Displays rendered ANSI art with scroll support."""

    def __init__(self) -> None:
        super().__init__()
        self._document: Optional[AnsiDocument] = None
        self._rendered_lines: list[str] = []
        self._scroll_y: int = 0
        self._visible_height: int = 20
        self._visible_width: int = 80

    def load(self, doc: AnsiDocument) -> None:
        """Load an ANSI document for display."""
        self._document = doc
        self._rendered_lines = doc.render().split('\n')
        self._scroll_y = 0

    def clear(self) -> None:
        """Clear the display."""
        self._document = None
        self._rendered_lines = []
        self._scroll_y = 0

    def handle_input(self, event: KeyEvent) -> bool:
        if not self._rendered_lines:
            return False

        max_scroll = max(0, len(self._rendered_lines) - self._visible_height)

        if event.key == Key.UP or event.char == 'k':
            self._scroll_y = max(0, self._scroll_y - 1)
            return True
        elif event.key == Key.DOWN or event.char == 'j':
            self._scroll_y = min(max_scroll, self._scroll_y + 1)
            return True
        elif event.key == Key.PAGE_UP:
            self._scroll_y = max(0, self._scroll_y - self._visible_height)
            return True
        elif event.key == Key.PAGE_DOWN:
            self._scroll_y = min(max_scroll, self._scroll_y + self._visible_height)
            return True
        elif event.key == Key.HOME:
            self._scroll_y = 0
            return True
        elif event.key == Key.END:
            self._scroll_y = max_scroll
            return True

        return False

    def render(self, bounds: Rect) -> list[str]:
        """Render visible portion of the art, clipped to bounds."""
        self._visible_height = bounds.height
        self._visible_width = bounds.width

        if not self._rendered_lines:
            # Empty state
            lines = [""] * bounds.height
            msg = "(No art loaded)"
            if bounds.height > 2 and bounds.width > len(msg):
                lines[bounds.height // 2] = f"\x1b[90m{msg:^{bounds.width}}\x1b[0m"
            return lines

        # Get visible slice and truncate each line to width
        visible = []
        for line in self._rendered_lines[self._scroll_y:self._scroll_y + bounds.height]:
            truncated = _truncate_ansi(line, bounds.width)
            visible.append(truncated)

        # Pad to fill height
        while len(visible) < bounds.height:
            visible.append("")

        return visible

    @property
    def document(self) -> Optional[AnsiDocument]:
        return self._document

    @property
    def scroll_percent(self) -> float:
        """Get scroll position as percentage (0-100)."""
        if not self._rendered_lines or len(self._rendered_lines) <= self._visible_height:
            return 0.0
        max_scroll = len(self._rendered_lines) - self._visible_height
        if max_scroll <= 0:
            return 0.0
        return (self._scroll_y / max_scroll) * 100

    @property
    def total_lines(self) -> int:
        return len(self._rendered_lines)
