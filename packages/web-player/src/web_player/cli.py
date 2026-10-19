"""Command-line entry point: ``web-player <command>``."""

from __future__ import annotations

import argparse
import math
import random
import sys
import time

from web_player import Action, Game, GameClosed, Observation

# How often the loop observes and acts. The game itself sends at most one
# steering update every ~33 ms, so faster than this buys nothing.
_TICK_SECONDS = 0.05

DEFAULT_NICKNAME = "frederic_toothburn"


def main() -> None:
    parser = argparse.ArgumentParser(prog="web-player")
    commands = parser.add_subparsers(dest="command", required=True)

    play = commands.add_parser(
        "play",
        help="play one round, until the snake dies",
        description="Play one round. By default the bot wanders randomly; with "
        "--human you steer. Stops when the snake dies, the browser is closed, "
        "or you press Ctrl+C.",
    )
    play.add_argument("--headed", action="store_true", help="show the browser window")
    play.add_argument(
        "--human",
        action="store_true",
        help="you play with the game's own controls: the mouse steers; hold the "
        "mouse button, space, or up arrow to boost (implies --headed)",
    )
    play.add_argument("--nickname", default=DEFAULT_NICKNAME)

    args = parser.parse_args()
    if args.command == "play":
        headless = not (args.headed or args.human)
        sys.exit(_play(headless=headless, human=args.human, nickname=args.nickname))


def _play(*, headless: bool, human: bool, nickname: str) -> int:
    """Play one round and report why it ended. Returns a process exit code.

    With ``human`` set the bot never calls :meth:`Game.act`, so the game's own
    mouse and keyboard handling stays in charge. The loop still observes, which
    keeps the status line and death detection working.
    """
    start = time.monotonic()
    try:
        with Game(headless=headless) as game:
            obs = game.start_round(nickname)
            angle = obs.me.angle if obs.me else 0.0
            last_print = start
            while obs.alive:
                if not human:
                    angle = _wander(angle)
                    game.act(Action(angle))
                if (now := time.monotonic()) - last_print >= 1.0:
                    last_print = now
                    print(_status(obs, now - start), flush=True)
                time.sleep(_TICK_SECONDS)
                obs = game.observe()
            reason = "snake died"
    except GameClosed:
        reason = "browser closed"
    except KeyboardInterrupt:
        reason = "interrupted"
    print(f"{reason} after {time.monotonic() - start:.1f}s")
    return 0


def _wander(angle: float) -> float:
    """A random walk on heading: small nudges each tick make smooth, aimless curves."""
    return (angle + random.uniform(-0.25, 0.25)) % math.tau


def _status(obs: Observation, elapsed: float) -> str:
    me = obs.me
    if me is None:
        return f"t={elapsed:6.1f}s  (not alive)"
    return (
        f"t={elapsed:6.1f}s  len={me.length:5d}  "
        f"pos=({me.head.x:7.0f},{me.head.y:7.0f})  "
        f"snakes={len(obs.others):3d}  food={len(obs.foods):4d}"
    )
