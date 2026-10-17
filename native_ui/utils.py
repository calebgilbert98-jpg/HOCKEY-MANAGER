"""Shared data/serialization helpers for the native UI.

R17 (2026-10-16): extracted VERBATIM from web_ui/bridge.py -- only the
helpers still imported by native_ui screens (to_web_team, TEAM_ABBR,
_clean_position) plus their exact dependency closure (_safe,
_POSITION_ABBR). Everything else in web_ui/bridge.py (Flask server,
to_web_player, to_web_message, hub state, command queue, ...) was dead
code: archived under archive/dead_2026-10-16/web_ui/.

No logic was changed in the move; the bodies below are byte-identical to
their web_ui/bridge.py originals (see diff note in the R17 review).
"""


# ------------------------------------------------------------------
# Serialization helpers
# ------------------------------------------------------------------
def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


# Clean position abbreviations: PlayerPosition.CENTER -> "C", etc.
# The raw str(enum) gives "PlayerPosition.CENTER" which looks terrible in the UI.
_POSITION_ABBR = {
    "CENTER": "C", "LEFT_WING": "LW", "RIGHT_WING": "RW",
    "LEFT_DEFENSE": "LD", "RIGHT_DEFENSE": "RD", "GOALIE": "G",
    "C": "C", "LW": "LW", "RW": "RW", "LD": "LD", "RD": "RD", "G": "G",
}


def _clean_position(pos):
    """Map a position enum/string to a clean abbreviation."""
    try:
        s = str(pos or "")
        # Handle "PlayerPosition.CENTER" -> "CENTER" -> "C"
        if "." in s:
            s = s.split(".")[-1]
        s = s.strip().upper()
        return _POSITION_ABBR.get(s, s or "?")
    except Exception:
        return "?"


# Canonical NHL abbreviations: Team objects don't carry an `abbreviation`
# attribute, so the web UI maps full names here (else "Boston Bruins"
# becomes "BB" and nothing matches "BOS").
TEAM_ABBR = {
    "Anaheim Ducks": "ANA", "Boston Bruins": "BOS", "Buffalo Sabres": "BUF",
    "Calgary Flames": "CGY", "Carolina Hurricanes": "CAR",
    "Chicago Blackhawks": "CHI", "Colorado Avalanche": "COL",
    "Columbus Blue Jackets": "CBJ", "Dallas Stars": "DAL",
    "Detroit Red Wings": "DET", "Edmonton Oilers": "EDM",
    "Florida Panthers": "FLA", "Los Angeles Kings": "LAK",
    "Minnesota Wild": "MIN", "Montreal Canadiens": "MTL",
    "Montréal Canadiens": "MTL", "Nashville Predators": "NSH",
    "New Jersey Devils": "NJD", "New York Islanders": "NYI",
    "New York Rangers": "NYR", "Ottawa Senators": "OTT",
    "Philadelphia Flyers": "PHI", "Pittsburgh Penguins": "PIT",
    "San Jose Sharks": "SJS", "Seattle Kraken": "SEA",
    "St. Louis Blues": "STL", "Tampa Bay Lightning": "TBL",
    "Toronto Maple Leafs": "TOR", "Utah Hockey Club": "UTA",
    "Utah Mammoth": "UTA", "Vancouver Canucks": "VAN",
    "Vegas Golden Knights": "VGK", "Washington Capitals": "WSH",
    "Winnipeg Jets": "WPG",
}


def to_web_team(t):
    """Team -> JSON-safe dict (hub header data)."""
    _tname = _safe(lambda: str(getattr(t, "team_name", "?")), "?")
    _abbr = (_safe(lambda: getattr(t, "abbreviation", ""), "") or
             TEAM_ABBR.get(_tname) or
             "".join(w[0] for w in _tname.split()[:3]).upper())
    wins = _safe(lambda: int(getattr(t, "wins", 0) or 0), 0)
    losses = _safe(lambda: int(getattr(t, "losses", 0) or 0), 0)
    otl = _safe(lambda: int(getattr(t, "ot_losses", 0) or 0), 0)
    return {
        "name": _tname,
        "city": _safe(lambda: getattr(t, "city", "")),
        "abbr": _abbr,
        "wins": wins,
        "losses": losses,
        "otl": otl,
        # JS hub expects team.record.{w,l,otl} (matches mock shape)
        "record": {"w": wins, "l": losses, "otl": otl},
        "roster_size": _safe(lambda: len(getattr(t, "roster", None) or [])),
    }
