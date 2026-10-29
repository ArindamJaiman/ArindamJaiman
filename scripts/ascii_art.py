"""
Turn the profile avatar (white blackletter "A" on black) into ASCII art.

Instead of a brightness ramp, every character cell is compared against
rendered glyphs and the closest shape wins — so edges come out as
_ - / \\ ' ^ ` and solid strokes as @.

    pip install pillow numpy
    python scripts/ascii_art.py                        # fetches github.com/ArindamJaiman.png
    python scripts/ascii_art.py avatar.png --cols 46 --out assets/blackletter-a.txt

The result is committed as plain text; scripts/neofetch.py reads it, so this
only needs re-running when the avatar changes.
"""

import argparse
import io
import os
import sys
import urllib.request

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

CHARSET = " _-/\\|()'.,`^@"
ASPECT = 2.05          # line-height / char-width of the SVG grid in neofetch.py
CELL_W, CELL_H = 12, 25  # resolution each cell is compared at

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\consola.ttf",
    "/System/Library/Fonts/Menlo.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
]


def load_avatar(source):
    """Read the avatar from a path or URL and crop it to the letter."""
    if source.startswith("http"):
        with urllib.request.urlopen(source) as resp:
            source = io.BytesIO(resp.read())
    im = Image.open(source).convert("L")
    a = np.asarray(im)
    ys, xs = np.where(a > 127)
    pad = 6
    return im.crop((xs.min() - pad, ys.min() - pad, xs.max() + pad, ys.max() + pad))


def blur(a, radius=1.0):
    im = Image.fromarray((np.clip(a, 0, 1) * 255).astype(np.uint8))
    return np.asarray(im.filter(ImageFilter.GaussianBlur(radius)), dtype=np.float32) / 255


def glyph_bitmaps(font_path):
    """Render each candidate character into a CELL_W x CELL_H bitmap."""
    font = ImageFont.truetype(font_path, 40)
    adv = font.getlength("M")
    line_h = adv * ASPECT
    ascent, descent = font.getmetrics()
    glyphs = {}
    for ch in CHARSET:
        im = Image.new("L", (round(adv), round(line_h)), 0)
        ImageDraw.Draw(im).text((0, (line_h - ascent - descent) / 2), ch, font=font, fill=255)
        bitmap = np.asarray(im.resize((CELL_W, CELL_H), Image.LANCZOS), dtype=np.float32) / 255
        glyphs[ch] = blur(bitmap)
    return glyphs


def to_ascii(im, cols, font_path):
    w, h = im.size
    rows = round(cols * (h / w) / ASPECT)
    pixels = np.asarray(im.resize((cols * CELL_W, rows * CELL_H), Image.LANCZOS), dtype=np.float32) / 255
    glyphs = glyph_bitmaps(font_path)

    lines = []
    for r in range(rows):
        line = ""
        for c in range(cols):
            patch = blur(pixels[r * CELL_H:(r + 1) * CELL_H, c * CELL_W:(c + 1) * CELL_W])
            line += min(glyphs, key=lambda ch: float(((patch - glyphs[ch]) ** 2).sum()))
        lines.append(line.rstrip())

    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("avatar", nargs="?", default="https://github.com/ArindamJaiman.png?size=460")
    parser.add_argument("--cols", type=int, default=46)
    parser.add_argument("--out", default="assets/blackletter-a.txt")
    parser.add_argument("--font", default=next((f for f in FONT_CANDIDATES if os.path.exists(f)), None))
    args = parser.parse_args()

    if not args.font:
        sys.exit("No monospace font found — pass one with --font path/to/mono.ttf")

    lines = to_ascii(load_avatar(args.avatar), args.cols, args.font)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\n{len(lines)} rows x {args.cols} cols -> {args.out}")


if __name__ == "__main__":
    main()
