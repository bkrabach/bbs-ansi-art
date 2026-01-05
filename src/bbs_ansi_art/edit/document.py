"""EditableDocument - High-level editable document wrapper.

This module provides EditableDocument, which wraps EditableCanvas with
format detection and file I/O. It bridges AnsiDocument (the read-only
representation) with editable canvas implementations.
"""

from __future__ import annotations

from enum import Enum, auto
from pathlib import Path
from typing import TYPE_CHECKING

from bbs_ansi_art.core.document import AnsiDocument
from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.edit.editable import EditableCanvas, EditMode, ColorMode
from bbs_ansi_art.edit.cell_canvas import CellEditableCanvas
from bbs_ansi_art.edit.pixel_canvas import PixelEditableCanvas

if TYPE_CHECKING:
    from bbs_ansi_art.sauce.record import SauceRecord


class DocumentFormat(Enum):
    """Document format enumeration."""
    ANS = auto()  # Classic .ANS (CP437, 16-color)
    ART = auto()  # Modern .art (UTF-8, true-color)


class EditableDocument:
    """High-level editable document wrapper.
    
    Combines AnsiDocument with an appropriate EditableCanvas based on
    the document format. Handles format detection, canvas creation,
    and file I/O operations.
    
    Attributes:
        _document: The underlying AnsiDocument
        _path: File path (if loaded from or saved to disk)
        _format: Document format (ANS or ART)
        _canvas: The editable canvas for this document
    
    Example:
        # Load and edit an existing file
        doc = EditableDocument.load("artwork.ans")
        doc.canvas.draw_point(10, 5, (255, 0, 0), context)
        doc.save("artwork_modified.ans")
        
        # Create a new document
        doc = EditableDocument.new_ans(80, 25)
        doc.canvas.put_text(0, 0, "Hello ANSI!")
        doc.save("hello.ans")
    """
    
    def __init__(
        self,
        document: AnsiDocument,
        format: DocumentFormat | None = None,
    ) -> None:
        """Initialize with an existing AnsiDocument.
        
        Args:
            document: The AnsiDocument to wrap
            format: Optional format override (auto-detected if not provided)
        """
        self._document = document
        self._path: Path | None = document.source_path
        self._format = format or self._detect_format()
        self._canvas = self._create_canvas()
    
    # -------------------------------------------------------------------------
    # Class Methods - Factory constructors
    # -------------------------------------------------------------------------
    
    @classmethod
    def load(cls, path: Path | str) -> EditableDocument:
        """Load an editable document from file.
        
        Args:
            path: Path to the file (.ans or .art)
            
        Returns:
            EditableDocument ready for editing
            
        Example:
            doc = EditableDocument.load("artwork.ans")
        """
        from bbs_ansi_art import load
        doc = load(path)
        return cls(doc)
    
    @classmethod
    def new_ans(cls, width: int = 80, height: int = 25) -> EditableDocument:
        """Create a new .ANS document.
        
        Creates an empty document in classic .ANS format with 16-color
        palette and CP437 encoding.
        
        Args:
            width: Canvas width in columns (default: 80)
            height: Canvas height in rows (default: 25)
            
        Returns:
            New EditableDocument in ANS format
            
        Example:
            doc = EditableDocument.new_ans(80, 50)
        """
        canvas = Canvas(width=width, height=height)
        # Ensure canvas has the specified height
        if height > 0:
            canvas.ensure_row(height - 1)
        
        document = AnsiDocument(
            canvas=canvas,
            encoding="cp437",
        )
        return cls(document, format=DocumentFormat.ANS)
    
    @classmethod
    def new_art(cls, width: int = 80, pixel_height: int = 50) -> EditableDocument:
        """Create a new .art document.
        
        Creates an empty document in modern .art format with true-color
        support and UTF-8 encoding.
        
        Args:
            width: Canvas width in columns (default: 80)
            pixel_height: Canvas height in pixels (default: 50)
                         Note: Each terminal row = 2 pixels
            
        Returns:
            New EditableDocument in ART format
            
        Example:
            doc = EditableDocument.new_art(80, 100)  # 80x50 terminal cells
        """
        # Create an empty AnsiDocument with raw_text marker
        document = AnsiDocument(
            canvas=Canvas(width=width),
            encoding="utf-8",
            raw_text="",  # Empty raw_text signals .art format
        )
        
        result = cls(document, format=DocumentFormat.ART)
        # Replace canvas with properly sized PixelEditableCanvas
        result._canvas = PixelEditableCanvas(width, pixel_height)
        return result
    
    # -------------------------------------------------------------------------
    # Format Detection
    # -------------------------------------------------------------------------
    
    def _detect_format(self) -> DocumentFormat:
        """Auto-detect format from extension and content.
        
        Detection priority:
        1. If raw_text is set, it's an .art file
        2. If path has .art extension, it's an .art file
        3. Otherwise, assume .ANS format
        
        Returns:
            Detected DocumentFormat
        """
        # raw_text indicates true-color .art format
        if self._document.raw_text is not None:
            return DocumentFormat.ART
        
        # Check file extension
        if self._path and self._path.suffix.lower() == '.art':
            return DocumentFormat.ART
        
        # Default to classic .ANS format
        return DocumentFormat.ANS
    
    def _create_canvas(self) -> EditableCanvas:
        """Create appropriate canvas for the document format.
        
        Returns:
            EditableCanvas implementation matching the format
        """
        if self._format == DocumentFormat.ART:
            if self._document.raw_text:
                return PixelEditableCanvas.from_raw_text(self._document.raw_text)
            # Empty .art file - create default size
            return PixelEditableCanvas(80, 50)
        
        # .ANS format - wrap the existing canvas
        return CellEditableCanvas(self._document.canvas)
    
    # -------------------------------------------------------------------------
    # Properties
    # -------------------------------------------------------------------------
    
    @property
    def format(self) -> DocumentFormat:
        """Document format (ANS or ART)."""
        return self._format
    
    @property
    def canvas(self) -> EditableCanvas:
        """The editable canvas for this document."""
        return self._canvas
    
    @property
    def edit_mode(self) -> EditMode:
        """Suggested edit mode based on format.
        
        Returns:
            PIXEL for .art files, CELL for .ANS files
        """
        if self._format == DocumentFormat.ART:
            return EditMode.PIXEL
        return EditMode.CELL
    
    @property
    def color_mode(self) -> ColorMode:
        """Color mode for this document.
        
        Returns:
            TRUE_COLOR for .art files, INDEXED_16 for .ANS files
        """
        if self._format == DocumentFormat.ART:
            return ColorMode.TRUE_COLOR
        return ColorMode.INDEXED_16
    
    @property
    def width(self) -> int:
        """Document width in columns."""
        return self._canvas.width
    
    @property
    def height(self) -> int:
        """Document height in native units.
        
        For .ANS files: height in terminal rows
        For .art files: height in pixels
        """
        return self._canvas.height
    
    @property
    def terminal_height(self) -> int:
        """Document height in terminal rows.
        
        For .ANS files: same as height
        For .art files: pixel_height // 2
        """
        if isinstance(self._canvas, PixelEditableCanvas):
            return self._canvas.terminal_height
        return self._canvas.height
    
    @property
    def path(self) -> Path | None:
        """File path (if loaded from or saved to disk)."""
        return self._path
    
    @property
    def title(self) -> str:
        """Document title from SAUCE metadata or filename."""
        return self._document.title
    
    @property
    def author(self) -> str:
        """Document author from SAUCE metadata."""
        return self._document.author
    
    @property
    def group(self) -> str:
        """Document group from SAUCE metadata."""
        return self._document.group
    
    @property
    def sauce(self) -> SauceRecord | None:
        """SAUCE metadata record (if present)."""
        return self._document.sauce
    
    @sauce.setter
    def sauce(self, value: SauceRecord | None) -> None:
        """Set SAUCE metadata record."""
        self._document.sauce = value
    
    # -------------------------------------------------------------------------
    # Methods
    # -------------------------------------------------------------------------
    
    def render(self) -> str:
        """Render document to ANSI escape sequence string.
        
        Returns:
            String with ANSI escape sequences for terminal display
        """
        return self._canvas.render()
    
    def save(self, path: Path | str | None = None, include_sauce: bool = True) -> None:
        """Save document to file.
        
        Args:
            path: Destination path (uses existing path if not provided)
            include_sauce: Whether to include SAUCE metadata
            
        Raises:
            ValueError: If no path provided and document has no existing path
        """
        save_path = Path(path) if path else self._path
        if save_path is None:
            raise ValueError("No path specified and document has no existing path")
        
        # Update document state from canvas
        self._sync_canvas_to_document()
        
        # Determine format from save path if different from current
        save_format = self._format
        if save_path.suffix.lower() == '.art':
            save_format = DocumentFormat.ART
        elif save_path.suffix.lower() == '.ans':
            save_format = DocumentFormat.ANS
        
        # Save based on format
        if save_format == DocumentFormat.ART:
            self._save_art(save_path)
        else:
            self._save_ans(save_path, include_sauce)
        
        # Update path and clear modified flag
        self._path = save_path
        self._canvas.modified = False
    
    def _save_ans(self, path: Path, include_sauce: bool) -> None:
        """Save as .ANS format.
        
        Args:
            path: Destination path
            include_sauce: Whether to include SAUCE metadata
        """
        # Get bytes from canvas
        content = self._canvas.to_bytes()
        
        # Add SAUCE record if requested
        if include_sauce and self._document.sauce:
            from bbs_ansi_art.sauce.record import SauceRecord
            sauce_bytes = self._document.sauce.to_bytes()
            content = content + b'\x1a' + sauce_bytes
        
        path.write_bytes(content)
    
    def _save_art(self, path: Path) -> None:
        """Save as .art format.
        
        Args:
            path: Destination path
        """
        content = self._canvas.render()
        path.write_text(content, encoding='utf-8')
    
    def _sync_canvas_to_document(self) -> None:
        """Sync canvas state back to the underlying document."""
        if isinstance(self._canvas, CellEditableCanvas):
            # Update document's canvas reference
            self._document.canvas = self._canvas.get_canvas()
        elif isinstance(self._canvas, PixelEditableCanvas):
            # Update raw_text for .art format
            self._document.raw_text = self._canvas.render()
    
    def is_modified(self) -> bool:
        """Check if document has unsaved changes.
        
        Returns:
            True if canvas has been modified since last save
        """
        return self._canvas.modified
    
    def mark_saved(self) -> None:
        """Mark document as saved (clear modified flag)."""
        self._canvas.modified = False
        if isinstance(self._canvas, PixelEditableCanvas):
            self._canvas.clear_modified()
    
    # -------------------------------------------------------------------------
    # Utility Methods
    # -------------------------------------------------------------------------
    
    def get_document(self) -> AnsiDocument:
        """Get the underlying AnsiDocument.
        
        Note: Call _sync_canvas_to_document() first if you need
        the document to reflect recent canvas changes.
        
        Returns:
            The wrapped AnsiDocument
        """
        return self._document
    
    def resize(self, width: int, height: int) -> None:
        """Resize the document canvas.
        
        Args:
            width: New width in columns
            height: New height (rows for .ANS, pixels for .art)
        """
        if isinstance(self._canvas, PixelEditableCanvas):
            self._canvas.resize(width, height)
        else:
            self._canvas.resize(width, height)
    
    def __repr__(self) -> str:
        return (
            f"EditableDocument("
            f"format={self._format.name}, "
            f"width={self.width}, "
            f"height={self.height}, "
            f"modified={self.is_modified()}, "
            f"path={self._path})"
        )
