"""Canonical display formatting for domain values shared across layers."""

from __future__ import annotations

from datetime import date


def format_source_date(value: date | None) -> str:
    """Render a Source Date, or "--" when a Run has none recorded."""
    return f"{value:%d-%m-%Y}" if value is not None else "--"


def player_first_name(full_name: str) -> str:
    """First whitespace-separated token of a Player name, for compact copy."""
    parts = full_name.split()
    return parts[0] if parts else full_name


def player_last_name(full_name: str) -> str:
    """Last whitespace-separated token of a Player name, for compact copy."""
    parts = full_name.split()
    return parts[-1] if parts else full_name
