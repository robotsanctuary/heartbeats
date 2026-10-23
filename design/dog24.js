/* Site dog, 24 fps pitbull engine. Piece 1: walking on the floor only.
 *
 * Built in pieces (see the heartbeats skill): 1 walk, 2 random floor tricks, 3 solid cards (sniff/paw/hop up),
 * 4 ride cards + jump down, 5 phone layout. Lab/test page: dog-play24.html. The live site still uses DOG_JS.
 *
 * Art: <base>/frames.json (pack24.py) + engine.json (dog24_data.py). A frame record is
 * [sheet, sx, sy, w, h, ox, oy]: where to cut it from the atlas and where it sits in the owner's canvas (packed px).
 * World units are the OWNER'S canvas px; SC (150/399) turns them into packed px, K into screen px.
 * The canvas is drawn at a left position L (owner px) and stands on its ground line, so sets join as drawn.
 */
(() => {
  const BASE = (document.currentScript && document.currentScript.dataset.base) || "dog24-lossy/";
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const cv = document.createElement("canvas");
  cv.className = "dog24";
  cv.setAttribute("aria-hidden", "true");
  cv.style.cssText = "position:fixed;left:0;top:0;width:100vw;height:100vh;pointer-events:none;z-index:25";
  document.body.appendChild(cv);
  const ctx = cv.getContext("2d");

  let M, E, SC, K = 1, W = 0, H = 0, DPR = 1;
  const IMG = {};
  const img = f => IMG[f] || (IMG[f] = Object.assign(new Image(), { src: BASE + f }));

  /* dog state: set, frame index, time into frame, canvas left L (owner px), surface y (screen px) */
  const dog = { set: "walk", f: 0, u: 0, L: 0, mode: "walk", wait: 0 };

  function resize() {
    DPR = Math.min(2, devicePixelRatio || 1);
    W = innerWidth; H = innerHeight;
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    /* dog size on screen: walk is ~150 packed px long; ~105 px on phones, ~135 px on desktops */
    K = (W >= 900 ? 0.9 : 0.7);
  }

  const px = owner => owner * SC * K;               // owner px -> screen px
  const floorY = () => H - 6;                       // floor = bottom of the viewport (piece 4 adds cards)
  const walkSpeed = () => E.speed.walk;             // owner px / s, matches the art so paws don't slide

  /* the dog's visible extent (screen px) for the current frame */
  function extent() {
    const bb = E.bbox[dog.set][dog.f];
    return [px(dog.L + bb[0]), px(dog.L + bb[2])];
  }

  /* start the walk-in from off the left edge, so the dog never appears out of nowhere */
  function enterLeft() {
    const bb = E.bbox.walk[0];
    dog.set = "walk"; dog.f = 0; dog.u = 0; dog.mode = "walk";
    dog.L = -bb[2] - 20 / (SC * K);
  }

  function step(dt) {
    if (dog.mode === "offstage") {                  // walked off the right edge: pause, then come back from the left
      dog.wait -= dt;
      if (dog.wait <= 0) enterLeft();
      return;
    }
    const D = E.dur[dog.set];
    dog.L += walkSpeed() * dt;
    dog.u += dt;
    while (dog.u >= D[dog.f]) { dog.u -= D[dog.f]; dog.f = (dog.f + 1) % D.length; }
    if (extent()[0] > W + 10) { dog.mode = "offstage"; dog.wait = 2 + Math.random() * 3; }
  }

  function draw() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (dog.mode === "offstage") return;
    const S = M.sets[dog.set], [file, sx, sy, w, h, ox, oy] = S.frames[dog.f], im = img(file);
    if (!im.complete) return;
    ctx.drawImage(im, sx, sy, w, h, px(dog.L) + ox * K, floorY() + (oy - S.ground * SC) * K, w * K, h * K);
  }

  let last = 0;
  function tick(t) {
    const dt = last ? Math.min(0.05, (t - last) / 1000) : 0;   // tab switch / jank: never jump more than 50 ms
    last = t;
    step(dt * (window.__dog24speed || 1));
    draw();
    requestAnimationFrame(tick);
  }

  Promise.all([fetch(BASE + "frames.json").then(r => r.json()), fetch(BASE + "engine.json").then(r => r.json())])
    .then(([m, e]) => {
      M = m; E = e; SC = m.sc;
      img(M.sets.walk.frames[0][0]);                // walk sheet first (~0.1 MB); other sheets load on demand later
      resize(); addEventListener("resize", resize);
      enterLeft();
      dog.L = -E.bbox.walk[0][0] + 40 / (SC * K);   // first appearance: already on screen near the left
      requestAnimationFrame(tick);
    });

  /* debug hooks for the test page and browser checks */
  window.__dog24 = { state: () => ({ ...dog, x: M ? extent() : null, K, W, H }) };
})();
