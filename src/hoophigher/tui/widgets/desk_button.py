"""Shared reset for STAT DESK buttons.

Button's stock look (tall borders, surface fill, hover/focus tint) fights
the desk language, and overriding it means matching the `.-style-default`
variant class Textual stamps on plain buttons. That fight lives here once:
hairline outline at rest, muted outline on hover, solid accent fill with
near-black text on focus. Subclasses and screen CSS state only their color
and layout deltas.
"""

from __future__ import annotations

from textual.widgets import Button


class DeskButton(Button, inherit_bindings=False):
    """Button with the STAT DESK reset; screens own the Enter binding."""

    DEFAULT_CSS = """
    DeskButton, DeskButton.-style-default {
        width: 100%;
        height: 3;
        min-width: 0;
        padding: 0 2;
        border: round $border;
        background: transparent;
        color: $foreground;
        text-align: left;
        content-align: left middle;
        text-style: none;

        &:hover {
            border: round $muted;
            background: transparent;
        }

        &:focus {
            border: round $accent;
            background: $accent;
            color: $void;
            text-style: bold;
            background-tint: transparent;
        }

        &:disabled {
            border: round $border;
            background: transparent;
            color: $disabled-text;
            text-opacity: 1;
        }
    }
    """
