"""Settings for a collection run. Every field is saved in ``session.json``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MIX = {"random": 0.4, "heuristic": 0.3, "eps-heuristic": 0.3}


@dataclass
class CollectConfig:
    out_dir: Path
    policy: str = "random"  # random | heuristic | eps-heuristic | human | mixed
    mix: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_MIX))  # weights for "mixed"
    episodes: int | None = None  # stop after this many episodes
    minutes: float | None = None  # stop after this many minutes
    max_steps: int = 30_000  # cut an episode off after this many steps
    delta_ms: float = 200.0  # time between state reads (Δ)
    max_hold_ms: float | None = None  # longest key hold a policy may ask for (default Δ - margin)
    release_margin_ms: float = 10.0  # keys are released at least this long before the next read
    epsilon: float = 0.2  # random-action rate for eps-heuristic
    headless: bool = True
    channel: str | None = "chrome"  # "chrome" = installed Google Chrome; None = Playwright's Chromium
    viewport: tuple[int, int] = (1280, 800)
    nickname: str = ""
    seed: int | None = None  # None: a seed is drawn and saved, so the run can still be replayed
    screenshot_every_s: float = 1.0  # debug screenshot cadence (kept in memory); 0 = off
    keep_screenshot_every_s: float = 10.0  # how often one of those is saved to disk
    screenshot_quality: int = 60  # JPEG quality
    late_fraction: float = 0.2  # a read later than this fraction of Δ is flagged "late"

    @property
    def hold_ms(self) -> float:
        if self.max_hold_ms is not None:
            return self.max_hold_ms
        return max(0.0, self.delta_ms - self.release_margin_ms)


def default_out_dir() -> Path:
    """``Slitherbot/data/raw`` when running from this repo, otherwise ``./data/raw``."""
    package_root = Path(__file__).resolve().parents[2]  # .../DataCollection
    if (package_root / "pyproject.toml").exists():
        return package_root.parent / "data" / "raw"
    return Path.cwd() / "data" / "raw"
