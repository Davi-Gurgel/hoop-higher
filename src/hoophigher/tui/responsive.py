"""Shared responsive tier model.

One vocabulary for terminal-size degradation, per the handoff: `xs` below
72 columns, `sm` below 96, `full` at 96 and up. Copy (button labels, footer
hints, scorebug) also drops to `xs` under 24 rows, while card layout stays
width-only — short-but-wide terminals keep full cards and scroll instead.

The app's breakpoint classes (`-w-sm`, `-h-xs`, ...) are built from the
same thresholds, so TCSS rules and imperative tier switches can never
disagree.
"""

from __future__ import annotations

from typing import Literal

Tier = Literal["full", "sm", "xs"]

SM_MIN_WIDTH = 72
FULL_MIN_WIDTH = 96
SM_MIN_HEIGHT = 24


def tier_for(width: int, height: int | None = None) -> Tier:
    """Tier for a terminal size; pass `height` to also degrade on short terminals."""
    if width < SM_MIN_WIDTH or (height is not None and height < SM_MIN_HEIGHT):
        return "xs"
    if width < FULL_MIN_WIDTH:
        return "sm"
    return "full"
