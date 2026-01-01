"""Tests for the repair/cleaner module.

Verifies that cleaning preserves visual output while removing problematic sequences.
"""

import pytest
from pathlib import Path

import bbs_ansi_art as ansi
from bbs_ansi_art.repair import clean_bytes, clean_file


class TestCleanBytes:
    """Test clean_bytes function."""
    
    def test_removes_window_manipulation(self):
        """ESC[...t sequences should be removed."""
        data = b'\x1b[0;0;0t\x1b[31mHello\x1b[0m'
        cleaned, result = clean_bytes(data)
        
        assert b'\x1b[0;0;0t' not in cleaned
        assert b'\x1b[31mHello' in cleaned
        assert result.sequences_removed >= 1
        assert result.details['window_manip'] == 1
    
    def test_removes_mode_changes(self):
        """ESC[?...h/l sequences should be removed."""
        data = b'\x1b[?7h\x1b[31mHello\x1b[0m'
        cleaned, result = clean_bytes(data)
        
        assert b'\x1b[?7h' not in cleaned
        assert b'\x1b[31mHello' in cleaned
        assert result.details['mode_changes'] == 1
    
    def test_preserves_clear_screen(self):
        """ESC[2J should be PRESERVED (affects cursor position)."""
        data = b'\x1b[2J\x1b[31mHello\x1b[0m'
        cleaned, result = clean_bytes(data)
        
        # Clear screen is kept - it affects cursor positioning
        assert b'\x1b[2J' in cleaned
        assert b'\x1b[31mHello' in cleaned
    
    def test_preserves_cursor_save_restore(self):
        """ESC[s and ESC[u should be PRESERVED (they affect positioning)."""
        data = b'\x1b[s\x1b[31mHello\x1b[u\x1b[0m'
        cleaned, result = clean_bytes(data)
        
        # These are kept because they affect visual layout
        assert b'\x1b[s' in cleaned
        assert b'\x1b[u' in cleaned
    
    def test_preserves_cr_characters(self):
        """CR characters should be PRESERVED (parser uses them for positioning)."""
        data = b'Hello\r\nWorld\r\n'
        cleaned, result = clean_bytes(data)
        
        # CR is kept - parser treats it as cursor positioning
        assert b'\r' in cleaned
    
    def test_removes_redundant_resets(self):
        """Multiple ESC[0m in a row should be collapsed."""
        data = b'\x1b[31mHello\x1b[0m\x1b[0m\x1b[0mWorld'
        cleaned, result = clean_bytes(data)
        
        # Should have at most one reset sequence in that spot
        assert cleaned.count(b'\x1b[0m\x1b[0m') == 0
        assert result.details['redundant_resets'] >= 1
    
    def test_preserves_colors(self):
        """SGR color sequences should be preserved."""
        data = b'\x1b[1;31mBold Red\x1b[0m\x1b[34mBlue\x1b[0m'
        cleaned, result = clean_bytes(data)
        
        assert b'\x1b[1;31m' in cleaned
        assert b'\x1b[34m' in cleaned
    
    def test_preserves_cursor_positioning(self):
        """Cursor movement sequences should be preserved."""
        data = b'\x1b[10;20H\x1b[5CText\x1b[2A'
        cleaned, result = clean_bytes(data)
        
        assert b'\x1b[10;20H' in cleaned  # Cursor position
        assert b'\x1b[5C' in cleaned       # Cursor forward
        assert b'\x1b[2A' in cleaned       # Cursor up
    
    def test_preserves_sauce(self):
        """SAUCE metadata should be preserved exactly."""
        art = b'\x1b[31mHello\x1b[0m'
        sauce = b'\x1aSAUCE00Test Title Here'
        data = art + sauce
        
        cleaned, result = clean_bytes(data)
        
        assert cleaned.endswith(sauce)
    
    def test_adds_final_reset(self):
        """Should add ESC[0m at end if not present."""
        data = b'\x1b[31mHello'  # No reset at end
        cleaned, result = clean_bytes(data)
        
        # Should end with reset before final newline
        assert b'\x1b[0m\n' in cleaned or cleaned.endswith(b'\x1b[0m')
        assert result.details.get('reset_added', 0) == 1
    
    def test_preserves_line_endings(self):
        """Should preserve existing line ending structure."""
        # File with newline stays with newline
        data_with_nl = b'\x1b[31mHello\x1b[0m\n'
        cleaned, _ = clean_bytes(data_with_nl)
        assert cleaned.endswith(b'\n')
        
        # File without newline stays without (to preserve exact output)
        data_no_nl = b'\x1b[31mHello\x1b[0m'
        cleaned, _ = clean_bytes(data_no_nl)
        assert not cleaned.endswith(b'\n')


class TestVisualEquivalence:
    """Test that cleaning preserves visual output."""
    
    @pytest.fixture
    def sample_files(self):
        """Find sample .ANS files in Downloads."""
        downloads = Path.home() / "Downloads"
        files = list(downloads.glob("*.ANS")) + list(downloads.glob("*.ans"))
        return [f for f in files if f.stat().st_size < 50000]  # Skip huge files
    
    def test_render_equivalence(self, sample_files):
        """Cleaned files should render identically to originals."""
        if not sample_files:
            pytest.skip("No sample .ANS files found in ~/Downloads")
        
        for filepath in sample_files[:5]:  # Test first 5 files
            # Load and render original
            original_doc = ansi.load(filepath)
            original_render = original_doc.render()
            
            # Clean the file data
            original_data = filepath.read_bytes()
            cleaned_data, result = clean_bytes(original_data)
            
            # Load and render cleaned version
            # Write to temp location to load
            temp_path = filepath.with_suffix('.tmp')
            try:
                temp_path.write_bytes(cleaned_data)
                cleaned_doc = ansi.load(temp_path)
                cleaned_render = cleaned_doc.render()
                
                # Compare renders (strip trailing whitespace for comparison)
                orig_lines = [l.rstrip() for l in original_render.split('\n')]
                clean_lines = [l.rstrip() for l in cleaned_render.split('\n')]
                
                # They should be identical
                assert orig_lines == clean_lines, (
                    f"Render mismatch for {filepath.name}:\n"
                    f"Original lines: {len(orig_lines)}, Cleaned lines: {len(clean_lines)}"
                )
            finally:
                if temp_path.exists():
                    temp_path.unlink()
    
    def test_canvas_equivalence(self, sample_files):
        """Cleaned files should produce identical canvas content."""
        if not sample_files:
            pytest.skip("No sample .ANS files found in ~/Downloads")
        
        for filepath in sample_files[:5]:
            original_doc = ansi.load(filepath)
            
            # Clean and reload
            original_data = filepath.read_bytes()
            cleaned_data, _ = clean_bytes(original_data)
            
            temp_path = filepath.with_suffix('.tmp')
            try:
                temp_path.write_bytes(cleaned_data)
                cleaned_doc = ansi.load(temp_path)
                
                if original_doc.canvas and cleaned_doc.canvas:
                    # Compare dimensions
                    assert original_doc.canvas.width == cleaned_doc.canvas.width
                    
                    orig_height = original_doc.canvas.height or 0
                    clean_height = cleaned_doc.canvas.height or 0
                    assert orig_height == clean_height, f"Height mismatch: {orig_height} vs {clean_height}"
                    
                    # Compare cell content
                    for y in range(min(orig_height, 100)):
                        for x in range(original_doc.canvas.width):
                            orig_cell = original_doc.canvas.get(x, y)
                            clean_cell = cleaned_doc.canvas.get(x, y)
                            
                            assert orig_cell.char == clean_cell.char, (
                                f"Char mismatch at ({x},{y}) in {filepath.name}"
                            )
                            assert orig_cell.fg == clean_cell.fg, (
                                f"FG mismatch at ({x},{y}) in {filepath.name}"
                            )
                            assert orig_cell.bg == clean_cell.bg, (
                                f"BG mismatch at ({x},{y}) in {filepath.name}"
                            )
            finally:
                if temp_path.exists():
                    temp_path.unlink()
