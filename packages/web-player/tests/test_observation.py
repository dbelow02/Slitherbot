from web_player import Point
from web_player.observation import parse_observation

DEAD = {
    "time_ms": 10.0, "alive": False, "me": None, "others": [], "foods": [], "preys": [],
    "world_radius": 0, "rank": 0, "player_count": 0,
}


def _snake(id_: int, name: str) -> dict:
    return {
        "id": id_, "name": name, "head": [5.0, 6.0], "angle": 1.5, "speed": 5.8,
        "scale": 1, "length": 16, "body": [[1.0, 2.0], [5.0, 6.0]],
    }


def test_dead_observation_is_empty() -> None:
    obs = parse_observation(DEAD)
    assert not obs.alive
    assert obs.me is None
    assert obs.others == obs.foods == obs.preys == ()


def test_alive_observation_parses_every_entity() -> None:
    raw = DEAD | {
        "alive": True,
        "me": _snake(1, "bot"),
        "others": [_snake(2, "rival")],
        "foods": [[3.0, 4.0, 4.8]],
        "preys": [[7.0, 8.0, 2.0, 0.5, 9.0]],
        "world_radius": 32550,
        "rank": 3,
        "player_count": 500,
    }
    obs = parse_observation(raw)
    assert obs.me is not None
    assert obs.me.body == (Point(1.0, 2.0), Point(5.0, 6.0))
    assert obs.me.head == obs.me.body[-1]
    assert [s.name for s in obs.others] == ["rival"]
    assert obs.foods[0].position == Point(3.0, 4.0) and obs.foods[0].size == 4.8
    assert obs.preys[0].speed == 9.0
    assert (obs.world_radius, obs.rank, obs.player_count) == (32550.0, 3, 500)
