/* Site dog, 24 fps pitbull engine.
 * Pieces (see the heartbeats skill): 1 walk (done), 2 floor tricks (done), 3 solid cards (done),
 * 4 ride cards + jump-down art + neighbours (this), 5 phone layout. Test page: dog-play24.html.
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
 * to the floor.
 *
 * Piece 4: standing on a card the dog walks along it and rides it as the page scrolls (feet = card top,
 * also during a sit). A card at the same height just past the right edge (the 2-column row-mate) is
 * walked onto across the gap. Otherwise, at the right edge, the jump-down art takes it off: walk-in frames
 * on the card, the drop is stretched to the real height (the art's own fall curve, jd_low), and it lands on
 * the first card below the landing spot or on the floor. A card that sinks to the floor is stepped off.
 * Emergency: a card carried up toward the top bar before the dog reaches the edge -> the jump art hop
 * straight down to the floor (piece 3's hop).
 *
 * Piece 5: the dog stays on screen on phones AND laptops. It has a direction (dir +1 right, -1 left).
 * All logic runs in "dog space": when it faces left, card rects are mirrored (x -> W - x) and the frame is
 * drawn mirrored, so every rule above (edges, row-mates, jump-down, entry tables) works unchanged both ways.
 * Turning uses the owner's turn-around art (walk -> slow -> stop -> turn -> walk back), entered mid-walk
 * from the entry table so it ends just inside the screen edge, then hands off to the mirrored walk.
 * On a card, the jump-down takes off where the landing still fits on screen (phone cards are full width,
 * so that is inside the card edge); a dog already past that point turns round and walks the other way.
 * Phone vs laptop (W >= 900) still picks the scale and layout (2 columns + row-mates on laptops).
 *
 * Piece 6: the owner's walk->run and run->walk art. "run" is a floor trick (walk -> speeds up -> 1-5 run
 * strides -> slows to a walk), sized to end before the next card / the turn-round zone. Any run (also the
 * get-up-run) slows down with the art at a cycle start when the next stride would leave too little room;
 * the old hard run->walk join is only the fallback. Card sides get a third wait: "pick" = the one-paw
 * "pick me" (pawone walk-in, then its scratch loop).
 *
 * Piece 7: a card scrolling up from under a dog on the floor picks it up. When a card's top passes up
 * through the dog's feet (and the dog's middle is over that card), the dog stands on it and rides it from
 * then on, also mid-trick: sit / sniff / lie / turn keep playing with the feet on the rising card, and the
 * trick ends in "oncard" instead of the floor walk. A lying dog carried toward the top bar skips to its
 * get-up. Not scooped: runs, hops, jump-downs, and the card-side waits (the card in front is the one it
 * sniffs; a card under it there is rare).
 *
 * Piece 8: near the top of the screen the dog jumps down to the card below. "Near the top" = its head would
 * reach the top bar soon at the card's current speed (or, card standing still, the card is in the top band).
 * The landing card is picked again at take-off from the LIVE positions: the highest card under the landing spot
 * that will still be clear of the top bar for a few seconds; a card below that is itself near the top is
 * skipped for the next one down, else the floor. Fast scroll: the hop starts from any walk frame and the
 * wind-up (sit back, rear up) plays faster, so the dog leaves before it is carried off the top.
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

  let M, E, SC, K = 1, W = 0, H = 0, DPR = 1, NOW = 0, PHONE = true;
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
                dir: 1, holdT: 0,
                gy: null, cardEl: null, hop: null, jd: null, satOn: null, holdX: false, wantEdge: "", lastEdge: "", kind: "", leave: 0, since: 0 };

  function resize() {
    DPR = Math.min(2, devicePixelRatio || 1);
    const vv = window.visualViewport;               // the VISIBLE viewport (phones: no pinch-zoom/toolbars)
    W = Math.round(vv ? vv.width : document.documentElement.clientWidth || innerWidth);
    H = Math.round(vv ? vv.height : innerHeight);
    cv.style.width = W + "px"; cv.style.height = H + "px";
    cv.width = Math.round(W * DPR); cv.height = Math.round(H * DPR);
    K = (W >= 900 ? 0.9 : 0.7);
    PHONE = W < 900;                     // walk ~105 px long on phones, ~135 px on desktops
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

  /* piece 5: turn-around. Lt = turn canvas left, j = first turn frame (entry table / walk>turn). */
  const TURN_PH = [[29, "walks"], [57, "slows down"], [78, "stops"], [111, "turns around"], [1e9, "walks back"]];
  function turnPlan(Lt, j, card) {
    const T = [];
    for (let f = j; f < N("turn"); f++) T.push(["turn", f, E.dur.turn[f], Lt, TURN_PH.find(p => f < p[0])[1]]);
    const [, , wf, dx] = J("turn>walkm");
    return { T, next: { mode: card ? "oncard" : "walk", f: wf, flipL: Lt + dx, card } };
  }
  let TURN_R = null, TURN_L = null;                 // per turn frame: furthest right / left canvas x from there on
  function turnReach() {
    if (TURN_R) return;
    const bb = E.bbox.turn; TURN_R = []; TURN_L = [];
    for (let j = bb.length - 1, r = -1e9, l = 1e9; j >= 0; j--) { r = Math.max(r, bb[j][2]); l = Math.min(l, bb[j][0]); TURN_R[j] = r; TURN_L[j] = l; }
  }
  /* turn so the whole turn stays left of `limit` (screen px, dog space) and right of `lo`.
     urgent = take any fitting option now; otherwise only start when the turn would end close to the limit. */
  function tryTurn(limit, lo, urgent, card) {
    if (!preload("turn")) return false;
    turnReach();
    let best = null, least = null;
    for (const [j, dx] of (E.entry.turn && E.entry.turn[dog.f]) || []) {
      const Lt = dog.L + dx, R = px(Lt + TURN_R[j]);
      if (px(Lt + TURN_L[j]) < lo) continue;
      if (!least || R < least.R) least = { j, Lt, R };
      if (R > limit) continue;
      if (!best || R > best.R) best = { j, Lt, R };
    }
    if (!best && urgent) best = least;              // already at/over the edge: the turn that reaches out least
    if (!best || (!urgent && best.R < limit - px(170))) return false;
    const p = turnPlan(best.Lt, best.j, card);
    Object.assign(dog, { mode: "play", T: p.T, i: 0, u: 0, next: p.next, trick: "turn", pending: "", holdX: false, label: p.T[0][4], holdT: 0 });
    return true;
  }

  /* piece 6: run <-> walk with the owner's transition art (travel is baked into the frames; canvas stays put). */
  function r2wPlan(Lr) {                           // Lr = run canvas left at run frame 1 (cycle start)
    const T = [], [, , , d1] = J("run>r2w"), Lt = Lr + d1, [, , wf, d2] = J("r2w>walk");
    once(T, "r2w", Lt, 0, N("r2w") - 1, "slows to a walk");
    return { T, next: { mode: "walk", f: wf, L: Lt + d2 } };
  }
  function floorCardLimit(x1) {                    // screen x of the first card ahead in the dog's floor row
    let lim = 1e9;
    for (const c of cards()) if (c.t < floorY() - 8 && c.b > headY() && c.l > x1 - 8) lim = Math.min(lim, c.l - 10);
    return lim;
  }
  const RUN_CYC = () => E.dur.run.reduce((a, b) => a + b, 0);
  // running: start slowing at this cycle start if the next cycle would leave too little room for the slow-down
  // (r2w reaches ~440 owner px past the run's nose) before the first card ahead or the turn-round zone.
  function runShouldStop() {
    const reach = J("run>r2w")[3] + Math.max(...E.bbox.r2w.map(b => b[2]));
    const end = px(dog.L + reach + E.speed.run * RUN_CYC());
    return end > Math.min(W - px(420), floorCardLimit(extent()[1]));
  }

  const TRICKS = {
    run: { weight: .7, at: () => J("walk>w2r")[1], plan(Lw, opts = {}) {
      const [, , , d1] = J("walk>w2r"), Lt = Lw + d1, [, , rf, d2] = J("w2r>run");
      const room = Math.min(Wo() - 300, own(floorCardLimit(extent()[1])));
      let best = null;
      for (let k = opts.cycles || Math.ceil(rnd(1, 5)); k >= 1; k--) {
        const T = [];
        once(T, "w2r", Lt, 0, N("w2r") - 1, "speeds up");
        const x = loopTo(T, "run", Lt + d2, rf, N("run") - 1, (k - 1) * RUN_CYC(), "runs", E.speed.run);
        const r = r2wPlan(x);
        best = { T: T.concat(r.T), next: r.next };
        if (maxRight(best.T) <= room) return Object.assign(best, { fitT: best.T });
      }
      return Object.assign(best, { fitT: null });   // too little room: only a forced run plays
    } },

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

    turn: { weight: .5, at: () => J("walk>turn")[1], plan(Lw) {
      return turnPlan(Lw + J("walk>turn")[3], J("walk>turn")[2], null);
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
      const run = opts.run !== undefined ? opts.run : Math.random() < .35;
      const g = getup(run ? "getuprun" : "getupwalk", Ll);
      // piece 5: the dog never leaves the screen, so the get-up (walk version) must fit too
      return { T: T.concat(g.T), next: g.next, fitT: walkFits ? T.slice(0, lying) : null };
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
    const fits = (p.fitT !== null || opts) && maxRight(p.fitT || p.T) <= Wo() - 10 && extent()[0] >= 4;
    if (!fits || !need.every(ready)) return false;
    Object.assign(dog, { mode: "play", T: p.T, i: 0, u: 0, next: p.next, trick: name, pending: "" });
    if (!opts) dog.last = name;
    return true;
  }

  /* ---------- solid cards (rects in dog space: mirrored when the dog faces left) ---------- */
  function cards() {
    return [...document.querySelectorAll(".card24")].map(rectOf).filter(c => c.r > 0 && c.l < W && c.b > 0 && c.t < H);
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
      // piece 6 fix: a card the dog already stands in front of (not hoppable) is behind it. Skip it here, or it
      // hides the NEXT card and the dog walks straight through that one (seen on laptop rows: card 11 -> 12).
      if (c.l < x1 - px(120) && !canHop(c)) continue;
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
  // piece 8: highest card under screen x `mid` (dog space), below src, that stays clear of the top bar for `sec` s
  function landCard(srcEl, mid, sec) {
    const src = srcEl && srcEl.isConnected ? rectOf(srcEl) : null;
    let best = null;
    for (const el of document.querySelectorAll(".card24")) {
      if (el === srcEl) continue;
      const m = rectOf(el);
      if (src && m.t < src.t + 30) continue;
      if (m.t > floorY() - 10 || mid < m.l + 12 || mid > m.r - 12) continue;
      if (m.t < TOP_BAND() || tooHigh(m.t, sec)) continue;   // this one is near the top too: try the next one down
      if (!best || m.t < best.t) best = m;
    }
    return best;
  }
  function startHop(card, dir, rate = 1) {
    if (!preload("jump")) return false;
    let [, , to, dx] = J("walk>jump");
    if (rate !== 1) to = 30;                        // piece 8, no time: start from the crouch (small pose pop)
    const Lj = dog.L + dx;
    const T = [];
    once(T, "jump", Lj, to, N("jump") - 1, dir === "up" ? "hops up" : "hops down");
    if (rate !== 1) T.forEach(st => { if (st[1] < E.jump_air[0]) { st[2] /= rate; st[4] = "hops down (quick!)"; } });
    const [, , wf, wdx] = J("jump>walk");
    let below = null, mid = 0;
    if (dir === "down" && dog.cardEl) {
      const bb = E.bbox.jump[N("jump") - 1];
      mid = px(Lj + (bb[0] + bb[2]) / 2);
      below = landCard(dog.cardEl, mid, 2);      // first guess; picked again at take-off (applyHop)
    }
    dog.hop = { y0: groundY(), y1: dir === "up" ? card.t : below ? below.t : floorY(), a0: E.jump_air[0], a1: E.jump_air[1],
                src: dir === "down" ? dog.cardEl : null, tgt: dir === "up" ? card.el : below && below.el, mid, picked: dir === "up" };
    Object.assign(dog, {
      mode: "play", T, i: 0, u: 0, trick: "hop", pending: "", holdX: false, label: T[0][4],
      next: { mode: dir === "up" || below ? "oncard" : "walk", f: (wf + 1) % N("walk"), L: Lj + wdx, card: dir === "up" ? card.el : below && below.el }
    });
    return true;
  }
  // kind -> [walk-in set, wait loop, label, loop frame that follows the walk-in's last frame]
  // pawbox last frame joins pawloop frame 14 (not stored in engine.json); pawone (piece 6) is measured.
  const EDGE = { sniff: ["sniffbox", "sniffloop", "sniffs the card", () => 0],
                 paw: ["pawbox", "pawloop", "paws the card", () => 13],
                 pick: ["pawone", "pawoneloop", "pick me! (paw on the card)", () => J("pawone>pawoneloop")[2]] };
  function tryEdge(card) {
    if (!dog.wantEdge || dog.wantEdge === dog.lastEdge) {
      const choices = ["sniff", "paw", "pick"].filter(k => k !== dog.lastEdge);
      dog.wantEdge = dog.forceEdge || choices[Math.floor(Math.random() * choices.length)] || "sniff";
    }
    const kind = dog.wantEdge;
    const set = EDGE[kind][0], loop = EDGE[kind][1];
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
    once(T, set, L, best.j, N(set) - 1, EDGE[kind][2]);
    const loopFrom = EDGE[kind][3]();
    dog.forceEdge = "";
    Object.assign(dog, {
      mode: "play", T, i: 0, u: 0, trick: kind, pending: "", holdX: false, label: T[0][4],
      lastEdge: kind, wantEdge: "",
      next: { mode: "edge", f: loopFrom, L, set: loop, card: card.el, kind }
    });
    return true;
  }
  function stillBlocks(el) {
    if (!el || !el.isConnected) return false;
    const r = rectOf(el);
    const [x0, x1] = extent();
    if (r.b < headY() || r.t > floorY() - 8) return false;
    if (r.r < x0 + 8 || r.l > x1 + 36) return false;
    return true;
  }
  function applyHop() {
    if (!dog.hop || dog.set !== "jump") return;
    const h = dog.hop, f = dog.f, live = el => el && el.isConnected ? Math.min(el.getBoundingClientRect().top, floorY()) : null;
    if (!h.picked && f >= h.a0) {                   // piece 8: take-off: choose the landing from where cards are NOW
      h.picked = true;
      const air = E.dur.jump.slice(f, h.a1).reduce((a, b) => a + b, 0);
      const t = landCard(h.src, h.mid, air + .3);
      h.tgt = t && t.el; h.y1 = t ? t.t : floorY();
      Object.assign(dog.next, { mode: t ? "oncard" : "walk", card: t && t.el });
      dog.label = t ? "hops down to card " + (t.el.dataset.n || "") : "hops down to the floor";
      dog.T.forEach(st => { if (st[1] >= f) st[4] = dog.label; });
    }
    if (h.src) h.y0 = Math.max(live(h.src) ?? h.y0, topbar() + px(DOG_H) * 1.05);   // rides until take-off, head stays below the bar
    if (h.tgt) h.y1 = live(h.tgt) ?? h.y1;          // land where the card IS now, not where it was
    const { y0, y1, a0, a1 } = h;
    dog.gy = f <= a0 ? y0 : f >= a1 ? y1 : y0 + (y1 - y0) * (f - a0) / (a1 - a0);
  }
  function rideTop() {                              // live top of the card the dog stands on (never below the floor)
    const el = dog.cardEl;
    if (!el || !el.isConnected) return null;
    return Math.min(el.getBoundingClientRect().top, floorY());
  }
  function applyJD() {
    if (!dog.jd || dog.set !== "jumpdown") return;
    const j = dog.jd, f = dog.f, box = E.jd_box, low = E.jd_low;
    if (!j.picked && f >= E.jd_air[0]) {            // piece 8: leaving the card: re-check the landing card
      j.picked = true;
      if (j.tgt && j.tgt.isConnected && rectOf(j.tgt).t < TOP_BAND()) {
        const t = j.src.isConnected ? jdTarget(rectOf(j.src), j.Ljd) : null;
        j.tgt = t && t.el;
        Object.assign(dog.next, { mode: t ? "oncard" : "walk", card: t && t.el });
      }
    }
    const c = j.src.isConnected ? j.src.getBoundingClientRect().top : j.c0;
    const t = j.tgt && j.tgt.isConnected ? Math.min(j.tgt.getBoundingClientRect().top, floorY()) : floorY();
    if (f < E.jd_air[0]) { dog.gy = c + px(box.floor - box.top); return; }
    if (f >= E.jd_air[1]) { dog.gy = t; return; }
    const p = Math.max(0, Math.min(1, (low[f] - box.top) / (box.floor - box.top)));
    dog.gy = c + (t - c) * p + px(box.floor - low[f]);   // lowest paw follows the art's own fall, stretched
  }
  function clearCard() {
    dog.gy = null; dog.cardEl = null; dog.hop = null; dog.jd = null; dog.kind = ""; dog.wantEdge = "";
  }

  /* ---------- piece 7: a rising card scoops the dog up ---------- */
  const PREV = new WeakMap();                       // card element -> its top last frame
  const SCOOP_OK = { walk: 1, sit: 1, sniff: 1, lie: 1, turn: 1 };
  function scoop() {
    const feet = floorY();
    let hit = null;
    for (const el of document.querySelectorAll(".card24")) {
      const top = el.getBoundingClientRect().top, was = PREV.get(el);
      PREV.set(el, top);
      if (hit || was == null || dog.gy != null || dog.cardEl) continue;
      if (!(was >= feet - 1 && top < feet - 1)) continue;          // its top just came up through the feet
      if (top - px(DOG_H) * 1.1 < topbar()) continue;               // a fling past the top bar: let it go by
      const c = rectOf(el), [x0, x1] = extent(), mid = (x0 + x1) / 2;
      if (mid < c.l + px(40) || mid > c.r - px(40)) continue;       // middle of the dog must be over the card
      hit = { el, top };
    }
    if (!hit) return false;
    const trick = dog.mode === "walk" ? "walk" : dog.mode === "play" ? dog.trick : "";
    if (!SCOOP_OK[trick]) return false;
    dog.cardEl = hit.el; dog.gy = hit.top; dog.vy = null; dog.satOn = null; dog.scooped = true;
    if (dog.mode === "walk") {
      Object.assign(dog, { mode: "oncard", set: "walk", label: "picked up by the card", pending: "" });
      dog.edgePlan = Math.random() < .45 ? "turn" : "jump";
      dog.nextTry = NOW + rnd(1, 3);
    }
    return true;
  }
  function cutLie() {                               // lying on a card carried up: skip ahead to the get-up
    const i = dog.T.findIndex((st, k) => k > dog.i && /^gets up/.test(st[4]));
    if (i > dog.i) { dog.i = i; dog.u = 0; }
  }

  /* ---------- piece 4: on a card ---------- */
  function rectOf(el) {
    const r = el.getBoundingClientRect();
    return dog.dir > 0 ? { el, l: r.left, r: r.right, t: r.top, b: r.bottom } : { el, l: W - r.right, r: W - r.left, t: r.top, b: r.bottom };
  }
  // landing reach of the jump-down art past its box edge (screen px): take off no later than W - 6 - this
  const jdReach = () => px(E.bbox.jumpdown[N("jumpdown") - 1][2] - E.jd_box.edge);
  function levelMate(c) {                           // same-height card just past the right edge (2-column row-mate)
    for (const el of document.querySelectorAll(".card24")) {
      if (el === c.el) continue;
      const m = rectOf(el);
      if (Math.abs(m.t - c.t) <= 4 && m.l >= c.r - 2 && m.l - c.r <= 60) return m;
    }
    return null;
  }
  function jdTarget(src, Ljd) {                     // first card under the landing spot, else the floor
    const bb = E.bbox.jumpdown[N("jumpdown") - 1];
    const mid = px(Ljd + (bb[0] + bb[2]) / 2);
    let best = null;
    for (const el of document.querySelectorAll(".card24")) {
      if (el === src.el) continue;
      const m = rectOf(el);
      if (m.t < src.t + 30 || m.t > floorY() - 10) continue;
      if (mid < m.l + 12 || mid > m.r - 12) continue;
      if (m.t < TOP_BAND() || tooHigh(m.t, 1.5)) continue;   // piece 8: near the top too -> the next card down
      if (!best || m.t < best.t) best = m;
    }
    return best;
  }
  function startJD(c, j, Ljd) {
    if (!preload("jumpdown")) return false;
    const tgt = jdTarget(c, Ljd);
    const T = [];
    once(T, "jumpdown", Ljd, j, N("jumpdown") - 1, tgt ? "jumps down to a card" : "jumps down");
    const [, , wf, wdx] = J("jumpdown>walk");
    dog.jd = { src: c.el, tgt: tgt && tgt.el, c0: c.t, Ljd };
    Object.assign(dog, {
      mode: "play", T, i: 0, u: 0, trick: "jumpdown", pending: "", holdX: false, label: T[0][4],
      next: { mode: tgt ? "oncard" : "walk", f: (wf + 1) % N("walk"), L: Ljd + wdx, card: tgt && tgt.el }
    });
    return true;
  }
  function tryJD(c, force, P) {                     // enter the jump-down walk-in so the art's box edge = take-off point P
    const edge = own(P == null ? c.r : P) - E.jd_box.edge;   // L of the jump-down canvas
    const opts = (E.entry.jumpdown && E.entry.jumpdown[dog.f]) || [];
    let best = null;
    for (const [j, dx] of opts) {
      const err = dog.L + dx - edge;
      if (!force && Math.abs(err) > 16) continue;
      if (!best || Math.abs(err) < Math.abs(best.err)) best = { j, err };
    }
    if (!best && force && dog.f === J("walk>jumpdown")[1]) best = { j: J("walk>jumpdown")[2], err: 0 };
    return best ? startJD(c, best.j, edge) : false;
  }
  function trackVy(el, top, dt) {                  // card speed in px/s (- = rising), smoothed
    if (dog.vy == null || dog.vyEl !== el) { dog.vy = 0; dog.vyEl = el; }
    else if (dt > 0 && dog.gy != null) dog.vy += ((top - dog.gy) / dt - dog.vy) * Math.min(1, dt * 4);
  }
  // the head would reach the top bar within `sec` seconds at the card's current speed
  const tooHigh = (top, sec) => top + Math.min(0, dog.vy || 0) * sec - px(DOG_H) * 1.1 < topbar();
  // piece 8: "near the top of the screen": about to reach the top bar, or (card still) parked in the top band
  const TOP_BAND = () => topbar() + px(DOG_H) * 1.7;
  const nearTop = (top, sec) => tooHigh(top, sec) || top < TOP_BAND();
  function cutSit() {                               // riding card rising fast: stand up now (pose-matched exit)
    const T = dog.T, i = dog.i, cur = T[i];
    if (cur[4] === "stands up") return;
    const [, , s0] = J("walk>sit");
    const R = [];
    if (cur[0] === "sit") once(R, "sit", cur[3], cur[1], s0, "stands up", 1 / 40);   // still sitting down: reverse from here
    else R.push(...T.slice(i).filter(st => st[4] === "stands up"));                // holding paw: hold loop joins the stand-up
    dog.T = R; dog.i = 0; dog.u = 0;
  }
  function cutTurn() {                              // turn not past the slow-down yet: back to the walk it came from
    const j = dog.f, Lt = dog.L;
    for (let i = 0; i < N("walk"); i++)
      for (const [jj, dx] of E.entry.turn[i] || []) if (jj === j) {
        Object.assign(dog, { mode: "oncard", set: "walk", f: i, u: 0, L: Lt - dx, T: null, trick: "", label: "too high!" });
        return true;
      }
    return false;
  }
  function onCard(dt) {
    const el = dog.cardEl;
    if (!el || !el.isConnected) { goto({ mode: "walk", f: dog.f, L: dog.L }); return; }
    const c = rectOf(el);
    if (c.t >= floorY() - 2) {                      // card sank to the floor: just walk on
      Object.assign(dog, { mode: "walk", set: "walk", T: null, label: "" }); clearCard();
      dog.nextTry = NOW + rnd(2, 4); return;
    }
    trackVy(el, c.t, dt);
    dog.gy = Math.max(c.t, topbar() + px(DOG_H) * 1.05);
    ["jumpdown", "jump", "sit", "sithold"].forEach(preload);
    const [x0, x1] = extent(), mid = (x0 + x1) / 2;
    const mate = levelMate(c);
    if (mate && mid > c.r) { dog.cardEl = mate.el; dog.label = "steps across"; }
    // head would reach the top bar before the hop's ~2 s wind-up is over (at the card's current speed)
    // piece 8: wind-up 2.1 s + up to 1 s waiting for the joining walk frame
    const danger = nearTop(c.t, 3.3);
    const urgent = tooHigh(c.t, 1.4);                // no time for the full wind-up
    dog.label = danger ? "near the top!" : mate ? "walks to the next card" : "rides the card";
    if (danger) {
      dog.holdX = false;
      if (urgent && startHop(null, "down", 2.6)) { dog.quickAt = [Math.round(c.t), Math.round(dog.vy)]; return step(0); }
      if (dog.f === J("walk>jump")[1] && startHop(null, "down")) return step(0);
    }
    // Take-off point. The landing must stay on screen: use the card's own edge when that leaves room,
    // otherwise leap from inside the card (phone cards are full width), early enough to land on screen.
    // Per card the dog either jumps off or walks to the end and turns back (edgePlan, set on landing).
    const room = c.r + jdReach() + px(80) <= W;
    const P = room ? c.r : Math.min(c.r, W - px(80) - jdReach());
    const turnHere = dog.edgePlan === "turn" || P < c.l + px(300);
    if (!danger && !mate && dog.edgePlan !== "jumpNow" && (turnHere || x1 > P + px(40))) {
      const lim = Math.min(W - 4, c.r + px(60));    // nose may hang a little past the card; feet stay on it
      dog.label = "turns round on the card";
      if (!tooHigh(c.t, 8) && tryTurn(lim, c.l - px(60), x1 > lim - px(80), el)) return step(0);
      if (x1 > lim - px(60)) {
        dog.holdX = true; dog.holdT += dt;
        if (dog.holdT > 1.5 && tryJD(c, true, Math.min(c.r, x1))) { dog.holdT = 0; return step(0); }   // no turn fits: old jump
      }
    } else if (!danger && !mate) {
      if (x1 >= P - px(140) && tryJD(c, x1 >= P + px(20), P)) return step(0);
      if (x1 >= P + px(20)) dog.holdX = true;       // wait at the take-off point for a frame that joins the jump-down
    }
    // sometimes sit while riding (lower half of the screen, once per card, only if it fits on the card)
    if (!danger && !tooHigh(c.t, 7) && dog.satOn !== el && NOW >= dog.nextTry && c.t > H * 0.5 && dog.f === TRICKS.sit.at()) {
      dog.nextTry = NOW + rnd(2, 4);
      if (Math.random() < 0.5 && preload("sit") && preload("sithold")) {
        const p = TRICKS.sit.plan(dog.L);
        if (px(maxRight(p.T)) <= c.r - 10) {
          dog.satOn = el;
          p.next.mode = "oncard"; p.next.card = el;
          Object.assign(dog, { mode: "play", T: p.T, i: 0, u: 0, next: p.next, trick: "sit", pending: "" });
          return step(0);
        }
      } else dog.satOn = el;
    }
    if (!dog.holdX) dog.L += E.speed.walk * dt;
    dog.holdX = false;
    const Dw = E.dur.walk;
    dog.u += dt;
    while (dog.u >= Dw[dog.f]) { dog.u -= Dw[dog.f]; dog.f = (dog.f + 1) % Dw.length; }
  }

  function goto(next) {
    const flipped = next.flipL != null;
    dog.hop = null; dog.jd = null; dog.T = null; dog.trick = ""; dog.holdX = false; dog.holdT = 0;
    if (next.flipL != null) {                       // end of a turn: face the other way, same spot on screen
      next = Object.assign({}, next, { L: Wo() - next.flipL - M.sets.walk.canvas[0] });
      dog.dir = -dog.dir;
    }
    if (next.mode === "edge") {
      Object.assign(dog, { mode: "edge", set: next.set, f: next.f, u: 0, L: next.L, cardEl: next.card, kind: next.kind, gy: null, label: "" });
      dog.leave = J(next.set + ">walk")[1];
      return;
    }
    if (next.mode === "oncard") {
      const r = next.card && next.card.isConnected ? next.card.getBoundingClientRect() : null;
      if (!r || r.top > floorY() - 2 || r.bottom < 0) {
        Object.assign(dog, { mode: "walk", set: "walk", f: next.f, u: 0, L: next.L, label: "" });
        clearCard();
      } else {
        Object.assign(dog, { mode: "oncard", set: "walk", f: next.f, u: 0, L: next.L, cardEl: next.card, gy: r.top, label: "on the card" });
        // piece 5: after landing, sometimes walk to the end and turn back (once) instead of jumping off
        dog.edgePlan = flipped ? "jumpNow" : Math.random() < .45 ? "turn" : "jump";   // jumpNow: just turned here
        dog.jd = null; dog.hop = null;
          if (next.card !== dog.satOn) dog.satOn = null;
      }
      dog.nextTry = NOW + rnd(1, 3);
      return;
    }
    Object.assign(dog, { mode: next.mode, set: next.mode === "run" ? "run" : "walk", f: next.f, u: 0, L: next.L, label: "" });
    clearCard(); dog.scooped = false;
    dog.nextTry = NOW + rnd(2.5, 6);
  }
  function enterLeft() {
    Object.assign(dog, { set: "walk", f: 0, u: 0, mode: "walk", T: null, trick: "", label: "", dir: 1 });
    clearCard();
    dog.L = -E.bbox.walk[0][2] - 20 / (SC * K);
    dog.nextTry = NOW + rnd(2, 4);
  }

  function step(dt) {
    const [x0, x1] = extent();
    dog.lost = (x1 < -40 || x0 > W + 40) && dog.mode !== "offstage" && dog.mode !== "edge" ? dog.lost + dt : 0;
    if (dog.lost > 6) { dog.lost = 0; enterLeft(); }

    if (dog.mode === "offstage") { dog.wait -= dt; if (dog.wait <= 0) enterLeft(); return; }
    if (M && scoop() && dog.mode === "oncard") return onCard(dt);

    if (dog.mode === "play") {
      dog.u += dt;
      while (dog.T && dog.u >= dog.T[dog.i][2]) {
        dog.u -= dog.T[dog.i][2];
        if (++dog.i >= dog.T.length) {
          const u = dog.u;
          let nx = dog.next;
          if (dog.scooped && dog.cardEl && (nx.mode === "walk" || nx.mode === "run")) {   // piece 7
            if (nx.mode === "run") { const [, , wf, dx] = J("run>walk"); nx = Object.assign({}, nx, { f: wf, L: nx.L + dx }); }
            nx = Object.assign({}, nx, { mode: "oncard", card: dog.cardEl });
          }
          dog.scooped = false;
          goto(nx); return step(u);
        }
      }
      if (dog.mode !== "play") return;
      const s = dog.T[dog.i]; dog.set = s[0]; dog.f = s[1]; dog.L = s[3]; dog.label = s[4];
      applyHop();
      applyJD();
      if (dog.cardEl && !dog.hop && !dog.jd) {
        const t = rideTop();
        if (t != null) { trackVy(dog.cardEl, t, dt); dog.gy = Math.max(t, topbar() + px(DOG_H) * 1.05); }
        if (t != null && dog.trick === "sit" && tooHigh(t, 2.5)) cutSit();
        if (t != null && dog.trick === "turn" && tooHigh(t, 2) && dog.f < 57) cutTurn();
        if (t != null && dog.trick === "lie" && tooHigh(t, 4)) cutLie();
      }
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
      dog.label = { paw: "paws the card", sniff: "sniffs the card", pick: "pick me! (scratches the card)" }[dog.kind];
      return;
    }

    if (dog.mode === "oncard") { onCard(dt); return; }

    if (cards().length) ["jump", "sniffbox", "sniffloop", "pawbox", "pawloop", "pawone", "pawoneloop"].forEach(preload);
    if (dog.mode === "run") preload("r2w");
    let front = dog.mode === "walk" ? frontCard() : null;
    // piece 5: a card the dog is already standing in front of (it landed there; phone cards are full width) is
    // behind it, not in its way. It can still be hopped onto, but it must never pin (that teleported the dog
    // back to the card's edge, mostly off screen).
    const inFront = front && front.l < extent()[1] - px(120);
    if (inFront && !canHop(front)) front = null;
    if (dog.mode === "run" && dog.wrap) {            // a run cycle just started: slow down now if room is short
      dog.wrap = false;
      const r = runShouldStop() ? r2wPlan(dog.L) : null;
      if (r && files(r.T).every(ready)) {
        Object.assign(dog, { mode: "play", T: r.T, i: 0, u: dog.u, next: r.next, trick: "slow", pending: "", label: r.T[0][4] });
        return step(0);
      }
    }
    if (dog.mode === "run" && frontCard()) {
      dog.holdX = true;
      if (dog.f === J("run>walk")[1]) {
        const [, , wf, dx] = J("run>walk");
        dog.mode = "walk"; dog.set = "walk"; dog.f = wf; dog.L += dx; dog.u = 0;
      }
    }
    if (front && canHop(front)) {
      if (dog.f === J("walk>jump")[1] && startHop(front, "up")) return step(0);
      if (!inFront && extent()[1] >= front.l - 1) pinToEdge(front);
    } else if (front) {
      if (hasSide(front) && tryEdge(front)) return step(0);
      if (extent()[1] >= front.l - 1) {
        pinToEdge(front);
        if (!hasSide(front)) dog.label = "waiting";
      }
    }

    // piece 5: never leave the screen. A run near the edge drops to a walk; a walk turns round before the edge.
    if (dog.mode === "run" && extent()[1] > W - px(700) && dog.f === J("run>walk")[1]) {
      const [, , wf, dx] = J("run>walk");
      dog.mode = "walk"; dog.set = "walk"; dog.f = wf; dog.L += dx; dog.u = 0;
    }
    if (dog.mode === "walk" && !dog.holdX && extent()[1] > W - px(420)) {
      const x1 = extent()[1];                       // a dog already hanging past the edge turns back where it is
      if (tryTurn(Math.max(W - 4, x1 + px(30)), -1e9, x1 > W - px(90), null)) return step(0);
    }

    const D = E.dur[dog.set];
    if (!dog.holdX) dog.L += (dog.mode === "run" ? E.speed.run : E.speed.walk) * dt;
    dog.holdX = false;
    dog.u += dt;
    while (dog.u >= D[dog.f]) {
      dog.u -= D[dog.f]; dog.f = (dog.f + 1) % D.length;
      if (dog.mode === "run" && dog.f === 0) dog.wrap = true;
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
    let d = [rec, S.ground, dog.L, groundY(), dog.dir];
    if (!ready(rec[0])) d = lastDraw;
    if (!d) return;
    lastDraw = d;
    const [[file, sx, sy, w, h, ox, oy], ground, L, gy, dir] = d;
    if (dir < 0) ctx.setTransform(-DPR, 0, 0, DPR, W * DPR, 0);   // facing left: mirror the whole dog space
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
      setTimeout(() => preload("turn"), 1500);     // needed at the first screen edge
      resize(); addEventListener("resize", resize);
      if (window.visualViewport) visualViewport.addEventListener("resize", resize);
      enterLeft();
      dog.L = -E.bbox.walk[0][0] + 40 / (SC * K);
      requestAnimationFrame(tick);
    });

  window.__dog24 = {
    piece: 8,
    state: () => ({ dir: dog.dir, phone: PHONE, xr: M ? (dog.dir > 0 ? extent() : extent().map(v => W - v).reverse()) : null, mode: dog.mode, set: dog.set, f: dog.f, L: dog.L, trick: dog.trick, label: dog.label,
                    pending: dog.pending, wait: dog.wait, x: M ? extent() : null, K, W, H,
                    gy: dog.gy, feet: M ? groundY() : null, floor: M ? floorY() : null, kind: dog.kind,
                    card: dog.cardEl ? +dog.cardEl.dataset.n || 0 : 0, jdTo: dog.jd ? (dog.jd.tgt ? +dog.jd.tgt.dataset.n : "floor") : null }),
    force: (name, opts = {}) => { dog.pending = name; dog.forced = opts; dog.nextTry = 0; },
    dbg: () => ({ vy: dog.vy, quickAt: dog.quickAt, band: TOP_BAND(), bar: topbar(), dogH: px(DOG_H), hop: dog.hop && { mid: dog.hop.mid, picked: dog.hop.picked, tgt: dog.hop.tgt && dog.hop.tgt.dataset.n },
      cards: [...document.querySelectorAll(".card24")].map(el => { const m = rectOf(el); return [el.dataset.n, Math.round(m.l), Math.round(m.r), Math.round(m.t), nearTop(m.t, 4.5)]; }).filter(c => c[3] > -50 && c[3] < H) }),
    put: n => {                                       // test hook: stand the dog on card n (walking)
      const el = document.querySelector(`.card24[data-n="${n}"]`), r = rectOf(el);
      Object.assign(dog, { mode: "oncard", set: "walk", f: 0, u: 0, T: null, trick: "", cardEl: el, gy: r.t, vy: null, edgePlan: "jump" });
      dog.L = own(r.l + 20) - E.bbox.walk[0][0];
    },
    edge: kind => { dog.forceEdge = kind; dog.wantEdge = ""; },   // next card side: sniff | paw | pick
    plan: (name, opts) => TRICKS[name].plan(0, opts),
  };
})();
