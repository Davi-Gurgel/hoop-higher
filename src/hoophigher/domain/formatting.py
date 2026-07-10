"""Canonical display formatting for domain values shared across layers."""

from __future__ import annotations

from datetime import date


def format_source_date(value: date | None) -> str:
    """Render a Source Date, or "--" when a Run has none recorded."""
    return f"{value:%d-%m-%Y}" if value is not None else "--"
