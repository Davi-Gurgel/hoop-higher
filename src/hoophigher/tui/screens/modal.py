"""Shared Hoop Higher modal shell: a centered panel over the dimmed game."""

from __future__ import annotations

from textual.screen import ModalScreen


class AppModalScreen(ModalScreen[None]):
    """Base for Hoop Higher modals; compose the panel with `.app-modal-panel`."""

    DEFAULT_CSS = """
    AppModalScreen {
        align: center middle;
        background: $void 60%;
    }

    AppModalScreen .app-modal-panel {
        width: 66;
        max-width: 90%;
        height: auto;
        padding: 1 2;
    }
    """
