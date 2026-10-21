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

# Cells in dog-all.png: 0-11 jump zip frames 1-12, 12-17 run (zip 2 frames 3,6,1,4,7,8), 18-22 landing (dog_art.LAND), 23-30 walk, 31-38 frolic, 39-46 walk mix, 47-58 pitbull walk, 59-68 pitbull run, 69-83 pitbull sit S1-15, 84-89 sit hold H1-6, 90-110 pitbull jump (in-place sheet, arc kept).
# mode "run":  frames loop while the dog travels across the box (speed = box widths per second), hop per stride.
# mode "path": keys = [cell, x (0-1 across the box), height above the floor in px]; position glides between keys.
#              ledge = a card the dog jumps onto / off: [side, where it starts/ends (0-1), height px].
# mode "still": frames play in place (for checking single frames).
LEDGE_H = 80
ANIMS = {
    "PITBULL jump, travelling (sit back, rear up, leap, front paws land)": {"mode": "path", "fps": 12, "keys": [[90, 0.12, 0], [90, 0.12, 0], [90, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [91, 0.12, 0], [92, 0.12, 0], [92, 0.12, 0], [92, 0.12, 0], [92, 0.12, 0], [92, 0.12, 0], [92, 0.12, 0], [93, 0.12, 0], [93, 0.12, 0], [94, 0.12, 0], [95, 0.12, 0], [96, 0.12, 0], [97, 0.12, 0], [98, 0.12, 0], [99, 0.148, 0], [99, 0.176, 0], [100, 0.203, 0], [100, 0.231, 0], [101, 0.259, 0], [101, 0.287, 0], [101, 0.314, 0], [102, 0.342, 0], [102, 0.37, 0], [102, 0.398, 0], [103, 0.426, 0], [103, 0.453, 0], [103, 0.481, 0], [104, 0.509, 0], [104, 0.537, 0], [105, 0.564, 0], [106, 0.592, 0], [107, 0.62, 0], [108, 0.62, 0], [109, 0.62, 0], [109, 0.62, 0], [109, 0.62, 0], [109, 0.62, 0], [109, 0.62, 0], [109, 0.62, 0], [110, 0.62, 0], [110, 0.62, 0], [110, 0.62, 0], [110, 0.62, 0], [110, 0.62, 0], [110, 0.62, 0]]},
    "PITBULL jump in place (your timing)": {"mode": "still", "frames": [90, 90, 90, 91, 91, 91, 91, 91, 91, 91, 91, 91, 92, 92, 92, 92, 92, 92, 93, 93, 94, 95, 96, 97, 98, 99, 99, 100, 100, 101, 101, 101, 102, 102, 102, 103, 103, 103, 104, 104, 105, 106, 107, 108, 109, 109, 109, 109, 109, 109, 110, 110, 110, 110, 110, 110], "fps": 12},
    "PITBULL jump frames 1-21 (in place, slow)": {"mode": "still", "frames": list(range(90, 111)), "fps": 2},
    "PITBULL sit down (frames 1-6, then holds)": {"mode": "still", "frames": [69, 70, 71, 72, 73, 74, 74, 74, 74, 74], "fps": 5},
    "PITBULL give paw (frames 7-15, then hold loop)": {"mode": "still", "frames": list(range(75, 84)) + [84, 85, 86, 87, 88, 89] * 2, "fps": 6},
    "PITBULL sitting hold loop (tail wag + blink)": {"mode": "still", "frames": [84, 85, 86, 87, 88, 89], "fps": 5},
    "Run across: PITBULL gallop (10 frames)": {"mode": "run", "frames": list(range(59, 69)), "fps": 14, "speed": .38, "hop": .12},
    "Walk across: PITBULL sheet (12 frames)": {"mode": "run", "frames": list(range(47, 59)), "fps": 10, "speed": .12, "hop": 0},
    "Walk across A: new sheet, near front paw steps": {"mode": "run", "frames": [23, 24, 25, 26, 27, 28, 29, 30], "fps": 8, "speed": .12, "hop": 0},
    "Walk across B: mix, near front then far front": {"mode": "run", "frames": [39, 40, 41, 42, 43, 44, 45, 46], "fps": 7, "speed": .12, "hop": 0},
    "Frolic across (front together, back together)": {"mode": "run", "frames": [32, 33, 34, 35, 36], "fps": 9, "speed": .30, "hop": .3},
    "Frolic, all 8 frames as sent": {"mode": "run", "frames": [31, 32, 33, 34, 35, 36, 37, 38], "fps": 12, "speed": .30, "hop": .18},
    "Run across (bounding)": {"mode": "run", "frames": [12, 13, 14, 15, 16, 17], "fps": 14, "speed": .32, "hop": .2},
    "Jump UP onto a card": {"mode": "path", "fps": 7, "ledge": ["right", .58, LEDGE_H], "keys": [
        [7, .10, 0], [7, .10, 0], [6, .11, 0], [6, .11, 0], [9, .16, 25], [3, .30, 120], [3, .42, 150],
        [10, .55, 125], [11, .68, LEDGE_H], [11, .68, LEDGE_H], [11, .68, LEDGE_H], [11, .68, LEDGE_H]]},
    "Jump DOWN off a card (front paws land first)": {"mode": "path", "fps": 6, "ledge": ["left", .42, LEDGE_H], "keys": [
        [18, .22, LEDGE_H], [18, .30, LEDGE_H], [19, .40, LEDGE_H + 25], [20, .55, 55], [21, .68, 0],
        [22, .72, 0], [22, .72, 0], [22, .72, 0]]},
    "All jump frames 1-12 (in place)": {"mode": "still", "frames": list(range(12)), "fps": 2},
    "All run frames 1-6 (in place)": {"mode": "still", "frames": list(range(12, 18)), "fps": 2},
    "Walk frames 1-8 (in place)": {"mode": "still", "frames": list(range(23, 31)), "fps": 2},
    "Frolic frames 1-8 (in place)": {"mode": "still", "frames": list(range(31, 39)), "fps": 2},
    "Pitbull frames 1-12 (in place)": {"mode": "still", "frames": list(range(47, 59)), "fps": 2},
    "Pitbull run frames 1-10 (in place)": {"mode": "still", "frames": list(range(59, 69)), "fps": 2},
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
/* ---- pitbull obstacle course: walk in, jump UP onto a box, walk the top, jump DOWN, walk off; 3 box heights ---- */
(()=>{const WALK=[...Array(12).keys()].map(i=>47+i),JD=[3,9,6,2,1,1,1,1,1,2,2,3,3,3,2,1,1,1,1,6,6],S=110,AX=S*110/300,CELLS=__BGW__/150;
const sum=a=>a.reduce((x,y)=>x+y,0),items=[];
function plan(W,h){const bx0=W*.36,bx1=W*.74,segs=[];
 const walk=(x0,x1,y)=>{const d=Math.abs(x1-x0)/55;segs.push({t:d,f:(p)=>[WALK[Math.floor(p*d*10)%12],x0+(x1-x0)*p,y,"walk"]})};
 const jump=(x0,x1,y0,y1,from,name)=>{const ds=JD.slice(from),tot=sum(ds),a0=Math.max(0,9-from),a1=17-from,
   before=sum(ds.slice(0,a0)),airT=sum(ds.slice(a0,a1+1));
   segs.push({t:tot/12,f:(p)=>{let u=p*tot,i=0;while(i<ds.length-1&&u>=ds[i]){u-=ds[i];i++}
     const q=Math.min(1,Math.max(0,(p*tot-before)/airT));return[90+from+i,x0+(x1-x0)*q,y0+(y1-y0)*q,name+" · art cell "+(91+from+i)]}})};
 const stand=(x,y,t)=>segs.push({t,f:()=>[110,x,y,"stand"]});
 walk(-S,bx0-70,0);jump(bx0-70,bx0+12,0,h,0,"jump UP");stand(bx0+12,h,.5);walk(bx0+12,bx1-75,h);
 jump(bx1-75,bx1+35,h,0,9,"jump DOWN");stand(bx1+35,0,.4);walk(bx1+35,W+S,0);return segs}
[["tall",130],["medium",80],["small",35]].forEach(([label,h])=>{const b=document.createElement("div");b.className="box";
 b.innerHTML=`<h3>PITBULL: up and down a ${label} box (${h}px)</h3><small>walks in → jumps up → walks across the top → jumps down → walks off</small><div class="stage" style="height:330px"><div class="ground"></div><div class="ledge"></div><div class="dog"></div></div><div class="info"></div>`;
 boxes.prepend(b);b.style.setProperty("--bg","#FBF7F3");
 const dog=b.querySelector(".dog");dog.style.cssText+=`;width:${S}px;height:${S}px;bottom:2px;background-size:${CELLS*S}px ${S}px`;
 items.push({b,h,st:b.querySelector(".stage"),ledge:b.querySelector(".ledge"),dog,info:b.querySelector(".info"),segs:null,t:0})});
let last=performance.now();(function tick(n){const dt=Math.min(.05,(n-last)/1000)*speed;last=n;
 items.forEach(it=>{const W=it.st.clientWidth;it.ledge.style.cssText=`left:${W*.36}px;width:${W*.38}px;height:${it.h}px`;
  if(!it.segs)it.segs=plan(W,it.h);if(!stepping)it.t+=dt;
  let t=it.t,k=0;while(k<it.segs.length&&t>=it.segs[k].t){t-=it.segs[k].t;k++}
  if(k>=it.segs.length){it.segs=plan(W,it.h);it.t=0;k=0;t=0}
  const[cell,x,y,label]=it.segs[k].f(t/it.segs[k].t);
  it.dog.style.backgroundPosition=-cell*S+"px 0";it.dog.style.transform=`translate(${(x-AX).toFixed(1)}px,${(-y).toFixed(1)}px)`;
  it.info.textContent=label});requestAnimationFrame(tick)})(last)})();
/* ---- interactive pitbull: walks; hover/tap the dog -> sits, gives paw, holds (tail wag + blink); leave -> stands, walks on ---- */
(()=>{const WALK=[...Array(12).keys()].map(i=>47+i),SIT=[69,70,71,72,73,74],PAW=[75,76,77,78,79,80,81,82,83],HOLD=[84,85,86,87,88,89];
const b=document.createElement("div");b.className="box";
b.innerHTML=`<h3>PITBULL: hover or tap the dog</h3><small>walks → (hover/tap) sits → paw up → holds while you stay → stands and walks on</small><div class="stage"><div class="ground"></div><div class="dog" style="cursor:pointer"></div></div><div class="info"></div>`;
boxes.prepend(b);b.style.setProperty("--bg",getComputedStyle(document.querySelector(".box:not(:first-child)")||b).getPropertyValue("--bg")||"#FBF7F3");
const st=b.querySelector(".stage"),dog=b.querySelector(".dog"),info=b.querySelector(".info");
let mode="walk",i=0,acc=0,x=.1,held=false,tapUntil=0,last=performance.now();
const seq={walk:[WALK,10],sit:[SIT,9],paw:[PAW,9],hold:[HOLD,5],stand:[SIT.slice().reverse(),12]};
const go=m=>{mode=m;i=0;acc=0};
const want=()=>held||performance.now()<tapUntil;
dog.addEventListener("pointerenter",e=>{if(e.pointerType==="mouse"){held=true;if(mode==="walk"||mode==="stand")go("sit")}});
dog.addEventListener("pointerleave",e=>{if(e.pointerType==="mouse")held=false});
dog.addEventListener("pointerdown",e=>{if(e.pointerType!=="mouse"){tapUntil=performance.now()+4000;if(mode==="walk"||mode==="stand")go("sit")}});
(function tick(t){const dt=Math.min(.05,(t-last)/1000)*speed;last=t;const[fr,fps]=seq[mode];
if(!stepping){acc+=dt*fps;while(acc>=1){acc--;i++;
 if(i>=fr.length){if(mode==="walk"||mode==="hold")i=0;
  else if(mode==="sit")go("paw");else if(mode==="paw")go("hold");else if(mode==="stand")go("walk")}}}
if(mode==="hold"&&!want())go("stand");
if(mode==="walk"&&!stepping){x+=dt*.12;if(x>1.1)x=-.1}
const W=st.clientWidth,cell=seq[mode][0][Math.min(i,seq[mode][0].length-1)];
dog.style.backgroundPosition=-cell*150+"px 0";dog.style.transform=`translate(${(x*W-AX).toFixed(1)}px,0)`;
info.textContent=`${mode} · frame ${i+1}/${seq[mode][0].length} · art cell ${cell+1}`;requestAnimationFrame(tick)})(last)})();

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
