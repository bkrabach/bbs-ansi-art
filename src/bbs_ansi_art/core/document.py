"""AnsiDocument - high-level representation of an ANSI art file."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from bbs_ansi_art.core.canvas import Canvas

if TYPE_CHECKING:
    from bbs_ansi_art.sauce.record import SauceRecord


@dataclass
class AnsiDocument:
    """
    Represents a complete ANSI artwork with metadata.
    
    Combines Canvas + SAUCE metadata + source info into a single
    high-level object for working with ANSI art files.
    
    Supports two formats:
    - Classic .ANS (CP437 encoding, 16-color)
    - Modern .art (UTF-8 encoding, true-color)
    """
    canvas: Canvas = field(default_factory=Canvas)
    sauce: "SauceRecord | None" = None
    source_path: Path | None = None
    encoding: str = "cp437"
    raw_text: str | None = None  # Original text for .art files (preserves true color)
    
    @classmethod
    def load(cls, path: str | Path) -> "AnsiDocument":
        """Load an ANSI file from disk."""
        from bbs_ansi_art.io.reader import load
        return load(path)
    
    def save(self, path: str | Path, include_sauce: bool = True) -> None:
        """Save this document to disk."""
        from bbs_ansi_art.io.writer import save
        save(self, path, include_sauce=include_sauce)
    
    def render(self) -> str:
        """Render to terminal-compatible ANSI string.
        
        For .art files (UTF-8/true-color), returns the original text
        to preserve full color fidelity. For .ANS files, renders the
        canvas with 16-color ANSI codes.
        """
        # For .art files, use the original true-color text
        if self.raw_text is not None:
            return self.raw_text.rstrip('\n')
        
        # For .ANS files, render from canvas
        from bbs_ansi_art.render.terminal import TerminalRenderer
        return TerminalRenderer().render(self.canvas)
    
    def render_to_html(self, **kwargs) -> str:
        """Render to HTML."""
        from bbs_ansi_art.render.html import HtmlRenderer
        return HtmlRenderer(**kwargs).render(self.canvas)
    
    def render_to_text(self) -> str:
        """Render to plain text (no colors)."""
        from bbs_ansi_art.render.text import TextRenderer
        return TextRenderer().render(self.canvas)
    
    @property
    def title(self) -> str:
        """Get title from SAUCE or filename."""
        if self.sauce and self.sauce.title:
            return self.sauce.title
        if self.source_path:
            return self.source_path.stem
        return "Untitled"
    
    @property
    def author(self) -> str:
        """Get author from SAUCE."""
        return self.sauce.author if self.sauce else ""
    
    @property
    def group(self) -> str:
        """Get group from SAUCE."""
        return self.sauce.group if self.sauce else ""
    
    @property
    def width(self) -> int:
        """Get width (from SAUCE or canvas)."""
        if self.sauce and self.sauce.tinfo1 > 0:
            return self.sauce.tinfo1
        return self.canvas.width
    
    @property
    def height(self) -> int:
        """Get height (from canvas)."""
        return self.canvas.current_height
