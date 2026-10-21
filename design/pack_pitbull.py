"""Re-pack the owner's pitbull sets (v2, 2026-10-21: everything at the WALK scale) into strips + hand-off data.

Run with a Python that has PIL (the project venv doesn't):  /Users/ghost/venv/bin/python3 design/pack_pitbull.py
Sources are already copied into design/brand/dog-src-pitbull-*/ (see DOG_ART_INVENTORY.md). Raw zips live in
/Volumes/Extreme/heartbeats-data/art-inbox/. Then it runs --combine; the lab (dog_lab.py) reads the json files.
"""
import json
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dog_art  # noqa: E402

BRAND = dog_art.BRAND
INBOX = Path("/Volumes/Extreme/heartbeats-data/art-inbox")
SC = 150 / 399  # walk frame_01 is 399 px wide in the owner's canvas -> 150 px in our cells
RAW = {"walk": INBOX / "pitbull-064012", "run": INBOX / "pitbull-run-v2-142215"}

ORDER = ["jump", "run", "land", "walk", "frolic", "walkmix", "pitbull", "pitbullrun", "pitbullsit", "pitbulljump",
         "pitbulljumpdown", "pitbullliedown", "pitbullbellyrub", "pitbullliewag", "pitbullliewait",
         "pitbullgetupwalk", "pitbullgetuprun"]


def run_src():
    """Run v2 (pink cleaned): crop + scale the raw frames into dog-src-pitbull-run/pr-N.png."""
    for n in range(1, 11):
        im = Image.open(RAW["run"] / f"frame_{n:02d}.png").convert("RGBA")
        im = im.crop(im.getchannel("A").getbbox())
        im.resize((round(im.width * SC), round(im.height * SC)), Image.LANCZOS).save(
            BRAND / "dog-src-pitbull-run" / f"pr-{n}.png")


def loop_lefts(kind, prefix, count):
    """World-left (cell px, owner canvas scaled) of each loop cell IF the loop element sits at canvas x 0.
    = raw bbox x0 * SC - where dog_art.build pasted the frame in its cell."""
    out = []
    for n in range(1, count + 1):
        x0 = Image.open(RAW[kind] / f"frame_{n:02d}.png").getbbox()[0]
        im = dog_art.clean(Image.open(BRAND / f"dog-src-{prefix}" / f"{'pb' if kind == 'walk' else 'pr'}-{n}.png"))
        out.append(round(x0 * SC - round(dog_art.ANCHOR[0] - dog_art.hind_foot_x(im)), 1))
    return out


def main():
    run_src()
    dog_art.build(BRAND / "dog-src-pitbull-run", "pitbullrun")
    tr = dog_art.build_travel
    tr(BRAND / "dog-src-pitbull-liedown", "pitbullliedown", SC, 0, 345, 0, 1)
    tr(BRAND / "dog-src-pitbull-liewag", "pitbullliewag", SC, 0, 345, 0, 1)
    tr(BRAND / "dog-src-pitbull-liewait", "pitbullliewait", SC, 0, 345, 0, 1)
    tr(BRAND / "dog-src-pitbull-bellyrub", "pitbullbellyrub", SC, 0, 328, 0, 1)
    for kind, name in (("walk", "pitbullgetupwalk"), ("run", "pitbullgetuprun")):
        tr(BRAND / f"dog-src-{name.replace('pitbull', 'pitbull-')}", name, SC, 0, 405 if kind == "walk" else 455, 0, 1)
        meta = json.loads((BRAND / f"dog-{name}.json").read_text())
        owner = json.loads((BRAND / f"dog-src-{name.replace('pitbull', 'pitbull-')}" / "orig/meta.json").read_text())
        h = owner["handoff"]
        meta["sc"] = SC
        meta["ms"] = [e["ms"] for e in owner["sequence"]]
        meta["loop"] = {"kind": kind, "first": h["continue_with_frame"] - 1,  # 0-based loop frame to continue with
                        "left": h["loop_left_vs_liedown"] * SC, "speed": h["speed_px_s"] * SC,
                        "lefts": loop_lefts(kind, "pitbull" if kind == "walk" else "pitbull-run", 12 if kind == "walk" else 10)}
        (BRAND / f"dog-{name}.json").write_text(json.dumps(meta))
    # belly rub canvas sits at lie-down canvas x + 328 (owner's CSS), in owner px
    br = json.loads((BRAND / "dog-pitbullbellyrub.json").read_text())
    br["sc"], br["vs_liedown"] = SC, 328
    (BRAND / "dog-pitbullbellyrub.json").write_text(json.dumps(br))
    print(dog_art.combine(tuple(ORDER)))


if __name__ == "__main__":
    main()
