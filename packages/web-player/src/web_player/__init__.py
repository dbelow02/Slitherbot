"""Play slither.io from Python.

The public interface is :class:`Game` plus the plain data types it exchanges.
Everything else in this package is an implementation detail.
"""

from web_player.game import Game, GameClosed, GameError
from web_player.observation import Action, Food, Observation, Point, Prey, Snake

__all__ = [
    "Action",
    "Food",
    "Game",
    "GameClosed",
    "GameError",
    "Observation",
    "Point",
    "Prey",
    "Snake",
]
