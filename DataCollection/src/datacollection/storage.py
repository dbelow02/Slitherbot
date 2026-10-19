"""Reading and writing the dataset on disk.

Layout::

    <out>/session_<time>_<policy>/
        session.json                 run settings, seed, versions, git commit
        ep_000001/
            steps.jsonl.gz           one JSON record per step
            frames.tar               one JPEG of the game per step: frame_000000.jpg, ...
            episode.json             episode summary (written last)
            shots/*.jpg              debug screenshots
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import re
import shutil
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1


class EpisodeWriter:
    """Appends step records to ``steps.jsonl``; on close, gzips it and writes ``episode.json``.

    Writing plain lines first means a crash loses at most the line being written.
    """

    def __init__(self, ep_dir: Path) -> None:
        self.dir = ep_dir
        self.dir.mkdir(parents=True, exist_ok=False)
        self._raw = self.dir / "steps.jsonl"
        self._fh = self._raw.open("w", encoding="utf-8")
        self.n_records = 0
        self.raw_bytes = 0
        self._frames: tarfile.TarFile | None = None  # opened on the first frame
        self.n_frames = 0
        self.frame_bytes = 0

    def write(self, record: dict[str, Any]) -> None:
        line = json.dumps(record, separators=(",", ":"))
        self._fh.write(line + "\n")
        self.n_records += 1
        self.raw_bytes += len(line) + 1

    def add_frame(self, step: int, data_url: str) -> str:
        """Append a step's frame (a ``data:image/jpeg;base64,...`` URL) to ``frames.tar``.

        Returns the name it's stored under, which the step record points to.
        """
        data = base64.b64decode(data_url.split(",", 1)[1])
        name = frame_name(step)
        if self._frames is None:
            self._frames = tarfile.open(self.dir / "frames.tar", "w")
        info = tarfile.TarInfo(name)
        info.size = len(data)
        self._frames.addfile(info, io.BytesIO(data))
        self.n_frames += 1
        self.frame_bytes += len(data)
        return name

    def save_image(self, name: str, data: bytes) -> None:
        shots = self.dir / "shots"
        shots.mkdir(exist_ok=True)
        (shots / name).write_bytes(data)

    def close(self, summary: dict[str, Any]) -> None:
        self._fh.close()
        if self._frames is not None:
            self._frames.close()
        gz = self.dir / "steps.jsonl.gz"
        with self._raw.open("rb") as src, gzip.open(gz, "wb", compresslevel=6) as dst:
            shutil.copyfileobj(src, dst)
        self._raw.unlink()
        summary["n_steps"] = self.n_records
        summary["raw_bytes"] = self.raw_bytes
        summary["gz_bytes"] = gz.stat().st_size
        summary["n_frames"] = self.n_frames
        summary["frame_bytes"] = self.frame_bytes
        write_json(self.dir / "episode.json", summary)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def episode_dirs(root: Path) -> list[Path]:
    """Every finished episode folder under ``root`` (one with an ``episode.json``), sorted."""
    return sorted(p.parent for p in root.rglob("episode.json"))


def load_steps(ep_dir: Path) -> Iterator[dict[str, Any]]:
    with gzip.open(ep_dir / "steps.jsonl.gz", "rt", encoding="utf-8") as fh:
        for line in fh:
            yield json.loads(line)


def frame_name(step: int) -> str:
    return f"frame_{step:06d}.jpg"


def load_frames(ep_dir: Path) -> Iterator[tuple[str, bytes]]:
    """Yields ``(name, jpeg_bytes)`` for every frame of an episode, in step order."""
    path = ep_dir / "frames.tar"
    if not path.exists():
        return
    with tarfile.open(path, "r") as tar:
        for member in tar:
            f = tar.extractfile(member)
            if f is not None:
                yield member.name, f.read()


def parse_final_length(text: str | None) -> int | None:
    """``"Your final length was 1,234"`` -> 1234."""
    if not text:
        return None
    m = re.search(r"(\d[\d,]*)", text)
    return int(m.group(1).replace(",", "")) if m else None
