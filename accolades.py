"""Player accolades: the permanent trophy case.

Every award win and Stanley Cup is banked onto the player as a plain dict
``{"award": key, "year": label}`` in ``player.career_accolades`` -- never
duplicated (banking is idempotent on (award, year)), never wiped.
Plain dicts = save/load safe with zero new serialization code.

Display groups by award, Muck's format:
    Hart Trophy Winner: 2021, 2025
    Rocket Richard Winner: 2021
    Stanley Cup Winner: 2021-22, 2022-23, 2023-24

Year conventions (his format):
- Individual awards: ceremony year, e.g. "2025" for the 2024-25 season.
- Stanley Cup: season label, e.g. "2024-25".
"""
from typing import Any, Dict, List, Tuple

# Canonical key -> display name. Keys match reputation_system's award keys
# ('lady_byng' normalized to 'byng' at bank time).
ACCOLADE_LABELS: Dict[str, str] = {
    "stanley_cup": "Stanley Cup",
    "hart": "Hart Trophy",
    "art_ross": "Art Ross Trophy",
    "rocket": "Rocket Richard Trophy",
    "norris": "Norris Trophy",
    "vezina": "Vezina Trophy",
    "selke": "Selke Trophy",
    "byng": "Lady Byng Trophy",
    "calder": "Calder Trophy",
    "conn_smythe": "Conn Smythe Trophy",
    "jennings": "Jennings Trophy",
}

# Display order: the Cup first, then individual awards by prestige.
ACCOLADE_ORDER: List[str] = [
    "stanley_cup", "conn_smythe", "hart", "art_ross", "rocket",
    "norris", "vezina", "selke", "byng", "calder", "jennings",
]

_KEY_ALIASES = {"lady_byng": "byng"}


def _canon_key(award_key: str) -> str:
    return _KEY_ALIASES.get(str(award_key or "").lower(),
                            str(award_key or "").lower())


def bank_accolade(player: Any, award_key: str, year_label: str) -> bool:
    """Record an award/Cup win on the player. Idempotent on
    (award, year) -- safe to call every rollover. Returns True if added."""
    try:
        key = _canon_key(award_key)
        year = str(year_label or "")
        if not key or not year:
            return False
        acc = getattr(player, "career_accolades", None)
        if not isinstance(acc, list):
            try:
                player.career_accolades = acc = []
            except Exception:
                return False
        for e in acc:
            if isinstance(e, dict) and e.get("award") == key \
                    and str(e.get("year")) == year:
                return False  # already banked -- never duplicate
        acc.append({"award": key, "year": year})
        return True
    except Exception:
        return False


def group_accolades(player: Any) -> List[Tuple[str, List[str]]]:
    """Return [(display_label, [year, ...]), ...] in ACCOLADE_ORDER.
    Years sorted ascending. Unknown keys appended at the end."""
    grouped: Dict[str, List[str]] = {}
    try:
        for e in getattr(player, "career_accolades", None) or []:
            if not isinstance(e, dict):
                continue
            key = _canon_key(e.get("award"))
            year = str(e.get("year", ""))
            if not key or not year:
                continue
            if year not in grouped.setdefault(key, []):
                grouped[key].append(year)
    except Exception:
        pass
    out: List[Tuple[str, List[str]]] = []
    for key in ACCOLADE_ORDER:
        if key in grouped:
            out.append((ACCOLADE_LABELS.get(key, key),
                        sorted(grouped.pop(key))))
    for key in sorted(grouped):
        out.append((ACCOLADE_LABELS.get(key, key), sorted(grouped[key])))
    return out


def accolade_count(player: Any) -> int:
    """Total banked accolades (for QA)."""
    try:
        return sum(1 for e in getattr(player, "career_accolades", None) or []
                   if isinstance(e, dict))
    except Exception:
        return 0
