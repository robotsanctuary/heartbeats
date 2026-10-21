"""Walk cycle made in code from ONE standing drawing (owner chose this over more generator attempts).

The lower part of each leg is cut off below CUT and swung around its own top ("knee") in a real
4-beat walk order: near back, near front, far back, far front, a quarter cycle apart. Each leg spends
75% of the cycle on the ground sweeping backwards and 25% lifted and swinging forward, so only one
paw is ever in the air. Output: design/brand/dog-walk.png directly (fixed body position per cell) + frames in dog-src-walk-rig/.

python design/dog_rig.py            (then: python design/dog_art.py --combine jump run land walk frolic)
"""
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "brand" / "dog-src-walk" / "walk-8.png"   # square stance, all four paws down
OUT = HERE / "brand" / "dog-src-walk-rig"
CUT = 86          # rows below this are only legs (4 separate pieces)
OVERLAP = 4       # leg pieces start this many rows higher so no gap opens at the joint
FRAMES = 8
SWING = 22        # degrees each leg swings either side of straight down
LIFT = 0.30       # how much a lifted leg shortens (bent paw), as a fraction of its length
RAISE = 9         # px a lifted paw rises off the ground (whole leg piece moves up)
BOB = 2           # px the body rises while a paw is in the air
# swing timing: one leg lifts at a time, a quarter cycle apart (near back, near front, far back, far front)
# leg: (x-range at CUT+1 from the drawing, is_far, phase offset in the cycle)
LEGS = {"near_back": ((0, 22), False, 0.00), "near_front": ((60, 78), False, 0.25),
        "far_back": ((24, 46), True, 0.50), "far_front": ((79, 106), True, 0.75)}


def leg_pose(t):
    """t in 0..1 -> (angle deg, lift 0..1). Positive angle = paw swung back. Swing = last 25%."""
    if t < 0.75:                               # stance: paw on the ground, sweeps front -> back
        return -SWING + 2 * SWING * (t / 0.75), 0.0
    s = (t - 0.75) / 0.25                     # swing: lifted, back -> front
    return SWING - 2 * SWING * s, math.sin(math.pi * s)


def build():
    im = Image.open(SRC).convert("RGBA")
    w, h = im.size
    body = im.copy()
    body.paste((0, 0, 0, 0), (0, CUT, w, h))
    pieces = {}
    for name, ((x0, x1), far, ph) in LEGS.items():
        piece = im.crop((x0, CUT - OVERLAP, x1, h))
        # keep only this leg inside its own column range (drop bits of neighbouring legs)
        pieces[name] = (piece, x0, far, ph)
    OUT.mkdir(parents=True, exist_ok=True)
    # Fixed placement in every cell, taken from the standing drawing, so the body never slides.
    sys.path.insert(0, str(HERE))
    import dog_art
    fx = dog_art.hind_foot_x(dog_art.clean(im.copy()))
    ox, oy = round(dog_art.ANCHOR[0] - fx), dog_art.ANCHOR[1] - h
    C = dog_art.CELL
    sheet = Image.new("RGBA", (C * FRAMES, C))
    for f in range(FRAMES):
        cell = Image.new("RGBA", (C, C))
        far_l, near_l = [], []
        up = 0
        for name, (piece, x0, far, ph) in pieces.items():
            ang, lift = leg_pose((f / FRAMES + ph) % 1)
            up = max(up, lift)
            pw, phh = piece.size
            leg = piece.resize((pw, max(4, round(phh * (1 - LIFT * lift)))), Image.LANCZOS) if lift else piece
            big = Image.new("RGBA", (pw * 3, phh * 3))
            big.paste(leg, (pw, phh))
            big = big.rotate(-ang, resample=Image.BICUBIC, center=(pw * 1.5, phh))
            (far_l if far else near_l).append((big, ox + x0 - pw, oy + CUT - OVERLAP - phh - round(RAISE * lift)))
        bob = round(BOB * up)
        for big, x, y in far_l:
            cell.alpha_composite(big, (x, y - bob))
        cell.alpha_composite(body, (ox, oy - bob))
        for big, x, y in near_l:
            cell.alpha_composite(big, (x, y - bob))
        cell.save(OUT / f"walk-{f + 1}.png")
        sheet.paste(cell, (f * C, 0))
    sheet.save(HERE / "brand" / "dog-walk.png", optimize=True)
    return OUT


if __name__ == "__main__":
    print(build())
