"""Status bar widget for displaying info and shortcuts."""

from __future__ import annotations

import re
from dataclasses import dataclass

from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect
from bbs_ansi_art.cli.core.input import KeyEvent


def _visible_len(s: str) -> int:
    """Get visible length of string (excluding ANSI codes)."""
    return len(re.sub(r'\x1b\[[0-9;]*m', '', s))


@dataclass
class Shortcut:
    """A keyboard shortcut to display."""
    key: str
    label: str


class StatusBarWidget(BaseWidget):
    """Bottom status bar showing info and keyboard shortcuts."""

    def __init__(self) -> None:
        super().__init__()
        self._left_text: str = ""
        self._center_text: str = ""
        self._shortcuts: list[Shortcut] = []

    @property
    def focusable(self) -> bool:
        return False  # Status bar doesn't receive focus

    def set_left(self, text: str) -> None:
        """Set left-aligned text."""
        self._left_text = text

    def set_center(self, text: str) -> None:
        """Set center text (e.g., scroll position)."""
        self._center_text = text

    def set_shortcuts(self, shortcuts: list[Shortcut]) -> None:
        """Set keyboard shortcuts to display."""
        self._shortcuts = shortcuts

    def render(self, bounds: Rect) -> list[str]:
        """Render the status bar, fitting within bounds.width."""
        width = bounds.width
        
        # Build shortcuts from right, only include what fits
        shortcut_parts: list[str] = []
        shortcuts_visible_len = 0
        
        for sc in reversed(self._shortcuts):
            part = f"\x1b[7m {sc.key} \x1b[0;36m{sc.label} "
            part_len = _visible_len(part)
            
            # Reserve space for left text + some padding
            if shortcuts_visible_len + part_len + 20 < width:
                shortcut_parts.insert(0, part)
                shortcuts_visible_len += part_len
            else:
                break
        
        shortcuts_str = "".join(shortcut_parts)
        
        # Build left side
        left = self._left_text
        center = self._center_text
        
        # Calculate available space for left+center
        available = width - shortcuts_visible_len - 2
        
        left_center = f" {left}"
        if center:
            left_center += f"  {center}"
        
        # Truncate if needed
        if len(left_center) > available:
            left_center = left_center[:available - 1] + "…"
        
        # Build final line
        padding_needed = width - len(left_center) - shortcuts_visible_len
        padding = " " * max(0, padding_needed)
        
        line = f"\x1b[100m\x1b[97m{left_center}{padding}{shortcuts_str}\x1b[0m"
        
        return [line]

    def handle_input(self, event: KeyEvent) -> bool:
        return False  # Status bar doesn't handle input
