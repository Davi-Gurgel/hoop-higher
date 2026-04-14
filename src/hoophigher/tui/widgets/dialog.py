from __future__ import annotations

from textual.containers import Vertical


class DialogShell(Vertical):
    """Shared container for centered panels and modal overlays."""

    DEFAULT_CSS = """
    DialogShell {
        width: auto;
        height: auto;
    }
    """
