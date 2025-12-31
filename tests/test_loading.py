"""Tests for loading ANSI art files (requires external files)."""

import pytest
from pathlib import Path

import bbs_ansi_art as ansi


class TestWithoutExternalFiles:
    """Tests that work without external files."""

    def test_create_simple_art(self) -> None:
        """Test builder without external files."""
        art = (ansi.create(40)
            .fg(36).text("Hello")
            .newline()
            .fg(33).text("World")
            .build())

        assert art.current_height == 2
        assert art.get(0, 0).char == 'H'
        assert art.get(0, 0).fg == 36
        assert art.get(0, 1).char == 'W'
        assert art.get(0, 1).fg == 33

    def test_empty_canvas(self) -> None:
        """Test empty canvas behavior."""
        from bbs_ansi_art.core.canvas import Canvas
        canvas = Canvas(width=80)
        assert canvas.current_height >= 1
        assert canvas.width == 80


@pytest.mark.external
class TestExternalFiles:
    """Tests that require external .ans files."""

    def test_load_single_file(self, single_ans_file: Path) -> None:
        """Basic load test."""
        doc = ansi.load(single_ans_file)
        assert doc.canvas.current_height > 0
        assert doc.canvas.width > 0

    def test_load_file_has_content(self, single_ans_file: Path) -> None:
        """Verify loaded file has actual content."""
        doc = ansi.load(single_ans_file)
        # Should have at least some non-space characters
        has_content = False
        for row in doc.canvas.rows():
            for cell in row:
                if cell.char != ' ':
                    has_content = True
                    break
            if has_content:
                break
        assert has_content, "Loaded file should have content"

    def test_render_roundtrip(self, single_ans_file: Path) -> None:
        """Load, render, verify output is valid."""
        doc = ansi.load(single_ans_file)
        rendered = doc.render()
        assert isinstance(rendered, str)
        assert len(rendered) > 0

    def test_render_to_text(self, single_ans_file: Path) -> None:
        """Test plain text rendering."""
        doc = ansi.load(single_ans_file)
        text = doc.render_to_text()
        assert isinstance(text, str)
        # Plain text should not contain ANSI escapes
        assert '\x1b[' not in text

    def test_render_to_html(self, single_ans_file: Path) -> None:
        """Test HTML rendering."""
        doc = ansi.load(single_ans_file)
        html = doc.render_to_html()
        assert isinstance(html, str)
        assert '<pre' in html
        assert '</pre>' in html


@pytest.mark.external
class TestSauceMetadata:
    """Tests for SAUCE metadata extraction."""

    def test_sauce_extraction(self, sample_ans_files: list[Path]) -> None:
        """Test SAUCE metadata extraction on files that have it."""
        sauce_found = 0
        for path in sample_ans_files:
            doc = ansi.load(path)
            if doc.sauce:
                sauce_found += 1
                # If SAUCE exists, at least one field should be set
                has_field = (
                    doc.sauce.title or
                    doc.sauce.author or
                    doc.sauce.group or
                    doc.sauce.tinfo1 > 0
                )
                assert has_field, f"SAUCE record in {path.name} should have data"

        # Just report - don't require all files have SAUCE
        print(f"\nFound SAUCE in {sauce_found}/{len(sample_ans_files)} files")


@pytest.mark.external
@pytest.mark.slow
class TestAllFiles:
    """Parametrized tests across all sample files."""

    def test_load_all_files(self, ans_file: Path) -> None:
        """Load test across all sample files."""
        doc = ansi.load(ans_file)
        assert doc is not None
        assert doc.canvas is not None
