"""A small PNG writer (standard library only): 8-bit RGB or RGBA, no interlace.

The theme images are flat colours, soft gradients and a dot pattern, so a plain zlib stream is
small enough and the build needs no imaging library. Output is deterministic: the same pixels
give the same bytes.
"""

from __future__ import annotations

import struct
import zlib


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def encode(width: int, height: int, rows: list[bytes] | list[bytearray], alpha: bool = False) -> bytes:
    """Encode rows of packed pixels (3 or 4 bytes each) as a PNG file."""
    channels = 4 if alpha else 3
    if width < 1 or height < 1 or len(rows) != height:
        raise ValueError("image size and row count do not match")
    raw = bytearray()
    for row in rows:
        if len(row) != width * channels:
            raise ValueError("row length does not match the width")
        raw.append(0)  # filter type None
        raw += row
    header = struct.pack(">IIBBBBB", width, height, 8, 6 if alpha else 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + _chunk(b"IEND", b""))


def solid(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    row = bytes(rgb) * width
    return encode(width, height, [row] * height)


def read_size(data: bytes) -> tuple[int, int]:
    """Width and height of a PNG file (raises ValueError for anything else)."""
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError("not a PNG file")
    return struct.unpack(">II", data[16:24])
