# Development

## One-time setup

Requires [uv](https://docs.astral.sh/uv/). From the repo root:

```bash
uv sync --all-packages                    # create .venv and install every workspace member
uv run playwright install chromium        # download Playwright's Chromium builds
uv run playwright install-deps chromium   # install the system libraries Chromium needs (asks for sudo)
```

Why `--all-packages`: the root `pyproject.toml` is a virtual workspace root with
no `[project]` table, so a plain `uv sync` installs nothing.

Why `install-deps`: Playwright downloads Chromium itself, but not the system
libraries Chromium links against, such as `libnss3` and `libnspr4`. Without
them every launch fails with
`error while loading shared libraries: libnspr4.so`. `install-deps` installs
them through `apt`.

### WSL

Headed mode works on WSL2 through WSLg, which Windows 11 includes. The browser
opens as a normal window on the Windows desktop with no X server or display
setup. Check that WSLg is active:

```bash
echo $DISPLAY $WAYLAND_DISPLAY            # expect something like ":0 wayland-0"
```

If both are empty, update WSL from Windows with `wsl --update`, then restart it
with `wsl --shutdown`. Headless mode works either way.

## Everyday commands

```bash
uv run web-player play --headed                            # watch the bot play one round
uv run web-player play --human                             # play a round yourself
uv run web-player play                                     # one round, headless
uv run --package web-player pytest packages/web-player     # offline unit tests
uv run python my_script.py                                 # run your own script against the workspace
```

Unit tests never touch the live site. Running `web-player play` is the
end-to-end check against the real game.

- The whole workspace shares one `.venv` at the repo root.
- Add a dependency to one member with `uv add --package <member> <dep>`, and
  dev-only tools with `uv add --dev --package <member> <dep>`. Never add
  dependencies to the root.

## Troubleshooting

**`libnspr4.so: cannot open shared object file`.** The system libraries are
missing. Run `uv run playwright install-deps chromium`.

**`install-deps` fails with `Could not get lock /var/lib/apt/lists/lock`.**
Another apt process holds the lock. On WSL this is often Ubuntu's automatic
daily update (`apt.systemd.daily`) stuck in `apt-get update`. Find it:

```bash
ps -eo pid,etime,args | grep -E 'apt|dpkg' | grep -v grep
```

If it is an `apt-get update` that has been running for a long time, stop it
with `sudo kill <pid>`. It only refreshes package lists, so stopping it is safe.
Then rerun `install-deps`. Do not delete the lock file.

**Exit status 130 after Ctrl+C.** This status comes from `uv run`, not from
`web-player`. The bot itself shuts down cleanly.

**The bot stops working after a slither.io update.** Recheck the table in
[web-player.md](web-player.md#what-the-bridge-relies-on) against the new game
script. Fixes belong in `bridge.js`.

## Adding the planned packages

When the time comes:

```bash
uv init --lib packages/slither-core
uv init --lib packages/analysis

uv add --package web-player slither-core
uv add --package analysis   slither-core polars
uv add --package analysis   --dev ipykernel
```

New directories under `packages/` join the workspace automatically. When one
member depends on another, uv records it under `[tool.uv.sources]` as
`slither-core = { workspace = true }`. Members install in editable mode, so a
change in one shows up immediately in the others.
