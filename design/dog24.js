/* Site dog, 24 fps pitbull engine.
 * Pieces (see the heartbeats skill): 1 walk (done), 2 floor tricks (done), 3 solid cards (this),
 * 4 ride cards + jump-down art + hop to a neighbour, 5 phone layout. Test page: dog-play24.html.
 * The live site still uses DOG_JS.
 *
 * Art: <base>/frames.json (pack24.py) + engine.json (dog24_data.py). A frame record is
 * [sheet, sx, sy, w, h, ox, oy]: where to cut it from the atlas and where it sits in the owner's canvas (packed px).
 * World units are the OWNER'S canvas px; SC (150/399) turns them into packed px, K into screen px.
 * Each set's canvas is drawn at a left position L (owner px) standing on its ground line, so sets join as drawn.
 *
 * Piece 3: .card24 elements are solid. A side too high to hop is sniffed or pawed (sniffbox/pawbox, entered
 * mid-walk so the nose arrives at the edge, then the wait loop) until the card scrolls clear. A top within
 * about one dog-height of the floor is hopped onto (jump art; the ground line rises to the card during the
 * air frames). Standing on a card, the feet follow that card. When the card leaves, the same jump hops back
 * to the floor. Riding, the jump-down art, and hopping to another card are piece 4.
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
  const DOG_H = 315;                                // owner px, walk ground line to the ears

  /* mode: walk | play (timeline) | run | offstage | edge (sniff/paw loop) | oncard */
  const dog = { mode: "walk", set: "walk", f: 0, u: 0, L: 0, T: null, i: 0, next: null, wait: 0,
                trick: "", label: "", last: "", pending: "", forced: null, nextTry: 3, lost: 0,
                gy: null, cardEl: null, hop: null, holdX: false, wantEdge: "", lastEdge: "", kind: "", leave: 0, since: 0 };

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
  const own = screen => screen / (SC * K);
  const Wo = () => W / (SC * K);                    // screen width in owner px
  const floorY = () => H - 6;
  const groundY = () => dog.gy == null ? floorY() : dog.gy;
  const headY = () => groundY() - px(DOG_H) * 0.62;
  const hopMax = () => px(DOG_H);

  function extent(set = dog.set, f = dog.f, L = dog.L) {
    const bb = E.bbox[set][f];
    return [px(L + bb[0]), px(L + bb[2])];
  }

  /* ---------- timeline builders. Steps: [set, frame, seconds, L, label] ---------- */
  function once(T, s, L, a, b, label, sec) {
    const st = a <= b ? 1 : -1;
    for (let f = a; ; f += st) { T.push([s, f, sec || E.dur[s][f], L, label]); if (f === b) break; }
  }
  function loopTo(T, s, L, from, to, minSec, label, speed = 0) {
    const n = N(s); let t = 0, f = from % n, x = L;
    for (let guard = 0; guard < 5000; guard++) {
      const d = E.dur[s][f]; T.push([s, f, d, x, label]); t += d; x += speed * d;
      if (f === to && t >= minSec) break;
      f = (f + 1) % n;
    }
    return x;
  }
  const rest = (T, Ll, a, b) => T.push(["liedown", N("liedown") - 1, rnd(a, b), Ll, "resting"]);

  function getup(s, Ll) {
    const T = [];
    once(T, s, Ll, 1, N(s) - 1, s === "getuprun" ? "gets up, runs off" : "gets up, walks on");
    const [, , f, dx] = J(s === "getuprun" ? "getuprun>run" : "getupwalk>walk");
    return { T, next: { mode: s === "getuprun" ? "run" : "walk", f, L: Ll + dx } };
  }
  const maxRight = T => Math.max(...T.map(([s, f, , L]) => L + E.bbox[s][f][2]));
  const files = T => [...new Set(T.map(([s, f]) => M.sets[s].frames[f][0]))];

  const TRICKS = {
    sit: { weight: 1, at: () => J("walk>sit")[1], plan(Lw) {
      const T = [], [, , s0, dx] = J("walk>sit"), Ls = Lw + dx, ns = N("sit");
      const [, h, s99] = J("sithold>sit");
      once(T, "sit", Ls, s0, ns - 1, "sits + gives paw");
      loopTo(T, "sithold", Ls, h + 1, h, rnd(2, 4), "holds paw up");
      once(T, "sit", Ls, s99 - 1, s0, "stands up", 1 / 40);
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
          once(T, "belly", Lb, nb - 2, 1, "rolls back", 1 / 40);
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

  function choose() {
    const names = Object.keys(TRICKS).filter(k => k !== dog.last);
    let r = Math.random() * names.reduce((a, k) => a + TRICKS[k].weight, 0);
    for (const k of names) if ((r -= TRICKS[k].weight) <= 0) return k;
    return names[0];
  }
  function tryStart(name, opts) {
    const p = TRICKS[name].plan(dog.L, opts || {});
    const need = files(p.T);
    need.forEach(img);
    const fits = maxRight(p.mustFit ? p.T.slice(0, p.mustFit) : p.T) <= Wo() - 10 && extent()[0] >= 4;
    if (!fits || !need.every(ready)) return false;
    Object.assign(dog, { mode: "play", T: p.T, i: 0, u: 0, next: p.next, trick: name, pending: "" });
    if (!opts) dog.last = name;
    return true;
  }

  /* ---------- solid cards ---------- */
  function cards() {
    return [...document.querySelectorAll(".card24")].map(el => {
      const r = el.getBoundingClientRect();
      return { el, l: r.left, r: r.right, t: r.top, b: r.bottom };
    }).filter(c => c.r > 0 && c.l < W && c.b > 0 && c.t < H);
  }
  function topbar() {
    const b = document.querySelector(".bar");
    return b ? b.getBoundingClientRect().bottom : 56;
  }
  function hasSide(c) { return c.l > 36 || c.r < W - 36; }   // a full-width phone card has no side to walk into
  function canHop(c) {
    const rise = floorY() - c.t;
    return rise >= 40 && rise <= hopMax() + 8 && c.t >= topbar() + 8 && c.b > floorY() - 4;
  }
  function landOff() {
    const f = E.jump_air[1], bb = E.bbox.jump[f];
    return J("walk>jump")[3] + (bb[0] + bb[2]) / 2;
  }
  /* a card the chest is about to walk into (not one the dog can walk under) */
  function frontCard() {
    const [x0, x1] = extent();
    const feet = groundY(), head = headY();
    let best = null;
    for (const c of cards()) {
      if (c.r < x0 + 8 || c.l > x1 + 90) continue;
      if (c.t > feet - 8 || c.b < head) continue;
      if (!best || c.l < best.l) best = c;
    }
    return best;
  }
  function cardNear() {
    const nose = extent()[1], feet = groundY(), head = headY();
    return cards().some(c => c.l < nose + 360 && c.r > nose - 20 && c.t < feet - 8 && c.b > head);
  }
  function preload(set) {
    const fs = new Set(M.sets[set].frames.map(fr => fr[0]));
    fs.forEach(img);
    return [...fs].every(ready);
  }
  function pinToEdge(card) {
    const over = extent()[1] - (card.l - 2);
    if (over > 0) dog.L -= own(over);
    dog.holdX = true;
  }
  function startHop(card, dir) {
    if (!preload("jump")) return false;
    const [, , to, dx] = J("walk>jump");
    const Lj = dog.L + dx;
    const T = [];
    once(T, "jump", Lj, to, N("jump") - 1, dir === "up" ? "hops up" : "hops down");
    const [, , wf, wdx] = J("jump>walk");
    dog.hop = { y0: groundY(), y1: dir === "up" ? card.t : floorY(), a0: E.jump_air[0], a1: E.jump_air[1] };
    Object.assign(dog, {
      mode: "play", T, i: 0, u: 0, trick: "hop", pending: "", holdX: false, label: T[0][4],
      next: { mode: dir === "up" ? "oncard" : "walk", f: (wf + 1) % N("walk"), L: Lj + wdx, card: card && card.el }
    });
    return true;
  }
  function tryEdge(card) {
    if (!dog.wantEdge || dog.wantEdge === dog.lastEdge) {
      const choices = ["sniff", "paw"].filter(k => k !== dog.lastEdge);
      dog.wantEdge = choices[Math.floor(Math.random() * choices.length)] || "sniff";
    }
    const kind = dog.wantEdge;
    const set = kind === "sniff" ? "sniffbox" : "pawbox";
    const loop = kind === "sniff" ? "sniffloop" : "pawloop";
    if (!preload(set) || !preload(loop)) return false;
    const noseOff = E.bbox[set][N(set) - 1][2];
    const opts = (E.entry[set] && E.entry[set][dog.f]) || [];
    const edge = own(card.l);
    const atEdge = extent()[1] >= card.l - 8;
    let best = null;
    for (const [j, dx] of opts) {
      const err = dog.L + dx + noseOff - edge;      // + = nose would pass the card
      if (err > (atEdge ? 48 : 14)) continue;       // entry tables stop ~30 owner px short of a pinned nose
      if (!atEdge && err < -48) continue;
      if (!best || err > best.err) best = { j, dx, err };
    }
    if (!best) return false;
    const L = edge - noseOff;                       // wait-pose nose on the card edge; small pose pop is the table gap
    const T = [];
    once(T, set, L, best.j, N(set) - 1, kind === "sniff" ? "sniffs the card" : "paws the card");
    const loopFrom = kind === "sniff" ? 0 : 13;     // pawbox last frame joins pawloop frame 14 (not stored in engine.json)
    Object.assign(dog, {
      mode: "play", T, i: 0, u: 0, trick: kind, pending: "", holdX: false, label: T[0][4],
      lastEdge: kind, wantEdge: "",
      next: { mode: "edge", f: loopFrom, L, set: loop, card: card.el, kind }
    });
    return true;
  }
  function stillBlocks(el) {
    if (!el || !el.isConnected) return false;
    const r = el.getBoundingClientRect();
    const [x0, x1] = extent();
    if (r.bottom < headY() || r.top > floorY() - 8) return false;
    if (r.right < x0 + 8 || r.left > x1 + 36) return false;
    return true;
  }
  function applyHop() {
    if (!dog.hop || dog.set !== "jump") return;
    const { y0, y1, a0, a1 } = dog.hop, f = dog.f;
    dog.gy = f <= a0 ? y0 : f >= a1 ? y1 : y0 + (y1 - y0) * (f - a0) / (a1 - a0);
  }
  function clearCard() {
    dog.gy = null; dog.cardEl = null; dog.hop = null; dog.kind = ""; dog.wantEdge = "";
  }

  function goto(next) {
    dog.hop = null; dog.T = null; dog.trick = ""; dog.holdX = false;
    if (next.mode === "edge") {
      Object.assign(dog, { mode: "edge", set: next.set, f: next.f, u: 0, L: next.L, cardEl: next.card, kind: next.kind, gy: null, label: "" });
      dog.leave = J(next.set + ">walk")[1];
      return;
    }
    if (next.mode === "oncard") {
      const r = next.card && next.card.isConnected ? next.card.getBoundingClientRect() : null;
      if (!r || r.top > floorY() - 24 || r.bottom < headY()) {
        Object.assign(dog, { mode: "walk", set: "walk", f: next.f, u: 0, L: next.L, label: "" });
        clearCard();
      } else {
        Object.assign(dog, { mode: "oncard", set: "walk", f: next.f, u: 0, L: next.L, cardEl: next.card, gy: r.top, label: "on the card" });
        dog.since = NOW;
      }
      dog.nextTry = NOW + 8;
      return;
    }
    Object.assign(dog, { mode: next.mode, set: next.mode === "run" ? "run" : "walk", f: next.f, u: 0, L: next.L, label: "" });
    clearCard();
    dog.nextTry = NOW + rnd(2.5, 6);
  }
  function enterLeft() {
    Object.assign(dog, { set: "walk", f: 0, u: 0, mode: "walk", T: null, trick: "", label: "" });
    clearCard();
    dog.L = -E.bbox.walk[0][2] - 20 / (SC * K);
    dog.nextTry = NOW + rnd(2, 4);
  }

  function step(dt) {
    const [x0, x1] = extent();
    dog.lost = (x1 < -40 || x0 > W + 40) && dog.mode !== "offstage" && dog.mode !== "edge" ? dog.lost + dt : 0;
    if (dog.lost > 6) { dog.lost = 0; enterLeft(); }

    if (dog.mode === "offstage") { dog.wait -= dt; if (dog.wait <= 0) enterLeft(); return; }

    if (dog.mode === "play") {
      dog.u += dt;
      while (dog.T && dog.u >= dog.T[dog.i][2]) {
        dog.u -= dog.T[dog.i][2];
        if (++dog.i >= dog.T.length) { const u = dog.u; goto(dog.next); return step(u); }
      }
      if (dog.mode !== "play") return;
      const s = dog.T[dog.i]; dog.set = s[0]; dog.f = s[1]; dog.L = s[3]; dog.label = s[4];
      applyHop();
      return;
    }

    if (dog.mode === "edge") {
      const D = E.dur[dog.set];
      dog.u += dt;
      while (dog.u >= D[dog.f]) {
        dog.u -= D[dog.f];
        dog.f = (dog.f + 1) % D.length;
        if (dog.f === dog.leave && !stillBlocks(dog.cardEl)) {
          const j = J(dog.set + ">walk");
          Object.assign(dog, { mode: "walk", set: "walk", f: j[2], u: 0, L: dog.L + j[3], T: null, trick: "", label: "" });
          clearCard();
          dog.nextTry = NOW + rnd(2, 4);
          return;
        }
      }
      dog.label = dog.kind === "paw" ? "paws the card" : "sniffs the card";
      return;
    }

    if (dog.mode === "oncard") {
      const el = dog.cardEl;
      const r = el && el.isConnected ? el.getBoundingClientRect() : null;
      const mid = (extent()[0] + extent()[1]) / 2;
      const gone = !r || r.top < topbar() + 16 || r.top > floorY() - 16 || mid < r.left + 8 || mid > r.right - 8;
      if (r && !gone) dog.gy = r.top;
      if (!gone && NOW < dog.since + 1.1) { dog.label = "on the card"; return; }
      if (gone && dog.f === J("walk>jump")[1] && startHop(null, "down")) return step(0);
      dog.label = gone ? "hops down" : "on the card";
      const Dw = E.dur.walk;
      dog.u += dt;
      while (dog.u >= Dw[dog.f]) { dog.u -= Dw[dog.f]; dog.f = (dog.f + 1) % Dw.length; }
      return;
    }

    if (cards().length) ["jump", "sniffbox", "sniffloop", "pawbox", "pawloop"].forEach(preload);
    const front = dog.mode === "walk" ? frontCard() : null;
    if (dog.mode === "run" && frontCard()) {
      dog.holdX = true;
      if (dog.f === J("run>walk")[1]) {
        const [, , wf, dx] = J("run>walk");
        dog.mode = "walk"; dog.set = "walk"; dog.f = wf; dog.L += dx; dog.u = 0;
      }
    }
    if (front && canHop(front)) {
      if (dog.f === J("walk>jump")[1] && startHop(front, "up")) return step(0);
      if (extent()[1] >= front.l - 1) pinToEdge(front);
    } else if (front) {
      if (hasSide(front) && tryEdge(front)) return step(0);
      if (extent()[1] >= front.l - 1) {
        pinToEdge(front);
        if (!hasSide(front)) dog.label = "waiting";
      }
    }

    const D = E.dur[dog.set];
    if (!dog.holdX) dog.L += (dog.mode === "run" ? E.speed.run : E.speed.walk) * dt;
    dog.holdX = false;
    dog.u += dt;
    while (dog.u >= D[dog.f]) {
      dog.u -= D[dog.f]; dog.f = (dog.f + 1) % D.length;
      if (dog.mode !== "walk") continue;
      const blocked = cardNear();
      if (!dog.pending && NOW >= dog.nextTry && !blocked) dog.pending = choose();
      if (dog.pending && NOW >= dog.nextTry && dog.f === TRICKS[dog.pending].at() && !blocked) {
        const name = dog.pending, opts = dog.forced;
        if (tryStart(name, opts)) { dog.forced = null; dog.u = 0; return step(0); }
        if (!opts) dog.pending = "";
        dog.nextTry = NOW + rnd(1, 2.5);
      }
    }
    if (dog.mode === "walk" && extent()[0] > W + 10) {
      dog.mode = "offstage"; dog.wait = rnd(1.5, 3.5); dog.gy = null;
    }
  }

  let lastDraw = null;
  function draw() {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (dog.mode === "offstage") return;
    const S = M.sets[dog.set], rec = S.frames[dog.f];
    let d = [rec, S.ground, dog.L, groundY()];
    if (!ready(rec[0])) d = lastDraw;
    if (!d) return;
    lastDraw = d;
    const [[file, sx, sy, w, h, ox, oy], ground, L, gy] = d;
    ctx.drawImage(img(file), sx, sy, w, h, px(L) + ox * K, gy + (oy - ground * SC) * K, w * K, h * K);
  }

  let last = 0;
  function tick(t) {
    const dt = last ? Math.min(0.05, (t - last) / 1000) : 0;
    last = t;
    const s = dt * (window.__dog24speed || 1);
    NOW += s;
    try { step(s); } catch (e) { dog.label = "error " + (e && e.message); }
    draw();
    requestAnimationFrame(tick);
  }

  Promise.all([fetch(BASE + "frames.json").then(r => r.json()), fetch(BASE + "engine.json").then(r => r.json())])
    .then(([m, e]) => {
      M = m; E = e; SC = m.sc;
      img(M.sets.walk.frames[0][0]);
      resize(); addEventListener("resize", resize);
      if (window.visualViewport) visualViewport.addEventListener("resize", resize);
      enterLeft();
      dog.L = -E.bbox.walk[0][0] + 40 / (SC * K);
      requestAnimationFrame(tick);
    });

  window.__dog24 = {
    piece: 3,
    state: () => ({ mode: dog.mode, set: dog.set, f: dog.f, L: dog.L, trick: dog.trick, label: dog.label,
                    pending: dog.pending, wait: dog.wait, x: M ? extent() : null, K, W, H,
                    gy: dog.gy, feet: M ? groundY() : null, floor: M ? floorY() : null, kind: dog.kind }),
    force: (name, opts = {}) => { dog.pending = name; dog.forced = opts; dog.nextTry = 0; },
    plan: (name, opts) => TRICKS[name].plan(0, opts),
  };
})();
