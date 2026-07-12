"""Status strip: a left-barred, tinted band for transient states.

Used by Mode Select (loading, amber) and the Game reveal verdict
(success/danger). The tone class picks the bar color and fill:
`-loading`, `-success`, or `-danger`.
"""

from __future__ import annotations

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.content import Content
from textual.widgets import Static

STATUS_STRIP_TONES = ("-loading", "-success", "-danger")


class StatusStrip(Horizontal):
    DEFAULT_CSS = """
    StatusStrip {
        width: 100%;
        height: auto;
        padding: 1 2;
        display: none;
    }

    StatusStrip.-visible {
        display: block;
    }

    StatusStrip.-loading {
        border-left: thick $warning;
        background: $loading-fill;
    }

    StatusStrip.-success {
        border-left: thick $success;
        background: $success-fill;
    }

    StatusStrip.-danger {
        border-left: thick $error;
        background: $danger-fill;
    }

    StatusStrip #strip-body {
        width: 1fr;
        content-align: left middle;
    }

    StatusStrip #strip-value {
        width: auto;
        content-align: right middle;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static("", id="strip-body")
        yield Static("", id="strip-value")

    def show(self, tone: str, body_markup: str | Content, value_markup: str | Content = "") -> None:
        """Reveal the strip with the given tone, body, and right-aligned value."""
        if tone not in STATUS_STRIP_TONES:
            raise ValueError(f"Unknown StatusStrip tone {tone!r}.")
        for existing in STATUS_STRIP_TONES:
            self.remove_class(existing)
        self.add_class(tone, "-visible")
        self.query_one("#strip-body", Static).update(body_markup)
        self.query_one("#strip-value", Static).update(value_markup)

    def hide(self) -> None:
        self.remove_class("-visible")
        self.query_one("#strip-body", Static).update("")
        self.query_one("#strip-value", Static).update("")
