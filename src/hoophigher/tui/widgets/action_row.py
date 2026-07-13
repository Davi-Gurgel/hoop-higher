"""Full-width menu action row: label left, shortcut right.

Focused row = solid accent fill + near-black bold text + `▸` marker;
unfocused = hairline outline with muted label and dim shortcut. Focus is a
fill change first, color second, so it survives 16-color terminals.
"""

from __future__ import annotations

from textual.content import Content

from hoophigher.tui.widgets.desk_button import DeskButton


class ActionRow(DeskButton):
    """A Button restyled as a STAT DESK menu row.

    Keeps Button's press/click/message semantics but renders its own
    two-sided line (label left, shortcut right). The DeskButton reset is
    exactly this row's look, so it carries no CSS of its own.
    """

    def __init__(self, text: str, shortcut: str, **kwargs: object) -> None:
        super().__init__(text, **kwargs)
        self._text = text
        self._shortcut = shortcut

    def render(self) -> Content:
        # Button pads each rendered line by `line-pad` cells per side; stay
        # inside that budget or the shortcut wraps onto a hidden second line.
        width = self.content_size.width - 2 * self.styles.line_pad
        left = f"▸ {self._text}" if self.has_focus else self._text
        gap = " " * max(1, width - len(left) - len(self._shortcut))
        # Substitution keeps literal brackets in shortcuts ("[L]") out of the
        # markup parser.
        if self.has_focus:
            return Content.from_markup("$left$gap$key", left=left, gap=gap, key=self._shortcut)
        return Content.from_markup("$left$gap[$dim]$key[/]", left=left, gap=gap, key=self._shortcut)
