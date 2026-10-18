"""Dataset summary and a turn check that catches misaligned actions and states."""

from __future__ import annotations

import math
from pathlib import Path

import pandas as pd

from datacollection.policies import turn_rate, wrap_angle
from datacollection.storage import episode_dirs, load_steps, read_json


def episodes_table(root: Path) -> pd.DataFrame:
    """One row per episode, from each ``episode.json``."""
    rows = [{**read_json(ep / "episode.json"), "path": str(ep)} for ep in episode_dirs(root)]
    return pd.DataFrame(rows)


def turn_check(ep_dir: Path, min_expected_rad: float = 0.2) -> dict[str, float]:
    """Compare each step's heading change with the turn its action should cause.

    Uses steps whose action should turn at least ``min_expected_rad``. A low sign-agreement
    rate means actions and states are out of step.
    """
    agree = total = 0
    ratios = []
    prev = None
    for rec in load_steps(ep_dir):
        if prev is not None and not prev["flags"]:
            a = prev["action"]
            me0, me1 = prev["state"]["self"], rec["state"]["self"]
            if a and a["key"] and me0 and me1:
                expected = (a["ms"] / 1000.0) * turn_rate(me0) * (-1 if a["key"] == "left" else 1)
                if abs(expected) >= min_expected_rad:
                    actual = wrap_angle(me1["ang"] - me0["ang"])
                    total += 1
                    agree += math.copysign(1, actual) == math.copysign(1, expected)
                    ratios.append(actual / expected)
        prev = rec
    ratios.sort()
    return {
        "checked_steps": total,
        "sign_agreement": agree / total if total else float("nan"),
        "median_actual_over_expected": ratios[len(ratios) // 2] if ratios else float("nan"),
    }


def summarize(root: Path, check_turns: bool = False) -> None:
    df = episodes_table(root)
    if df.empty:
        print(f"No episodes under {root}")
        return
    df["hours"] = df["duration_s"] / 3600
    by = df.groupby("policy").agg(
        episodes=("episode", "count"),
        steps=("n_steps", "sum"),
        hours=("hours", "sum"),
        median_final_length=("final_length", "median"),
        p90_final_length=("final_length", lambda s: s.quantile(0.9)),
        max_length=("max_length", "max"),
        bad_steps=("bad_steps", "sum"),
        gz_mb=("gz_bytes", lambda s: s.sum() / 1e6),
    )
    by["bad_step_rate"] = by["bad_steps"] / by["steps"]
    by["kb_per_step_gz"] = by["gz_mb"] * 1000 / by["steps"]
    pd.set_option("display.width", 160)
    print(by.round(3).to_string())
    print(f"\nTotal: {len(df)} episodes, {int(df['n_steps'].sum())} steps, {df['hours'].sum():.2f} h, "
          f"{df['gz_bytes'].sum() / 1e6:.1f} MB compressed")
    print("End reasons:", df["end_reason"].value_counts().to_dict())

    if check_turns:
        rows = []
        for ep in episode_dirs(root):
            info = read_json(ep / "episode.json")
            rows.append({"episode": ep.name, "policy": info["policy"], **turn_check(ep)})
        print("\nTurn check (actual heading change vs. what the action should cause):")
        print(pd.DataFrame(rows).round(3).to_string(index=False))
