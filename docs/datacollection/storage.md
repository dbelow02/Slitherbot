# `storage.py`

**Job:** write episodes to disk and read them back. The format itself is described in
[data-format.md](../data-format.md).

## `EpisodeWriter`

| Method | What it does |
| --- | --- |
| `EpisodeWriter(ep_dir)` | Creates the episode folder (fails if it exists, so nothing is overwritten) and opens `steps.jsonl` |
| `write(record)` | Appends one record as a compact JSON line |
| `save_image(name, data)` | Writes `shots/<name>` |
| `close(summary)` | Gzips `steps.jsonl` → `steps.jsonl.gz`, deletes the plain file, adds `n_steps`, `raw_bytes`, `gz_bytes` to the summary, and writes `episode.json` |

Records go to a plain text file first and are compressed at the end. If the process is killed,
everything up to the last full line survives in `steps.jsonl` (an episode folder without
`episode.json` is one of these).

## Reading

| Function | What it does |
| --- | --- |
| `episode_dirs(root)` | Every finished episode folder under `root` (those with `episode.json`), sorted |
| `load_steps(ep_dir)` | Yields the records of `steps.jsonl.gz` one at a time (doesn't load the whole file) |
| `read_json(path)` / `write_json(path, data)` | JSON helpers |
| `parse_final_length(text)` | `"Your final length was 1,234"` → `1234`; `None` if no number |

`SCHEMA_VERSION` (1) is written into `session.json` and every `episode.json`. Increase it when
the record format changes, so readers can tell old data from new.
