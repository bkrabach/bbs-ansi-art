"""CP437 (IBM PC) character set conversion."""

from bbs_ansi_art.core.constants import CP437_TO_UNICODE


# Build reverse mapping
UNICODE_TO_CP437: dict[str, int] = {
    char: idx for idx, char in enumerate(CP437_TO_UNICODE)
}


def cp437_to_unicode(data: bytes) -> str:
    """Convert CP437-encoded bytes to Unicode string."""
    return ''.join(CP437_TO_UNICODE[b] for b in data)


def unicode_to_cp437(text: str) -> bytes:
    """Convert Unicode string to CP437 bytes."""
    result = bytearray()
    for char in text:
        if char in UNICODE_TO_CP437:
            result.append(UNICODE_TO_CP437[char])
        elif ord(char) < 256:
            result.append(ord(char))
        else:
            result.append(0x3F)  # '?' for unmappable chars
    return bytes(result)
