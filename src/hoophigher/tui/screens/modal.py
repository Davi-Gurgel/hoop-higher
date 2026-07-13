"""Shared STAT DESK modal shell: a centered panel over the dimmed game."""

from __future__ import annotations

from textual.screen import ModalScreen


class DeskModalScreen(ModalScreen[None]):
    """Base for STAT DESK modals; compose the panel with `.desk-modal-panel`."""

    DEFAULT_CSS = """
    DeskModalScreen {
        align: center middle;
        background: $void 60%;
    }

    DeskModalScreen .desk-modal-panel {
        width: 66;
        max-width: 90%;
        height: auto;
        padding: 1 2;
    }
    """
