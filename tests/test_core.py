"""Tests for core data structures (no external files needed)."""

import pytest

from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.core.cell import Cell
from bbs_ansi_art.core.color import Color, ColorMode


class TestCell:
    """Tests for Cell dataclass."""

    def test_default_cell(self) -> None:
        cell = Cell()
        assert cell.char == ' '
        assert cell.fg == 37
        assert cell.bg == 40
        assert cell.bold is False
        assert cell.blink is False

    def test_cell_copy(self) -> None:
        cell = Cell(char='X', fg=31, bg=44, bold=True)
        copy = cell.copy()
        assert copy.char == 'X'
        assert copy.fg == 31
        assert copy.bg == 44
        assert copy.bold is True
        assert copy is not cell

    def test_is_default(self) -> None:
        assert Cell().is_default() is True
        assert Cell(char='X').is_default() is False
        assert Cell(fg=31).is_default() is False
        assert Cell(bold=True).is_default() is False


class TestCanvas:
    """Tests for Canvas."""

    def test_default_canvas(self) -> None:
        canvas = Canvas()
        assert canvas.width == 80
        assert canvas.current_height >= 1

    def test_canvas_custom_width(self) -> None:
        canvas = Canvas(width=132)
        assert canvas.width == 132

    def test_get_set_cell(self) -> None:
        canvas = Canvas(width=80)
        cell = Cell(char='A', fg=31)
        canvas.set(10, 5, cell)
        retrieved = canvas.get(10, 5)
        assert retrieved.char == 'A'
        assert retrieved.fg == 31

    def test_canvas_indexing(self) -> None:
        canvas = Canvas(width=80)
        canvas[5, 3] = Cell(char='B')
        assert canvas[5, 3].char == 'B'

    def test_put_char(self) -> None:
        canvas = Canvas(width=80)
        canvas.put_char(0, 0, 'X', fg=36, bold=True)
        cell = canvas.get(0, 0)
        assert cell.char == 'X'
        assert cell.fg == 36
        assert cell.bold is True

    def test_put_text(self) -> None:
        canvas = Canvas(width=80)
        canvas.put_text(5, 0, "Hello", fg=33)
        assert canvas.get(5, 0).char == 'H'
        assert canvas.get(9, 0).char == 'o'
        assert canvas.get(5, 0).fg == 33

    def test_auto_expand_rows(self) -> None:
        canvas = Canvas(width=80)
        canvas.put_char(0, 100, 'Z')
        assert canvas.current_height > 100
        assert canvas.get(0, 100).char == 'Z'

    def test_out_of_bounds_x(self) -> None:
        canvas = Canvas(width=80)
        with pytest.raises(IndexError):
            canvas.get(80, 0)
        with pytest.raises(IndexError):
            canvas.get(-1, 0)


class TestColor:
    """Tests for Color class."""

    def test_standard_colors(self) -> None:
        assert Color.BLACK.value == 0
        assert Color.RED.value == 1
        assert Color.WHITE.value == 7
        assert Color.BRIGHT_WHITE.value == 15

    def test_from_sgr(self) -> None:
        red_fg = Color.from_sgr(31)
        assert red_fg.mode == ColorMode.STANDARD_16
        assert red_fg.value == 1

        blue_bg = Color.from_sgr(44)
        assert blue_bg.value == 4

    def test_from_256(self) -> None:
        color = Color.from_256(196)
        assert color.mode == ColorMode.EXTENDED_256
        assert color.value == 196

    def test_from_rgb(self) -> None:
        color = Color.from_rgb(255, 128, 64)
        assert color.mode == ColorMode.TRUE_COLOR
        assert color.value == (255, 128, 64)

    def test_to_sgr_fg(self) -> None:
        assert Color.RED.to_sgr_fg() == "31"
        assert Color.BRIGHT_CYAN.to_sgr_fg() == "96"
        assert Color.from_256(196).to_sgr_fg() == "38;5;196"
        assert Color.from_rgb(255, 0, 0).to_sgr_fg() == "38;2;255;0;0"

    def test_to_sgr_bg(self) -> None:
        assert Color.BLUE.to_sgr_bg() == "44"
        assert Color.BRIGHT_GREEN.to_sgr_bg() == "102"
