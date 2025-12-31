"""SAUCE record parsing."""

from datetime import datetime
from pathlib import Path

from bbs_ansi_art.sauce.record import SauceRecord, DataType, FileType


SAUCE_ID = b"SAUCE"
COMNT_ID = b"COMNT"
SAUCE_RECORD_SIZE = 128
COMMENT_LINE_SIZE = 64


def parse_sauce(path: str | Path) -> SauceRecord | None:
    """Parse SAUCE record from a file."""
    with open(path, "rb") as f:
        f.seek(0, 2)  # End of file
        file_size = f.tell()
        
        if file_size < SAUCE_RECORD_SIZE:
            return None
        
        # Read SAUCE record (last 128 bytes)
        f.seek(-SAUCE_RECORD_SIZE, 2)
        sauce_data = f.read(SAUCE_RECORD_SIZE)
        
        return parse_sauce_bytes(sauce_data, f, file_size)


def parse_sauce_bytes(
    data: bytes,
    file_handle=None,
    file_size: int = 0,
) -> SauceRecord | None:
    """Parse SAUCE record from raw bytes."""
    if len(data) < SAUCE_RECORD_SIZE:
        return None
    
    # Check for SAUCE signature
    if data[0:5] != SAUCE_ID:
        return None
    
    # Parse fields
    try:
        title = data[7:42].rstrip(b'\x00 ').decode('cp437', errors='replace')
        author = data[42:62].rstrip(b'\x00 ').decode('cp437', errors='replace')
        group = data[62:82].rstrip(b'\x00 ').decode('cp437', errors='replace')
        date_str = data[82:90].decode('cp437', errors='replace')
        
        # Parse date (YYYYMMDD format)
        date = None
        if len(date_str) == 8 and date_str.isdigit():
            try:
                date = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                pass
        
        data_type = DataType(data[94]) if data[94] < 9 else DataType.NONE
        file_type = FileType(data[95]) if data[95] < 9 else FileType.ASCII
        
        tinfo1 = int.from_bytes(data[96:98], 'little')
        tinfo2 = int.from_bytes(data[98:100], 'little')
        tinfo3 = int.from_bytes(data[100:102], 'little')
        tinfo4 = int.from_bytes(data[102:104], 'little')
        
        num_comments = data[104]
        tflags = data[105]
        tinfos = data[106:128].rstrip(b'\x00').decode('cp437', errors='replace')
        
        # Parse comments if present
        comments: list[str] = []
        if num_comments > 0 and file_handle is not None:
            comment_block_size = 5 + (num_comments * COMMENT_LINE_SIZE)
            comment_start = file_size - SAUCE_RECORD_SIZE - comment_block_size
            
            if comment_start >= 0:
                file_handle.seek(comment_start)
                comment_header = file_handle.read(5)
                
                if comment_header == COMNT_ID:
                    for _ in range(num_comments):
                        line = file_handle.read(COMMENT_LINE_SIZE)
                        comments.append(
                            line.rstrip(b'\x00 ').decode('cp437', errors='replace')
                        )
        
        return SauceRecord(
            title=title,
            author=author,
            group=group,
            date=date,
            file_size=int.from_bytes(data[90:94], 'little'),
            data_type=data_type,
            file_type=file_type,
            tinfo1=tinfo1,
            tinfo2=tinfo2,
            tinfo3=tinfo3,
            tinfo4=tinfo4,
            comments=comments,
            tflags=tflags,
            tinfos=tinfos,
        )
    except Exception:
        return None
