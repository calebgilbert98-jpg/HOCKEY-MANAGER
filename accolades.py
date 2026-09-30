# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
    "jack_adams": "Jack Adams Award",
    "all_star": "NHL All-Star",
    "player_of_month": "NHL Player of the Month",
    "rookie_of_month": "NHL Rookie of the Month",
    # --- Junior / college (banked by prospect_accolades.py) ---
    "memorial_cup": "Memorial Cup",
    "stafford_smythe": "Stafford Smythe Memorial Trophy",
    "ed_chynoweth_trophy": "Ed Chynoweth Trophy",
    "chl_player_of_year": "CHL Player of the Year",
    "chl_top_scorer": "CHL Top Scorer",
    "chl_goaltender_of_year": "CHL Goaltender of the Year",
    "chl_rookie_of_year": "CHL Rookie of the Year",
    "robertson_cup": "J. Ross Robertson Cup",
    "courteau_trophy": "Gilles-Courteau Trophy",
    "ed_chynoweth_cup": "Ed Chynoweth Cup",
    "red_tilson": "Red Tilson Trophy",
    "michel_briere": "Michel Brière Trophy",
    "four_broncos": "Four Broncos Memorial Trophy",
    "eddie_powers": "Eddie Powers Memorial Trophy",
    "jean_beliveau": "Jean Béliveau Trophy",
    "bob_clarke": "Bob Clarke Trophy",
    "max_kaminsky": "Max Kaminsky Trophy",
    "emile_bouchard": "Émile Bouchard Trophy",
    "bill_hunter": "Bill Hunter Memorial Trophy",
    "jim_rutherford": "Jim Rutherford Trophy",
    "jacques_plante": "Jacques Plante Trophy",
    "del_wilson": "Del Wilson Trophy",
    "emms_family": "Emms Family Award",
    "rds_cup": "RDS Cup",
    "jim_piggott": "Jim Piggott Memorial Trophy",
    "clark_cup": "Clark Cup",
    "ushl_player_of_year": "USHL Player of the Year",
    "ncaa_championship": "NCAA National Championship",
    "hobey_baker": "Hobey Baker Award",
    "mike_richter": "Mike Richter Award",
    "tim_taylor": "Tim Taylor Award",
    "kharlamov_cup": "Kharlamov Cup",
    "j20_champion": "J20 Nationell Champion",
    "u20_sm_champion": "U20 SM-sarja Champion",
    "le_mat": "Le Mat Trophy",
    "kanada_malja": "Kanada-malja",
    "gagarin_cup": "Gagarin Cup",
    "nl_champion": "National League Champion",
    "wjc_gold": "World Junior Gold Medal",
    "wjc_silver": "World Junior Silver Medal",
    "wjc_bronze": "World Junior Bronze Medal",
    "wjc_mvp": "World Junior Championship MVP",
}

# Display order: the Cup first, then individual awards by prestige,
# then the junior/college trophy case (a prospect's story arc reads
# pro-first, junior-below on the player card).
ACCOLADE_ORDER: List[str] = [
    "stanley_cup", "conn_smythe", "hart", "art_ross", "rocket",
    "norris", "vezina", "selke", "byng", "calder", "jennings",
    "jack_adams", "all_star", "player_of_month", "rookie_of_month",
    # --- Junior / college (prospect_accolades.py) ---
    "memorial_cup", "stafford_smythe", "ed_chynoweth_trophy",
    "chl_player_of_year", "chl_top_scorer", "chl_goaltender_of_year",
    "chl_rookie_of_year",
    "robertson_cup", "courteau_trophy", "ed_chynoweth_cup",
    "red_tilson", "michel_briere", "four_broncos",
    "eddie_powers", "jean_beliveau", "bob_clarke",
    "max_kaminsky", "emile_bouchard", "bill_hunter",
    "jim_rutherford", "jacques_plante", "del_wilson",
    "emms_family", "rds_cup", "jim_piggott",
    "clark_cup", "ushl_player_of_year",
    "ncaa_championship", "hobey_baker", "mike_richter", "tim_taylor",
    "kharlamov_cup", "j20_champion", "u20_sm_champion",
    "le_mat", "kanada_malja", "gagarin_cup", "nl_champion",
    "wjc_gold", "wjc_silver", "wjc_bronze", "wjc_mvp",
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
