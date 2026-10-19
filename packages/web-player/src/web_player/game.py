"""Drive a live slither.io session in a Playwright-controlled browser."""

from __future__ import annotations

import json
from collections.abc import Generator
from contextlib import contextmanager
from importlib.resources import files
from types import TracebackType

from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import Playwright, sync_playwright

from web_player.observation import Action, Observation, parse_observation

DEFAULT_URL = "http://slither.io"
_BRIDGE_JS = files("web_player").joinpath("bridge.js").read_text(encoding="utf-8")


class GameError(Exception):
    """The game could not be loaded, started, or talked to.

    Wraps every Playwright failure, so callers never need to import Playwright.
    """


class GameClosed(GameError):
    """The browser or its tab went away, typically because the user closed it."""


class Game:
    """One browser tab playing slither.io.

    This is the whole interface to the website. A typical loop::

        with Game(headless=False) as game:
            obs = game.start_round("bot")
            while obs.alive:
                game.act(strategy.decide(obs))
                obs = game.observe()

    The game keeps running in the browser between calls. Your loop decides
    how often to observe and act; the snake holds its last action in between.

    A ``Game`` uses Playwright's sync API and must stay on the thread that
    created it.
    """

    def __init__(
        self,
        *,
        headless: bool = True,
        viewport: tuple[int, int] = (1280, 800),
        url: str = DEFAULT_URL,
        timeout: float = 30.0,
    ) -> None:
        """Launch a browser and load the game, ready for :meth:`start_round`.

        ``timeout`` (seconds) bounds page loads and round starts.
        Raises :class:`GameError` if the game page does not load.
        """
        self._playwright: Playwright | None = sync_playwright().start()
        try:
            with self._translate_errors(f"load the game at {url}"):
                self._browser = self._playwright.chromium.launch(headless=headless)
                width, height = viewport
                self._page = self._browser.new_page(viewport={"width": width, "height": height})
                self._page.set_default_timeout(timeout * 1000)
                self._page.add_init_script(_BRIDGE_JS)
                self._page.goto(url, wait_until="load")
                self._page.wait_for_function("() => window.__slitherbot.canStart()")
        except BaseException:
            self.close()
            raise

    def start_round(self, nickname: str = "") -> Observation:
        """Join a new round and block until the snake is alive.

        Returns the first observation of the round. Calling this while a
        round is already in progress returns the current observation.
        After a death, the game shows a short fade before it allows a new
        round; this waits it out. Raises :class:`GameError` if the round
        does not start within the timeout.
        """
        with self._translate_errors("start a round"):
            if not self._page.evaluate("() => window.__slitherbot.isAlive()"):
                self._page.wait_for_function("() => window.__slitherbot.canStart()")
                self._page.evaluate("(n) => window.__slitherbot.start(n)", nickname)
                self._page.wait_for_function("() => window.__slitherbot.isAlive()")
        return self.observe()

    def observe(self) -> Observation:
        """Return a snapshot of the game right now. Cheap enough to call every tick.

        Raises :class:`GameClosed` if the browser has been closed.
        """
        with self._translate_errors("read game state"):
            # One JSON string crosses the Playwright boundary ~5x faster than the
            # same data as a JS object, which Playwright converts value by value.
            raw = self._page.evaluate("() => JSON.stringify(window.__slitherbot.observe())")
        return parse_observation(json.loads(raw))

    def act(self, action: Action) -> None:
        """Steer toward ``action.angle`` and set boost, until the next call.

        Does nothing when the snake is not alive, so a loop never has to
        guard against acting on the frame it dies.
        """
        with self._translate_errors("send an action"):
            self._page.evaluate(
                "([a, b]) => window.__slitherbot.act(a, b)", [action.angle, action.boost]
            )

    def close(self) -> None:
        """Shut down the browser. Safe to call more than once.

        Never raises: the browser may already be gone (closed by the user), or
        Playwright's driver process may have been interrupted by the same
        Ctrl+C that is unwinding the caller. Either way there is nothing
        useful a caller could do about a failed shutdown.
        """
        if self._playwright is None:
            return
        playwright, self._playwright = self._playwright, None
        try:
            if hasattr(self, "_browser"):
                self._browser.close()
        except Exception:
            pass
        try:
            playwright.stop()
        except Exception:
            pass

    @contextmanager
    def _translate_errors(self, doing: str) -> Generator[None]:
        """Re-raise Playwright failures as :class:`GameClosed` or :class:`GameError`."""
        try:
            yield
        except PlaywrightError as e:
            if self._is_gone():
                raise GameClosed("the browser was closed") from e
            raise GameError(f"could not {doing}: {e}") from e

    def _is_gone(self) -> bool:
        page = getattr(self, "_page", None)
        browser = getattr(self, "_browser", None)
        return (page is not None and page.is_closed()) or (
            browser is not None and not browser.is_connected()
        )

    def __enter__(self) -> Game:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
