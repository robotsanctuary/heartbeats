#!/bin/bash
# Phone-width (390px) JPG screenshots of the site preview, for review over Telegram.
# Usage: design/shoot.sh <page relative to preview dir> <out name> <height px> [...repeat]
# Needs Google Chrome + a Python with PIL (default /Users/ghost/venv/bin/python3, override with PIL_PY).
set -euo pipefail
SITE="${SITE_PREVIEW_DIR:-/Volumes/Extreme/heartbeats-data/site-preview}"
OUT="${SHOT_DIR:-/Volumes/Extreme/heartbeats-data/site-shots}"
PIL_PY="${PIL_PY:-/Users/ghost/venv/bin/python3}"
CH="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
mkdir -p "$OUT"
while [ $# -ge 3 ]; do
  page=$1 name=$2 h=$3; shift 3
  frame="$SITE/_frame.html"
  printf '<html><body style="margin:0"><iframe src="%s" style="width:390px;height:%spx;border:0;display:block"></iframe></body></html>' "$page" "$h" > "$frame"
  "$CH" --headless=new --disable-gpu --hide-scrollbars --virtual-time-budget=8000 \
    --window-size=800,"$h" --screenshot="$OUT/$name.png" "file://$frame" >/dev/null 2>&1
  # Crop left-aligned (sips -c crops from the centre and fakes edge clipping).
  "$PIL_PY" -c "import sys;from PIL import Image;p=sys.argv[1];Image.open(p).convert('RGB').crop((0,0,390,int(sys.argv[2]))).save(p[:-4]+'.jpg',quality=85)" "$OUT/$name.png" "$h"
  rm -f "$OUT/$name.png" "$frame"
  echo "$OUT/$name.jpg"
done
