"""SAUCE record data structure."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum


class DataType(IntEnum):
    """SAUCE data types."""
    NONE = 0
    CHARACTER = 1
    BITMAP = 2
    VECTOR = 3
    AUDIO = 4
    BINARYTEXT = 5
    XBIN = 6
    ARCHIVE = 7
    EXECUTABLE = 8


class FileType(IntEnum):
    """SAUCE file types for CHARACTER data type."""
    ASCII = 0
    ANSI = 1
    ANSIMATION = 2
    RIP = 3
    PCBOARD = 4
    AVATAR = 5
    HTML = 6
    SOURCE = 7
    TUNDRA = 8


@dataclass
class SauceRecord:
    """
    SAUCE (Standard Architecture for Universal Comment Extensions) record.
    
    SAUCE is a metadata format used by the BBS/ANSI art scene to embed
    information about artwork in files. See: https://www.acid.org/info/sauce/sauce.htm
    """
    title: str = ""
    author: str = ""
    group: str = ""
    date: datetime | None = None
    file_size: int = 0
    data_type: DataType = DataType.CHARACTER
    file_type: FileType = FileType.ANSI
    tinfo1: int = 0  # Width for character data
    tinfo2: int = 0  # Height for character data  
    tinfo3: int = 0
    tinfo4: int = 0
    comments: list[str] = field(default_factory=list)
    tflags: int = 0
    tinfos: str = ""
    
    @classmethod
    def from_bytes(cls, data: bytes) -> "SauceRecord | None":
        """Parse a SAUCE record from raw bytes."""
        from bbs_ansi_art.sauce.reader import parse_sauce_bytes
        return parse_sauce_bytes(data)
    
    def to_bytes(self) -> bytes:
        """Serialize this record to bytes."""
        from bbs_ansi_art.sauce.writer import sauce_to_bytes
        return sauce_to_bytes(self)
    
    @property
    def width(self) -> int:
        """Get width (alias for tinfo1)."""
        return self.tinfo1
    
    @property
    def height(self) -> int:
        """Get height (alias for tinfo2)."""
        return self.tinfo2
    
    def __str__(self) -> str:
        """Human-readable representation."""
        parts = []
        if self.title:
            parts.append(f"Title: {self.title}")
        if self.author:
            parts.append(f"Author: {self.author}")
        if self.group:
            parts.append(f"Group: {self.group}")
        if self.date:
            parts.append(f"Date: {self.date.strftime('%Y-%m-%d')}")
        if self.tinfo1:
            parts.append(f"Width: {self.tinfo1}")
        if self.tinfo2:
            parts.append(f"Height: {self.tinfo2}")
        return "\n".join(parts) if parts else "(No SAUCE metadata)"
