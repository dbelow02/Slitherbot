"""Plain data describing what the bot sees and what it does.

Nothing here touches a browser, so these types can be used anywhere,
including offline analysis of recorded sessions. They are expected to move
into ``slither-core`` once that package exists.

Conventions shared by every type:

* Positions are world units. The y axis points *down*, matching the screen.
* Angles are radians: ``0`` points along +x and ``pi/2`` along +y (down).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True, slots=True)
class Snake:
    """One snake as the client currently knows it."""

    id: int
    name: str
    head: Point
    angle: float
    """Current heading."""
    speed: float
    """World units per game tick. Roughly 5.8 when cruising, about 14 when boosting."""
    scale: float
    """Body thickness multiplier; grows as the snake grows."""
    length: int
    """The score the game shows as the snake's length."""
    body: tuple[Point, ...]
    """Body points, tail first, head last."""


@dataclass(frozen=True, slots=True)
class Food:
    position: Point
    size: float


@dataclass(frozen=True, slots=True)
class Prey:
    """A moving food pellet that flees from snakes."""

    position: Point
    size: float
    angle: float
    speed: float


@dataclass(frozen=True, slots=True)
class Observation:
    """A snapshot of the game from the player's point of view.

    When ``alive`` is false (before a round starts or after death) ``me`` is
    ``None`` and the entity collections are empty. Every other field is
    always populated.
    """

    time_ms: float
    """The page's monotonic clock (``performance.now()``) at capture time."""
    alive: bool
    me: Snake | None
    others: tuple[Snake, ...]
    """Other living snakes within the client's view. Excludes ``me``."""
    foods: tuple[Food, ...]
    preys: tuple[Prey, ...]
    world_radius: float
    """The game's ``grd`` value, which sets the size of the circular arena."""
    rank: int
    """Leaderboard rank, or 0 if the server has not reported it yet."""
    player_count: int
    """Players on the server, or 0 if not reported yet."""


@dataclass(frozen=True, slots=True)
class Action:
    """What the player wants to do from now until the next action.

    ``angle`` is the absolute heading to steer toward; the game turns the
    snake toward it at its own limited turn rate. ``boost`` trades length
    for speed while held.
    """

    angle: float
    boost: bool = False


def parse_observation(raw: dict[str, Any]) -> Observation:
    """Build an :class:`Observation` from the dict returned by ``bridge.js``.

    This is the only Python code that knows the bridge's wire format.
    """
    me = raw["me"]
    return Observation(
        time_ms=float(raw["time_ms"]),
        alive=bool(raw["alive"]),
        me=_parse_snake(me) if me is not None else None,
        others=tuple(_parse_snake(s) for s in raw["others"]),
        foods=tuple(Food(Point(x, y), size) for x, y, size in raw["foods"]),
        preys=tuple(
            Prey(Point(x, y), size, angle, speed)
            for x, y, size, angle, speed in raw["preys"]
        ),
        world_radius=float(raw["world_radius"]),
        rank=int(raw["rank"]),
        player_count=int(raw["player_count"]),
    )


def _parse_snake(raw: dict[str, Any]) -> Snake:
    return Snake(
        id=int(raw["id"]),
        name=str(raw["name"]),
        head=Point(*raw["head"]),
        angle=float(raw["angle"]),
        speed=float(raw["speed"]),
        scale=float(raw["scale"]),
        length=int(raw["length"]),
        body=tuple(Point(x, y) for x, y in raw["body"]),
    )
