"""Status bar widget for displaying info and shortcuts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from bbs_ansi_art.cli.widgets.base import BaseWidget, Rect
from bbs_ansi_art.cli.core.input import KeyEvent


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
        """Render the status bar."""
        # Build shortcuts string
        shortcut_parts = []
        for sc in self._shortcuts:
            shortcut_parts.append(f"\x1b[7m {sc.key} \x1b[0;36m {sc.label} ")
        shortcuts_str = "".join(shortcut_parts)

        # Build the bar
        # Left: info text
        # Center: scroll position
        # Right: shortcuts

        left = self._left_text[:bounds.width // 3]
        center = self._center_text
        
        # Calculate available space for shortcuts
        # For simplicity, we'll build a single line
        
        # Strip ANSI for length calculation
        import re
        def visible_len(s: str) -> int:
            return len(re.sub(r'\x1b\[[0-9;]*m', '', s))

        line = f"\x1b[100m\x1b[97m {left}"
        
        # Add center text if there's room
        if center:
            line += f"  {center}"
        
        # Pad and add shortcuts
        current_len = visible_len(line)
        shortcuts_len = visible_len(shortcuts_str)
        padding_needed = bounds.width - current_len - shortcuts_len - 1
        
        if padding_needed > 0:
            line += " " * padding_needed
        
        line += shortcuts_str
        line += "\x1b[0m"

        return [line]

    def handle_input(self, event: KeyEvent) -> bool:
        return False  # Status bar doesn't handle input
