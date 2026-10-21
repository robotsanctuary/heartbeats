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
FRONT_OFFSET = 100  # landing art: front paws sit this far in front of where hind feet usually go
CELL = 300          # px per square cell (native frames are ~150-185 px wide)
ANCHOR = (110, 250)
CHUNK = 50          # cells per lab sheet (50 * 300 = 15000 px, under the 16384 px texture limit)  # where the hind feet land inside each cell (x, y)


def clean(im: Image.Image, max_depth: int = 14) -> Image.Image:
    """Make the background fully transparent and strip the generator's white "sticker" border.
    The border is removed by flooding inward from the transparent area through near-white pixels only,
    at most max_depth px deep. The dog's dark outline stops the flood, so cream muzzle/paws inside it stay."""
    im = im.convert("RGBA")
    w, h = im.size
    px = im.load()
    whitish = lambda c: c[3] > 0 and min(c[:3]) > 180 and max(c[:3]) - min(c[:3]) < 45
    frontier = [(x, y) for y in range(h) for x in range(w) if px[x, y][3] <= 40]
    for x, y in frontier:
        px[x, y] = (0, 0, 0, 0)
    for _ in range(max_depth):
        nxt = []
        for x, y in frontier:
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= nx < w and 0 <= ny < h and whitish(px[nx, ny]):
                    px[nx, ny] = (0, 0, 0, 0)
                    nxt.append((nx, ny))
        frontier = nxt
        if not frontier:
            break
    # 2nd pass: enclosed pockets (between legs, under chin) the flood can't reach. Pure, colourless white
    # patches bigger than an eye highlight are background; the puppy's cream fur is warm (blue well below red).
    pure = lambda c: c[3] > 0 and min(c[:3]) > 215 and max(c[:3]) - min(c[:3]) < 22
    seen = set()
    for y0 in range(h):
        for x0 in range(w):
            if (x0, y0) in seen or not pure(px[x0, y0]):
                continue
            comp, stack = [], [(x0, y0)]
            seen.add((x0, y0))
            while stack:
                x, y = stack.pop()
                comp.append((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and pure(px[nx, ny]):
                        seen.add((nx, ny))
                        stack.append((nx, ny))
            if len(comp) >= 18:
                for x, y in comp:
                    px[x, y] = (0, 0, 0, 0)
    a = im.getchannel("A").filter(ImageFilter.MinFilter(3)).filter(ImageFilter.MaxFilter(3))  # drop lone specks
    im.putalpha(Image.eval(a, lambda v: 255 if v > 40 else 0))
    return im.crop(im.getchannel("A").getbbox())


def front_foot_x(im: Image.Image) -> float:
    a = im.getchannel("A"); w, h = im.size
    xs = [x for y in range(max(0, h - 8), h) for x in range(int(w * .5), w) if a.getpixel((x, y))]
    return sum(xs) / len(xs) if xs else w * .75


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
        fx = hind_foot_x(im) if name != "landart" else front_foot_x(im) - FRONT_OFFSET
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


def build_travel(src: Path, name: str, scale: float, top_y: float, floor_y: float, on_top: int, on_floor: int):
    """Pack a set that moves across its own canvas (e.g. the owner's jump-down: dog walks off a box and lands
    on the floor). Each frame is scaled by ONE factor (to match the other sets) and centred in its cell; the
    motion the art had on its canvas is kept as data in dog-<name>.json so the engine can replay it:
      dx[i]  = how far (cell px) frame i's cell sits right of frame 1's cell,
      cxa[i] = canvas x (scaled px) of cell i's centre, so sets drawn on the same canvas line up exactly,
      up[i]  = height above the floor as a fraction of the drawn box height (1 = on the box top, 0 = floor).
    Frames 1..on_top stand on the box top (top_y), frames on_floor..N on the floor (floor_y); the frames in
    between are airborne and use their lowest pixel. Feet go on the cell ground line (ANCHOR y).
    hind[i] = the hind-foot x in the cell for standing frames (to join walk cycles without a jump)."""
    files = sorted(src.glob("*.png"), key=lambda p: int(re.findall(r"(\d+)\.png$", p.name)[0]))
    cells, dx, up, hind, cxa, ox0 = [], [], [], [], [], None
    for n, f in enumerate(files, 1):
        raw = Image.open(f).convert("RGBA")
        x0, y0, x1, y1 = raw.getchannel("A").getbbox()
        support = top_y if n <= on_top else floor_y if n >= on_floor else y1
        im = clean(raw)  # cropped to bbox
        im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        cx = (x0 + x1) / 2 * scale
        cell = Image.new("RGBA", (CELL, CELL))
        px, py = round(CELL / 2 - im.width / 2), round(ANCHOR[1] - (support - y0) * scale)
        cell.paste(im, (px, py), im)
        cells.append(cell)
        if ox0 is None:
            ox0 = cx
        dx.append(round(cx - ox0, 1))
        cxa.append(round(cx - (px + im.width / 2 - CELL / 2), 1))  # canvas x (scaled) of the cell's centre
        up.append(round((floor_y - support) / (floor_y - top_y), 3))
        hind.append(round(px + hind_foot_x(im), 1) if (n <= on_top or n >= on_floor) else None)
    sheet = Image.new("RGBA", (CELL * len(cells), CELL))
    for i, c in enumerate(cells):
        sheet.paste(c, (i * CELL, 0))
    out = BRAND / f"dog-{name}.png"
    sheet.save(out, optimize=True)
    meta = {"frames": len(cells), "cell": CELL, "cx": ANCHOR[0] / CELL, "foot": ANCHOR[1] / CELL,
            "dx": dx, "up": up, "hind": hind, "cxa": cxa}
    (BRAND / f"dog-{name}.json").write_text(json.dumps(meta))
    return out, meta


def tilt(cell: Image.Image, deg: float) -> Image.Image:
    """Tip a packed cell nose-down (negative deg) around its FRONT paw, then drop it so the lowest
    point touches the ground line. Used to draw landing frames where the front paws hit first."""
    a = cell.getchannel("A")
    x0, y0, x1, y1 = a.getbbox()
    mid, px = (x0 + x1) // 2, a.load()
    fy = max(y for y in range(y0, y1) for x in range(mid, x1) if px[x, y] > 128)
    xs = [x for x in range(mid, x1) if px[x, fy] > 128]
    r = cell.rotate(deg, resample=Image.BICUBIC, center=(sum(xs) / len(xs), fy))
    out = Image.new("RGBA", cell.size)
    out.paste(r, (0, ANCHOR[1] - r.getchannel("A").getbbox()[3]), r)
    return out


# Jump-down landing, drawn from existing art: (strip, cell in that strip, tilt degrees)
# Jump-down landing: (strip, cell in that strip, tilt degrees). "landart" = owner's 3 landing frames.
LAND = [("jump", 11, 0),     # 1 peek over the edge
        ("jump", 3, -14),    # 2 hop off
        ("landart", 0, 0),   # 3 falling nose-down, front legs reaching (engine keeps it in the air)
        ("landart", 1, 0),   # 4 FRONT PAWS TOUCH DOWN, back end still up
        ("landart", 2, 0)]   # 5 back end drops, crouch


def build_land():
    strips = {n: Image.open(BRAND / f"dog-{n}.png") for n in ("jump", "run", "landart")}
    sheet = Image.new("RGBA", (CELL * len(LAND), CELL))
    for i, (n, c, deg) in enumerate(LAND):
        cell = strips[n].crop((c * CELL, 0, c * CELL + CELL, CELL))
        sheet.paste(tilt(cell, deg) if deg else cell, (i * CELL, 0))
    sheet.save(BRAND / "dog-land.png", optimize=True)
    return len(LAND)


def combine(names=("jump", "run", "land")):
    """Joins the strips side by side into brand/dog-all.png (what the site uses). Prints each strip's first cell."""
    strips = [Image.open(BRAND / f"dog-{n}.png") for n in names]
    out = Image.new("RGBA", (sum(i.width for i in strips), CELL))
    x, starts = 0, {}
    for n, im in zip(names, strips):
        starts[n] = x // CELL
        out.paste(im, (x, 0))
        x += im.width
    out.save(BRAND / "dog-all.png", optimize=True)
    # Lab sheets: chunks of CHUNK cells. The full strip is 100k+ px wide, past the GPU's max texture size (16384),
    # so browsers (phones especially) redraw it slowly and the lab animations stutter.
    for old in BRAND.glob("dog-lab-*.png"):
        old.unlink()
    for k in range(0, x // CELL, CHUNK):
        out.crop((k * CELL, 0, min(x, (k + CHUNK) * CELL), CELL)).save(BRAND / f"dog-lab-{k // CHUNK}.png", optimize=True)
    return {"cells": x // CELL, "start": starts}


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--land":
        print(build_land(), combine())
        sys.exit()
    if args and args[0] == "--combine":
        print(combine(tuple(args[1:]) or ("jump", "run", "land")))
        sys.exit()
    name = args[args.index("--name") + 1] if "--name" in args else "jump"
    pick = [int(n) for n in args[args.index("--frames") + 1].split(",")] if "--frames" in args else None
    print(build(Path(args[0]), name, pick))
