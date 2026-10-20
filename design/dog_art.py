"""Packs the owner's dog art frames into one sprite strip for the site.

Usage: python design/dog_art.py <folder with frames> [--name jump]
Frames are numbered PNGs (…-1.png … -N.png, transparent background, dog facing RIGHT).
Every frame is placed in an equal square cell at its native scale, anchored so the HIND FEET
sit on the same point in every cell (so a crouch -> rear -> leap doesn't slide around).
Output: design/brand/dog-<name>.png (cell index = frame number - 1) and the anchor numbers the
engine needs (printed; also stored in design/brand/dog-<name>.json).
"""
import json
import re
import sys
from pathlib import Path

from PIL import Image, ImageFilter

BRAND = Path(__file__).resolve().parent / "brand"
CELL = 300          # px per square cell (native frames are ~150-185 px wide)
ANCHOR = (110, 250)  # where the hind feet land inside each cell (x, y)


def clean(im: Image.Image) -> Image.Image:
    """Trim the 1px halo left by background removal (white/black fringes)."""
    im = im.convert("RGBA")
    a = im.getchannel("A").point(lambda v: 255 if v > 40 else 0).filter(ImageFilter.MinFilter(3))
    im.putalpha(a)
    return im.crop(a.getbbox())


def hind_foot_x(im: Image.Image) -> float:
    """Mean x of opaque pixels in the bottom 8 rows of the back 45% of the frame."""
    a = im.getchannel("A")
    w, h = im.size
    xs = [x for y in range(max(0, h - 8), h) for x in range(int(w * .45)) if a.getpixel((x, y))]
    return sum(xs) / len(xs) if xs else w * .25


def build(src: Path, name: str = "jump", pick=None):
    """pick = frame numbers to keep, in play order (e.g. [3, 6, 1, 4, 7, 8]); default = all, numbered order."""
    files = sorted(src.glob("*.png"), key=lambda p: int(re.findall(r"(\d+)\.png$", p.name)[0]))
    if pick:
        byn = {int(re.findall(r"(\d+)\.png$", f.name)[0]): f for f in files}
        files = [byn[n] for n in pick]
    cells = []
    for f in files:
        im = clean(Image.open(f))
        fx = hind_foot_x(im)
        cell = Image.new("RGBA", (CELL, CELL))
        cell.paste(im, (round(ANCHOR[0] - fx), ANCHOR[1] - im.height), im)
        cells.append(cell)
    sheet = Image.new("RGBA", (CELL * len(cells), CELL))
    for i, c in enumerate(cells):
        sheet.paste(c, (i * CELL, 0))
    out = BRAND / f"dog-{name}.png"
    sheet.save(out, optimize=True)
    meta = {"frames": len(cells), "cell": CELL, "cx": ANCHOR[0] / CELL, "foot": ANCHOR[1] / CELL}
    (BRAND / f"dog-{name}.json").write_text(json.dumps(meta))
    return out, meta


def combine(names=("jump", "run")):
    """Joins the strips side by side into brand/dog-all.png (what the site uses). Prints each strip's first cell."""
    strips = [Image.open(BRAND / f"dog-{n}.png") for n in names]
    out = Image.new("RGBA", (sum(i.width for i in strips), CELL))
    x, starts = 0, {}
    for n, im in zip(names, strips):
        starts[n] = x // CELL
        out.paste(im, (x, 0))
        x += im.width
    out.save(BRAND / "dog-all.png", optimize=True)
    return {"cells": x // CELL, "start": starts}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--combine":
        print(combine(tuple(args[1:]) or ("jump", "run")))
        sys.exit()
    name = args[args.index("--name") + 1] if "--name" in args else "jump"
    pick = [int(n) for n in args[args.index("--frames") + 1].split(",")] if "--frames" in args else None
    print(build(Path(args[0]), name, pick))
