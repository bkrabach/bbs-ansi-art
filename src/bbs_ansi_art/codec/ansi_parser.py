"""ANSI escape sequence parser with virtual terminal emulation.

Based on the proven byte-level parsing approach - handles escape sequences
at the raw byte level BEFORE any CP437 conversion.
"""

from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.core.cell import Cell
from bbs_ansi_art.core.constants import CP437_TO_UNICODE


class AnsiParser:
    """
    Stateful ANSI parser that processes raw bytes into a Canvas.
    
    Simulates a virtual terminal to correctly interpret cursor movements,
    color codes, and other ANSI escape sequences.
    
    Key insight: Parse escape sequences at the BYTE level, before any
    character encoding conversion. Only convert displayable characters
    to Unicode via CP437.
    """
    
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
        """
        Process raw bytes (CP437 encoded) into the canvas.
        
        Handles escape sequences at byte level before CP437 conversion.
        """
        i = 0
        while i < len(data):
            byte = data[i]
            
            if byte == 0x1B:  # ESC
                # Parse escape sequence from raw bytes
                i += 1
                if i < len(data) and data[i] == 0x5B:  # '['
                    i += 1
                    seq = '['
                    while i < len(data):
                        ch = data[i]
                        seq += chr(ch)
                        i += 1
                        # CSI sequences end with a letter (0x40-0x7E)
                        if 0x40 <= ch <= 0x7E:
                            break
                    self._process_escape(seq)
                continue
            elif byte == 0x0D:  # CR - Carriage Return
                self.cursor_x = 0
            elif byte == 0x0A:  # LF - Line Feed
                self.cursor_y += 1
                self.canvas.ensure_row(self.cursor_y)
            elif byte == 0x09:  # TAB
                # Move to next tab stop (every 8 columns)
                self.cursor_x = ((self.cursor_x // 8) + 1) * 8
                if self.cursor_x >= self.width:
                    self.cursor_x = 0
                    self.cursor_y += 1
                    self.canvas.ensure_row(self.cursor_y)
            elif byte == 0x1A:  # EOF (SAUCE marker)
                break
            else:
                # Regular character - convert CP437 to Unicode
                char = CP437_TO_UNICODE[byte]
                self._put_char(char)
            
            i += 1
    
    def feed_unicode(self, text: str) -> None:
        """Process Unicode text into the canvas (for pre-converted text)."""
        # Convert back to bytes and use standard feed
        # This is a fallback - prefer feed() with raw bytes
        data = text.encode('cp437', errors='replace')
        self.feed(data)
    
    def _put_char(self, char: str) -> None:
        """Put a character at current cursor position."""
        # Handle wrap
        if self.cursor_x >= self.width:
            self.cursor_x = 0
            self.cursor_y += 1
        
        self.canvas.ensure_row(self.cursor_y)
        cell = self.canvas._buffer[self.cursor_y][self.cursor_x]
        cell.char = char
        cell.fg = self.fg
        cell.bg = self.bg
        cell.bold = self.bold
        cell.blink = self.blink
        
        self.cursor_x += 1
    
    def _process_escape(self, seq: str) -> None:
        """Process an ANSI escape sequence."""
        if not seq.startswith('['):
            return
        
        seq = seq[1:]  # Remove '['
        
        if not seq:
            return
        
        # Get the final character (command)
        cmd = seq[-1]
        params_str = seq[:-1]
        
        # Parse parameters
        params: list[int] = []
        if params_str:
            for p in params_str.split(';'):
                try:
                    params.append(int(p) if p else 0)
                except ValueError:
                    params.append(0)
        
        if cmd == 'm':
            self._handle_sgr(params)
        elif cmd == 't':
            # Window manipulation - IGNORE (causes terminal flicker/resize)
            pass
        elif cmd == 'h' or cmd == 'l':
            # Mode set/reset (like ?7h for line wrap) - IGNORE for display
            pass
        elif cmd == 'H' or cmd == 'f':
            # Cursor position
            row = params[0] if params else 1
            col = params[1] if len(params) > 1 else 1
            self.cursor_y = max(0, row - 1)
            self.cursor_x = max(0, min(col - 1, self.width - 1))
            self.canvas.ensure_row(self.cursor_y)
        elif cmd == 'A':
            # Cursor up
            n = params[0] if params else 1
            self.cursor_y = max(0, self.cursor_y - n)
        elif cmd == 'B':
            # Cursor down
            n = params[0] if params else 1
            self.cursor_y += n
            self.canvas.ensure_row(self.cursor_y)
        elif cmd == 'C':
            # Cursor forward (right)
            n = params[0] if params else 1
            if self.cursor_x >= self.width:
                # At right margin: wrap first, then position
                self.cursor_x = 0
                self.cursor_y += 1
                self.canvas.ensure_row(self.cursor_y)
            self.cursor_x = min(self.cursor_x + n, self.width)
        elif cmd == 'D':
            # Cursor back (left)
            n = params[0] if params else 1
            self.cursor_x = max(0, self.cursor_x - n)
        elif cmd == 'J':
            # Erase in display
            mode = params[0] if params else 0
            self._erase_display(mode)
        elif cmd == 'K':
            # Erase in line
            mode = params[0] if params else 0
            self._erase_line(mode)
        elif cmd == 's':
            # Save cursor position
            self.saved_x = self.cursor_x
            self.saved_y = self.cursor_y
        elif cmd == 'u':
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
        if mode == 0:
            # Erase from cursor to end of display
            self.canvas.ensure_row(self.cursor_y)
            # Clear rest of current line
            row = self.canvas._buffer[self.cursor_y]
            for x in range(self.cursor_x, self.width):
                row[x] = Cell()
            # Clear all lines below
            for y in range(self.cursor_y + 1, len(self.canvas._buffer)):
                for x in range(self.width):
                    self.canvas._buffer[y][x] = Cell()
        elif mode == 1:
            # Erase from start of display to cursor
            # Clear all lines above
            for y in range(self.cursor_y):
                if y < len(self.canvas._buffer):
                    for x in range(self.width):
                        self.canvas._buffer[y][x] = Cell()
            # Clear current line up to cursor
            self.canvas.ensure_row(self.cursor_y)
            row = self.canvas._buffer[self.cursor_y]
            for x in range(self.cursor_x + 1):
                row[x] = Cell()
        elif mode == 2:
            # Erase entire display
            self.canvas = Canvas(width=self.width)
            self.cursor_x = 0
            self.cursor_y = 0
    
    def _erase_line(self, mode: int) -> None:
        """Erase in line."""
        self.canvas.ensure_row(self.cursor_y)
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
