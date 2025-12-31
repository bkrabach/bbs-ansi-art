"""Keyboard input handling with event abstraction."""

from __future__ import annotations

import sys
import select
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class Key(Enum):
    """Named key constants."""
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    ENTER = auto()
    ESCAPE = auto()
    TAB = auto()
    BACKSPACE = auto()
    HOME = auto()
    END = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    DELETE = auto()
    INSERT = auto()
    F1 = auto()
    F2 = auto()
    F3 = auto()
    F4 = auto()
    F5 = auto()
    F10 = auto()
    F12 = auto()


@dataclass(frozen=True)
class KeyEvent:
    """Represents a keyboard input event."""
    key: Optional[Key] = None  # Named key if recognized
    char: Optional[str] = None  # Character if printable
    raw: str = ""  # Raw escape sequence

    @property
    def is_char(self) -> bool:
        """Check if this is a printable character."""
        return self.char is not None and self.key is None


class InputReader:
    """Non-blocking keyboard input reader."""

    # Escape sequence mappings
    SEQUENCES: dict[str, Key] = {
        '\x1b[A': Key.UP,
        '\x1b[B': Key.DOWN,
        '\x1b[C': Key.RIGHT,
        '\x1b[D': Key.LEFT,
        '\x1b[H': Key.HOME,
        '\x1b[F': Key.END,
        '\x1b[1~': Key.HOME,
        '\x1b[4~': Key.END,
        '\x1b[5~': Key.PAGE_UP,
        '\x1b[6~': Key.PAGE_DOWN,
        '\x1b[2~': Key.INSERT,
        '\x1b[3~': Key.DELETE,
        '\x1bOP': Key.F1,
        '\x1bOQ': Key.F2,
        '\x1bOR': Key.F3,
        '\x1bOS': Key.F4,
        '\x1b[15~': Key.F5,
        '\x1b[21~': Key.F10,
        '\x1b[24~': Key.F12,
        '\r': Key.ENTER,
        '\n': Key.ENTER,
        '\x1b': Key.ESCAPE,
        '\t': Key.TAB,
        '\x7f': Key.BACKSPACE,
        '\x08': Key.BACKSPACE,
    }

    def __init__(self) -> None:
        self._buffer = ""

    def read(self, timeout: float = 0.1) -> Optional[KeyEvent]:
        """
        Read a single key event.
        
        Returns None if no input available within timeout.
        """
        if not self._has_input(timeout):
            return None

        ch = sys.stdin.read(1)
        raw = ch

        # Handle escape sequences
        if ch == '\x1b':
            # Check for more input (escape sequence)
            if self._has_input(0.01):
                ch2 = sys.stdin.read(1)
                raw += ch2
                if ch2 == '[' or ch2 == 'O':
                    # CSI or SS3 sequence
                    while self._has_input(0.01):
                        ch3 = sys.stdin.read(1)
                        raw += ch3
                        if ch3.isalpha() or ch3 == '~':
                            break

        # Check for named key
        if raw in self.SEQUENCES:
            return KeyEvent(key=self.SEQUENCES[raw], raw=raw)

        # Printable character
        if len(raw) == 1 and raw.isprintable():
            return KeyEvent(char=raw, raw=raw)

        # Control character or unknown sequence
        return KeyEvent(raw=raw)

    def read_blocking(self) -> KeyEvent:
        """Read a key event, blocking until input is available."""
        while True:
            event = self.read(timeout=1.0)
            if event is not None:
                return event

    def _has_input(self, timeout: float) -> bool:
        """Check if input is available within timeout."""
        try:
            ready, _, _ = select.select([sys.stdin], [], [], timeout)
            return bool(ready)
        except (ValueError, OSError):
            return False
