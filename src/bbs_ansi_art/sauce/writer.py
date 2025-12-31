"""SAUCE record writing."""

from datetime import datetime

from bbs_ansi_art.sauce.record import SauceRecord


SAUCE_ID = b"SAUCE"
SAUCE_VERSION = b"00"
COMNT_ID = b"COMNT"
COMMENT_LINE_SIZE = 64


def sauce_to_bytes(record: SauceRecord) -> bytes:
    """Serialize a SAUCE record to bytes."""
    # Start with SAUCE signature and version
    data = bytearray(SAUCE_ID + SAUCE_VERSION)
    
    # Title (35 bytes, padded with spaces)
    title = record.title.encode('cp437', errors='replace')[:35]
    data.extend(title.ljust(35, b' '))
    
    # Author (20 bytes)
    author = record.author.encode('cp437', errors='replace')[:20]
    data.extend(author.ljust(20, b' '))
    
    # Group (20 bytes)
    group = record.group.encode('cp437', errors='replace')[:20]
    data.extend(group.ljust(20, b' '))
    
    # Date (8 bytes, YYYYMMDD)
    if record.date:
        date_str = record.date.strftime("%Y%m%d")
    else:
        date_str = datetime.now().strftime("%Y%m%d")
    data.extend(date_str.encode('ascii'))
    
    # File size (4 bytes, little-endian)
    data.extend(record.file_size.to_bytes(4, 'little'))
    
    # Data type and file type (1 byte each)
    data.append(record.data_type)
    data.append(record.file_type)
    
    # TInfo fields (2 bytes each, little-endian)
    data.extend(record.tinfo1.to_bytes(2, 'little'))
    data.extend(record.tinfo2.to_bytes(2, 'little'))
    data.extend(record.tinfo3.to_bytes(2, 'little'))
    data.extend(record.tinfo4.to_bytes(2, 'little'))
    
    # Number of comments
    num_comments = min(len(record.comments), 255)
    data.append(num_comments)
    
    # TFlags
    data.append(record.tflags)
    
    # TInfoS (22 bytes)
    tinfos = record.tinfos.encode('cp437', errors='replace')[:22]
    data.extend(tinfos.ljust(22, b'\x00'))
    
    return bytes(data)


def write_sauce(record: SauceRecord, data: bytes) -> bytes:
    """Append SAUCE record to data, including comments if present."""
    result = bytearray(data)
    
    # Add EOF marker
    result.append(0x1A)
    
    # Add comments if present
    if record.comments:
        result.extend(COMNT_ID)
        for comment in record.comments[:255]:
            line = comment.encode('cp437', errors='replace')[:COMMENT_LINE_SIZE]
            result.extend(line.ljust(COMMENT_LINE_SIZE, b' '))
    
    # Add SAUCE record
    result.extend(sauce_to_bytes(record))
    
    return bytes(result)
