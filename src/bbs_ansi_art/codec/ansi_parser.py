"""ANSI escape sequence parser with virtual terminal emulation."""

import re
from typing import Callable

from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.core.cell import Cell
from bbs_ansi_art.core.constants import CP437_TO_UNICODE


class AnsiParser:
    """
    Stateful ANSI parser that processes raw bytes into a Canvas.
    
    Simulates a virtual terminal to correctly interpret cursor movements,
    color codes, and other ANSI escape sequences.
    """
    
    # Regex for CSI sequences: ESC [ params command
    CSI_PATTERN = re.compile(r'\x1b\[([0-9;]*)([A-Za-z])')
    
    def __init__(self, width: int = 80):
        self.width = width
        self.canvas = Canvas(width=width)
        
        # Terminal state
        self.cursor_x = 0
        self.cursor_y = 0
        self.fg = 37  # Default white
        self.bg = 40  # Default black
        self.bold = False
        self.blink = False
        
        # Saved cursor position
        self.saved_x = 0
        self.saved_y = 0
    
    def feed(self, data: bytes) -> None:
        """Process raw bytes (CP437 encoded) into the canvas."""
        # Convert to Unicode
        text = ''.join(CP437_TO_UNICODE[b] for b in data)
        self._process_text(text)
    
    def feed_unicode(self, text: str) -> None:
        """Process Unicode text into the canvas."""
        self._process_text(text)
    
    def _process_text(self, text: str) -> None:
        """Process text with ANSI sequences."""
        i = 0
        while i < len(text):
            # Check for escape sequence
            if text[i] == '\x1b' and i + 1 < len(text) and text[i + 1] == '[':
                # Find end of CSI sequence
                match = self.CSI_PATTERN.match(text, i)
                if match:
                    params_str = match.group(1)
                    command = match.group(2)
                    self._handle_csi(params_str, command)
                    i = match.end()
                    continue
            
            # Handle special characters
            char = text[i]
            if char == '\r':
                self.cursor_x = 0
            elif char == '\n':
                self.cursor_y += 1
                self.canvas._ensure_row(self.cursor_y)
            elif char == '\x1a':
                # EOF marker - stop processing
                break
            elif char == '\x1b':
                # Unhandled escape - skip
                pass
            else:
                # Regular character
                self._put_char(char)
            
            i += 1
    
    def _put_char(self, char: str) -> None:
        """Put a character at current cursor position."""
        # Handle wrap
        if self.cursor_x >= self.width:
            self.cursor_x = 0
            self.cursor_y += 1
        
        self.canvas._ensure_row(self.cursor_y)
        cell = self.canvas._buffer[self.cursor_y][self.cursor_x]
        cell.char = char
        cell.fg = self.fg
        cell.bg = self.bg
        cell.bold = self.bold
        cell.blink = self.blink
        
        self.cursor_x += 1
    
    def _handle_csi(self, params_str: str, command: str) -> None:
        """Handle a CSI escape sequence."""
        # Parse parameters
        params: list[int] = []
        if params_str:
            params = [int(p) if p else 0 for p in params_str.split(';')]
        
        if command == 'm':
            self._handle_sgr(params)
        elif command == 'H' or command == 'f':
            # Cursor position
            row = params[0] if params else 1
            col = params[1] if len(params) > 1 else 1
            self.cursor_y = max(0, row - 1)
            self.cursor_x = max(0, min(col - 1, self.width - 1))
            self.canvas._ensure_row(self.cursor_y)
        elif command == 'A':
            # Cursor up
            n = params[0] if params else 1
            self.cursor_y = max(0, self.cursor_y - n)
        elif command == 'B':
            # Cursor down
            n = params[0] if params else 1
            self.cursor_y += n
            self.canvas._ensure_row(self.cursor_y)
        elif command == 'C':
            # Cursor forward
            n = params[0] if params else 1
            if self.cursor_x >= self.width:
                # At right margin: wrap first, then position
                self.cursor_x = 0
                self.cursor_y += 1
                self.canvas._ensure_row(self.cursor_y)
            self.cursor_x = min(self.cursor_x + n, self.width)
        elif command == 'D':
            # Cursor back
            n = params[0] if params else 1
            self.cursor_x = max(0, self.cursor_x - n)
        elif command == 'J':
            # Erase in display
            mode = params[0] if params else 0
            self._erase_display(mode)
        elif command == 'K':
            # Erase in line
            mode = params[0] if params else 0
            self._erase_line(mode)
        elif command == 's':
            # Save cursor position
            self.saved_x = self.cursor_x
            self.saved_y = self.cursor_y
        elif command == 'u':
            # Restore cursor position
            self.cursor_x = self.saved_x
            self.cursor_y = self.saved_y
    
    def _handle_sgr(self, params: list[int]) -> None:
        """Handle SGR (Select Graphic Rendition) parameters."""
        if not params:
            params = [0]
        
        i = 0
        while i < len(params):
            p = params[i]
            
            if p == 0:
                # Reset
                self.fg = 37
                self.bg = 40
                self.bold = False
                self.blink = False
            elif p == 1:
                self.bold = True
            elif p == 5:
                self.blink = True
            elif p == 22:
                self.bold = False
            elif p == 25:
                self.blink = False
            elif 30 <= p <= 37:
                self.fg = p
            elif p == 38:
                # Extended foreground color
                if i + 2 < len(params) and params[i + 1] == 5:
                    # 256-color: 38;5;n
                    self.fg = params[i + 2]
                    i += 2
            elif p == 39:
                self.fg = 37  # Default foreground
            elif 40 <= p <= 47:
                self.bg = p
            elif p == 48:
                # Extended background color
                if i + 2 < len(params) and params[i + 1] == 5:
                    # 256-color: 48;5;n
                    self.bg = params[i + 2]
                    i += 2
            elif p == 49:
                self.bg = 40  # Default background
            elif 90 <= p <= 97:
                # Bright foreground
                self.fg = p
            elif 100 <= p <= 107:
                # Bright background
                self.bg = p
            
            i += 1
    
    def _erase_display(self, mode: int) -> None:
        """Erase in display."""
        if mode == 2:
            # Erase entire display
            self.canvas = Canvas(width=self.width)
            self.cursor_x = 0
            self.cursor_y = 0
    
    def _erase_line(self, mode: int) -> None:
        """Erase in line."""
        self.canvas._ensure_row(self.cursor_y)
        row = self.canvas._buffer[self.cursor_y]
        
        if mode == 0:
            # Erase from cursor to end of line
            for x in range(self.cursor_x, self.width):
                row[x] = Cell()
        elif mode == 1:
            # Erase from start of line to cursor
            for x in range(0, self.cursor_x + 1):
                row[x] = Cell()
        elif mode == 2:
            # Erase entire line
            for x in range(self.width):
                row[x] = Cell()
    
    def get_canvas(self) -> Canvas:
        """Get the resulting canvas."""
        return self.canvas
