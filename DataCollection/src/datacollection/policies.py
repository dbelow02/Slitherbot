"""Policies that choose an arrow-key action from the raw game state.

An action is ``(key, ms)``: hold ``key`` ("left", "right", or None) for ``ms`` milliseconds.
Left lowers the snake's heading ``ang``; right raises it. World angles follow the game:
``x += cos(ang) * speed``, ``y += sin(ang) * speed``.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any

# From the client code: each 8 ms frame a held key turns mamu * scang * spang radians,
# with mamu = 0.033 and spang = min(1, sp / 4.8).
TURN_RAD_PER_S = 0.033 * 125
SPANG_DIVISOR = 4.8
# Distance per second = sp * 31.25 (client moves sp / 4 world units per 8 ms frame).
UNITS_PER_S_PER_SP = 31.25

POLICY_NAMES = ("random", "heuristic", "eps-heuristic", "human")


@dataclass(frozen=True)
class Action:
    key: str | None
    ms: float
    source: str

    def to_json(self) -> dict[str, Any]:
        return {"key": self.key, "ms": round(self.ms, 1), "source": self.source}


def wrap_angle(a: float) -> float:
    return math.atan2(math.sin(a), math.cos(a))


def turn_rate(me: dict[str, Any]) -> float:
    """Radians per second a held arrow key turns this snake."""
    scang = me.get("scang") or 1.0
    spang = min(1.0, (me.get("sp") or SPANG_DIVISOR) / SPANG_DIVISOR)
    return TURN_RAD_PER_S * scang * spang


class Policy:
    name = "base"

    def act(self, state: dict[str, Any]) -> Action:
        raise NotImplementedError

    def params(self) -> dict[str, Any]:
        """Settings saved in each episode's summary, so the run can be reproduced."""
        return {}


class RandomPolicy(Policy):
    """Sticky random presses: often repeats the last key, with a fresh random duration."""

    name = "random"

    def __init__(self, rng: random.Random, max_ms: float, p_none: float = 0.2, p_repeat: float = 0.6) -> None:
        self.rng = rng
        self.max_ms = max_ms
        self.p_none = p_none
        self.p_repeat = p_repeat
        self.last_key: str | None = None

    def params(self) -> dict[str, Any]:
        return {"max_ms": self.max_ms, "p_none": self.p_none, "p_repeat": self.p_repeat}

    def act(self, state: dict[str, Any]) -> Action:
        if self.rng.random() < self.p_repeat:
            key = self.last_key
        elif self.rng.random() < self.p_none:
            key = None
        else:
            key = self.rng.choice(("left", "right"))
        self.last_key = key
        ms = 0.0 if key is None else self.rng.uniform(0.0, self.max_ms)
        return Action(key, ms, self.name)


class HeuristicPolicy(Policy):
    """Steer toward food, away from other snakes and the border.

    Deliberately simple: it is a data source and the baseline to beat, not a strong player.
    """

    name = "heuristic"

    def __init__(self, max_ms: float, food_radius: float = 700.0, danger_radius: float = 450.0,
                 border_margin: float = 900.0, head_lookahead_s: float = 0.5, danger_scale: float = 30.0) -> None:
        self.max_ms = max_ms
        self.food_radius = food_radius
        self.danger_radius = danger_radius
        self.border_margin = border_margin
        self.head_lookahead_s = head_lookahead_s
        self.danger_scale = danger_scale

    def params(self) -> dict[str, Any]:
        return {"max_ms": self.max_ms, "food_radius": self.food_radius, "danger_radius": self.danger_radius,
                "border_margin": self.border_margin, "head_lookahead_s": self.head_lookahead_s,
                "danger_scale": self.danger_scale}

    def act(self, state: dict[str, Any]) -> Action:
        me = state.get("self")
        if not me:
            return Action(None, 0.0, self.name)
        hx, hy, ang = me["x"], me["y"], me["ang"]
        fwd = (math.cos(ang), math.sin(ang))

        food_x = food_y = 0.0
        for fx, fy, sz, eaten in state.get("foods", []):
            if eaten:
                continue
            dx, dy = fx - hx, fy - hy
            d = math.hypot(dx, dy)
            if d < 1 or d > self.food_radius:
                continue
            ahead = (dx * fwd[0] + dy * fwd[1]) / d  # prefer food in front: turning costs time
            w = sz * (1.5 + ahead) / (d + 30.0) ** 1.5
            food_x += w * dx / d
            food_y += w * dy / d

        danger_x = danger_y = 0.0
        for o in state.get("snakes", []):
            if o.get("dead"):
                continue
            width = 29.0 * (o.get("sc") or 1.0) / 2
            # Where the enemy head will be soon, plus its body. The projection is capped at half the
            # current distance so a head coming straight at us is never projected behind us.
            speed = (o.get("sp") or 0.0) * UNITS_PER_S_PER_SP
            ahead_dist = min(speed * self.head_lookahead_s, 0.5 * math.hypot(o["x"] - hx, o["y"] - hy))
            px = o["x"] + math.cos(o["ang"]) * ahead_dist
            py = o["y"] + math.sin(o["ang"]) * ahead_dist
            body = [(x, y, 1.0) for x, y, dying in o.get("pts", []) if not dying]
            pts = [(px, py, 3.0), (o["x"], o["y"], 2.0), *body]
            for x, y, weight in pts:
                dx, dy = x - hx, y - hy
                d = math.hypot(dx, dy) - width
                if d > self.danger_radius:
                    continue
                d = max(d, 5.0)
                ahead = (dx * fwd[0] + dy * fwd[1]) / max(math.hypot(dx, dy), 1.0)
                w = weight * (1.2 + ahead) * (self.danger_radius / d) ** 2
                norm = max(math.hypot(dx, dy), 1.0)
                danger_x -= w * dx / norm
                danger_y -= w * dy / norm

        grd = state.get("grd") or 0
        if grd:
            cx, cy = hx - grd, hy - grd
            r = math.hypot(cx, cy)
            to_edge = grd - r
            if to_edge < self.border_margin and r > 0:
                w = 50.0 * ((self.border_margin - to_edge) / self.border_margin) ** 2
                danger_x -= w * cx / r
                danger_y -= w * cy / r

        if food_x or food_y:
            goal = (food_x, food_y)
        else:
            # No food nearby: drift toward the arena center, where snakes and food are denser.
            goal = (grd - hx, grd - hy) if grd else fwd
        # Blend unit vectors: the more danger, the more it overrides the goal.
        danger = math.hypot(danger_x, danger_y)
        alpha = min(1.0, danger / self.danger_scale)
        gnorm = max(math.hypot(*goal), 1e-9)
        vx = (1 - alpha) * goal[0] / gnorm + (alpha * danger_x / danger if danger else 0.0)
        vy = (1 - alpha) * goal[1] / gnorm + (alpha * danger_y / danger if danger else 0.0)

        err = wrap_angle(math.atan2(vy, vx) - ang)
        if abs(err) < 0.05:
            return Action(None, 0.0, self.name)
        ms = min(self.max_ms, abs(err) / turn_rate(me) * 1000.0)
        return Action("left" if err < 0 else "right", ms, self.name)


class EpsilonHeuristicPolicy(Policy):
    """Heuristic, but a random action with probability ``epsilon``."""

    name = "eps-heuristic"

    def __init__(self, heuristic: HeuristicPolicy, random_policy: RandomPolicy, rng: random.Random,
                 epsilon: float) -> None:
        self.heuristic = heuristic
        self.random = random_policy
        self.rng = rng
        self.epsilon = epsilon

    def params(self) -> dict[str, Any]:
        return {"epsilon": self.epsilon, "heuristic": self.heuristic.params(), "random": self.random.params()}

    def act(self, state: dict[str, Any]) -> Action:
        if self.rng.random() < self.epsilon:
            a = self.random.act(state)
        else:
            a = self.heuristic.act(state)
        return Action(a.key, a.ms, f"{self.name}/{a.source}")


def check_policy_names(names: list[str]) -> None:
    for n in names:
        if n not in POLICY_NAMES:
            raise ValueError(f"unknown policy {n!r}; choose from {', '.join(POLICY_NAMES)}")


def make_policy(name: str, rng: random.Random, max_ms: float, epsilon: float) -> Policy | None:
    """Build a policy by name, with its own random generator. ``human`` returns None: the person
    at the keyboard acts."""
    if name == "random":
        return RandomPolicy(rng, max_ms)
    if name == "heuristic":
        return HeuristicPolicy(max_ms)
    if name == "eps-heuristic":
        return EpsilonHeuristicPolicy(HeuristicPolicy(max_ms), RandomPolicy(rng, max_ms), rng, epsilon)
    if name == "human":
        return None
    raise ValueError(f"unknown policy {name!r}")


class HumanKeyTracker:
    """Turns logged human key events into one ``(key, ms)`` action per step."""

    def __init__(self) -> None:
        self.held: dict[str, float] = {}  # key -> time it went down, or start of this step if earlier

    def action_for(self, events: list[list[Any]], t_start: float, t_end: float) -> tuple[Action, dict[str, Any]]:
        """Action for the interval ``[t_start, t_end]`` from the key events logged in it."""
        totals = {"left": 0.0, "right": 0.0, "boost": 0.0}
        for t, down, name in events:
            if down:
                self.held.setdefault(name, t)
            elif name in self.held:
                totals[name] += t - max(self.held.pop(name), t_start)
        for name, t0 in self.held.items():
            totals[name] += t_end - max(t0, t_start)
            self.held[name] = t_end  # keeps counting from here next step

        left, right = totals["left"], totals["right"]
        if left <= 0 and right <= 0:
            action = Action(None, 0.0, "human")
        elif left >= right:
            action = Action("left", left, "human")
        else:
            action = Action("right", right, "human")
        extra = {
            "left_ms": round(left, 1),
            "right_ms": round(right, 1),
            "boost_ms": round(totals["boost"], 1),
            "both_keys": left > 0 and right > 0,
        }
        return action, extra
