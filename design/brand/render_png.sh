#!/bin/bash
# Re-render PNG brand assets from the SVGs (needs Google Chrome + Pillow at /Users/ghost/venv/bin/python3).
set -euo pipefail
cd "$(dirname "$0")"; D=$PWD; CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"; T=${TMPDIR:-/tmp}
lockup(){ # w h markw titlepx tagpx out
cat > $T/lk.html <<EOF
<html><head><link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Source+Sans+3:wght@500&display=swap" rel="stylesheet"></head>
<body style="margin:0"><div style="width:${1}px;height:${2}px;display:flex;align-items:center;justify-content:center;gap:${3}px;font-family:'Source Sans 3';
background:radial-gradient(60% 90% at 10% 0%,#FFDCCB 0,transparent 70%),radial-gradient(50% 80% at 100% 100%,#FCE3EA 0,transparent 70%),#FBF7F3">
<img src="file://$D/mark.svg" style="width:${4}px"><div><div style="font:400 ${5}px/1 'Instrument Serif';color:#1F1A17">Fading <i style="background:linear-gradient(95deg,#D9472F,#C4304F 55%,#9E2A66);-webkit-background-clip:text;color:transparent;padding-right:.07em;filter:drop-shadow(0 10px 24px rgba(217,71,47,.5))">Heartbeats</i></div>
<div style="font-weight:500;font-size:${6}px;color:#6B625C;margin-top:.5em;letter-spacing:-.01em">Every heartbeat deserves a home.</div></div></div></body></html>
EOF
"$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --virtual-time-budget=6000 --window-size=$1,$2 --screenshot=$D/$7 file://$T/lk.html >/dev/null 2>&1; }
lockup 1500 500 36 470 100 32 banner-1500x500.png
cat > $T/og.html <<EOF
<html><head><link href="https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Source+Sans+3:wght@500&display=swap" rel="stylesheet"></head>
<body style="margin:0"><div style="width:1200px;height:630px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:34px;font-family:'Source Sans 3';text-align:center;
background:radial-gradient(60% 90% at 10% 0%,#FFDCCB 0,transparent 70%),radial-gradient(50% 80% at 100% 100%,#FCE3EA 0,transparent 70%),#FBF7F3">
<img src="file://$D/mark.svg" style="width:560px"><div><div style="font:400 104px/1 'Instrument Serif';color:#1F1A17">Fading <i style="background:linear-gradient(95deg,#D9472F,#C4304F 55%,#9E2A66);-webkit-background-clip:text;color:transparent;padding-right:.07em;filter:drop-shadow(0 10px 24px rgba(217,71,47,.5))">Heartbeats</i></div>
<div style="font-weight:500;font-size:36px;color:#6B625C;margin-top:18px">Every heartbeat deserves a home.</div></div></div></body></html>
EOF
"$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --virtual-time-budget=6000 --window-size=1200,630 --screenshot=$D/og-1200x630.png file://$T/og.html >/dev/null 2>&1
printf '<html><body style="margin:0"><img src="file://%s/icon.svg" style="width:180px;display:block"></body></html>' "$D" > $T/ic.html
"$CH" --headless=new --disable-gpu --hide-scrollbars --allow-file-access-from-files --window-size=180,180 --screenshot=$D/apple-touch-icon.png file://$T/ic.html >/dev/null 2>&1
/Users/ghost/venv/bin/python3 - "$D" <<'PY'
import sys; from PIL import Image; d=sys.argv[1]
for f in ("banner-1500x500.png","og-1200x630.png","apple-touch-icon.png"):
    Image.open(f"{d}/{f}").convert("RGB").save(f"{d}/{f}", optimize=True)
PY
ls -la $D/*.png
