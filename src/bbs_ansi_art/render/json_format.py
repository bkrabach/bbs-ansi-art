"""Render ANSI art to structured JSON format.

This format is designed for LLM structured output and perfect round-trips:
- Explicit cell data (no escape sequence parsing needed)
- Row-major organization matching visual layout
- Optional run-length encoding for efficiency
- Lossless bidirectional conversion

Example output (compact mode):
{
  "width": 80,
  "height": 25,
  "rows": [
    {"y": 0, "runs": [
      {"chars": "████", "fg": "red", "bg": "black", "bold": true},
      {"chars": "▄▄▄▄", "fg": "yellow", "bg": "black"}
    ]}
  ]
}

Example output (full mode):
{
  "width": 80,
  "height": 25,
  "cells": [
    {"x": 0, "y": 0, "char": "█", "fg": "red", "bg": "black", "bold": true},
    {"x": 1, "y": 0, "char": "█", "fg": "red", "bg": "black", "bold": true}
  ]
}
"""

import json
from typing import Any
from bbs_ansi_art.core.canvas import Canvas


# SGR code to human-readable color name mapping
COLOR_NAMES = {
    30: "black", 31: "red", 32: "green", 33: "yellow",
    34: "blue", 35: "magenta", 36: "cyan", 37: "white",
    40: "black", 41: "red", 42: "green", 43: "yellow",
    44: "blue", 45: "magenta", 46: "cyan", 47: "white",
}

NAME_TO_FG = {"black": 30, "red": 31, "green": 32, "yellow": 33,
              "blue": 34, "magenta": 35, "cyan": 36, "white": 37}
NAME_TO_BG = {"black": 40, "red": 41, "green": 42, "yellow": 43,
              "blue": 44, "magenta": 45, "cyan": 46, "white": 47}


class JsonRenderer:
    """
    Render a Canvas to structured JSON format.
    
    Supports multiple output modes:
    - runs: Run-length encoded (most compact, good for LLM output)
    - cells: Every cell explicit (verbose but simple)
    - sparse: Only non-default cells (good for art with whitespace)
    """
    
    def __init__(
        self,
        mode: str = "runs",
        use_color_names: bool = True,
        indent: int | None = 2,
        include_defaults: bool = False,
    ):
        """
        Args:
            mode: Output mode - "runs", "cells", or "sparse"
            use_color_names: Use "red" instead of 31 for colors
            indent: JSON indentation (None for compact)
            include_defaults: Include cells with default values (space, white on black)
        """
        self.mode = mode
        self.use_color_names = use_color_names
        self.indent = indent
        self.include_defaults = include_defaults
    
    def render(self, canvas: Canvas) -> str:
        """Render canvas to JSON string."""
        data = self.to_dict(canvas)
        return json.dumps(data, indent=self.indent, ensure_ascii=False)
    
    def to_dict(self, canvas: Canvas) -> dict[str, Any]:
        """Convert canvas to dictionary."""
        result: dict[str, Any] = {
            "width": canvas.width,
            "height": canvas.current_height,
        }
        
        if self.mode == "runs":
            result["rows"] = self._to_runs(canvas)
        elif self.mode == "cells":
            result["cells"] = self._to_cells(canvas)
        elif self.mode == "sparse":
            result["cells"] = self._to_sparse(canvas)
        else:
            raise ValueError(f"Unknown mode: {self.mode}")
        
        return result
    
    def _color_name(self, code: int) -> str | int:
        """Convert color code to name if enabled."""
        if self.use_color_names:
            return COLOR_NAMES.get(code, code)
        return code
    
    def _to_runs(self, canvas: Canvas) -> list[dict]:
        """Convert to run-length encoded format."""
        rows = []
        
        for y, row in enumerate(canvas.rows()):
            runs = []
            current_run: dict | None = None
            
            # Find last non-empty cell
            last_col = -1
            for x, cell in enumerate(row):
                if cell.char != ' ' or cell.bg != 40:
                    last_col = x
            
            for x, cell in enumerate(row):
                if x > last_col and not self.include_defaults:
                    break
                
                # Check if we can extend current run
                if (current_run and 
                    cell.fg == current_run.get('_fg') and
                    cell.bg == current_run.get('_bg') and
                    cell.bold == current_run.get('_bold', False)):
                    current_run['chars'] += cell.char
                else:
                    # Start new run
                    if current_run:
                        # Clean up internal tracking fields
                        del current_run['_fg']
                        del current_run['_bg']
                        if '_bold' in current_run:
                            del current_run['_bold']
                        runs.append(current_run)
                    
                    current_run = {
                        'chars': cell.char,
                        'fg': self._color_name(cell.fg),
                        '_fg': cell.fg,
                        '_bg': cell.bg,
                    }
                    
                    # Only include non-default values
                    if cell.bg != 40:
                        current_run['bg'] = self._color_name(cell.bg)
                    if cell.bold:
                        current_run['bold'] = True
                        current_run['_bold'] = True
            
            if current_run:
                del current_run['_fg']
                del current_run['_bg']
                if '_bold' in current_run:
                    del current_run['_bold']
                runs.append(current_run)
            
            if runs:  # Only include non-empty rows
                rows.append({"y": y, "runs": runs})
        
        return rows
    
    def _to_cells(self, canvas: Canvas) -> list[dict]:
        """Convert to explicit cell format."""
        cells = []
        
        for y, row in enumerate(canvas.rows()):
            for x, cell in enumerate(row):
                if not self.include_defaults:
                    if cell.char == ' ' and cell.fg == 37 and cell.bg == 40 and not cell.bold:
                        continue
                
                cell_data = {
                    'x': x,
                    'y': y,
                    'char': cell.char,
                    'fg': self._color_name(cell.fg),
                }
                
                if cell.bg != 40:
                    cell_data['bg'] = self._color_name(cell.bg)
                if cell.bold:
                    cell_data['bold'] = True
                
                cells.append(cell_data)
        
        return cells
    
    def _to_sparse(self, canvas: Canvas) -> list[dict]:
        """Convert to sparse format (only non-default cells)."""
        # Same as cells but always excludes defaults
        old_include = self.include_defaults
        self.include_defaults = False
        result = self._to_cells(canvas)
        self.include_defaults = old_include
        return result


class JsonParser:
    """
    Parse JSON format back to a Canvas.
    
    Supports all output modes from JsonRenderer.
    """
    
    def parse(self, json_str: str) -> Canvas:
        """Parse JSON string to Canvas."""
        data = json.loads(json_str)
        return self.from_dict(data)
    
    def from_dict(self, data: dict) -> Canvas:
        """Convert dictionary to Canvas."""
        width = data.get('width', 80)
        canvas = Canvas(width=width)
        
        if 'rows' in data:
            self._parse_runs(canvas, data['rows'])
        elif 'cells' in data:
            self._parse_cells(canvas, data['cells'])
        
        return canvas
    
    def _parse_color(self, value: str | int, is_bg: bool = False) -> int:
        """Parse color value (name or code)."""
        if isinstance(value, int):
            return value
        
        value = value.lower()
        if is_bg:
            return NAME_TO_BG.get(value, 40)
        return NAME_TO_FG.get(value, 37)
    
    def _parse_runs(self, canvas: Canvas, rows: list[dict]) -> None:
        """Parse run-length encoded format."""
        for row_data in rows:
            y = row_data['y']
            x = 0
            
            for run in row_data.get('runs', []):
                chars = run.get('chars', '')
                fg = self._parse_color(run.get('fg', 'white'))
                bg = self._parse_color(run.get('bg', 'black'), is_bg=True)
                bold = run.get('bold', False)
                
                for char in chars:
                    canvas.put_char(x, y, char, fg, bg, bold)
                    x += 1
    
    def _parse_cells(self, canvas: Canvas, cells: list[dict]) -> None:
        """Parse explicit cell format."""
        for cell_data in cells:
            x = cell_data['x']
            y = cell_data['y']
            char = cell_data.get('char', ' ')
            fg = self._parse_color(cell_data.get('fg', 'white'))
            bg = self._parse_color(cell_data.get('bg', 'black'), is_bg=True)
            bold = cell_data.get('bold', False)
            
            canvas.put_char(x, y, char, fg, bg, bold)
