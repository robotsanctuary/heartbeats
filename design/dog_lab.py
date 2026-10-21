"""Dog animation lab: one page to test the dog's animations on the site's own background colours.

python design/dog_lab.py  ->  <site preview>/dog-lab.html  (open http://<mac>:8787/dog-lab.html)
Each animation loops in its own box, with speed and background buttons and a frame-by-frame step mode.
Uses design/brand/dog-all.png (packed by design/dog_art.py). Edit the ANIMS table to try frame orders.
"""
import json
import os
import shutil
from pathlib import Path

BRAND = Path(__file__).resolve().parent / "brand"
OUT = Path(os.environ.get("SITE_PREVIEW_DIR") or "/Volumes/Extreme/heartbeats-data/site-preview")

# Cells in dog-all.png: 0-11 jump zip frames 1-12, 12-17 run (zip 2 frames 3,6,1,4,7,8), 18-22 landing (dog_art.LAND).
# mode "run":  frames loop while the dog travels across the box (speed = box widths per second), hop per stride.
# mode "path": keys = [cell, x (0-1 across the box), height above the floor in px]; position glides between keys.
#              ledge = a card the dog jumps onto / off: [side, where it starts/ends (0-1), height px].
# mode "still": frames play in place (for checking single frames).
LEDGE_H = 80
ANIMS = {
    "Run across (bounding)": {"mode": "run", "frames": [12, 13, 14, 15, 16, 17], "fps": 14, "speed": .32, "hop": .2},
    "Jump UP onto a card": {"mode": "path", "fps": 7, "ledge": ["right", .58, LEDGE_H], "keys": [
        [7, .10, 0], [7, .10, 0], [6, .11, 0], [6, .11, 0], [9, .16, 25], [3, .30, 120], [3, .42, 150],
        [10, .55, 125], [11, .68, LEDGE_H], [11, .68, LEDGE_H], [11, .68, LEDGE_H], [11, .68, LEDGE_H]]},
    "Jump DOWN off a card (front paws land first)": {"mode": "path", "fps": 6, "ledge": ["left", .42, LEDGE_H], "keys": [
        [18, .22, LEDGE_H], [18, .30, LEDGE_H], [19, .40, LEDGE_H + 25], [20, .55, 55], [21, .68, 0],
        [22, .72, 0], [22, .72, 0], [22, .72, 0]]},
    "All jump frames 1-12 (in place)": {"mode": "still", "frames": list(range(12)), "fps": 2},
    "All run frames 1-6 (in place)": {"mode": "still", "frames": list(range(12, 18)), "fps": 2},
    "Landing frames 1-5 (in place)": {"mode": "still", "frames": list(range(18, 23)), "fps": 2},
}

PAGE = """<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Dog lab</title><style>
body{margin:0;font:15px system-ui,sans-serif;background:#FBF7F3;color:#1F1A17}
.bar{position:sticky;top:0;z-index:2;background:#fff;padding:10px 14px;display:flex;flex-wrap:wrap;gap:6px;box-shadow:0 2px 8px rgba(0,0,0,.08)}
button{font:600 14px system-ui;border:1px solid #ddd;background:#fff;border-radius:999px;padding:7px 12px}
button.on{background:#D9472F;color:#fff;border-color:#D9472F}
.box{margin:14px;border-radius:18px;padding:12px;background:var(--bg);border:1px solid rgba(0,0,0,.08)}
.box h3{margin:0 0 4px;font-size:15px;color:var(--fg,#1F1A17)}.box small{color:var(--fg2,#6B625C)}
.stage{position:relative;height:300px;overflow:hidden}
.ground{position:absolute;left:0;right:0;bottom:20px;border-top:2px dashed rgba(0,0,0,.15)}
.dog{position:absolute;left:0;bottom:-5px;width:150px;height:150px;background:url(dog.png) no-repeat;
background-size:__BGW__px 150px;z-index:1}
.ledge{position:absolute;bottom:20px;background:#fff;border:1px solid rgba(0,0,0,.12);border-radius:16px 16px 0 0;
box-shadow:0 10px 24px -14px rgba(120,60,40,.5)}
.info{font:12px ui-monospace,monospace;color:var(--fg2,#6B625C)}
</style></head><body>
<div class="bar"><b style="align-self:center">Dog lab</b>
<button data-sp="0.25">¼ speed</button><button data-sp="0.5">½</button><button data-sp="1" class="on">1×</button>
<button id="step">Step ▶</button>
<button data-bg="#FBF7F3" class="on">Cream</button><button data-bg="#FCE6EE">Pink band</button><button data-bg="#ffffff">White card</button><button data-bg="#2a2020">Dark</button></div>
<div id="boxes"></div>
<script>const ANIMS=__ANIMS__;let speed=1,stepping=false;
const boxes=document.getElementById("boxes"),items=[];
for(const[name,A]of Object.entries(ANIMS)){const b=document.createElement("div");b.className="box";
const n=A.keys?A.keys.length:A.frames.length;
b.innerHTML=`<h3>${name}</h3><small>${n} frames · ${A.fps} fps</small><div class="stage"><div class="ground"></div><div class="dog"></div></div><div class="info"></div>`;
boxes.appendChild(b);const st=b.querySelector(".stage");
if(A.ledge){const[side,at,h]=A.ledge,l=document.createElement("div");l.className="ledge";l.style.height=h+"px";
if(side==="right"){l.style.left=at*100+"%";l.style.right="0"}else{l.style.left="0";l.style.right=(1-at)*100+"%"}st.appendChild(l)}
items.push({A,n,st,dog:b.querySelector(".dog"),info:b.querySelector(".info"),i:0,acc:0,x:.1})}
const AX=55; /* hind-foot anchor inside the 150px dog box */
function draw(it){const A=it.A,W=it.st.clientWidth;let cell,x,y=0;
if(A.mode==="path"){const k=A.keys[it.i],k2=A.keys[Math.min(it.i+1,it.n-1)],f=stepping?0:it.acc;
cell=k[0];x=(k[1]+(k2[1]-k[1])*f)*W;y=k[2]+(k2[2]-k[2])*f}
else if(A.mode==="run"){cell=A.frames[it.i];x=it.x*W;y=Math.sin(Math.PI*(it.i+it.acc)/it.n)*A.hop*150}
else{cell=A.frames[it.i];x=W/2}
it.dog.style.backgroundPosition=-cell*150+"px 0";it.dog.style.transform=`translate(${(x-AX).toFixed(1)}px,${(-y).toFixed(1)}px)`;
it.info.textContent=`frame ${it.i+1}/${it.n} · art cell ${cell+1}`}
function adv(it){it.i=(it.i+1)%it.n;if(it.A.mode==="run"&&stepping)it.x+=it.A.speed/it.A.fps}
let last=performance.now();(function tick(t){const dt=Math.min(.05,(t-last)/1000);last=t;
if(!stepping)items.forEach(it=>{it.acc+=dt*speed*it.A.fps;while(it.acc>=1){it.acc--;adv(it)}
if(it.A.mode==="run")it.x+=dt*speed*it.A.speed});
items.forEach(it=>{if(it.A.mode==="run"&&it.x>1.15)it.x=-.15;draw(it)});requestAnimationFrame(tick)})(last);
document.querySelectorAll("[data-sp]").forEach(b=>b.onclick=()=>{stepping=false;speed=+b.dataset.sp;document.querySelectorAll("[data-sp],#step").forEach(x=>x.classList.toggle("on",x===b))});
document.getElementById("step").onclick=e=>{stepping=true;document.querySelectorAll("[data-sp]").forEach(x=>x.classList.remove("on"));e.target.classList.add("on");
items.forEach(it=>{it.acc=0;adv(it)})};
document.querySelectorAll("[data-bg]").forEach(b=>b.onclick=()=>{document.querySelectorAll(".box").forEach(x=>{x.style.setProperty("--bg",b.dataset.bg);const dk=b.dataset.bg==="#2a2020";x.style.setProperty("--fg",dk?"#fff":"#1F1A17");x.style.setProperty("--fg2",dk?"#d8cfc9":"#6B625C")});
document.querySelectorAll("[data-bg]").forEach(x=>x.classList.toggle("on",x===b))});
document.querySelectorAll(".box").forEach(x=>x.style.setProperty("--bg","#FBF7F3"));
</script></body></html>"""


def build(out: Path = OUT):
    out.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BRAND / "dog-all.png", out / "dog.png")
    page = out / "dog-lab.html"
    import struct
    cells = struct.unpack(">I", (BRAND / "dog-all.png").read_bytes()[16:20])[0] // 300  # PNG width / cell
    page.write_text(PAGE.replace("__ANIMS__", json.dumps(ANIMS)).replace("__BGW__", str(cells * 150)))
    return page


if __name__ == "__main__":
    print(build())
