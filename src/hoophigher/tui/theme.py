"""Hoop Higher design tokens.

Two sibling themes (dark default, light "paper") mapping the handoff role
table onto Textual theme variables. Widgets must reference a role variable
($accent, $success, $muted, $card-fill, ...) — never a raw hex — so a theme
swap stays a one-table change.

Role → Textual field mapping:
accent→primary+accent, success→success, danger→error, highlight→warning,
screen→background, panel→panel, raised→surface, text→foreground. The
remaining roles and the extra surface fills ship as custom variables.
"""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_path
from textual.theme import Theme

from hoophigher.data.db import APP_NAME

DARK_THEME_NAME = "hoop-higher-dark"
LIGHT_THEME_NAME = "hoop-higher-light"
DEFAULT_THEME_NAME = DARK_THEME_NAME

HOOP_HIGHER_DARK_THEME = Theme(
    name=DARK_THEME_NAME,
    primary="#FF6A3D",
    accent="#FF6A3D",
    success="#46C988",
    error="#FF5D61",
    warning="#F2C14E",
    foreground="#E8E6E1",
    background="#0E1013",
    surface="#22262E",
    panel="#191C22",
    dark=True,
    variables={
        "border": "#2A2F38",
        "border-blurred": "#2A2F38",
        "footer-background": "#0C0E11",
        "footer-key-foreground": "#9AA0AB",
        "footer-description-foreground": "#5C626D",
        # Handoff roles without a Textual field.
        "void": "#08090B",
        "muted": "#9AA0AB",
        "dim": "#5C626D",
        # Extra surfaces used in the mocks.
        "band-fill": "#191C22",
        "card-fill": "#12151B",
        "footer-strip": "#0C0E11",
        "success-fill": "#0F1A14",
        "danger-fill": "#1A1012",
        "loading-fill": "#16130C",
        "accent-fill": "#1A120D",
        "disabled-text": "#363B44",
        "hidden-glyph": "#3A4048",
        "zebra-fill": "#101216",
    },
)

HOOP_HIGHER_LIGHT_THEME = Theme(
    name=LIGHT_THEME_NAME,
    primary="#E0521F",
    accent="#E0521F",
    success="#1F9D57",
    error="#D13B3F",
    warning="#B8791A",
    foreground="#1E1B16",
    background="#FAF7F1",
    surface="#E0D9CB",
    panel="#ECE7DD",
    dark=False,
    variables={
        "border": "#D5CDBD",
        "border-blurred": "#D5CDBD",
        "footer-background": "#F0EBE1",
        "footer-key-foreground": "#6B6355",
        "footer-description-foreground": "#948B7A",
        "void": "#EAE4D8",
        "muted": "#6B6355",
        "dim": "#948B7A",
        # Paper-tint equivalents of the dark mock surfaces.
        "band-fill": "#F0EBE1",
        "card-fill": "#F3EEE4",
        "footer-strip": "#F0EBE1",
        "success-fill": "#E4F0E6",
        "danger-fill": "#F5E4E2",
        "loading-fill": "#F4EBD6",
        "accent-fill": "#F6E6DB",
        "disabled-text": "#C7BEAC",
        "hidden-glyph": "#B9AF9C",
        "zebra-fill": "#F3EEE3",
    },
)

HOOP_HIGHER_THEMES = (HOOP_HIGHER_DARK_THEME, HOOP_HIGHER_LIGHT_THEME)

# Fallback values so TCSS referencing the custom tokens keeps resolving when a
# non-Hoop Higher theme is active (e.g. the built-in ansi themes used for the
# 16-color validation harness).
THEME_VARIABLE_DEFAULTS: dict[str, str] = dict(HOOP_HIGHER_DARK_THEME.variables)


def theme_settings_path() -> Path:
    """File holding the persisted theme name for this machine."""
    return user_data_path(APP_NAME, appauthor=False) / "theme"


def load_saved_theme_name(path: Path | None = None) -> str | None:
    settings_path = path or theme_settings_path()
    try:
        name = settings_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return name or None


def save_theme_name(name: str, path: Path | None = None) -> None:
    settings_path = path or theme_settings_path()
    try:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(f"{name}\n", encoding="utf-8")
    except OSError:
        # Theme persistence is best-effort; never break the app over it.
        pass
