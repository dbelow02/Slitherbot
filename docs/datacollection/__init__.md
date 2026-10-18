# `__init__.py`

**Job:** entry point for the `datacollection` command.

`DataCollection/pyproject.toml` maps the command to `datacollection:main`:

```toml
[project.scripts]
datacollection = "datacollection:main"
```

`main()` imports and calls [`cli.main()`](cli.md). The import happens inside the function so
importing the package (for example, `from datacollection.storage import load_steps` in a
training script) doesn't load Playwright or pandas.

Run it with `uv run datacollection ...` from anywhere in the repo.
