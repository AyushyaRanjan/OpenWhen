"""Generate the PWA icons with no third-party libraries.

Run once from the repo root:

    python tools/make_icons.py

It writes static/icon-192.png and static/icon-512.png. It is committed so the
binaries are reproducible, and it uses only the standard library (zlib, struct),
so it adds no runtime dependency. See AGENTS.md.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = BASE_DIR / "static"

BACKGROUND = (231, 163, 140)  # warm terracotta
HEART = (255, 250, 247)  # warm white

# The heart implicit curve is evaluated inside a box of about +/-1.2 units.
_HEART_EXTENT = 1.2
# Share of the icon the heart should span for the normal "any" icons.
_HEART_FRACTION = 0.62
# Maskable icons may be cropped to a circle by the launcher, so the heart has to
# sit well inside the safe zone. A smaller share guarantees that.
_MASKABLE_FRACTION = 0.48
# Sub-samples per axis for edge anti-aliasing.
_SUBSAMPLES = 4


def _inside_heart(x: float, y: float) -> bool:
    # Classic implicit heart: (x^2 + y^2 - 1)^3 - x^2 * y^3 <= 0
    a = x * x + y * y - 1.0
    return a * a * a - x * x * y * y * y <= 0.0


def _render(size: int, fraction: float) -> bytes:
    """Return raw RGBA scanlines (with filter byte) for one square icon."""
    cx = cy = (size - 1) / 2.0
    scale = (fraction * size) / (2.0 * _HEART_EXTENT)
    step = 1.0 / _SUBSAMPLES
    total = _SUBSAMPLES * _SUBSAMPLES

    rows = bytearray()
    for py in range(size):
        rows.append(0)  # PNG filter type 0 (None) for this scanline
        for px in range(size):
            hits = 0
            for sy in range(_SUBSAMPLES):
                ny = (cy - (py + (sy + 0.5) * step)) / scale
                for sx in range(_SUBSAMPLES):
                    nx = ((px + (sx + 0.5) * step) - cx) / scale
                    if _inside_heart(nx, ny):
                        hits += 1
            alpha = hits / total
            if alpha <= 0.0:
                rows += bytes((*BACKGROUND, 255))
            elif alpha >= 1.0:
                rows += bytes((*HEART, 255))
            else:
                blended = tuple(
                    round(BACKGROUND[i] * (1.0 - alpha) + HEART[i] * alpha)
                    for i in range(3)
                )
                rows += bytes((*blended, 255))
    return bytes(rows)


def _chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def write_png(path: Path, size: int, fraction: float) -> None:
    raw = _render(size, fraction)
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)  # 8-bit RGBA
    png = (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(raw, 9))
        + _chunk(b"IEND", b"")
    )
    path.write_bytes(png)
    print(f"wrote {path.relative_to(BASE_DIR)} ({size}x{size}, {len(png)} bytes)")


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_png(OUT_DIR / "icon-192.png", 192, _HEART_FRACTION)
    write_png(OUT_DIR / "icon-512.png", 512, _HEART_FRACTION)
    write_png(OUT_DIR / "icon-192-maskable.png", 192, _MASKABLE_FRACTION)
    write_png(OUT_DIR / "icon-512-maskable.png", 512, _MASKABLE_FRACTION)


if __name__ == "__main__":
    main()
