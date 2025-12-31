"""
bbs-ansi-art: Python library for ANSI art

Create, view, convert, and repair BBS-era ANSI artwork.

Quick Start:
    >>> import bbs_ansi_art as ansi
    >>> doc = ansi.load("artwork.ans")
    >>> print(doc.render())
    >>> doc.save_as_image("artwork.png")

Features:
    - Load and parse .ans, .asc, .diz files with CP437 encoding
    - Virtual 80-column terminal for authentic rendering
    - SAUCE metadata reading and writing
    - Render to terminal, image (PNG), HTML, or plain text
    - Create ANSI art programmatically with fluent builder API
    - Transform: resize, crop, decolor, merge
    - Repair common encoding and sequence issues
    - LLM integration tools for AI-generated art
"""

__version__ = "0.1.0"

# Core types
from bbs_ansi_art.core.cell import Cell
from bbs_ansi_art.core.canvas import Canvas
from bbs_ansi_art.core.color import Color
from bbs_ansi_art.core.document import AnsiDocument

# SAUCE metadata
from bbs_ansi_art.sauce.record import SauceRecord

# Convenience functions
from bbs_ansi_art.io.reader import load
from bbs_ansi_art.io.writer import save

# Creation
from bbs_ansi_art.create.builder import ArtBuilder

def create(width: int = 80) -> ArtBuilder:
    """Start creating new ANSI art with a fluent builder API."""
    return ArtBuilder(width)

__all__ = [
    # Version
    "__version__",
    # Core types
    "Cell",
    "Canvas", 
    "Color",
    "AnsiDocument",
    # SAUCE
    "SauceRecord",
    # I/O
    "load",
    "save",
    # Creation
    "create",
    "ArtBuilder",
]
