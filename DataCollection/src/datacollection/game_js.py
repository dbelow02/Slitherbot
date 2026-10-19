"""JavaScript installed into the slither.io page.

It defines ``window.__dc``, which reads the game's globals at call time, presses
arrow keys for the bot, and logs real (trusted) key presses for human play.
Every slither.io global name used by this project lives in this file.
"""

INIT_SCRIPT = r"""
(() => {
  if (window.__dc) return;

  // The game's images come from a different origin than the page (slither.io vs slither.com),
  // which "taints" the canvas and blocks copying frames from it. Load every image as a CORS
  // request; browser.py adds the matching Access-Control-Allow-Origin header to image responses.
  const srcProp = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, 'src');
  Object.defineProperty(HTMLImageElement.prototype, 'src', {
    configurable: true, enumerable: srcProp.enumerable,
    get() { return srcProp.get.call(this); },
    set(v) {
      if (this.crossOrigin === null && typeof v === 'string' && !v.startsWith('data:')) this.crossOrigin = 'anonymous';
      srcProp.set.call(this, v);
    },
  });
  const R1 = v => (typeof v === 'number' && isFinite(v)) ? Math.round(v * 10) / 10 : null;
  const R3 = v => (typeof v === 'number' && isFinite(v)) ? Math.round(v * 1000) / 1000 : null;
  const KEY_CODES = {ArrowLeft: 37, ArrowRight: 39, ArrowUp: 38};
  const KEY_NAMES = {left: 'ArrowLeft', right: 'ArrowRight'};

  const dc = {
    events: [],       // trusted key events: [t, down(1)/up(0), name]
    mouseMoves: 0,    // trusted mouse moves since the last read
    held: null,       // key the bot is holding right now
    heldTimer: null,
    lastAct: null,    // timing of the bot's most recent action
  };

  function send(type, name) {
    const code = KEY_CODES[name];
    document.dispatchEvent(new KeyboardEvent(type, {key: name, code: name, keyCode: code, which: code, bubbles: true}));
  }

  function logKey(e) {
    if (!e.isTrusted) return;
    let name = null;
    if (e.keyCode === 37) name = 'left';
    else if (e.keyCode === 39) name = 'right';
    else if (e.keyCode === 38 || e.keyCode === 32) name = 'boost';
    else return;
    if (e.type === 'keydown' && e.repeat) return;
    dc.events.push([performance.now(), e.type === 'keydown' ? 1 : 0, name]);
  }
  window.addEventListener('keydown', logKey, true);
  window.addEventListener('keyup', logKey, true);
  window.addEventListener('mousemove', e => { if (e.isTrusted) dc.mouseMoves++; }, true);

  // Release whatever the bot holds. Marks the action as forced if its timer had not fired yet.
  dc.release = function () {
    if (dc.heldTimer !== null) { clearTimeout(dc.heldTimer); dc.heldTimer = null; }
    if (dc.held) {
      send('keyup', dc.held);
      dc.held = null;
      if (dc.lastAct) { dc.lastAct.t_up = performance.now(); dc.lastAct.forced = true; }
    }
  };

  // Hold `key` ('left' | 'right' | null) for `ms` milliseconds.
  dc.act = function (key, ms) {
    dc.release();
    const rec = {key: key, ms: ms, t_call: performance.now(), t_down: null, t_up: null, forced: false};
    dc.lastAct = rec;
    if (!key || !(ms > 0)) return rec.t_call;
    const name = KEY_NAMES[key];
    send('keydown', name);
    dc.held = name;
    rec.t_down = performance.now();
    dc.heldTimer = setTimeout(() => {
      send('keyup', name);
      rec.t_up = performance.now();
      if (dc.held === name) dc.held = null;
      dc.heldTimer = null;
    }, ms);
    return rec.t_down;
  };

  function points(o) {
    const out = [];
    const p = o.pts;
    if (!p) return out;
    for (let i = 0; i < p.length; i++) {
      const q = p[i];
      out.push([R1(q.xx + (q.fx || 0)), R1(q.yy + (q.fy || 0)), q.dying ? 1 : 0]);
    }
    return out;
  }

  function snake(o) {
    return {
      id: o.id,
      x: R1(o.xx + (o.fx || 0)), y: R1(o.yy + (o.fy || 0)),
      ang: R3(o.ang), wang: R3(o.wang), eang: R3(o.eang),
      sp: R3(o.sp), ssp: R3(o.ssp), fsp: R3(o.fsp), msp: R3(o.msp),
      sc: R3(o.sc), scang: R3(o.scang), spang: R3(o.spang),
      sct: o.sct, rsc: o.rsc || 0, fam: R3(o.fam),
      dead: !!o.dead,
      pts: points(o),
    };
  }

  function length(o, floor) {
    if (!window.fpsls || !window.fmlts || !fmlts.length) return null;
    const sct = o.sct + (o.rsc || 0);
    const v = (fpsls[sct] + o.fam / fmlts[sct] - 1) * 15 - 5;
    return floor ? Math.floor(v) : R3(v);
  }

  // Copy the game canvas (window.mc) into a JPEG data URL, `width` px wide, same aspect ratio.
  function captureFrame(width, quality) {
    const mc = window.mc;
    if (!(width > 0) || !mc || !mc.width) return {frame: null, frame_error: width > 0 ? 'no canvas' : null};
    const height = Math.round(width * mc.height / mc.width);
    if (!dc.frameCanvas) dc.frameCanvas = document.createElement('canvas');
    const fc = dc.frameCanvas;
    if (fc.width !== width || fc.height !== height) { fc.width = width; fc.height = height; }
    try {
      fc.getContext('2d').drawImage(mc, 0, 0, width, height);
      return {frame: fc.toDataURL('image/jpeg', quality), frame_error: null};
    } catch (e) {
      return {frame: null, frame_error: String(e)};
    }
  }

  // State and frame from the same game frame. The game's loop (oef) updates the world, redraws
  // the canvas, then schedules itself with requestAnimationFrame. A callback we schedule now runs
  // in the next frame right after the game's own, so the state we read is exactly what was just
  // drawn. If animation frames are paused (hidden tab), fall back after 100 ms and say so.
  dc.read = function (frameWidth, frameQuality) {
    return new Promise(resolve => {
      let done = false;
      const run = sync => {
        if (done) return;
        done = true;
        resolve(snapshot(sync, frameWidth, frameQuality));
      };
      requestAnimationFrame(() => run('raf'));
      setTimeout(() => run('timeout'), 100);
    });
  };

  function snapshot(sync, frameWidth, frameQuality) {
    dc.release();
    const act = dc.lastAct;
    dc.lastAct = null;
    const s = {
      t: performance.now(), wall: Date.now(), sync: sync, game_fr: R3(window.fr),
      playing: !!window.playing, connected: !!window.connected,
      dead_mtm: window.dead_mtm,
      grd: window.grd, view_x: R1(window.view_xx), view_y: R1(window.view_yy),
      view_dist: R1(window.view_dist), view_ang: R3(window.view_ang),
      gsc: R3(window.gsc), mww2: window.mww2, mhh2: window.mhh2,
      rank: window.rank, best_rank: window.best_rank, slither_count: window.slither_count,
      fps: window.fps, lag_mult: R3(window.lag_mult), lagging: !!window.lagging,
      kd_l: !!window.kd_l, kd_r: !!window.kd_r, kd_u: !!window.kd_u,
      xm: R1(window.xm), ym: R1(window.ym),
      act: act,
      key_events: dc.events.splice(0),
      mouse_moves: dc.mouseMoves,
      self: null, snakes: [], foods: [], preys: [],
    };
    dc.mouseMoves = 0;

    const me = window.slither;
    if (me) {
      s.self = snake(me);
      s.self.md = !!me.md;
      s.self.wmd = !!me.wmd;
      s.self.kill_count = me.kill_count || 0;
      s.self.length = length(me, true);
      s.self.length_f = length(me, false);
    }
    const all = window.slithers || [];
    for (let i = 0; i < all.length; i++) {
      const o = all[i];
      if (o && o !== me) s.snakes.push(snake(o));
    }
    const foods = window.foods || [];
    const n = Math.min(foods.length, window.foods_c || foods.length);
    for (let i = 0; i < n; i++) {
      const f = foods[i];
      if (f) s.foods.push([R1(f.xx), R1(f.yy), R3(f.sz), f.eaten ? 1 : 0]);
    }
    const preys = window.preys || [];
    for (let i = 0; i < preys.length; i++) {
      const p = preys[i];
      if (p) s.preys.push({id: p.id, x: R1(p.xx), y: R1(p.yy), sz: R3(p.sz), ang: R3(p.ang),
                           wang: R3(p.wang), sp: R3(p.sp), dir: p.dir, eaten: p.eaten ? 1 : 0});
    }
    const t0 = performance.now();
    Object.assign(s, captureFrame(frameWidth, frameQuality));
    s.frame_ms = R3(performance.now() - t0);
    return s;
  }

  dc.ready = function () {
    return !!(window.play_btn && window.play_btn.elem && window.nick);
  };

  dc.start = function (nickname) {
    if (window.playing || window.want_play) return 'busy';
    if (window.play_btn.disabled) return 'disabled';
    window.nick.value = nickname || '';
    window.play_btn.elem.onclick();
    return 'started';
  };

  dc.inRound = function () {
    return !!(window.playing && window.slither && !window.slither.dead && window.dead_mtm === -1 &&
              window.fmlts && fmlts.length > 0);
  };

  // Death-screen text, or null while the round (or its death animation) is still running,
  // so a previous round's text is never returned.
  dc.lastScore = function () {
    if (window.playing) return null;
    const el = window.lastscore;
    return el ? el.innerText : null;
  };

  dc.clientInfo = function () {
    const scripts = Array.from(document.scripts).map(x => x.src).filter(x => x.includes('/s/'));
    return {client_script: scripts[0] || null, protocol_version: window.protocol_version,
            user_agent: navigator.userAgent, viewport: [window.innerWidth, window.innerHeight]};
  };

  window.__dc = dc;
})();
"""
