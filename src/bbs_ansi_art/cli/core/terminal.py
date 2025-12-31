"""Low-level terminal operations - platform-independent abstraction."""

from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator


@dataclass(frozen=True)
class TerminalSize:
    """Terminal dimensions."""
    rows: int
    cols: int


class Terminal:
    """Terminal I/O abstraction for TUI applications."""

    @staticmethod
    def size() -> TerminalSize:
        """Get current terminal dimensions."""
        try:
            size = os.get_terminal_size()
            return TerminalSize(size.lines, size.columns)
        except OSError:
            return TerminalSize(24, 80)

    @staticmethod
    def clear() -> None:
        """Clear screen and move cursor to home."""
        sys.stdout.write('\x1b[2J\x1b[H')
        sys.stdout.flush()

    @staticmethod
    def reset() -> None:
        """Reset all terminal attributes."""
        sys.stdout.write('\x1b[0m')
        sys.stdout.flush()

    @staticmethod
    def hide_cursor() -> None:
        """Hide the cursor."""
        sys.stdout.write('\x1b[?25l')
        sys.stdout.flush()

    @staticmethod
    def show_cursor() -> None:
        """Show the cursor."""
        sys.stdout.write('\x1b[?25h')
        sys.stdout.flush()

    @staticmethod
    def move_to(row: int, col: int) -> None:
        """Move cursor to position (1-indexed)."""
        sys.stdout.write(f'\x1b[{row};{col}H')
        sys.stdout.flush()

    @staticmethod
    def write(text: str) -> None:
        """Write text to terminal."""
        sys.stdout.write(text)
        sys.stdout.flush()

    @staticmethod
    @contextmanager
    def raw_mode() -> Iterator[None]:
        """Context manager for raw terminal mode (Unix only)."""
        try:
            import termios
            import tty
            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                yield
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except ImportError:
            # Windows or no termios - just yield
            yield

    @staticmethod
    @contextmanager
    def alternate_screen() -> Iterator[None]:
        """Use alternate screen buffer (preserves scrollback)."""
        sys.stdout.write('\x1b[?1049h')
        sys.stdout.flush()
        try:
            yield
        finally:
            sys.stdout.write('\x1b[?1049l')
            sys.stdout.flush()

    @staticmethod
    @contextmanager
    def managed_mode() -> Iterator[None]:
        """Full TUI mode: alternate screen, hidden cursor, raw input."""
        with Terminal.alternate_screen():
            Terminal.hide_cursor()
            try:
                with Terminal.raw_mode():
                    yield
            finally:
                Terminal.show_cursor()
                Terminal.reset()
