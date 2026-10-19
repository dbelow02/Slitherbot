// Bridge between the Python driver (game.py) and slither.io's page globals.
//
// This is the only file that knows the game's internal variable names. It is
// installed with Playwright's add_init_script, so it exists before the game
// script loads; every function reads the game's globals lazily, at call time.
//
// Coordinates are the game's world units, with y increasing downward. Angles
// are radians: 0 points along +x and pi/2 along +y.
(() => {
  // Steering works by pretending the mouse is this many pixels from the screen
  // centre. It must exceed the game's 16 px dead zone.
  const STEER_RADIUS = 300;

  const pair = (o) => [o.xx, o.yy];

  // Mirrors the game's own "Your final length was" formula.
  function lengthOf(s) {
    const sct = s.sct + (s.rsc || 0);
    return Math.floor((window.fpsls[sct] + s.fam / window.fmlts[sct] - 1) * 15 - 5);
  }

  function snake(s) {
    return {
      id: s.id,
      name: s.nk || "",
      head: pair(s),
      angle: s.ang,
      speed: s.sp,
      scale: s.sc,
      length: lengthOf(s),
      // Tail first, head last. Points flagged `dying` are being removed.
      body: s.pts.filter((p) => !p.dying).map(pair),
    };
  }

  // On death the game stamps `dead_mtm` immediately but leaves `playing` true
  // through a ~2 s game-over fade, so `playing` alone would report a corpse.
  function isAlive() {
    return window.playing === true && window.slither != null && window.dead_mtm === -1;
  }

  window.__slitherbot = {
    observe() {
      const alive = isAlive();
      const obs = {
        time_ms: performance.now(),
        alive,
        me: null,
        others: [],
        foods: [],
        preys: [],
        world_radius: window.grd || 0,
        rank: window.rank || 0,
        player_count: window.slither_count || 0,
      };
      if (!alive) return obs;

      const me = window.slither;
      obs.me = snake(me);
      obs.others = window.slithers.filter((s) => s !== me && !s.dead).map(snake);
      // `foods` is a sparse buffer with `foods_c` live slots.
      for (let i = 0; i < window.foods_c; i++) {
        const f = window.foods[i];
        if (f && !f.eaten) obs.foods.push([f.xx, f.yy, f.sz]);
      }
      obs.preys = window.preys
        .filter((p) => !p.eaten)
        .map((p) => [p.xx, p.yy, p.sz, p.ang, p.sp]);
      return obs;
    },

    act(angle, boost) {
      if (!isAlive()) return;
      window.xm = Math.cos(angle) * STEER_RADIUS;
      window.ym = Math.sin(angle) * STEER_RADIUS;
      window.setAcceleration(boost ? 1 : 0);
    },

    canStart() {
      return (
        typeof window.play_btn !== "undefined" &&
        !window.play_btn.disabled &&
        !window.want_play &&
        !window.playing &&
        window.dead_mtm === -1
      );
    },

    start(nickname) {
      document.getElementById("nick").value = nickname;
      window.play_btn.elem.onclick();
    },

    isAlive,
  };
})();
