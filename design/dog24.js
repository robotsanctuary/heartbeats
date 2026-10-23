/* Site dog, 24 fps pitbull engine.
 * Pieces (see the heartbeats skill): 1 walk (done), 2 random floor tricks (this), 3 solid cards (sniff/paw/hop up),
 * 4 ride cards + jump down, 5 phone layout. Test page: dog-play24.html. The live site still uses DOG_JS.
 *
 * Art: <base>/frames.json (pack24.py) + engine.json (dog24_data.py). A frame record is
 * [sheet, sx, sy, w, h, ox, oy]: where to cut it from the atlas and where it sits in the owner's canvas (packed px).
 * World units are the OWNER'S canvas px; SC (150/399) turns them into packed px, K into screen px.
 * Each set's canvas is drawn at a left position L (owner px) standing on its ground line, so sets join as drawn.
 *
 * Behaviour: walking is the default. Every few seconds it may start a trick, picked at random (never the same
 * one twice in a row). A trick is a TIMELINE of steps [set, frame, seconds, L, label] built only from the
 * measured joins in engine.json (joins[k] = [score, A frame, B frame, dx]: A frame == B frame, B's canvas dx owner
 * px right of A's), so every move follows from the current pose. A trick only starts when the dog is fully on
 * screen, the part it can't walk away from (lying) fits, and the trick's art has loaded.
 */
(() => {
  const BASE = (document.currentScript && document.currentScript.dataset.base) || "dog24-lossy/";
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;

  const cv = document.createElement("canvas");
  cv.className = "dog24";
  cv.setAttribute("aria-hidden", "true");
  cv.style.cssText = "position:fixed;left:0;top:0;pointer-events:none;z-index:25";
  document.body.appendChild(cv);
  const ctx = cv.getContext("2d");

  let M, E, SC, K = 1, W = 0, H = 0, DPR = 1, NOW = 0;
  const IMG = {};
  const img = f => IMG[f] || (IMG[f] = Object.assign(new Image(), { src: BASE + f }));
  const ready = f => img(f).complete && img(f).naturalWidth > 0;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const shuffle = a => { for (let i = a.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [a[i], a[j]] = [a[j], a[i]]; } return a; };
  const J = k => E.joins[k];
  const N = s => E.dur[s].length;

  /* mode: walk | play (timeline) | run | offstage */
  const dog = { mode: "walk", set: "walk", f: 0, u: 0, L: 0, T: null, i: 0, next: null, wait: 0,
                trick: "", label: "", last: "", pending: "", forced: null, nextTry: 3, lost: 0 };

  function resize() {
    DPR = Math.min(2, devicePixelRatio || 1);
    const vv = window.visualViewport;               // the VISIBLE viewport (phones: no pinch-zoom/toolbars)
    W = Math.round(vv ? vv.width : document.documentElement.clientWidth || innerWidth);
    H = Math.round(vv ? vv.height : innerHeight);
    cv.style.width = W + "px"; cv.style.height = H + "px";
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    K = (W >= 900 ? 0.9 : 0.7);                     // walk ~105 px long on phones, ~135 px on desktops
  }
  const px = owner => owner * SC * K;               // owner px -> screen px
  const Wo = () => W / (SC * K);                    // screen width in owner px
  const floorY = () => H - 6;

  function extent(set = dog.set, f = dog.f, L = dog.L) {
    const bb = E.bbox[set][f];
    return [px(L + bb[0]), px(L + bb[2])];
  }

  /* ---------- timeline builders. Steps: [set, frame, seconds, L, label] ---------- */
  /* frames a..b inclusive, forwards or backwards; sec = fixed seconds per frame (default: the art's timing) */
  function once(T, s, L, a, b, label, sec) {
    const st = a <= b ? 1 : -1;
    for (let f = a; ; f += st) { T.push([s, f, sec || E.dur[s][f], L, label]); if (f === b) break; }
  }
  /* loop set s from frame `from`, stop ON frame `to` once at least minSec have passed; canvas moves `speed`
     owner px/s. Returns the canvas position after the last frame. */
  function loopTo(T, s, L, from, to, minSec, label, speed = 0) {
    const n = N(s); let t = 0, f = from % n, x = L;
    for (let guard = 0; guard < 5000; guard++) {
      const d = E.dur[s][f]; T.push([s, f, d, x, label]); t += d; x += speed * d;
      if (f === to && t >= minSec) break;
      f = (f + 1) % n;
    }
    return x;
  }
  /* the lying "base" pose = last lie-down frame; every lying set starts and ends on it */
  const rest = (T, Ll, a, b) => T.push(["liedown", N("liedown") - 1, rnd(a, b), Ll, "resting"]);

  function getup(s, Ll) {
    const T = [];
    once(T, s, Ll, 1, N(s) - 1, s === "getuprun" ? "gets up, runs off" : "gets up, walks on");
    const [, , f, dx] = J(s === "getuprun" ? "getuprun>run" : "getupwalk>walk");   // owner's hand-off
    return { T, next: { mode: s === "getuprun" ? "run" : "walk", f, L: Ll + dx } };
  }
  const maxRight = T => Math.max(...T.map(([s, f, , L]) => L + E.bbox[s][f][2]));
  const files = T => [...new Set(T.map(([s, f]) => M.sets[s].frames[f][0]))];

  /* ---------- tricks. at() = walk frame the trick starts from; plan(L of walk canvas) -> {T, next, mustFit} ---- */
  const TRICKS = {
    sit: { weight: 1, at: () => J("walk>sit")[1], plan(Lw) {
      const T = [], [, , s0, dx] = J("walk>sit"), Ls = Lw + dx, ns = N("sit");
      const [, h, s99] = J("sithold>sit");          // sithold frame h == last sit frame
      once(T, "sit", Ls, s0, ns - 1, "sits + gives paw");
      loopTo(T, "sithold", Ls, h + 1, h, rnd(2, 4), "holds paw up");
      once(T, "sit", Ls, s99 - 1, s0, "stands up", 1 / 40);   // stand-in: sit played back (no stand-up art)
      const [, , wf, bdx] = J("sit>walk");
      return { T, next: { mode: "walk", f: (wf + 1) % N("walk"), L: Ls + bdx } };
    } },

    sniff: { weight: 1, at: () => J("walk>sniffwalk")[1], plan(Lw) {
      const T = [], [, , j, dx] = J("walk>sniffwalk"), [, back, wf, bdx] = J("sniffwalk>walk");
      const x = loopTo(T, "sniffwalk", Lw + dx, j, back, rnd(2, 4.5), "sniffs the ground", E.speed.sniffwalk);
      return { T, next: { mode: "walk", f: (wf + 1) % N("walk"), L: x + bdx } };
    } },

    lie: { weight: 1.3, at: () => J("walk>liedown")[1], plan(Lw, opts = {}) {
      const T = [], [, , l0, dx] = J("walk>liedown"), Ll = Lw + dx, nl = N("liedown");
      once(T, "liedown", Ll, l0, nl - 1, "lies down");
      const acts = opts.acts || shuffle(["pant", "wag", "wait", "belly"]).slice(0, Math.random() < .5 ? 2 : 1);
      for (const a of acts) {
        rest(T, Ll, .4, 1.2);
        if (a === "pant") { const j = J("base>lieidle")[2]; loopTo(T, "lieidle", Ll, j + 1, j, rnd(2.5, 5), "pants"); }
        if (a === "wag") { const j = J("base>liewag")[2]; loopTo(T, "liewag", Ll, j + 1, j, rnd(2, 4), "wags tail"); }
        if (a === "wait") {
          const nw = N("liewait"), b = J("liewait>waitblink")[2], [, b2, w0] = J("waitblink>waitwag");
          once(T, "liewait", Ll, 1, nw - 1, "chin on paws");
          loopTo(T, "waitblink", Ll, b + 1, b2, rnd(3, 6), "waits, blinks");
          loopTo(T, "waitwag", Ll, w0 + 1, J("waitwag>liewait")[1], rnd(1.5, 3), "wags, chin down");
          once(T, "liewait", Ll, nw - 2, 1, "lifts head", 1 / 30);
        }
        if (a === "belly") {
          const Lb = Ll + J("liedown>belly")[3], nb = N("belly"), w = J("wiggle>belly")[1];
          once(T, "belly", Lb, 1, nb - 1, "rolls onto back");
          loopTo(T, "wiggle", Lb, w + 1, w, rnd(2.5, 4.5), "belly-up wiggle");
          once(T, "belly", Lb, nb - 2, 1, "rolls back", 1 / 40);  // stand-in: roll played back
        }
      }
      rest(T, Ll, .3, .9);
      const lying = T.length;
      const walkFits = maxRight([...T, ...getup("getupwalk", Ll).T]) <= Wo() - 10;
      const run = opts.run !== undefined ? opts.run : (!walkFits || Math.random() < .35);
      const g = getup(run ? "getuprun" : "getupwalk", Ll);
      return { T: T.concat(g.T), next: g.next, mustFit: lying };
    } },
  };

  /* ---------- choosing and starting a trick ---------- */
  function choose() {
    const names = Object.keys(TRICKS).filter(k => k !== dog.last);
    let r = Math.random() * names.reduce((a, k) => a + TRICKS[k].weight, 0);
    for (const k of names) if ((r -= TRICKS[k].weight) <= 0) return k;
    return names[0];
  }
  function tryStart(name, opts) {
    const p = TRICKS[name].plan(dog.L, opts || {});
    const need = files(p.T);
    need.forEach(img);                              // fetch this trick's sheets on demand
    const fits = maxRight(p.mustFit ? p.T.slice(0, p.mustFit) : p.T) <= Wo() - 10 && extent()[0] >= 4;
    if (!fits || !need.every(ready)) return false;
    Object.assign(dog, { mode: "play", T: p.T, i: 0, u: 0, next: p.next, trick: name, pending: "" });
    if (!opts) dog.last = name;
    return true;
  }
  function goto(next) {
    Object.assign(dog, { mode: next.mode, set: next.mode === "run" ? "run" : "walk", f: next.f, u: 0, L: next.L,
                         T: null, trick: "", label: "" });
    dog.nextTry = NOW + rnd(2.5, 6);
  }
  function enterLeft() {                            // walk in from off the left edge: never appear out of nowhere
    Object.assign(dog, { set: "walk", f: 0, u: 0, mode: "walk", T: null, trick: "", label: "" });
    dog.L = -E.bbox.walk[0][2] - 20 / (SC * K);
    dog.nextTry = NOW + rnd(2, 4);
  }

  function step(dt) {
    const [x0, x1] = extent();                      // watchdog: lost off screen 6 s -> walk back in
    dog.lost = (x1 < -40 || x0 > W + 40) && dog.mode !== "offstage" ? dog.lost + dt : 0;
    if (dog.lost > 6) { dog.lost = 0; enterLeft(); }

    if (dog.mode === "offstage") { dog.wait -= dt; if (dog.wait <= 0) enterLeft(); return; }

    if (dog.mode === "play") {
      dog.u += dt;
      while (dog.u >= dog.T[dog.i][2]) {
        dog.u -= dog.T[dog.i][2];
        if (++dog.i >= dog.T.length) { const u = dog.u; goto(dog.next); return step(u); }
      }
      const s = dog.T[dog.i]; dog.set = s[0]; dog.f = s[1]; dog.L = s[3]; dog.label = s[4];
      return;
    }

    /* walk / run loops: the canvas moves at the art's own speed so paws stay planted */
    const D = E.dur[dog.set];
    dog.L += (dog.mode === "run" ? E.speed.run : E.speed.walk) * dt;
    dog.u += dt;
    while (dog.u >= D[dog.f]) {
      dog.u -= D[dog.f]; dog.f = (dog.f + 1) % D.length;
      if (dog.mode !== "walk") continue;
      if (!dog.pending && NOW >= dog.nextTry) dog.pending = choose();
      if (dog.pending && NOW >= dog.nextTry && dog.f === TRICKS[dog.pending].at()) {
        const name = dog.pending, opts = dog.forced;
        if (tryStart(name, opts)) { dog.forced = null; dog.u = 0; return step(0); }
        if (!opts) dog.pending = "";                // random pick: re-roll later; a forced one waits for room
        dog.nextTry = NOW + rnd(1, 2.5);
      }
    }
    if (extent()[0] > W + 10) { dog.mode = "offstage"; dog.wait = rnd(1.5, 3.5); }
  }

  let lastDraw = null;
  function draw() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (dog.mode === "offstage") return;
    const S = M.sets[dog.set], rec = S.frames[dog.f];
    let d = [rec, S.ground, dog.L];
    if (!ready(rec[0])) d = lastDraw;               // sheet still loading: keep the previous frame
    if (!d) return;
    lastDraw = d;
    const [[file, sx, sy, w, h, ox, oy], ground, L] = d;
    ctx.drawImage(img(file), sx, sy, w, h, px(L) + ox * K, floorY() + (oy - ground * SC) * K, w * K, h * K);
  }

  let last = 0;
  function tick(t) {
    const dt = last ? Math.min(0.05, (t - last) / 1000) : 0;   // tab switch / jank: never jump more than 50 ms
    last = t;
    const s = dt * (window.__dog24speed || 1);
    NOW += s;
    step(s);
    draw();
    requestAnimationFrame(tick);
  }

  Promise.all([fetch(BASE + "frames.json").then(r => r.json()), fetch(BASE + "engine.json").then(r => r.json())])
    .then(([m, e]) => {
      M = m; E = e; SC = m.sc;
      img(M.sets.walk.frames[0][0]);                // walk sheet first; trick sheets load when a trick is picked
      resize(); addEventListener("resize", resize);
      if (window.visualViewport) visualViewport.addEventListener("resize", resize);
      enterLeft();
      dog.L = -E.bbox.walk[0][0] + 40 / (SC * K);   // first appearance: already on screen near the left
      requestAnimationFrame(tick);
    });

  /* debug hooks for the test page and browser checks */
  window.__dog24 = {
    state: () => ({ mode: dog.mode, set: dog.set, f: dog.f, L: dog.L, trick: dog.trick, label: dog.label,
                    pending: dog.pending, wait: dog.wait, x: M ? extent() : null, K, W, H }),
    /* do this trick next, as soon as the walk reaches its start frame and there's room,
       e.g. force("lie", {acts: ["belly"], run: false}) */
    force: (name, opts = {}) => { dog.pending = name; dog.forced = opts; dog.nextTry = 0; },
    plan: (name, opts) => TRICKS[name].plan(0, opts),
  };
})();
