"""Mode Select card: `N NAME` + scoring right, muted description below.

Focused card = accent border, faint accent fill, `▸` marker, accent name.
While a fetch is in flight the selected card shows `← starting` and the
other cards render disabled (dim text and border, non-focusable).
"""

from __future__ import annotations

from textual.content import Content

from hoophigher.domain.enums import GameMode
from hoophigher.tui.widgets.desk_button import DeskButton

_SCORING_MARKUP = {
    GameMode.ENDLESS: ("[$success]+100[/][$dim] / [/][$error]−60[/]", "+100 / −60"),
    GameMode.ARCADE: ("[$success]+150[/][$dim] / over[/]", "+150 / over"),
    GameMode.HISTORICAL: ("[$success]+100[/][$dim] / [/][$error]−60[/]", "+100 / −60"),
}

_DESCRIPTIONS = {
    GameMode.ENDLESS: "Miss all you like — the run rolls on.",
    GameMode.ARCADE: "One miss and you're done. Bigger points.",
    GameMode.HISTORICAL: "A random night from the archives.",
}


class ModeCard(DeskButton):
    DEFAULT_CSS = """
    ModeCard, ModeCard.-style-default {
        height: 4;
        background: $card-fill;
        content-align: left top;
        margin-bottom: 1;

        &:hover {
            background: $card-fill;
        }

        &:focus {
            background: $accent-fill;
            color: $foreground;
            text-style: none;
        }

        &:disabled {
            background: $card-fill;
        }
    }
    """

    def __init__(self, mode: GameMode, shortcut: str, **kwargs: object) -> None:
        super().__init__(mode.value.upper(), **kwargs)
        self._mode = mode
        self._shortcut = shortcut
        self._loading = False

    @property
    def mode(self) -> GameMode:
        return self._mode

    def set_loading(self, loading: bool) -> None:
        if loading != self._loading:
            self._loading = loading
            self.refresh()

    def render(self) -> Content:
        width = self.content_size.width - 2 * self.styles.line_pad
        name = self._mode.value.upper()
        marker = "▸ " if self.has_focus else "  "
        left_plain = f"{marker}{self._shortcut}  {name}"

        if self.disabled:
            top = f"{left_plain}[$dim] · disabled while loading[/]"
            return Content.from_markup(f"{top}\n     $desc", desc=_DESCRIPTIONS[self._mode])

        if self._loading:
            right_markup, right_plain = ("[$warning]← starting[/]", "← starting")
        else:
            right_markup, right_plain = _SCORING_MARKUP[self._mode]
        gap = " " * max(1, width - len(left_plain) - len(right_plain))
        name_markup = f"[$accent]{name}[/]" if self.has_focus else name
        top = f"[bold]{marker}{self._shortcut}  {name_markup}[/]{gap}{right_markup}"
        return Content.from_markup(f"{top}\n     [$muted]$desc[/]", desc=_DESCRIPTIONS[self._mode])
