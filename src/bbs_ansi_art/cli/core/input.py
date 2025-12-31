"""Keyboard input handling with event abstraction."""

from __future__ import annotations

import os
import sys
import select
import time
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
    """
    Non-blocking keyboard input reader.
    
    Uses os.read() to bypass Python's I/O buffering and properly
    handle escape sequences that may arrive split across reads.
    """

    # Escape sequence mappings (without the \x1b prefix)
    SEQUENCES: dict[str, Key] = {
        # Arrow keys (CSI)
        '[A': Key.UP,
        '[B': Key.DOWN,
        '[C': Key.RIGHT,
        '[D': Key.LEFT,
        # Arrow keys (SS3 - application mode)
        'OA': Key.UP,
        'OB': Key.DOWN,
        'OC': Key.RIGHT,
        'OD': Key.LEFT,
        # Navigation
        '[H': Key.HOME,
        '[F': Key.END,
        '[1~': Key.HOME,
        '[4~': Key.END,
        '[5~': Key.PAGE_UP,
        '[6~': Key.PAGE_DOWN,
        '[2~': Key.INSERT,
        '[3~': Key.DELETE,
        # Function keys
        'OP': Key.F1,
        'OQ': Key.F2,
        'OR': Key.F3,
        'OS': Key.F4,
        '[15~': Key.F5,
        '[21~': Key.F10,
        '[24~': Key.F12,
    }
    
    SIMPLE_KEYS: dict[str, Key] = {
        '\r': Key.ENTER,
        '\n': Key.ENTER,
        '\t': Key.TAB,
        '\x7f': Key.BACKSPACE,
        '\x08': Key.BACKSPACE,
    }

    def __init__(self) -> None:
        self._buffer = ""
        self._fd = sys.stdin.fileno()

    def read(self, timeout: float = 0.1) -> Optional[KeyEvent]:
        """
        Read a single key event.
        
        Returns None if no input available within timeout.
        """
        # Process any buffered input first
        if self._buffer:
            return self._process_buffer()
        
        if not self._has_input(timeout):
            return None

        # Read all available input using os.read to bypass Python buffering
        self._read_available()
        
        if self._buffer:
            return self._process_buffer()
        
        return None

    def _read_available(self) -> None:
        """Read all currently available input into buffer using os.read."""
        try:
            # Read up to 1024 bytes at once - gets everything available
            data = os.read(self._fd, 1024)
            self._buffer += data.decode('utf-8', errors='replace')
        except (OSError, BlockingIOError):
            pass
        
        # If buffer is just escape, wait for potential sequence
        if self._buffer == '\x1b':
            self._wait_for_escape_sequence()

    def _wait_for_escape_sequence(self) -> None:
        """Wait for escape sequence to complete with proper timeouts."""
        deadline = time.monotonic() + 0.1  # 100ms total wait
        
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            wait_time = min(remaining, 0.025)  # 25ms intervals
            
            if wait_time <= 0:
                break
                
            if self._has_input(wait_time):
                try:
                    data = os.read(self._fd, 1024)
                    self._buffer += data.decode('utf-8', errors='replace')
                except (OSError, BlockingIOError):
                    pass
                
                # Check if sequence looks complete
                if len(self._buffer) > 1:
                    rest = self._buffer[1:]
                    # Sequence ends with letter or ~
                    if rest and (rest[-1].isalpha() or rest[-1] == '~'):
                        return
                    # Or we have a known sequence
                    if rest in self.SEQUENCES:
                        return

    def _process_buffer(self) -> Optional[KeyEvent]:
        """Process buffered input and return next key event."""
        if not self._buffer:
            return None
        
        # Simple keys
        if self._buffer[0] in self.SIMPLE_KEYS:
            key = self.SIMPLE_KEYS[self._buffer[0]]
            raw = self._buffer[0]
            self._buffer = self._buffer[1:]
            return KeyEvent(key=key, raw=raw)
        
        # Escape sequence
        if self._buffer[0] == '\x1b':
            return self._parse_escape_sequence()
        
        # Printable character
        if self._buffer[0].isprintable():
            ch = self._buffer[0]
            self._buffer = self._buffer[1:]
            return KeyEvent(char=ch, raw=ch)
        
        # Unknown control character - skip it
        self._buffer = self._buffer[1:]
        return None

    def _parse_escape_sequence(self) -> KeyEvent:
        """Parse an escape sequence from the buffer."""
        # Buffer starts with \x1b
        if len(self._buffer) == 1:
            # Just escape, no sequence
            self._buffer = ""
            return KeyEvent(key=Key.ESCAPE, raw='\x1b')
        
        # Look for matching sequence (without the \x1b prefix)
        rest = self._buffer[1:]
        
        # Find where this sequence ends
        end_idx = 0
        for i, ch in enumerate(rest):
            if ch == '\x1b':
                # Start of next escape sequence
                end_idx = i
                break
            if ch.isalpha() or ch == '~':
                # End of this sequence
                end_idx = i + 1
                break
            end_idx = i + 1
        
        if end_idx == 0:
            # Nothing after escape
            self._buffer = ""
            return KeyEvent(key=Key.ESCAPE, raw='\x1b')
        
        seq = rest[:end_idx]
        
        if seq in self.SEQUENCES:
            key = self.SEQUENCES[seq]
            raw = '\x1b' + seq
            self._buffer = self._buffer[1 + end_idx:]
            return KeyEvent(key=key, raw=raw)
        
        # Unknown sequence
        raw = '\x1b' + seq
        self._buffer = self._buffer[1 + end_idx:]
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
            ready, _, _ = select.select([self._fd], [], [], timeout)
            return bool(ready)
        except (ValueError, OSError):
            return False
