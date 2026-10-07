"""Shared helpers for the read-only Systems explainer screens (Phase 6).

Each page documents sim mechanics inline; every number shown is a direct
engine read. These helpers keep the six screens small and consistent.
"""
from PySide6.QtWidgets import QLabel


#: Qualitative tone -> hex. No teal per UI rules; slate stands in for cool.
TONE_COLORS = {
    "red": "#ef4444",
    "gold": "#f59e0b",
    "green": "#22c55e",
    "blue": "#3B82F6",
    "slate": "#8b95ab",
    "white": "#ffffff",
}


def tone_color(tone):
    """Hex color for a qualitative tone name (red/gold/green/blue/slate)."""
    return TONE_COLORS.get(str(tone or "").lower(), TONE_COLORS["slate"])


def gm_of(game):
    """Game manager whether game IS the manager or wraps it in .game_manager."""
    try:
        return getattr(game, "game_manager", None) or game
    except Exception:
        return game


def _attr(obj, name):
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def user_team(game):
    gm = gm_of(game)
    return _attr(gm, "user_team") or _attr(game, "user_team")


def league_of(game):
    gm = gm_of(game)
    return _attr(gm, "league") or _attr(game, "league")


def today_of(game):
    gm = gm_of(game)
    return _attr(gm, "current_date") or _attr(game, "current_date")


def player_name(p):
    return str(_attr(p, "full_name") or "?")


def pos_short(p):
    """Short position string, enum-aware (never raw enum repr).

    PlayerPosition values are already short ("C", "LW", "RW", "LD", "RD",
    "D", "G"); str() fallback only for plain-string positions.
    """
    pos = _attr(p, "primary_position") or _attr(p, "position")
    return str(getattr(pos, "value", pos) or "?")


def heat_band(intensity):
    """(band label, tone) for a rivalry intensity 0-100."""
    try:
        i = float(intensity)
    except (TypeError, ValueError):
        i = 0.0
    if i >= 80:
        return "WHITE HOT", "red"
    if i >= 60:
        return "Heated", "gold"
    if i >= 40:
        return "Simmering", "blue"
    return "Cooling", "slate"


def explainer_label(text):
    """Muted, word-wrapped paragraph for the inline design text."""
    lbl = QLabel(text)
    lbl.setWordWrap(True)
    lbl.setStyleSheet("color: #8b95ab; font-size: 13px;")
    return lbl


def section_title(text):
    lbl = QLabel(text)
    lbl.setObjectName("section-header")
    return lbl


def no_game_label():
    return explainer_label("No game loaded.")


def clear_layout(layout):
    """Remove all widgets from a layout (used by refresh())."""
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()


def systems_nav_bar(screen):
    """Nav bar linking all 6 systems screens. Call at top of _build_body."""
    from PySide6.QtWidgets import QHBoxLayout, QPushButton
    from PySide6.QtCore import Qt
    bar = QHBoxLayout()
    bar.setSpacing(8)
    screens = [
        ("Clutch", "systems_clutch"),
        ("Circumstance", "systems_circumstance"),
        ("Discipline", "systems_discipline"),
        ("Rivalry", "systems_rivalry"),
        ("Deployment", "systems_deployment"),
        ("Condition", "systems_condition"),
    ]
    for label, name in screens:
        btn = QPushButton(label)
        btn.setCursor(Qt.PointingHandCursor)
        btn.clicked.connect(
            lambda _=False, n=name: screen.main_window.show_screen(n))
        bar.addWidget(btn)
    bar.addStretch()
    return bar
