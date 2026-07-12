"""STAT DESK global chrome: Scorebug, HeaderBand, and FooterHints.

These carry the shared visual language across screens: a panel band pinned
to the top (Scorebug on Game, HeaderBand elsewhere) and a dim strip of live
key bindings pinned to the bottom.
"""

from __future__ import annotations

from typing import Literal

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.widgets import Static

from hoophigher.services import GameplaySnapshot

ChromeTier = Literal["full", "sm", "xs"]

_SCORE_FLASH_SECONDS = 0.8


def hints(*pairs: tuple[str, str]) -> str:
    """Render `(key, label)` pairs as one dim footer line: `H higher · L lower`."""
    parts = []
    for key, label in pairs:
        if key and label:
            parts.append(f"[$muted]{key}[/] {label}")
        elif key:
            parts.append(f"[$muted]{key}[/]")
        else:
            parts.append(label)
    return " · ".join(parts)


class Scorebug(Horizontal):
    """Single band at the top of Game: brand/mode/round/Q left, score/streak/best right.

    On a scoring event the score value recolors for one beat (success ▲ on a
    gain, danger ▼ on a loss) before settling back to highlight.
    """

    DEFAULT_CSS = """
    Scorebug {
        dock: top;
        height: 2;
        width: 100%;
        background: $band-fill;
        border-bottom: solid $border;
        padding: 0 2;
    }

    Scorebug #scorebug-run {
        width: 1fr;
        content-align: left middle;
    }

    Scorebug #scorebug-score {
        width: auto;
        content-align: right middle;
    }
    """

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._snapshot: GameplaySnapshot | None = None
        self._tier: ChromeTier = "full"
        self._flash: Literal["gain", "loss", None] = None

    def compose(self) -> ComposeResult:
        yield Static("", id="scorebug-run")
        yield Static("", id="scorebug-score")

    def update_snapshot(self, snapshot: GameplaySnapshot) -> None:
        self._snapshot = snapshot
        self._render_band()

    def set_tier(self, tier: ChromeTier) -> None:
        if tier != self._tier:
            self._tier = tier
            self._render_band()

    def show_scoring_event(self, *, is_gain: bool) -> None:
        """Flash the score value for one beat, then settle back to highlight."""
        self._flash = "gain" if is_gain else "loss"
        self._render_band()
        self.set_timer(_SCORE_FLASH_SECONDS, self._settle_score)

    def _settle_score(self) -> None:
        self._flash = None
        self._render_band()

    def _render_band(self) -> None:
        s = self._snapshot
        if s is None:
            return
        brand = "[bold $accent]HOOP HIGHER[/]"
        question_counter = f"{s.question_index + 1}/{s.total_questions}"
        if self._tier == "full":
            run_part = (
                f"{brand}[$dim] · [/][$muted]{s.mode.value.upper()}[/]"
                f"[$dim] · round [/][bold]{s.round_index + 1}[/]"
                f"[$dim] · Q [/][bold]{question_counter}[/]"
            )
        elif self._tier == "sm":
            run_part = (
                f"{brand}[$dim] · [/][$muted]{s.mode.value[0].upper()}[/]"
                f"[$dim] · Q[/][bold]{question_counter}[/]"
            )
        else:
            run_part = brand
        self.query_one("#scorebug-run", Static).update(run_part)

        if self._flash == "gain":
            score_value = f"[bold $success]{s.score} ▲[/]"
        elif self._flash == "loss":
            score_value = f"[bold $error]{s.score} ▼[/]"
        else:
            score_value = f"[bold $warning]{s.score}[/]"
        if self._tier == "full":
            score_part = (
                f"[$dim]score [/]{score_value}"
                f"[$dim] · streak [/][bold]{s.current_streak}[/]"
                f"[$dim] · best [/][$muted]{s.best_streak}[/]"
            )
        elif self._tier == "sm":
            score_part = (
                f"{score_value}[$dim] · [/][bold]{s.current_streak}[/][$dim]/{s.best_streak}[/]"
            )
        else:
            score_part = f"{score_value} [$muted]★{s.current_streak}[/]"
        self.query_one("#scorebug-score", Static).update(score_part)


class HeaderBand(Horizontal):
    """Non-Game screen header: `‹ back  TITLE · subtitle` on a panel band."""

    DEFAULT_CSS = """
    HeaderBand {
        dock: top;
        height: 2;
        width: 100%;
        background: $band-fill;
        border-bottom: solid $border;
        padding: 0 2;
    }

    HeaderBand #header-band-text {
        width: 1fr;
        content-align: left middle;
    }
    """

    def __init__(self, title: str, subtitle: str = "", **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._title = title
        self._subtitle = subtitle

    def compose(self) -> ComposeResult:
        yield Static(self._band_markup(), id="header-band-text")

    def _band_markup(self) -> str:
        band = f"[$dim]‹ back[/]  [bold]{self._title}[/]"
        if self._subtitle:
            band += f"[$muted] · {self._subtitle}[/]"
        return band


class FooterHints(Static):
    """Dim strip of live bindings pinned to the bottom of every screen.

    Content is markup; screens use `hints()` for the standard key line and
    pass richer markup for transient states (`esc CANCEL`, the blinking
    reveal-held line).
    """

    DEFAULT_CSS = """
    FooterHints {
        dock: bottom;
        height: 2;
        width: 100%;
        background: $footer-strip;
        border-top: solid $border;
        color: $dim;
        padding: 0 2;
        content-align: left middle;
    }
    """

    def set_hints(self, markup: str) -> None:
        self.update(markup)
