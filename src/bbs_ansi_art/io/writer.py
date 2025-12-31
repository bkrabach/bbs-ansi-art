"""Save ANSI art files."""

from pathlib import Path
from typing import TYPE_CHECKING

from bbs_ansi_art.codec.cp437 import unicode_to_cp437
from bbs_ansi_art.sauce.writer import write_sauce
from bbs_ansi_art.sauce.record import SauceRecord, DataType, FileType

if TYPE_CHECKING:
    from bbs_ansi_art.core.document import AnsiDocument


def save(
    doc: "AnsiDocument",
    path: str | Path,
    include_sauce: bool = True,
) -> None:
    """
    Save an ANSI document to disk.
    
    Renders the canvas to CP437-encoded ANSI sequences and
    optionally appends SAUCE metadata.
    """
    path = Path(path)
    
    # Render to ANSI string
    from bbs_ansi_art.render.terminal import TerminalRenderer
    content = TerminalRenderer(reset_at_end=False).render(doc.canvas)
    
    # Convert to CP437 bytes
    data = unicode_to_cp437(content)
    
    # Add SAUCE if requested
    if include_sauce:
        sauce = doc.sauce or SauceRecord(
            title=path.stem[:35],
            data_type=DataType.CHARACTER,
            file_type=FileType.ANSI,
            tinfo1=doc.canvas.width,
            tinfo2=doc.canvas.current_height,
        )
        data = write_sauce(sauce, data)
    
    # Write to file
    with open(path, 'wb') as f:
        f.write(data)
