"""FM / Eastside-style player list views.

A *view* is a named column preset for any player table in the game
(roster screens, scouting screens, draft board, ...). Views are shared:
picking "Offense" on the roster shows the same columns as "Offense" in
scouting, so the GM learns one set of lenses and uses them everywhere.

Knowledge lens
--------------
Values are read through a :class:`ViewContext`. ``mode="full"`` shows true
values (your own roster -- you know your players). ``mode="scouted"``
shows *perceived* values through your scouts' eyes (scout_perception):
a barely-scouted player shows ranges like ``62-78`` and filters match on
the midpoint of what you actually know. That keeps the "analytics is a
puzzle, not answers" philosophy intact inside the new UI.

Custom views are persisted per user at ``~/.puck-dynasty/player_views.json``
(outside the repo, so they never dirty the tree).

This module only READS attributes/composites -- the attribute and
composite definitions themselves are protected ground (observation only).
"""

import json
import os
from dataclasses import dataclass, field

# ---------------------------------------------------------------------------
# Custom-view persistence (user-local, outside the repo)
# ---------------------------------------------------------------------------

_CUSTOM_DIR = os.path.join(os.path.expanduser("~"), ".puck-dynasty")
_CUSTOM_PATH = os.path.join(_CUSTOM_DIR, "player_views.json")


def load_custom_views():
    """Return {view_name: [column_key, ...]} saved by the user."""
    try:
        with open(_CUSTOM_PATH, "r") as f:
            data = json.load(f)
        views = data.get("views", {})
        return {str(k): [str(c) for c in v]
                for k, v in views.items() if isinstance(v, list) and v}
    except Exception:
        return {}


def save_custom_view(name, column_keys):
    """Persist one user-defined view. Raises ValueError on bad input."""
    name = (name or "").strip()
    cols = [c for c in (column_keys or []) if c in COLUMN_DEFS]
    if not name:
        raise ValueError("View name cannot be empty.")
    if name in VIEWS:
        raise ValueError(f"'{name}' is a built-in view and cannot be overwritten.")
    if not cols:
        raise ValueError("A view needs at least one column.")
    views = load_custom_views()
    views[name] = cols
    _write_custom_views(views)


def delete_custom_view(name):
    views = load_custom_views()
    if name in views:
        del views[name]
        _write_custom_views(views)


def _write_custom_views(views):
    os.makedirs(_CUSTOM_DIR, exist_ok=True)
    tmp = _CUSTOM_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"views": views}, f, indent=2)
    os.replace(tmp, _CUSTOM_PATH)


def list_view_names():
    """Built-in view names first, then the user's custom views."""
    names = list(VIEWS.keys())
    for n in load_custom_views():
        if n not in VIEWS and n not in names:
            names.append(n)
    return names


def get_view_columns(name):
    """Column keys for a built-in or custom view (None if unknown)."""
    if name in VIEWS:
        return list(VIEWS[name])
    return load_custom_views().get(name)


# ---------------------------------------------------------------------------
# Knowledge lens
# ---------------------------------------------------------------------------

def _fmt_val(v):
    """Display text for an int, float, or (lo, hi) perceived range."""
    if v is None:
        return "--"
    if isinstance(v, tuple):
        lo, hi = v
        try:
            return f"{int(round(lo))}\u2013{int(round(hi))}"
        except (TypeError, ValueError):
            return "--"
    try:
        return str(int(round(float(v))))
    except (TypeError, ValueError):
        return str(v)


def _mid(v):
    """Numeric midpoint used for filtering/sorting (ranges collapse)."""
    if v is None:
        return None
    if isinstance(v, tuple):
        try:
            return (float(v[0]) + float(v[1])) / 2.0
        except (TypeError, ValueError):
            return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


class ViewContext:
    """How a screen reads player values: true or scout-perceived."""

    def __init__(self, app=None, mode="full"):
        self.app = app
        self.mode = mode  # "full" | "scouted"
        self._attr_cache = {}
        self._comp_cache = {}

    # -- perceived reads ----------------------------------------------------
    def _perceived(self, player):
        pid = getattr(player, "id", None)
        if pid in self._attr_cache:
            return self._attr_cache[pid], self._comp_cache.get(pid)
        attrs, comps = None, None
        try:
            from scout_perception import (
                resolve_tab_scout, perceived_attributes,
                perceived_composites,
            )
            user_team = getattr(self.app, "user_team", None)
            scout, _rep = resolve_tab_scout(user_team, player)
            if scout is None:
                # No scout on staff: the honest state is "unknown", never
                # a noisy read and never true values (matches the tab's
                # contract in scout_perception.resolve_tab_scout).
                self._attr_cache[pid] = None
                self._comp_cache[pid] = None
                return None, None
            reports = getattr(user_team, "scouting_reports", None) or {}
            report = reports.get(pid)
            attrs = perceived_attributes(player, scout, report)
            try:
                comps = perceived_composites(player, scout, report)
            except Exception:
                comps = None
        except Exception:
            attrs, comps = None, None
        self._attr_cache[pid] = attrs
        self._comp_cache[pid] = comps
        return attrs, comps

    @staticmethod
    def _true_attr(player, key):
        try:
            v = getattr(player, key, None)
        except Exception:
            return None
        if v is None:
            return None
        try:
            return max(1.0, min(100.0, float(v)))
        except (TypeError, ValueError):
            return None

    def attr(self, player, key):
        """Attribute value: int in full mode, int or (lo, hi) scouted."""
        if self.mode == "scouted":
            attrs, _ = self._perceived(player)
            if attrs and key in attrs:
                return attrs[key]
            # Unknown to the scout (or no scout): never leak true values.
            return None
        return self._true_attr(player, key)

    def composite(self, player, key):
        """Composite rating: float in full mode, float or (lo, hi) scouted."""
        if self.mode == "scouted":
            _, comps = self._perceived(player)
            if comps and key in comps:
                return comps[key]
            return None
        try:
            import attribute_composites as ac
            ratings = ac.get_composite_ratings(player)
            v = ratings.get(key)
            return float(v) if v is not None else None
        except Exception:
            return None

    def invalidate(self):
        self._attr_cache.clear()
        self._comp_cache.clear()


# ---------------------------------------------------------------------------
# Column registry
# ---------------------------------------------------------------------------

@dataclass
class ColumnDef:
    key: str
    header: str
    width: int
    group: str            # picker grouping in the view editor
    align: str = "center"  # "center" | "w"


def _attr_label(key):
    try:
        from scout_perception import attr_label
        return attr_label(key)
    except Exception:
        return key.replace("_", " ").title()


def _composite_label(key):
    try:
        from scout_perception import composite_label
        return composite_label(key)
    except Exception:
        return key.replace("_", " ").title()


def _skater_attrs():
    try:
        from scout_perception import SKATER_ATTRS
        return list(SKATER_ATTRS)
    except Exception:
        return ["skating", "shooting", "passing", "deking",
                "offensive_awareness", "defensive_awareness",
                "checking", "faceoffs", "strength"]


def _goalie_attrs():
    try:
        from scout_perception import GOALIE_ATTRS
        return list(GOALIE_ATTRS)
    except Exception:
        return ["goaltending"]


def _composite_keys():
    try:
        from attribute_composites import COMPOSITE_KEYS
        return list(COMPOSITE_KEYS)
    except Exception:
        return []


def build_column_defs():
    """Full column registry: static columns + generated attr/composite ones."""
    defs = {}

    def add(key, header, width, group, align="center"):
        defs[key] = ColumnDef(key, header, width, group, align)

    # -- identity -----------------------------------------------------------
    add("name", "Name", 170, "Info", "w")
    add("pos", "Pos", 48, "Info")
    add("age", "Age", 42, "Info")
    add("ovr", "OVR", 48, "Info")
    add("team", "Team", 140, "Info", "w")
    add("nat", "Nat", 64, "Info")
    add("ht", "Ht", 54, "Info")
    add("wt", "Wt", 52, "Info")
    # -- season stats (skaters) ----------------------------------------------
    add("gp", "GP", 42, "Season")
    add("g", "G", 38, "Season")
    add("a", "A", 38, "Season")
    add("p", "P", 42, "Season")
    add("ppg", "P/GP", 48, "Season")
    add("pm", "+/-", 44, "Season")
    add("shots", "Shots", 52, "Season")
    add("hits", "Hits", 46, "Season")
    add("blocks", "Blocks", 54, "Season")
    add("takeaways", "Takeaways", 70, "Season")
    add("pim", "PIM", 46, "Season")
    # -- goalie stats ----------------------------------------------------------
    add("w", "W", 38, "Goalie")
    add("l", "L", 38, "Goalie")
    add("gaa", "GAA", 52, "Goalie")
    add("svp", "SV%", 56, "Goalie")
    add("so", "SO", 38, "Goalie")
    add("gsv", "Saves", 52, "Goalie")
    # -- contract -----------------------------------------------------------------
    add("cap_hit", "Cap Hit", 92, "Contract")
    add("term", "Term", 52, "Contract")
    add("clause", "Clause", 64, "Contract")
    add("two_way", "2-Way", 52, "Contract")
    # -- form -----------------------------------------------------------------------
    add("pt_streak", "Streak", 64, "Form")
    add("morale", "Morale", 60, "Form")
    add("form", "Form", 64, "Form")
    # -- generated attribute columns -------------------------------------------------
    seen = set()
    for a in _skater_attrs() + [g for g in _goalie_attrs()
                                if g not in _skater_attrs()]:
        if a in seen:
            continue
        seen.add(a)
        add(f"attr:{a}", _attr_label(a), 64, "Attributes")
    # -- generated composite columns ----------------------------------------------------
    for c in _composite_keys():
        add(f"comp:{c}", _composite_label(c), 70, "Composites")
    return defs


COLUMN_DEFS = build_column_defs()


# ---------------------------------------------------------------------------
# Value readers: text for display, numeric key for sorting
# ---------------------------------------------------------------------------

def _stats(player):
    return getattr(player, "stats", None)


def _is_goalie(player):
    try:
        return player.primary_position.value == "G"
    except Exception:
        return False


def _contract(player):
    return getattr(player, "contract", None)


def column_text(key, player, ctx):
    """Display string for a column."""
    if key.startswith("attr:"):
        return _fmt_val(ctx.attr(player, key[5:]))
    if key.startswith("comp:"):
        return _fmt_val(ctx.composite(player, key[5:]))

    if key == "name":
        return getattr(player, "full_name", "?")
    if key == "pos":
        try:
            return player.primary_position.value
        except Exception:
            return "?"
    if key == "age":
        return str(getattr(player, "age", "--"))
    if key == "ovr":
        try:
            from game_classes import to_100_scale
            return str(int(to_100_scale(player.overall_rating())))
        except Exception:
            try:
                return str(int(player.overall_rating()))
            except Exception:
                return "--"
    if key == "team":
        return getattr(player, "team_name", "") or ""
    if key == "nat":
        return getattr(player, "nationality", "?") or "?"
    if key == "ht":
        return str(getattr(player, "height", "--"))
    if key == "wt":
        w = getattr(player, "weight", None)
        return str(w) if w else "--"

    st = _stats(player)
    if key == "gp":
        return str(getattr(st, "games_played", 0) if st else 0)
    if key == "g":
        return str(getattr(st, "goals", 0) if st else 0)
    if key == "a":
        return str(getattr(st, "assists", 0) if st else 0)
    if key == "p":
        g = getattr(st, "goals", 0) if st else 0
        a = getattr(st, "assists", 0) if st else 0
        return str(g + a)
    if key == "ppg":
        gp = getattr(st, "games_played", 0) if st else 0
        if not gp:
            return "--"
        g = getattr(st, "goals", 0) if st else 0
        a = getattr(st, "assists", 0) if st else 0
        return f"{(g + a) / gp:.2f}"
    if key == "pm":
        v = getattr(player, "plus_minus", None)
        if v is None and st:
            v = getattr(st, "plus_minus", 0)
        v = v or 0
        return f"+{v}" if v > 0 else str(v)
    if key == "shots":
        return str(getattr(st, "shots", 0) if st else 0)
    if key == "hits":
        return str(getattr(st, "hits", 0) if st else 0)
    if key == "blocks":
        return str(getattr(st, "blocked_shots", 0) if st else 0)
    if key == "takeaways":
        return str(getattr(st, "takeaways", 0) if st else 0)
    if key == "pim":
        return str(getattr(st, "penalties_in_minutes", 0) if st else 0)

    if key == "w":
        return str(getattr(st, "wins", 0) if st else 0) if _is_goalie(player) else "--"
    if key == "l":
        return str(getattr(st, "losses", 0) if st else 0) if _is_goalie(player) else "--"
    if key == "gaa":
        if not _is_goalie(player):
            return "--"
        v = getattr(st, "goals_against_avg", None) if st else None
        return f"{v:.2f}" if v else "--"
    if key == "svp":
        if not _is_goalie(player):
            return "--"
        v = getattr(st, "save_percentage", None) if st else None
        return f"{v:.3f}" if v else "--"
    if key == "so":
        return str(getattr(st, "shutouts", 0) if st else 0) if _is_goalie(player) else "--"
    if key == "gsv":
        return str(getattr(st, "saves", 0) if st else 0) if _is_goalie(player) else "--"

    c = _contract(player)
    if key == "cap_hit":
        v = getattr(c, "salary", None) if c else getattr(player, "salary", None)
        if not v:
            return "--"
        return f"${v / 1_000_000:.3f}M" if v >= 1_000_000 else f"${v:,}"
    if key == "term":
        v = getattr(c, "years_remaining", None) if c else None
        return f"{v}y" if v else "--"
    if key == "clause":
        if not c:
            return "--"
        if getattr(c, "no_movement_clause", False):
            return "NMC"
        if getattr(c, "no_trade_clause", False):
            return "NTC"
        if getattr(c, "modified_ntc_teams", None):
            return "M-NTC"
        return "--"
    if key == "two_way":
        return "Yes" if (c and getattr(c, "two_way", False)) else "--"

    if key == "pt_streak":
        s = int(getattr(player, "current_point_streak", 0) or 0)
        gs = int(getattr(player, "current_goal_streak", 0) or 0)
        if s >= 3:
            return f"{s}G Pt"
        if gs >= 2:
            return f"{gs}G Gl"
        return "--"
    if key == "morale":
        m = getattr(player, "morale", None)
        if m is None:
            return "--"
        try:
            m = int(m)
            return str(m * 10 if m <= 10 else m)
        except (TypeError, ValueError):
            return "--"
    if key == "form":
        g = _form_avg(player)
        return f"{g:.0f}" if g is not None else "--"
    return "--"


def _form_avg(player):
    """Average of the recent-game grade ledger (last 10), or None."""
    try:
        grades = getattr(player, "recent_game_grades", None) or []
        recent = [float(x) for x in grades[-10:]]
        if not recent:
            return None
        return sum(recent) / len(recent)
    except (TypeError, ValueError):
        return None


def column_sort(key, player, ctx):
    """Numeric sort key (None sorts last). Name sorts alphabetically."""
    if key == "name":
        return getattr(player, "full_name", "") or ""
    if key == "pos":
        return getattr(player, "primary_position", "") and player.primary_position.value or ""
    if key == "team":
        return getattr(player, "team_name", "") or ""
    if key == "nat":
        return getattr(player, "nationality", "") or ""
    if key.startswith("attr:"):
        return _mid(ctx.attr(player, key[5:]))
    if key.startswith("comp:"):
        return _mid(ctx.composite(player, key[5:]))
    if key == "ovr":
        try:
            from game_classes import to_100_scale
            return float(to_100_scale(player.overall_rating()))
        except Exception:
            try:
                return float(player.overall_rating())
            except Exception:
                return None
    if key == "age":
        try:
            return float(player.age)
        except (TypeError, ValueError):
            return None

    st = _stats(player)
    _num = {
        "gp": getattr(st, "games_played", 0) if st else 0,
        "g": getattr(st, "goals", 0) if st else 0,
        "a": getattr(st, "assists", 0) if st else 0,
        "shots": getattr(st, "shots", 0) if st else 0,
        "hits": getattr(st, "hits", 0) if st else 0,
        "blocks": getattr(st, "blocked_shots", 0) if st else 0,
        "takeaways": getattr(st, "takeaways", 0) if st else 0,
        "pim": getattr(st, "penalties_in_minutes", 0) if st else 0,
        "w": getattr(st, "wins", 0) if st else 0,
        "l": getattr(st, "losses", 0) if st else 0,
        "so": getattr(st, "shutouts", 0) if st else 0,
        "gsv": getattr(st, "saves", 0) if st else 0,
    }
    if key in _num:
        try:
            return float(_num[key])
        except (TypeError, ValueError):
            return None
    if key == "p":
        return float(_num["g"] + _num["a"])
    if key == "ppg":
        gp = _num["gp"]
        return float((_num["g"] + _num["a"]) / gp) if gp else None
    if key == "pm":
        v = getattr(player, "plus_minus", None)
        if v is None and st:
            v = getattr(st, "plus_minus", 0)
        try:
            return float(v or 0)
        except (TypeError, ValueError):
            return None
    if key == "gaa":
        v = getattr(st, "goals_against_avg", None) if st else None
        return float(v) if v else None
    if key == "svp":
        v = getattr(st, "save_percentage", None) if st else None
        return float(v) if v else None
    if key == "cap_hit":
        c = _contract(player)
        v = getattr(c, "salary", None) if c else getattr(player, "salary", None)
        try:
            return float(v) if v else None
        except (TypeError, ValueError):
            return None
    if key == "term":
        c = _contract(player)
        v = getattr(c, "years_remaining", None) if c else None
        try:
            return float(v) if v else None
        except (TypeError, ValueError):
            return None
    if key == "pt_streak":
        try:
            return float(getattr(player, "current_point_streak", 0) or 0)
        except (TypeError, ValueError):
            return None
    if key == "morale":
        m = getattr(player, "morale", None)
        try:
            m = int(m)
            return float(m * 10 if m <= 10 else m)
        except (TypeError, ValueError):
            return None
    if key == "form":
        return _form_avg(player)
    # text-ish columns: sort by display text
    return column_text(key, player, ctx)


# ---------------------------------------------------------------------------
# Built-in views (FM/Eastside-style presets)
# ---------------------------------------------------------------------------

VIEWS = {
    "Overview": ["name", "pos", "age", "ovr", "team", "nat"],
    "Offense": ["name", "pos", "gp", "g", "a", "p", "ppg", "pm", "shots"],
    "Defense": ["name", "pos", "gp", "pm", "hits", "blocks", "takeaways",
                "pim", "comp:defensive_play"],
    "Goaltending": ["name", "gp", "w", "l", "gaa", "svp", "so",
                    "comp:goalie_save"],
    "Physical": ["name", "pos", "age", "ht", "wt", "attr:strength",
                 "attr:checking", "comp:physicality"],
    "Composites": ["name", "pos", "comp:chance_creation", "comp:finishing",
                   "comp:defensive_play", "comp:physicality",
                   "comp:faceoff", "comp:puck_retrieval", "comp:skating",
                   "comp:discipline"],
    "Season + Form": ["name", "team", "gp", "g", "a", "p", "form",
                      "pt_streak", "morale"],
    "Contract": ["name", "age", "cap_hit", "term", "clause", "two_way"],
}
# Drop any preset column that failed to register (e.g. a composite key
# missing on an old build) rather than crashing the table builder.
VIEWS = {name: [c for c in cols if c in COLUMN_DEFS]
         for name, cols in VIEWS.items()}
