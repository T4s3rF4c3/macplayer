#!/usr/bin/env python3
"""
Generate MacPlayer app icons.

Creates:
  assets/icon.icns  — macOS app icon (requires macOS + iconutil)
  assets/icon.ico   — Windows app icon

Usage:
  pip install Pillow
  python create_icon.py
"""

import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:
    print("Pillow is required:  pip install Pillow")
    sys.exit(1)

ASSETS  = Path("assets")
ICONSET = ASSETS / "MacPlayer.iconset"

# Icon sizes expected by macOS iconset
MAC_SIZES = [16, 32, 128, 256, 512]
# Sizes bundled into the Windows .ico
WIN_SIZES  = [16, 24, 32, 48, 64, 128, 256]


def draw_icon(size: int) -> Image.Image:
    """Draw the MacPlayer icon at the given pixel size."""
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    m = int(size * 0.06)

    # Dark rounded background
    draw.rounded_rectangle(
        [m, m, size - m - 1, size - m - 1],
        radius=int(size * 0.22),
        fill=(22, 22, 22, 255),
    )

    # Blue circle
    pad = int(size * 0.14)
    draw.ellipse(
        [pad, pad, size - pad - 1, size - pad - 1],
        fill=(0, 120, 212, 255),
    )

    # White play triangle (slightly right-of-centre)
    cx  = size / 2 + size * 0.04
    cy  = size / 2
    r   = size * 0.24
    tri = [
        (cx - r * 0.55, cy - r),
        (cx - r * 0.55, cy + r),
        (cx + r * 0.85, cy),
    ]
    draw.polygon(tri, fill=(255, 255, 255, 255))

    return img


def create_icns() -> bool:
    """Build assets/icon.icns using macOS iconutil."""
    if sys.platform != "darwin":
        print("  Skipping .icns — macOS only")
        return False
    if not shutil.which("iconutil"):
        print("  Skipping .icns — iconutil not found")
        return False

    ICONSET.mkdir(parents=True, exist_ok=True)

    for size in MAC_SIZES:
        draw_icon(size).save(ICONSET / f"icon_{size}x{size}.png")
        draw_icon(size * 2).save(ICONSET / f"icon_{size}x{size}@2x.png")

    out = ASSETS / "icon.icns"
    result = subprocess.run(
        ["iconutil", "-c", "icns", str(ICONSET), "-o", str(out)],
        capture_output=True, text=True,
    )
    shutil.rmtree(ICONSET, ignore_errors=True)

    if result.returncode == 0:
        print(f"  Created {out}")
        return True
    else:
        print(f"  iconutil error: {result.stderr.strip()}")
        return False


def create_ico() -> bool:
    """Build assets/icon.ico (all sizes in one file)."""
    images = [draw_icon(s) for s in WIN_SIZES]
    out    = ASSETS / "icon.ico"
    images[0].save(
        out,
        format="ICO",
        sizes=[(img.width, img.height) for img in images],
        append_images=images[1:],
    )
    print(f"  Created {out}")
    return True


if __name__ == "__main__":
    ASSETS.mkdir(exist_ok=True)
    print("Generating icons…")
    create_ico()
    create_icns()
    print("Done.")
