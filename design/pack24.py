"""Pack the owner's 24 fps pitbull sets (2026-10-21 batch) into per-set texture atlases for the 24 fps dog lab.

Run with a Python that has PIL:  /Users/ghost/venv/bin/python3 design/pack24.py
Sources stay in the raw art inbox (not copied into git, ~1200 PNGs): /Volumes/Extreme/heartbeats-data/art-inbox/.
Output: design/brand/dog24/<set>-<n>.webp (lossless, <= 2048 px wide) + design/brand/dog24/frames.json.

How it differs from dog_art.py (the 12 fps packer):
- No re-anchoring and no white-border cleanup: the owner's frames are clean RGBA and every set is drawn on a
  fixed canvas, so each frame keeps its exact canvas position. Sets that chain (lie-down -> wag / belly rub /
  get-up -> walk/run) line up with the owner's own canvas offsets.
- Every frame is cropped to its alpha bbox on a pixel grid that is the same for all frames of a set
  (scaled crop box snapped to whole output px), so nothing jitters between frames.
- Tight shelf-packed atlases per set instead of 300 px cells: ~1200 frames would be 25 x 15k-px strips.
"""
import glob
import json
import math
from pathlib import Path

from PIL import Image

INBOX = Path("/Volumes/Extreme/heartbeats-data/art-inbox")
OUT = Path(__file__).resolve().parent / "brand" / "dog24"
SC = 150 / 399     # walk frame_01 is 399 px wide in the owner's canvas -> 150 px packed (same factor as v2)
MAXW = 2048        # atlas width; small sheets decode fast on phones and stay far under GPU texture limits

# set -> (glob of frames in play order, canvas ground y in owner px)
SETS = {
    "walk": ("pitbull-walk24-152615/frame_*.png", 334),
    "run": ("pitbull-run24-152642/frame_*.png", 359),
    "sit": ("pitbull-sit24-p1-152910/frames/frame_*.png", 374),
    "sithold": ("pitbull-sit24-p1-152910/hold_loop/hold_*.png", 374),
    "jump": ("pitbull-jump24-190638/travel/frame_*.png", 564),
    "jumpdown": ("pitbull-jumpdown24-193029/dog_only/frame_*.png", 633),
    "liedown": ("pitbull-liedown24-193029/frames/frame_*.png", 345),
    "lieidle": ("pitbull-liedown24-193029/idle_loop/idle_*.png", 345),
    "liewag": ("pitbull-liewag24-193029/frames/wag_*.png", 345),
    "liewait": ("pitbull-liewait24-193029/frames/frame_*.png", 345),
    "waitwag": ("pitbull-liewait24-193029/wag_loop/wag_*.png", 345),
    "waitblink": ("pitbull-liewait24-193029/wait_loop/wait_*.png", 345),
    "belly": ("pitbull-bellyrub24-193202/frames/frame_*.png", 328),
    "wiggle": ("pitbull-bellyrub24-193202/wiggle_loop/wiggle_*.png", 328),
    "getupwalk": ("pitbull-getupwalk24-193202/frames/frame_*.png", 405),
    "getuprun": ("pitbull-getuprun24-193202/frames/frame_*.png", 455),
    "sniffwalk": ("pitbull-sniffwalk24-192821/frames/frame_*.png", 334),
    "sniffbox": ("pitbull-sniffbox24-192821/dog_only/frame_*.png", 334),
    "sniffloop": ("pitbull-sniffbox24-192821/sniff_loop_dog_only/sniff_*.png", 334),
    "pawbox": ("pitbull-pawbox24-192932/dog_only/frame_*.png", 334),
    "pawloop": ("pitbull-pawbox24-192932/paw_loop_dog_only/paw_*.png", 334),
}
EXTRA = {"box": "pitbull-sniffbox24-192821/box_layer.png"}  # same box for sniff + paw (cmp-identical)


def crop_scaled(im):
    """Crop to the alpha bbox on the scaled pixel grid. Returns (image, x, y) = packed px offset in the canvas."""
    x0, y0, x1, y1 = im.getchannel("A").getbbox()
    tx0, ty0 = math.floor(x0 * SC), math.floor(y0 * SC)
    tx1, ty1 = math.ceil(x1 * SC), math.ceil(y1 * SC)
    box = (tx0 / SC, ty0 / SC, min(im.width, tx1 / SC), min(im.height, ty1 / SC))
    return im.resize((tx1 - tx0, ty1 - ty0), Image.LANCZOS, box=box), tx0, ty0


def hind_x(im):
    """Canvas x (owner px) of the hind feet: mean x of opaque pixels in the bottom 8 rows of the back 45%."""
    x0, y0, x1, y1 = im.getchannel("A").getbbox()
    a = im.getchannel("A").crop((x0, y0, x1, y1))
    w, h = a.size
    xs = [x for y in range(max(0, h - 8), h) for x in range(int(w * .45)) if a.getpixel((x, y)) > 40]
    return x0 + (sum(xs) / len(xs) if xs else w * .25)


def pack(name, items):
    """Shelf-pack [(image, ox, oy)] into atlases <= MAXW wide. Returns frame records [sheet, sx, sy, w, h, ox, oy]."""
    recs, sheets, x, y, row_h, placed = [], [], 0, 0, 0, []
    for im, ox, oy in items:
        if x + im.width > MAXW:
            x, y, row_h = 0, y + row_h + 1, 0
        if y + im.height > MAXW:  # start a new sheet
            sheets.append(placed)
            placed, x, y, row_h = [], 0, 0, 0
        placed.append((im, x, y))
        recs.append([len(sheets), x, y, im.width, im.height, ox, oy])
        x, row_h = x + im.width + 1, max(row_h, im.height)
    sheets.append(placed)
    files = []
    for k, pl in enumerate(sheets):
        w = max(px + im.width for im, px, py in pl)
        h = max(py + im.height for im, px, py in pl)
        sh = Image.new("RGBA", (w, h))
        for im, px, py in pl:
            sh.paste(im, (px, py))
        fn = f"{name}-{k}.webp"
        sh.save(OUT / fn, lossless=True, method=4)
        files.append(fn)
    for r in recs:
        r[0] = files[r[0]]
    return recs, files


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.webp"):
        old.unlink()
    meta = {"sc": SC, "sets": {}}
    for name, (pattern, ground) in SETS.items():
        files = sorted(glob.glob(str(INBOX / pattern)))
        assert files, name
        raw = [Image.open(f).convert("RGBA") for f in files]
        recs, sheets = pack(name, [crop_scaled(im) for im in raw])
        meta["sets"][name] = {"n": len(recs), "ground": ground, "canvas": list(raw[0].size), "frames": recs,
                              "sheets": sheets, "hind": [round(hind_x(im), 1) for im in raw],
                              "bbox": [im.getchannel("A").getbbox() for im in raw]}
        print(f"{name:10s} {len(recs):4d} frames  sheets {sheets}")
    for name, path in EXTRA.items():
        im, ox, oy = crop_scaled(Image.open(INBOX / path).convert("RGBA"))
        im.save(OUT / f"{name}.webp", lossless=True)
        meta[name] = {"file": f"{name}.webp", "w": im.width, "h": im.height, "ox": ox, "oy": oy}
    (OUT / "frames.json").write_text(json.dumps(meta))
    total = sum(s["n"] for s in meta["sets"].values())
    size = sum(f.stat().st_size for f in OUT.glob("*.webp")) / 1e6
    print(f"total {total} frames, {size:.1f} MB webp")


if __name__ == "__main__":
    main()
