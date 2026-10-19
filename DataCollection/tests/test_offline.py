"""Tests that need no browser or network."""

import math
import random

from datacollection.config import CollectConfig
from datacollection.policies import HeuristicPolicy, HumanKeyTracker, make_policy, turn_rate
from datacollection.recorder import complete_record, is_alive, step_flags
from datacollection.storage import EpisodeWriter, load_frames, load_steps, parse_final_length, read_json


def snake(**kw):
    base = {"id": 1, "x": 1000.0, "y": 1000.0, "ang": 0.0, "wang": 0.0, "sp": 5.79, "sc": 1.0,
            "scang": 1.0, "spang": 1.0, "sct": 2, "fam": 0.0, "dead": False, "pts": [], "length": 10}
    return {**base, **kw}


def game_state(**kw):
    base = {"t": 0.0, "sync": "raf", "playing": True, "connected": True, "dead_mtm": -1, "grd": 32550,
            "lagging": False, "lag_mult": 1.0, "self": snake(x=32550.0, y=32550.0),
            "snakes": [], "foods": [], "preys": []}
    return {**base, **kw}


def test_same_seed_gives_same_actions():
    state = game_state(foods=[[32700.0, 32550.0, 5.0, 0]])
    for name in ("random", "heuristic", "eps-heuristic"):
        a = make_policy(name, random.Random(7), 190.0, 0.2)
        b = make_policy(name, random.Random(7), 190.0, 0.2)
        assert [a.act(state) for _ in range(50)] == [b.act(state) for _ in range(50)]


def test_heuristic_turns_toward_food_and_away_from_enemy():
    policy = HeuristicPolicy(max_ms=190.0)
    # Heading +x (ang 0). Food straight "down" in world y (+y): ang must rise -> right.
    food_below = game_state(foods=[[32550.0, 32700.0, 10.0, 0]])
    assert policy.act(food_below).key == "right"
    # Enemy head right in front: must turn away (either way), never keep going straight.
    enemy = snake(id=2, x=32620.0, y=32550.0, ang=math.pi)
    assert policy.act(game_state(snakes=[enemy])).key in ("left", "right")


def test_turn_rate_matches_measured_small_snake():
    assert abs(turn_rate(snake()) - 4.125) < 1e-9  # ~4 rad/s measured in the live game


def test_human_key_tracker_splits_holds_across_steps():
    t = HumanKeyTracker()
    action, extra = t.action_for([[10, 1, "left"], [60, 0, "left"], [150, 1, "right"]], 0, 200)
    assert (action.key, action.ms, extra["both_keys"]) == ("left", 50, True)
    action, extra = t.action_for([[330, 0, "right"]], 200, 400)
    assert (action.key, action.ms) == ("right", 130)
    action, _ = t.action_for([], 400, 600)
    assert action.key is None


def test_is_alive_uses_dead_flag_not_just_playing():
    assert is_alive(game_state())
    assert not is_alive(game_state(self=snake(dead=True)))
    assert not is_alive(game_state(dead_mtm=1234.5))
    assert not is_alive(game_state(self=None))


def test_step_flags():
    cfg = CollectConfig(out_dir=None)
    assert step_flags(game_state(), 5.0, cfg) == []
    assert step_flags(game_state(lag_mult=0.5, connected=False), 100.0, cfg) == ["late", "lag", "disconnected"]
    assert step_flags(game_state(sync="timeout", frame_error="no canvas"), 5.0, cfg) == ["not_frame_synced", "no_frame"]


def test_complete_record_flags_forced_release_and_interference():
    record = {"flags": [], "state": {"t": 100.0}, "action": {"key": "left", "ms": 50}}
    interval = {"act": {"t_down": 103.0, "t_up": 153.0, "forced": True}, "key_events": [[150.0, 1, "left"]],
                "mouse_moves": 0}
    complete_record(record, interval, next_t=300.0, human=None)
    assert record["flags"] == ["forced_release", "human_interference"]
    assert record["dt_next_ms"] == 200.0
    # Key timing is relative to this step's frame (page time 100).
    assert (record["action"]["start_ms"], record["action"]["end_ms"]) == (3.0, 53.0)
    assert record["key_events"] == [[50.0, 1, "left"]]


def test_parse_final_length():
    assert parse_final_length("Your final length was 1,234") == 1234
    assert parse_final_length(None) is None


def test_episode_writer_round_trip(tmp_path):
    writer = EpisodeWriter(tmp_path / "ep_000001")
    writer.write({"step": 0})
    writer.write({"step": 1})
    writer.close({"policy": "random"})
    assert [r["step"] for r in load_steps(tmp_path / "ep_000001")] == [0, 1]
    assert read_json(tmp_path / "ep_000001" / "episode.json")["n_steps"] == 2


def test_frames_round_trip(tmp_path):
    import base64
    writer = EpisodeWriter(tmp_path / "ep_000001")
    jpeg = b"\xff\xd8fake-jpeg\xff\xd9"
    url = "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()
    assert writer.add_frame(0, url) == "frame_000000.jpg"
    writer.add_frame(1, url)
    writer.close({})
    assert list(load_frames(tmp_path / "ep_000001")) == [("frame_000000.jpg", jpeg), ("frame_000001.jpg", jpeg)]
    assert read_json(tmp_path / "ep_000001" / "episode.json")["n_frames"] == 2
