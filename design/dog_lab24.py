"""24 fps dog lab: every pitbull set from the owner's 24 fps batch (2026-10-21), on one page.

python design/dog_lab24.py  ->  <site preview>/dog-lab24.html  (also built by build_site.py)
Art: design/brand/dog24/ (packed by design/pack24.py). The old 12 fps lab (dog-lab.html) is untouched.

Every box is a TIMELINE built here in Python: steps [set, frame, seconds, left] where left = where the owner's
canvas for that set sits, in owner px, in one shared world. Sets the owner drew on a shared canvas (lie-down,
wag, wait, belly rub, get-ups and the walk/run they hand off to) use the owner's own offsets from the CSS/meta,
and every set is placed by its ground line, so chains join exactly as drawn. The JS only plays the list.
Drawing is a <canvas> per box (drawImage from small WebP atlases), only for boxes on screen.
"""
import json
import os
import shutil
from pathlib import Path

BRAND = Path(__file__).resolve().parent / "brand" / "dog24"
INBOX = Path("/Volumes/Extreme/heartbeats-data/art-inbox")
OUT = Path(os.environ.get("SITE_PREVIEW_DIR") or "/Volumes/Extreme/heartbeats-data/site-preview")
F = 1 / 24


def _meta(folder):
    return json.loads((INBOX / folder / "meta.json").read_text())


def durations():
    """Per-frame seconds for every set (owner's meta.json; null = last frame, held by the next step)."""
    M = json.loads((BRAND / "frames.json").read_text())["sets"]
    d = {k: [F] * v["n"] for k, v in M.items()}
    for name, folder in (("sit", "pitbull-sit24-p1-152910"), ("jump", "pitbull-jump24-190638"),
                         ("jumpdown", "pitbull-jumpdown24-193029"), ("liedown", "pitbull-liedown24-193029"),
                         ("belly", "pitbull-bellyrub24-193202"), ("sniffbox", "pitbull-sniffbox24-192821")):
        d[name] = [(ms or 41.67) / 1000 for ms in _meta(folder)["durations_ms"]]
    for name, folder in (("liewait", "pitbull-liewait24-193029"), ("getupwalk", "pitbull-getupwalk24-193202"),
                         ("getuprun", "pitbull-getuprun24-193202")):
        d[name] = [(e["ms"] or 41.67) / 1000 for e in _meta(folder)["sequence"]]
    d["waitblink"] = [e["ms"] / 1000 for e in _meta("pitbull-liewait24-193029")["blink_loop"]]
    return d


D = durations()


def play(name, left=0.0, first=0, count=None, hold=0.0):
    """One pass of a set at a fixed canvas position."""
    n = len(D[name])
    idx = list(range(first, n if count is None else first + count))
    steps = [[name, i % n, D[name][i % n], left] for i in idx]
    if hold:
        steps[-1][2] = hold
    return steps


def loop(name, seconds, left=0.0, speed=0.0, first=0):
    """Loop a set for `seconds`; the canvas moves `speed` owner px/s (walk 101, run 300, sniff-walk 103)."""
    n, t, i, out = len(D[name]), 0.0, first, []
    while t < seconds - 1e-9:
        d = D[name][i % n]
        out.append([name, i % n, d, round(left + speed * t, 1)])
        t += d
        i += 1
    return out


def boxes():
    gw = _meta("pitbull-getupwalk24-193202")["handoff"]
    gr = _meta("pitbull-getuprun24-193202")["handoff"]
    lie = play("liedown", hold=.4)
    B = []
    add = lambda title, note, T, **kw: B.append({"title": title, "note": note, "T": T, **kw})

    add("PITBULL hover or tap me: sits and gives paw (24 fps)",
        "walks → hover (mouse) / tap (4 s) → sit + paw up, holds while you stay → stands → walks on",
        loop("walk", 1.0), interactive=True, world=[0, 1016])
    add("Walk across (24 frames, 1.0 s per stride)", "", loop("walk", 15, -500, 101), world=[0, 1016])
    add("NEW sniff-walk across (33 frames, nose to the ground)", "", loop("sniffwalk", 15, -500, 103), world=[0, 1016])
    T = []
    for k in range(3):
        T += loop("walk", 2.0, -500 + 101 * 4.75 * k, 101)
        T += loop("sniffwalk", 2.75, -500 + 101 * 4.75 * k + 202, 103)
    add("NEW walk ↔ sniff-walk switching (same canvas, swap in place)", "walks 2 s, sniffs 2.75 s, repeats", T,
        world=[0, 1016])
    add("Run across (10 frames, 0.42 s per stride)", "", loop("run", 5, -500, 300), world=[0, 1016])
    add("NEW sniff-box: walks up to the box and sniffs (box in front)", "119 frames + sniff loop ×6, your timing",
        play("sniffbox") + loop("sniffloop", 3.5) + [["sniffloop", 0, .8, 0]], box="front")
    add("NEW paw-box: walks up and paws at the box, looks back at you (box behind)",
        "132 frames + paw loop ×6", play("pawbox") + loop("pawloop", 3.5) + [["pawloop", 0, .8, 0]], box="back")
    add("Sit + give paw → paw-hold loop", "100 frames (4.1 s) + hold loop ×6",
        play("sit") + loop("sithold", 3.0) + [["sithold", 0, .8, 0]])
    add("Jump (103 frames, travel as drawn)", "sits back, rears up, leaps, front paws land",
        play("jump", hold=1.2))
    add("Jump DOWN off a box (125 frames)", "walks to the edge, dives, front paws land first",
        play("jumpdown", hold=1.2), ledge=[0, 439, 303])
    add("Lie down → panting loop", "112 frames + idle loop ×8", lie + loop("lieidle", 4.0))
    add("Lie down → tail-wag loop", "", lie + loop("liewag", 4.0))
    add("Lie down → chin on paws → head-down wag → waiting blink", "",
        lie + play("liewait") + loop("waitwag", 3.25) + loop("waitblink", 5.6))
    add("Lie down → belly rub → paws-up wiggle", "belly-rub canvas at lie-down +328 px (your CSS)",
        lie + play("belly", 328) + loop("wiggle", 4.5, 328))
    add("Lie down → get up → WALK off", f"hand-off: walk frame {gw['continue_with_frame']} at +{gw['loop_left_vs_liedown']} px",
        lie + play("getupwalk") + loop("walk", 4, gw["loop_left_vs_liedown"], gw["speed_px_s"],
                                       gw["continue_with_frame"] - 1))
    add("Lie down → get up → RUN off", f"hand-off: run frame {gr['continue_with_frame']} at +{gr['loop_left_vs_liedown']} px",
        lie + play("getuprun") + loop("run", 2.5, gr["loop_left_vs_liedown"], gr["speed_px_s"],
                                      gr["continue_with_frame"] - 1))
    return B


PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dog lab 24 fps</title><style>
body{margin:0;font:15px system-ui,sans-serif;background:#FBF7F3;color:#1F1A17}
.bar{position:sticky;top:0;z-index:2;background:#fff;padding:10px 14px;display:flex;flex-wrap:wrap;gap:6px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
button{font:600 14px system-ui;border:1px solid #ddd;background:#fff;border-radius:999px;padding:7px 12px;color:#1F1A17}
button.on{background:#D9472F;color:#fff;border-color:#D9472F}
.box{margin:14px;border-radius:18px;padding:12px;background:var(--bg,#FBF7F3);border:1px solid rgba(0,0,0,.08)}
.box h3{margin:0 0 4px;font-size:15px;color:var(--fg,#1F1A17)}.box small{color:var(--fg2,#6B625C)}
canvas{display:block;width:100%;margin-top:6px}
.info{font:12px ui-monospace,monospace;color:var(--fg2,#6B625C)}
</style></head><body>
<div class="bar"><b style="align-self:center">Dog lab · 24 fps</b>
<button data-sp="0.25">¼ speed</button><button data-sp="0.5">½</button><button data-sp="1" class="on">1×</button>
<button id="step">Step ▶</button>
<button data-bg="#FBF7F3" class="on">Cream</button><button data-bg="#FCE6EE">Pink band</button><button data-bg="#ffffff">White card</button><button data-bg="#2a2020">Dark</button>
<button id="q">Quality: …</button>
<a href="dog-lab.html" style="align-self:center;margin-left:6px">old 12 fps lab</a></div>
<div id="boxes"></div>
<script>
const M=__META__,B=__BOXES__,SC=M.sc,VIEW=1056,IMG={};let DIR=localStorage.q==="lossy"?"dog24-lossy/":"dog24/";let speed=1,stepping=false;
function img(f){const u=DIR+f;return IMG[u]||(IMG[u]=Object.assign(new Image(),{src:u}))}
const qb=document.getElementById("q"),qlab=()=>qb.textContent=DIR==="dog24/"?"Quality: FULL (19.7 MB)":"Quality: SMALLER (7.3 MB)";qlab();
qb.onclick=()=>{DIR=DIR==="dog24/"?"dog24-lossy/":"dog24/";localStorage.q=DIR==="dog24/"?"full":"lossy";qlab()};
const io=new IntersectionObserver(es=>es.forEach(e=>e.target._vis=e.isIntersecting),{rootMargin:"150px"});
const items=[];
for(const A of B){const b=document.createElement("div");b.className="box";
 const tot=A.T.reduce((a,s)=>a+s[2],0);
 b.innerHTML=`<h3>${A.title}</h3><small>${A.note?A.note+" · ":""}${A.T.length} steps · ${tot.toFixed(1)} s, then repeats</small><canvas></canvas><div class="info"></div>`;
 document.getElementById("boxes").appendChild(b);io.observe(b);b._vis=true;
 /* world bounds (owner px) + tallest pose above the ground */
 let x0=1e9,x1=-1e9,h=0;for(const[s,f,,L]of A.T){const bb=M.sets[s].bbox[f],g=M.sets[s].ground;x0=Math.min(x0,L+bb[0]);x1=Math.max(x1,L+bb[2]);h=Math.max(h,g-bb[1])}
 if(A.world){x0=A.world[0];x1=A.world[1]}if(A.box){x1=Math.max(x1,889);h=Math.max(h,334-181)}if(A.ledge)h=Math.max(h,A.ledge[2]);
 const it={A,b,cv:b.querySelector("canvas"),info:b.querySelector(".info"),x0:x0-20,x1:x1+20,h:h+20,i:0,u:0,tot,hold:0,ix:0};
 if(A.interactive)setupHover(it);items.push(it)}
img(M.box.file);
function size(it){const W=it.cv.clientWidth,dpr=Math.min(2,devicePixelRatio||1);
 const k=Math.min(1,W/(VIEW*SC)),H=Math.round(it.h*SC*k+18);
 if(it.cv.width!==Math.round(W*dpr)||it.cv.height!==Math.round(H*dpr)){it.cv.width=Math.round(W*dpr);it.cv.height=Math.round(H*dpr);it.cv.style.height=H+"px"}
 return{k:k*dpr,gy:(H-14)*dpr,W:W*dpr}}
function draw(it,step){const ctx=it.cv.getContext("2d"),{k,gy,W}=size(it),[s,f,,L]=step,S=M.sets[s];
 ctx.clearRect(0,0,it.cv.width,it.cv.height);
 ctx.strokeStyle=getComputedStyle(it.b).getPropertyValue("--bg")==="#2a2020"?"rgba(255,255,255,.25)":"rgba(0,0,0,.15)";
 ctx.setLineDash([6,5]);ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(0,gy+1);ctx.lineTo(W,gy+1);ctx.stroke();ctx.setLineDash([]);
 const X=x=>(x-it.x0)*SC*k;
 if(it.A.ledge){const[a,c,h]=it.A.ledge;ctx.fillStyle="#fff";ctx.strokeStyle="rgba(0,0,0,.15)";ctx.beginPath();
  ctx.roundRect(X(a)-40,gy-h*SC*k,X(c)-X(a)+40,h*SC*k,[14,14,0,0]);ctx.fill();ctx.stroke()}
 const box=()=>{const bx=M.box,im=img(bx.file);if(im.complete)ctx.drawImage(im,X(0)+bx.ox*k,gy-334*SC*k+bx.oy*k,bx.w*k,bx.h*k)};
 if(it.A.box==="back")box();
 const[file,sx,sy,w,h,ox,oy]=S.frames[f],im=img(file);
 if(im.complete)ctx.drawImage(im,sx,sy,w,h,X(L)+ox*k,gy-S.ground*SC*k+oy*k,w*k,h*k);
 if(it.A.box==="front")box();
 it.info.textContent=`${s} frame ${f+1}/${S.n}`+(it.extra?" · "+it.extra():"")}
/* plain timeline player */
function adv(it,dt){const T=it.A.T;it.u+=dt;while(it.u>=T[it.i][2]){it.u-=T[it.i][2];it.i=(it.i+1)%T.length}return T[it.i]}
/* hover/tap box: walk loop in place while the box scrolls; hover -> sit + paw -> hold -> sit reversed -> walk */
function setupHover(it){let held=false,tapUntil=0;it.mode="walk";it.x=-300;it.n=0;
 const want=()=>held||performance.now()<tapUntil,go=m=>{it.mode=m;it.n=0;it.u=0};
 const react=()=>{if(it.mode==="walk")go("sit")};
 it.cv.style.cursor="pointer";
 it.cv.addEventListener("pointermove",e=>{if(e.pointerType==="mouse"&&near(e)){if(!held){held=true;react()}}else if(e.pointerType==="mouse")held=false});
 it.cv.addEventListener("pointerleave",()=>held=false);
 it.cv.addEventListener("pointerdown",e=>{if(e.pointerType!=="mouse"&&near(e)){tapUntil=performance.now()+4000;react()}});
 function near(e){const r=it.cv.getBoundingClientRect(),{k}=size(it),dpr=Math.min(2,devicePixelRatio||1);
  const cx=((it.x+250)-it.x0)*SC*k/dpr;return Math.abs(e.clientX-r.left-cx)<110}
 const SEQ={walk:["walk",null],sit:["sit",null],hold:["sithold",null],stand:["sit",null]};
 it.extra=()=>`mode ${it.mode}`;
 it.tick=dt=>{const s=it.mode==="hold"?"sithold":it.mode==="walk"?"walk":"sit",n=M.sets[s].n;
  if(it.mode==="walk"){it.x+=dt*101;if(it.x>it.x1)it.x=it.x0-500}
  it.u+=dt;const d=it.mode==="stand"?1/40:1/24;while(it.u>=d){it.u-=d;it.n++;
   if(it.mode==="walk")it.n%=n;else if(it.mode==="sit"&&it.n>=n)go("hold");else if(it.mode==="hold"){it.n%=n;if(!want())go("stand")}
   else if(it.mode==="stand"&&it.n>=n){go("walk")}}
  let f=it.mode==="stand"?n-1-it.n:it.n%n;f=Math.max(0,f);
  /* sit canvas: line its hind feet up with the walk's */
  const L=s==="walk"?it.x:it.x+M.sets.walk.hind[0]-M.sets.sit.hind[0];return[s,f,0,L]}}
let last=performance.now();
(function tick(t){const dt=Math.min(.05,(t-last)/1000)*speed;last=t;
 for(const it of items){if(!it.b._vis)continue;let st;
  if(it.tick)st=it.tick(stepping?0:dt);else st=adv(it,stepping?0:dt);draw(it,st)}
 requestAnimationFrame(tick)})(last);
document.querySelectorAll("[data-sp]").forEach(b=>b.onclick=()=>{stepping=false;speed=+b.dataset.sp;document.querySelectorAll("[data-sp],#step").forEach(x=>x.classList.toggle("on",x===b))});
document.getElementById("step").onclick=e=>{stepping=true;document.querySelectorAll("[data-sp]").forEach(x=>x.classList.remove("on"));e.target.classList.add("on");
 items.forEach(it=>{if(it.tick){it.u=1}else{it.u=0;it.i=(it.i+1)%it.A.T.length}})};
document.querySelectorAll("[data-bg]").forEach(b=>b.onclick=()=>{document.querySelectorAll(".box").forEach(x=>{x.style.setProperty("--bg",b.dataset.bg);const dk=b.dataset.bg==="#2a2020";x.style.setProperty("--fg",dk?"#fff":"#1F1A17");x.style.setProperty("--fg2",dk?"#d8cfc9":"#6B625C")});
 document.querySelectorAll("[data-bg]").forEach(x=>x.classList.toggle("on",x===b))});
</script></body></html>"""


PLAY = r"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dog play 24 fps</title><style>
body{margin:0;font:15px system-ui,sans-serif;background:#FBF7F3;color:#1F1A17;min-height:100vh}
.bar{position:sticky;top:0;z-index:30;background:#fff;padding:10px 14px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
.bar a{margin-left:8px}#st{font:12px ui-monospace,monospace;color:#6B625C;display:block;margin-top:4px}
button{font:600 14px system-ui;border:1px solid #ddd;background:#fff;border-radius:999px;padding:6px 11px}
button.on{background:#D9472F;color:#fff;border-color:#D9472F}
p{max-width:62ch;margin:18px}
.pets{display:flex;flex-direction:column;gap:13px;padding:8px 22px 78vh}
.card24{height:225px;background:#fff;border-radius:18px;box-shadow:0 8px 24px rgba(80,40,20,.08);position:relative;overflow:hidden}
.card24 i{position:absolute;inset:0 0 52px;background:linear-gradient(160deg,#f0d2c4,#e7b7a2)}
.card24:nth-child(3n) i{background:linear-gradient(160deg,#f3ddc4,#e6c3a0)}
.card24:nth-child(3n+2) i{background:linear-gradient(160deg,#f6d5cf,#e7b4b0)}
.card24 b,.card24 span{position:absolute;left:14px;right:14px}
.card24 b{bottom:26px;font-family:Georgia,serif}
.card24 span{bottom:8px;color:#6B625C;font-size:13px}
@media(min-width:900px){
  .pets{display:grid;grid-template-columns:507px 507px;gap:21px;justify-content:center;padding:24px 0 80vh}
  .card24{height:187px}
}
</style></head><body>
<div class="bar"><b>Dog play · piece 6: run ↔ walk + pick me</b>
<button data-sp="0.25">¼</button><button data-sp="1" class="on">1×</button><button data-sp="3">3×</button>
<a href="dog-lab24.html">lab</a><span id="st"></span></div>
<p>Scroll the page. The cards are solid. A card too high to hop onto is sniffed or pawed until it scrolls
out of the way; a low card is hopped onto. On a card the dog walks along it and rides it as you scroll (sometimes it
sits). On a computer it walks across to the card next to it when that one is level. At the right edge it jumps down
(front paws first) onto a card below or the floor. If you scroll its card up toward the top bar first, it hops
straight down. Piece 5: it never leaves the screen. Near an edge it slows, stops, turns round (the new art)
and walks back. Facing left it does everything mirrored, including jumping down to the left. On a phone the
cards are full width, so it leaps off before the landing would leave the screen.</p>
<p><button data-t="sniff">Sniff</button> <button data-t="sit">Sit + paw</button> <button data-t="lie" data-a="pant">Lie + pant</button>
<button data-t="lie" data-a="wag">Lie + wag</button> <button data-t="lie" data-a="wait">Lie + chin on paws</button>
<button data-t="lie" data-a="belly">Lie + belly rub</button> <button data-t="lie" data-a="pant" data-run="1">Lie + get up running</button> <button data-t="turn">Turn round</button>
<button data-t="run">Run (speeds up, slows down)</button> · next card side: <button data-e="pick">Pick me</button>
<button data-e="paw">Paw</button> <button data-e="sniff">Sniff</button></p>
<p>Piece 6: it sometimes speeds up into a run and slows back to a walk (your new art), sized to stop before the next
card or the screen edge. At a card side too high to hop it now also does the one-paw "pick me" and scratches the
card while it waits. The side buttons pick what it does at the NEXT card side it meets.</p>
<div class="pets" id="pets"></div>
<script>
const pets=document.getElementById("pets");
for(let i=1;i<=12;i++){const d=document.createElement("div");d.className="card24";d.dataset.n=i;
 d.innerHTML=`<i></i><b>Test card ${i}</b><span>Fake card — not a real animal</span>`;pets.appendChild(d);}
</script>
<script src="dog24.js?p7" data-base="dog24-lossy/"></script>
<script>
document.querySelectorAll("[data-sp]").forEach(b=>b.onclick=()=>{window.__dog24speed=+b.dataset.sp;
 document.querySelectorAll("[data-sp]").forEach(x=>x.classList.toggle("on",x===b))});
document.querySelectorAll("[data-t]").forEach(b=>b.onclick=()=>__dog24.force(b.dataset.t,
 b.dataset.a?{acts:[b.dataset.a],run:!!b.dataset.run}:{}));
document.querySelectorAll("[data-e]").forEach(b=>b.onclick=()=>__dog24.edge(b.dataset.e));
setInterval(()=>{if(!window.__dog24)return;const s=__dog24.state();
 document.getElementById("st").textContent=`${s.label?s.label+" · ":s.pending?"next: "+s.pending+" · ":""}${s.dir>0?"→":"←"} ${s.mode}${s.mode==="offstage"?" (back in "+s.wait.toFixed(1)+" s)":""} · ${s.set} frame ${s.f+1} · x ${s.xr?Math.round(s.xr[0]):"-"}–${s.xr?Math.round(s.xr[1]):"-"} of ${s.W}px`},200);
</script></body></html>"""


def build(out: Path = OUT):
    out.mkdir(parents=True, exist_ok=True)
    dst = out / "dog24"
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(BRAND, dst)
    lossy = BRAND.with_name("dog24-lossy")
    if lossy.exists():
        if (out / "dog24-lossy").exists():
            shutil.rmtree(out / "dog24-lossy")
        shutil.copytree(lossy, out / "dog24-lossy")
    shutil.copy(BRAND.parent.parent / "dog24.js", out / "dog24.js")
    (out / "dog-play24.html").write_text(PLAY)
    meta = json.loads((BRAND / "frames.json").read_text())
    page = out / "dog-lab24.html"
    page.write_text(PAGE.replace("__META__", json.dumps(meta)).replace("__BOXES__", json.dumps(boxes())))
    return page


if __name__ == "__main__":
    print(build())
