"""Renders a SAMPLE sprite sheet (placeholder line dog) showing every frame the site's dog needs.
The owner hands this to an image generator to redraw with better art in the same grid.
Output: /Volumes/Extreme/heartbeats-data/mockups/sprite-template/dog-sprite-template.html (+ PNG via Chrome).
"""
from pathlib import Path

OUT = Path("/Volumes/Extreme/heartbeats-data/mockups/sprite-template")
ST = 'stroke="#C4304F" stroke-width="4.5" stroke-linecap="round" stroke-linejoin="round"'
CELL, LABEL_W = 200, 170


import math


def _rot(pt, a, c):
    a = math.radians(a); x, y = pt[0] - c[0], pt[1] - c[1]
    return (c[0] + x * math.cos(a) - y * math.sin(a), c[1] + x * math.sin(a) + y * math.cos(a))


def grounded(**f):
    """Pick dy so the lowest foot (or the haunch, when sitting) touches the ground line. Used for poses with weight on the floor."""
    t, pv, fold = f.get("tilt", 0), f.get("pivot", (66, 62)), f.get("fold_rear", False)
    pts = [_rot(_rot((x + 20, 62) if fold and x in (48, 58) else (x, 87), a, (x, 56)), t, pv)
           for x, a in ((48, f.get("rl", 0)), (58, f.get("rf", 0)))]
    pts += [_rot(q, t, pv) for q in ((44, 60), (52, 62))]
    f["dy"] = round(91 - max(y for _, y in pts), 1)
    return f


def dog(rl=0, rf=0, fl=0, ff=0, tilt=0, dy=0, head=0, tail=0, eyes=True, fold_rear=False, legs=True, paw=False, sheet=False, size=None, pivot=(66, 62)):
    """rl/rf = near/far rear leg angle, fl/ff = near/far front leg angle (deg; negative = swings forward)."""
    def leg(x, a, far=False, fold=False):
        o = ' opacity=".45"' if far else ""
        d = f"M{x} 54L{x + 14} 62L{x + 20} 62" if fold else f"M{x} 54V87h6"
        return f'<g transform="rotate({a} {x} 56)"{o}><path d="{d}" fill="none" {ST}/></g>'
    lg = lambda *a, **k: leg(*a, **k) if legs else ""
    near_front = (f'<path d="M88 57C96 57 104 56 111 54" fill="none" {ST}/><ellipse cx="115" cy="53.5" rx="4.4" ry="3.6" fill="#C4304F"/>'
                  if paw else lg(88, fl))
    eye = ('<circle cx="109" cy="26" r="2.3" fill="#1F1A17"/>' if eyes
           else '<path d="M106 27Q109 29.5 112 27" stroke="#1F1A17" stroke-width="2" stroke-linecap="round"/>')
    vb, dims = ("-10 -46 152 152", f'width="{size}" height="{size}"') if sheet else ("-10 -30 152 128", f'width="{CELL - 30}"')
    ground = "" if sheet else '<line x1="-10" y1="91" x2="142" y2="91" stroke="#bbb" stroke-dasharray="3 3"/>'
    return (f'<svg viewBox="{vb}" {dims} fill="none">'
            f'<g transform="translate(0 {dy}) rotate({tilt} {pivot[0]} {pivot[1]})">'
            f'<g transform="rotate({tail} 40 46)"><path d="M40 46C29 43 24 33 28 23" {ST}/></g>'
            + lg(58, rl + (0 if not fold_rear else -10), True, fold_rear) + lg(78, ff, True) +
            f'<path d="M38 49C38 40 46 36 58 36H82C92 36 97 42 97 49C97 57 92 62 82 62H52C43 62 38 57 38 49Z" fill="#fff" {ST}/>'
            '<path d="M80 37L92 30L102 44L90 52Z" fill="#fff"/>'
            f'<path d="M82 36.5C87 35 90 33 92 30" {ST}/><path d="M90 60C95 56 98 51 99 45" {ST}/>'
            + lg(48, rl, False, fold_rear) + near_front +
            f'<g transform="rotate({head} 94 42)">'
            f'<path d="M91 31C91 22 97 16 105 16C113 16 117 21 118 26L124 28C128 29 128 35 124 36L117 38C114 43 109 46 103 46C96 46 91 39 91 31Z" fill="#fff" {ST}/>'
            f'<circle cx="124.5" cy="31" r="2.8" fill="#C4304F"/>{eye}'
            f'<path d="M101 19C94 18 91 26 94 34C96 37 100 35 101 31Z" fill="#FDEBE4" {ST}/></g></g>'
            f'{ground}</svg>')


HEAD_PATH = ("M91 31C91 22 97 16 105 16C113 16 117 21 118 26L124 28C128 29 128 35 124 36L117 38"
             "C114 43 109 46 103 46C96 46 91 39 91 31Z")


def pose(H, S, hind, front, N, head=0, tail=-30, sheet=False, size=None):
    """Jointed dog. H=hip, S=shoulder, N=neck top (head anchor). hind/front = (near, far) legs, each [knee, foot].
    Feet on the ground use y=89.5 (the ground line minus half a stroke)."""
    def leg(a, pts, far=False):
        o = ' opacity=".45"' if far else ""
        d = "M%s %s" % a + "".join("L%s %s" % q for q in pts)
        return f'<path d="{d}" fill="none" {ST}{o}/>'
    vb, dims = ("-10 -46 152 152", f'width="{size}" height="{size}"') if sheet else ("-10 -30 152 128", f'width="{CELL - 30}"')
    ground = "" if sheet else '<line x1="-10" y1="91" x2="142" y2="91" stroke="#bbb" stroke-dasharray="3 3"/>'
    ang = math.degrees(math.atan2(S[1] - H[1], S[0] - H[0]))
    tx, ty = _rot((H[0] - 16, H[1] - 6), ang, H)
    caps = lambda a, b, w, c: f'<line x1="{a[0]}" y1="{a[1]}" x2="{b[0]}" y2="{b[1]}" stroke="{c}" stroke-width="{w}" stroke-linecap="round"/>'
    return (f'<svg viewBox="{vb}" {dims} fill="none">'
            # tail: leaves the back of the hip, angle relative to the body line
            f'<g transform="rotate({ang + tail} {H[0]} {H[1]})"><path d="M{H[0] - 8} {H[1] - 4}C{H[0] - 18} {H[1] - 6} {H[0] - 24} {H[1] - 14} {H[0] - 22} {H[1] - 24}" {ST}/></g>'
            + leg(H, hind[1], True) + leg(S, front[1], True) + leg(H, hind[0]) + leg(S, front[0])
            # body + neck as outlined capsules (red outline, white fill) so legs tuck in behind them
            + caps(H, S, 27, "#C4304F") + caps(S, N, 19, "#C4304F") + caps(H, S, 18, "#fff") + caps(S, N, 10, "#fff")
            + f'<g transform="translate({N[0] - 101} {N[1] - 36}) rotate({head} 101 36)">'
            f'<path d="{HEAD_PATH}" fill="#fff" {ST}/><circle cx="124.5" cy="31" r="2.8" fill="#C4304F"/>'
            '<circle cx="109" cy="26" r="2.3" fill="#1F1A17"/>'
            f'<path d="M101 19C94 18 91 26 94 34C96 37 100 35 101 31Z" fill="#FDEBE4" {ST}/></g>'
            f'{ground}</svg>')


P = lambda **k: ("pose", k)  # frame spec for the jointed drawer


G = dict  # frame spec shorthand
ROWS = [
    ("1. RUN (gallop)", "loop, 8 frames · main way it gets around", [
        G(rl=35, rf=28, fl=-40, ff=-32, tilt=-3, dy=-2),          # full stretch
        G(rl=25, rf=15, fl=-15, ff=-25, tilt=-1, dy=-5),
        G(rl=5, rf=-5, fl=10, ff=0, tilt=2, dy=-7),               # airborne, gathering
        G(rl=-20, rf=-28, fl=30, ff=22, tilt=4, dy=-4),           # fully gathered
        G(rl=-30, rf=-22, fl=25, ff=30, tilt=3, dy=0),            # rear feet land
        G(rl=-10, rf=-18, fl=5, ff=15, tilt=0, dy=1),
        G(rl=15, rf=5, fl=-20, ff=-5, tilt=-3, dy=0),             # push off
        G(rl=30, rf=22, fl=-35, ff=-25, tilt=-4, dy=-1)]),
    ("2. TROT", "loop, 4 frames · slow wander / sniffing around", [
        G(rl=18, rf=-15, fl=-18, ff=15, dy=0), G(rl=5, rf=-5, fl=-5, ff=5, dy=-2),
        G(rl=-15, rf=18, fl=15, ff=-18, dy=0), G(rl=-5, rf=5, fl=5, ff=-5, dy=-2)]),
    ("3. SKIP / HOP", "loop, 4 frames · happy bouncy steps", [
        G(rl=-10, rf=-10, fl=10, ff=10, tilt=3, dy=4), G(rl=20, rf=20, fl=-25, ff=-25, tilt=-6, dy=-10),
        G(rl=10, rf=10, fl=-10, ff=-10, tilt=-2, dy=-16), G(rl=-5, rf=-5, fl=15, ff=15, tilt=5, dy=-4)]),
    ("4. JUMP UP", "once, 6 frames · sit back on hind legs, rear up with front paws in the air, spring, fly, reach, land", [
        # 1 sit back: haunches down, hind legs folded under, front legs straight, looking up at the card
        P(H=(54, 76), S=(80, 56), hind=[[(68, 82), (62, 89.5), (72, 89.5)], [(72, 80), (66, 89.5), (76, 89.5)]],
          front=[[(83, 73), (84, 89.5), (90, 89.5)], [(91, 73), (92, 89.5), (98, 89.5)]], N=(92, 40), head=-8, tail=-60),
        # 2 rear up: weight on the hind legs, chest up, front paws tucked up in the air
        P(H=(56, 72), S=(68, 40), hind=[[(66, 80), (58, 89.5), (68, 89.5)], [(70, 79), (63, 89.5), (73, 89.5)]],
          front=[[(80, 46), (82, 57)], [(84, 42), (88, 52)]], N=(76, 22), head=-14, tail=-75),
        # 3 spring: hind legs snap straight and push off the ground, front paws reach up
        P(H=(56, 58), S=(76, 32), hind=[[(52, 74), (46, 89.5), (54, 89.5)], [(56, 74), (52, 89.5), (60, 89.5)]],
          front=[[(90, 28), (100, 20)], [(92, 34), (102, 28)]], N=(86, 14), head=-20, tail=-40),
        # 4 airborne, fully stretched
        P(H=(46, 34), S=(86, 24), hind=[[(36, 44), (22, 48)], [(40, 46), (26, 52)]],
          front=[[(100, 28), (114, 24)], [(98, 32), (112, 30)]], N=(98, 8), head=-4, tail=-15),
        # 5 reach down for the card: front legs out to land, hind legs tucking
        P(H=(48, 44), S=(86, 48), hind=[[(58, 54), (50, 62)], [(62, 56), (54, 64)]],
          front=[[(98, 62), (104, 74)], [(94, 64), (98, 76)]], N=(98, 32), head=8, tail=-25),
        # 6 land: front feet down, body low, hind legs bent to absorb
        P(H=(52, 64), S=(86, 66), hind=[[(62, 76), (52, 89.5), (60, 89.5)], [(66, 77), (57, 89.5), (65, 89.5)]],
          front=[[(92, 78), (94, 89.5), (100, 89.5)], [(97, 78), (99, 89.5), (105, 89.5)]], N=(98, 50), head=6, tail=-20),
    ]),
    ("5. JUMP DOWN", "once, 4 frames · off a card", [
        G(rl=-15, rf=-15, fl=15, ff=15, tilt=10, dy=2, head=12),    # look down
        G(rl=20, rf=20, fl=-20, ff=-20, tilt=18, dy=-6),            # hop off
        G(rl=10, rf=10, fl=-40, ff=-35, tilt=22, dy=4),             # falling, front reaching
        G(rl=-20, rf=-20, fl=15, ff=15, tilt=-2, dy=8, tail=-10)]), # land, absorb
    ("6. IDLE MOVES", "single poses · stand, sit, give paw, look up, sniff", [
        G(), G(tilt=-22, dy=8, fold_rear=True, fl=18, ff=18, head=8),
        G(tilt=-22, dy=8, fold_rear=True, ff=18, head=4, paw=True),
        G(head=-32, tail=-8), G(tilt=12, dy=6, head=30, fl=-12, ff=-12)]),
    ("7. REST", "lie down → sleep (2-frame breathing loop) → wake stretch", [
        G(tilt=-10, dy=14, fold_rear=True, fl=-60, ff=-60, head=6),
        G(dy=25, legs=False, head=16, eyes=False, tail=30),
        G(dy=24, legs=False, head=14, eyes=False, tail=26, tilt=-1),
        G(rl=-8, rf=-8, fl=-82, ff=-78, tilt=16, dy=2, head=-14, tail=-12)]),  # play-bow stretch
]


def draw(f, **kw):
    if isinstance(f, tuple) and f[0] == "pose":
        return pose(**f[1], **kw)
    return dog(**f, **kw)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    cols = max(len(f) for _, _, f in ROWS)
    w = LABEL_W + cols * CELL
    rows = []
    for title, note, frames in ROWS:
        cells = "".join(f'<div class="c"><span>{i + 1}</span>{draw(f)}</div>' for i, f in enumerate(frames))
        cells += '<div class="c x"></div>' * (cols - len(frames))
        rows.append(f'<div class="r"><div class="l"><b>{title}</b><small>{note}</small></div>{cells}</div>')
    html = f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{margin:0;background:#fff;font:14px/1.3 -apple-system,Helvetica,sans-serif;color:#222;width:{w}px}}
h1{{font-size:22px;margin:18px 20px 4px}}p.s{{margin:0 20px 14px;color:#555;max-width:{w - 60}px}}
.r{{display:flex;border-top:1px solid #ccc}}.l{{width:{LABEL_W}px;padding:12px;box-sizing:border-box;flex:none}}
.l b{{display:block;font-size:15px}}.l small{{color:#666}}
.c{{width:{CELL}px;height:{CELL - 40}px;border-left:1px solid #ddd;position:relative;display:flex;align-items:center;justify-content:center;flex:none}}
.c span{{position:absolute;top:6px;left:8px;font-size:11px;color:#999}}.c.x{{background:repeating-linear-gradient(45deg,#fafafa 0 8px,#f0f0f0 8px 16px)}}
</style></head><body><h1>Fading Heartbeats dog: sprite sheet template (placeholder art)</h1>
<p class="s">Redraw the SAME dog in every frame, side view facing RIGHT, same size and same ground line (dashed) in every cell.
Poses matter, the drawing style does not. Each frame on its own equal square, transparent background, PNG, at least 256×256 px per frame.
Grey hatched cells = not needed.</p>{"".join(rows)}</body></html>"""
    p = OUT / "dog-sprite-template.html"
    p.write_text(html)
    return p, w, 120 + len(ROWS) * (CELL - 40)


SHEET_CELL = 160          # px per frame in the site's sprite sheet
SHEET_FOOT = (89.5 + 46) / 152  # where the feet touch height as a fraction of the cell (feet sit here)
BRAND = Path(__file__).resolve().parent / "brand"


def build_sheet(cell=SHEET_CELL):
    """Placeholder sprite sheet for the site: same grid as the template, no labels, transparent PNG."""
    import subprocess
    cols = max(len(f) for _, _, f in ROWS)
    cells = []
    for _, _, frames in ROWS:
        for i in range(cols):
            inner = draw(frames[i], sheet=True, size=cell) if i < len(frames) else ""
            cells.append(f'<div style="width:{cell}px;height:{cell}px">{inner}</div>')
    w, h = cols * cell, len(ROWS) * cell
    html = (f'<!doctype html><html style="background:transparent"><body style="margin:0;background:transparent;'
            f'display:grid;grid-template-columns:repeat({cols},{cell}px)">{"".join(cells)}</body></html>')
    OUT.mkdir(parents=True, exist_ok=True)
    src = OUT / "_sheet.html"
    src.write_text(html)
    dst = BRAND / "dog-sprite.png"
    subprocess.run(["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "--headless=new", "--disable-gpu",
                    "--hide-scrollbars", "--default-background-color=00000000", f"--window-size={w},{h}",
                    f"--screenshot={dst}", f"file://{src}"], check=True, capture_output=True)
    return dst, w, h


if __name__ == "__main__":
    import sys
    print(build_sheet() if "--sheet" in sys.argv else build())
