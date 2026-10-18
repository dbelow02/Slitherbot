# `browser.py`

**Job:** control the slither.io page with Playwright. Every call into the game goes through the
`window.__dc` helper that [`game_js.py`](game_js.md) installs.

## `SlitherBrowser`

Use as an async context manager:

```python
async with SlitherBrowser(headless=True, channel="chrome", viewport=(1280, 800)) as browser:
    await browser.start_round("")
    state = await browser.read_state()
```

| Method | What it does |
| --- | --- |
| `__aenter__` | Starts Playwright, launches the browser (`channel="chrome"` uses installed Google Chrome; `None` uses Playwright's Chromium), opens the page |
| `open_page()` | Creates a fresh browser context with the fixed viewport, adds the init script (so `__dc` exists before the game's code runs), loads `https://slither.io/`, waits until the Play button exists. Also used to recover from errors |
| `start_round(nickname)` | Calls the game's own Play-button handler (`play_btn.elem.onclick()`) until a live round is running (`__dc.inRound()`). The check ignores a dying snake, so it waits through the death animation. Times out after 45 s |
| `read_state()` | `__dc.read()`: the raw state dict |
| `act(key, ms)` | `__dc.act(key, ms)`: presses the arrow key in the page and releases it after `ms` with a page timer. Returns immediately |
| `release()` | Releases any key the bot holds |
| `screenshot_jpeg(quality)` | Screenshot of the viewport as JPEG bytes |
| `last_score()` | Death-screen text ("Your final length was N"). Waits up to 10 s for the round to fully end, so it never returns the previous round's text |
| `client_info()` | Game script URL, protocol version, user agent, viewport, browser version |

## Notes

- **Viewport is fixed** because it sets how far the player can see, and possibly which snakes
  the server sends.
- **The mouse is never moved.** In slither.io, mouse movement steers the snake and would
  override the arrow keys.
- **Starting a round** uses the game's Play handler rather than a click at screen coordinates,
  so it doesn't depend on layout. The Enter key does the same thing in the game.
