"""Engine data for the 24 fps site dog: joins between sets, ground-contact frames, timing.

Run after pack24.py:  /Users/ghost/venv/bin/python3 design/dog24_data.py
Writes design/brand/dog24/engine.json (read by design/dog24.js). Needs numpy + PIL (/Users/ghost/venv).

Joins: for a switch A -> B the engine needs (which frame of A to leave from, which frame of B to start at, and the
x offset between the two canvases). Owner-specified joins (shared canvases, hand-offs) are used where they exist;
the rest are found by matching the dog's silhouette (best overlap of the alpha masks, ground lines aligned).
"""
import glob
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pack24  # noqa: E402

INBOX, BRAND = pack24.INBOX, pack24.OUT
D = 4  # mask downsample (owner px per mask px)
_masks = {}


def frames(name):
    return sorted(glob.glob(str(INBOX / pack24.SETS[name][0])))


def mask(name, i, ground=None):
    """Alpha mask, bottom = the set's ground line (or `ground`), left = canvas x 0, at 1/D scale."""
    k = (name, i, ground)
    if k not in _masks:
        im = Image.open(frames(name)[i]).convert("RGBA")
        g = ground or pack24.SETS[name][1]
        a = np.asarray(im.getchannel("A").crop((0, 0, im.width, g + 1)).resize((im.width // D, (g + 1) // D))) > 40
        _masks[k] = a
    return _masks[k]


def iou(a, b, dx):
    """Overlap of mask a and mask b shifted right by dx mask px, both bottom-aligned."""
    h = min(a.shape[0], b.shape[0])
    a, b = a[-h:], b[-h:]
    w = max(a.shape[1], b.shape[1] + abs(dx)) + abs(dx) + 2
    A = np.zeros((h, w), bool)
    B = np.zeros((h, w), bool)
    o = abs(dx) + 1
    A[:, o:o + a.shape[1]] = a
    B[:, o + dx:o + dx + b.shape[1]] = b
    u = (A | B).sum()
    return (A & B).sum() / u if u else 0


def best(a_name, a_frames, b_name, b_frames, guess=0, span=40, bg=None):
    """Best (score, a_frame, b_frame, dx_owner_px) where B's canvas sits dx owner px right of A's canvas."""
    top = (0, 0, 0, 0)
    for i in a_frames:
        for j in b_frames:
            a, b = mask(a_name, i), mask(b_name, j, bg)
            # coarse: align bbox left edges, then search around
            ax = np.where(a.any(0))[0][0]
            bx = np.where(b.any(0))[0][0]
            c = ax - bx + guess // D
            for dx in range(c - span // D, c + span // D + 1):
                s = iou(a, b, dx)
                if s > top[0]:
                    top = (round(float(s), 3), i, j, dx * D)
    return top


def contacts(name, ground, tol=8):
    """Per frame: lowest opaque y (owner px) -> True if a paw is on the ground line."""
    m = json.loads((BRAND / "frames.json").read_text())["sets"][name]
    return [bb[3] >= ground - tol for bb in m["bbox"]], [bb[3] for bb in m["bbox"]]


def entry_table(b_name, b_frames, bg=None, min_score=.72):
    """For each walk frame i: the frames j of B (a walk-in) that match its pose, with B's canvas offset dx.
    Lets the engine enter a play-once set mid-way, so the dog arrives at an exact spot (box edge, card edge)."""
    out = []
    for i in range(len(frames("walk"))):
        row = []
        for j in b_frames:
            s, _, _, dx = best("walk", [i], b_name, [j], span=60, bg=bg)
            if s >= min_score:
                row.append([j, dx, s])
        out.append(row)
    return out


def main():
    M = json.loads((BRAND / "frames.json").read_text())
    S = M["sets"]
    n = {k: v["n"] for k, v in S.items()}
    J = {}
    allw, allsw = range(n["walk"]), range(n["sniffwalk"])
    # walk -> play-once sets that start from a walking/standing pose
    for b in ("sit", "liedown", "jump", "sniffbox", "pawbox"):
        J["walk>" + b] = best("walk", allw, b, [0])
    J["walk>jumpdown"] = best("walk", allw, "jumpdown", range(0, 48, 2), bg=331)  # standing on the box top
    J["sniffloop>walk"] = best("sniffloop", range(n["sniffloop"]), "walk", allw)
    J["walk>sniffloop"] = best("walk", allw, "sniffloop", [0])
    J["sithold>sit"] = best("sithold", range(n["sithold"]), "sit", range(60, 100))
    J["waitwag>liewait"] = best("waitwag", range(n["waitwag"]), "liewait", range(n["liewait"]), span=12)
    J["walk>sniffwalk"] = best("walk", allw, "sniffwalk", allsw[::2])
    J["sniffwalk>walk"] = best("sniffwalk", allsw, "walk", allw[::2])
    # play-once last frame -> walk loop
    for a in ("sit", "jump", "jumpdown"):
        J[a + ">walk"] = best(a, [0 if a == "sit" else n[a] - 1], "walk", allw)
    J["sniffloop>sniffwalk"] = best("sniffloop", range(n["sniffloop"]), "sniffwalk", allsw[::2])
    J["pawloop>walk"] = best("pawloop", range(n["pawloop"]), "walk", allw[::2])
    # lying loops -> get-up (same canvas): which loop frame matches get-up frame 1 best
    for a in ("lieidle", "liewag"):
        J[a + ">getup"] = best(a, range(n[a]), "getupwalk", [0], span=12)
    for k, v in J.items():
        print(f"{k:22s} score {v[0]:.2f}  from {v[1] + 1:3d}  to {v[2] + 1:3d}  dx {v[3]:+d}")
    gw = json.loads((INBOX / "pitbull-getupwalk24-193202/meta.json").read_text())["handoff"]
    gr = json.loads((INBOX / "pitbull-getuprun24-193202/meta.json").read_text())["handoff"]
    J["getupwalk>walk"] = [1, n["getupwalk"] - 1, gw["continue_with_frame"] - 1, gw["loop_left_vs_liedown"]]
    J["getuprun>run"] = [1, n["getuprun"] - 1, gr["continue_with_frame"] - 1, gr["loop_left_vs_liedown"]]
    J["liedown>belly"] = [1, n["liedown"] - 1, 0, 328]
    # ground contact: jump (floor to floor) and jump-down (box top 331 -> floor 633)
    jc, _ = contacts("jump", 564)
    a0 = next(i for i in range(40, n["jump"]) if not jc[i])
    a1 = next(i for i in range(a0, n["jump"]) if jc[i])
    _, low = contacts("jumpdown", 633)
    d0 = next(i for i, y in enumerate(low) if y > 331 + 8)
    d1 = next(i for i in range(d0, n["jumpdown"]) if low[i] >= 633 - 8)
    print(f"jump airborne frames {a0 + 1}-{a1} ; jump-down leaves the box at {d0 + 1}, front paws land at {d1 + 1}")
    J["walk>belly"] = best("walk", allw[::3], "belly", range(n["belly"]))
    J["run>walk"] = best("run", range(n["run"]), "walk", allw)
    J["belly>liedown"] = [1, 0, n["liedown"] - 1, -328]
    # lying "base" pose = last lie-down frame; every lying set shares the lie-down canvas (dx 0)
    base = [n["liedown"] - 1]
    for b in ("lieidle", "liewag", "liewait", "getupwalk", "getuprun"):
        J["base>" + b] = best("liedown", base, b, range(n[b]), span=12)
    J["liewait>waitblink"] = best("liewait", [n["liewait"] - 1], "waitblink", range(n["waitblink"]), span=12)
    J["waitblink>waitwag"] = best("waitblink", range(n["waitblink"]), "waitwag", [0], span=12)
    J["wiggle>belly"] = best("wiggle", range(n["wiggle"]), "belly", [n["belly"] - 1], span=12)
    print("walk>belly", J["walk>belly"], "run>walk", J["run>walk"])
    # piece 5: turn-around (walk right -> slow -> stop -> turn -> walk left), ends matching the MIRRORED walk.
    # Owner meta: walk frame 4 -> turn frame 1 at -20; turn frame 157 = mirrored walk 23, continue at 24, left -1.
    tm = json.loads((INBOX / "pitbull-turn24-103347/meta.json").read_text())
    J["walk>turn"] = list(best("walk", allw, "turn", [0]))
    J["turn>walkm"] = [tm["handoff_out"]["iou"], n["turn"] - 1, tm["handoff_out"]["continue_with_frame"] - 1,
                       tm["handoff_out"]["mirrored_walk_left_vs_turnaround"]]
    # piece 6: walk <-> run transitions (owner meta: element top-left deltas; ground lines differ by exactly the
    # top delta, so the left delta is the canvas dx). Travel is baked into the frames (canvas stays put).
    wr = json.loads((INBOX / "pitbull-runwalk24-212230/meta.json").read_text())["clips"]
    a, b = wr["w2r"], wr["r2w"]
    J["walk>w2r"] = [a["handoff_in"]["iou"], a["handoff_in"]["matches_frame"] - 1, 0, a["handoff_in"]["transition_left_vs_loop"]]
    J["w2r>run"] = [a["handoff_out"]["iou"], n["w2r"] - 1, a["handoff_out"]["continue_with_frame"] - 1,
                    a["handoff_out"]["loop_left_vs_transition"]]
    J["run>r2w"] = [b["handoff_in"]["iou"], b["handoff_in"]["matches_frame"] - 1, 0, b["handoff_in"]["transition_left_vs_loop"]]
    J["r2w>walk"] = [b["handoff_out"]["iou"], n["r2w"] - 1, b["handoff_out"]["continue_with_frame"] - 1,
                     b["handoff_out"]["loop_left_vs_transition"]]
    # one-paw "pick me" (no owner meta): last frame -> scratch loop, loop -> walk, measured
    J["pawone>pawoneloop"] = best("pawone", [n["pawone"] - 1], "pawoneloop", range(n["pawoneloop"]), span=12)
    J["pawoneloop>walk"] = best("pawoneloop", range(n["pawoneloop"]), "walk", allw[::2])
    J["walk>pawone"] = best("walk", allw, "pawone", [0])
    for k in ("walk>w2r", "w2r>run", "run>r2w", "r2w>walk", "pawone>pawoneloop", "pawoneloop>walk", "walk>pawone"):
        v = J[k]
        print(f"{k:22s} score {v[0]:.2f}  from {v[1] + 1:3d}  to {v[2] + 1:3d}  dx {v[3]:+d}")
    T = {"sniffbox": entry_table("sniffbox", range(0, 46)), "pawbox": entry_table("pawbox", range(0, 46)),
         "pawone": entry_table("pawone", range(0, 70)),
         "jumpdown": entry_table("jumpdown", range(0, 50), bg=331),
         "turn": entry_table("turn", range(0, 57), min_score=.8)}   # walk-right + slow-down frames only
    for k, v in T.items():
        print(k, "entry options per walk frame:", [len(r) for r in v])
    import dog_lab24
    E = {"joins": J, "entry": T, "dur": dog_lab24.D, "jump_air": [a0, a1], "jd_air": [d0, d1], "jd_low": low,
         "jd_box": {"top": 331, "edge": 439, "floor": 633},
         "box": {"body_left": 682, "lid_left": 674},
         "speed": {"walk": 101, "sniffwalk": 103.4, "run": gr["speed_px_s"]},
         "hind": {k: v["hind"] for k, v in S.items()}, "bbox": {k: v["bbox"] for k, v in S.items()}}
    (BRAND / "engine.json").write_text(json.dumps(E))
    lossy = BRAND.with_name("dog24-lossy")
    if lossy.exists():
        (lossy / "engine.json").write_text(json.dumps(E))


if __name__ == "__main__":
    main()
