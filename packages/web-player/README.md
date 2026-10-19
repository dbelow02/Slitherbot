# web-player

Plays slither.io from Python through a Playwright-controlled browser.

```bash
uv run web-player play --headed     # watch the bot play one round
uv run web-player play --human      # play a round yourself
```

```python
from web_player import Action, Game

with Game(headless=False) as game:
    obs = game.start_round("bot")
    while obs.alive:
        game.act(Action(angle=0.0, boost=False))
        obs = game.observe()
```

See [docs/web-player.md](../../docs/web-player.md) for the API reference and how
it works.
