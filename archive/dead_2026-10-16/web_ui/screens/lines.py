"""Lines screen: line combinations (read-only v1).

Shows app.user_team.lineup (Dict[str, Player]) grouped into forward lines
1-4, defensive pairs 1-3, and goalies. A future `set_lines` command will
enable web editing; until then this is a read-only display.
"""
import re
from flask import Blueprint, jsonify, render_template, request
from web_ui.bridge import _safe, to_web_player, enqueue_command, _resolve_gm

bp = Blueprint("lines", __name__)


def _live():
    import web_ui.bridge as _b
    return _b._web_app_ref


_SLOT_RE = re.compile(r"^([A-Z]+?)(\d*)$")


def _unit_label(slot_prefix, idx):
    n = idx if idx else 1
    if slot_prefix in ("LW", "C", "RW"):
        return ("forwards", f"Line {n}", n)
    if slot_prefix in ("LD", "RD"):
        return ("defense", f"Pairing {n}", n)
    if slot_prefix in ("G", "GK"):
        return ("goalies", "Goalies", 0)
    return ("other", "Other", 99)


def _group_lineup(lineup):
    """Group lineup dict into ordered units of slots."""
    buckets = {}  # (group, label) -> [(order, slot, player)]
    for slot, player in (_safe(lambda: list(lineup.items()), []) or []):
        try:
            slot = str(slot or "")
            m = _SLOT_RE.match(slot)
            prefix = m.group(1) if m else ""
            idx = int(m.group(2)) if m and m.group(2) else 1
            group, label, order = _unit_label(prefix, idx)
            web_p = to_web_player(player) if player is not None else None
            buckets.setdefault((group, label, order),
                               []).append((idx, slot, web_p))
        except Exception:
            continue
    units = []
    group_rank = {"forwards": 0, "defense": 1, "goalies": 2, "other": 3}
    for (group, label, order), slots in sorted(
            buckets.items(), key=lambda kv: (group_rank.get(kv[0][0], 9), kv[0][2])):
        slots.sort(key=lambda s: (s[0], s[1]))
        units.append({
            "group": group,
            "label": label,
            "slots": [{"slot": s[1], "player": s[2]} for s in slots],
        })
    return units


def get_lines(app):
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if team is None:
        return {"units": [], "roster": []}
    lineup = _safe(lambda: team.lineup, {}) or {}
    if not lineup or not lineup.get("Forwards"):
        # Fresh game: the sim hasn't built lines yet. Use the game's own
        # best-lines algorithm so the screen isn't empty. best_lines
        # returns flat keys like F1_LW/D1_L; normalize to LW1/LD1 form.
        try:
            from quick_sim import best_lines
            raw = best_lines(team) or {}
            _norm = {"F": "", "D": "D"}
            norm = {}
            for k, v in raw.items():
                ks = str(k)
                if ks.startswith("F") and "_" in ks:
                    # F1_LW -> LW1, F2_C -> C2
                    parts = ks.split("_", 1)
                    norm[f"{parts[1]}{parts[0][1:]}"] = v
                elif ks.startswith("D") and "_" in ks:
                    # D1_L -> LD1, D2_R -> RD2
                    parts = ks.split("_", 1)
                    side = "L" if parts[1] == "L" else "R"
                    norm[f"{side}D{parts[0][1:]}"] = v
                elif ks in ("G1", "G2"):
                    norm[ks] = v
            lineup = norm
        except Exception:
            lineup = {}
    roster = _safe(lambda: list(team.roster), []) or []
    return {
        "units": _group_lineup(lineup),
        "roster": [to_web_player(p) for p in roster],
    }


@bp.route("/lines")
def lines_page():
    return render_template("lines.html")


@bp.route("/api/lines")
def api_lines():
    live = _live()
    if live is None:
        return jsonify({"units": [], "roster": []})
    return jsonify(get_lines(live))


# ----------------------------------------------------------------------
# Line editor (real write path)
#
# The game's lineup lives on team.lineup as nested
#   {"Forwards": [[LW, C, RW] x4], "Defense": [[L, R] x3],
#    "Goalies": [G1, G2]}
# plus flat keys (F1_LW..F4_RW, D1_L..D3_R, G1, G2) that the sim reads,
# built by quick_sim.flatten_lineup -- the same function the desktop
# editor and the MP _mp_set_lines path (main.py) use to apply lines.
# The web editor works in slot labels (LW1..RW4, LD1..RD3, G1, G2) and
# converts to that nested shape before applying.
# ----------------------------------------------------------------------

import re as _re

LINE_SLOTS = ["LW1", "C1", "RW1",
              "LW2", "C2", "RW2",
              "LW3", "C3", "RW3",
              "LW4", "C4", "RW4",
              "LD1", "RD1", "LD2", "RD2", "LD3", "RD3",
              "G1", "G2"]
GOALIE_SLOTS = {"G1", "G2"}
_FLAT_KEY_RE = _re.compile(r"^[FD]\d+_[LRCW]+$|^G\d+$")


def _slot_parts(slot):
    """'LW1' -> ('LW', 1); 'G2' -> ('G', 2)."""
    m = _re.match(r"^([A-Z]+)(\d+)$", str(slot or ""))
    if not m:
        return None, None
    return m.group(1), int(m.group(2))


def _is_goalie_obj(p):
    pos = getattr(p, "primary_position", "")
    return getattr(pos, "value", pos) == "G"


def _slot_flat_key(slot):
    """Editable slot label -> flat lineup key the sim reads."""
    pos, num = _slot_parts(slot)
    if pos in ("LW", "C", "RW"):
        return f"F{num}_{pos}"
    if pos in ("LD", "RD"):
        return f"D{num}_{'L' if pos == 'LD' else 'R'}"
    if pos == "G":
        return f"G{num}"
    return None


def _current_slot_player(lineup, slot):
    """Player object currently in a slot (flat keys, then nested)."""
    key = _slot_flat_key(slot)
    if key and isinstance(lineup, dict):
        p = _safe(lambda: lineup.get(key))
        if p is not None:
            return p
        # Fall back to the nested shape the desktop editor writes.
        pos, num = _slot_parts(slot)
        try:
            if pos in ("LW", "C", "RW"):
                line = (lineup.get("Forwards") or [])[num - 1]
                return line[{"LW": 0, "C": 1, "RW": 2}[pos]] if line else None
            if pos in ("LD", "RD"):
                pair = (lineup.get("Defense") or [])[num - 1]
                return pair[0 if pos == "LD" else 1] if pair else None
            if pos == "G":
                gl = lineup.get("Goalies") or []
                return gl[num - 1] if len(gl) >= num else None
        except Exception:
            return None
    return None


def _roster_lookup(team, pid):
    """Find a player by id on the club (roster, then AHL/prospects)."""
    pid = str(pid or "")
    for attr in ("roster", "ahl_roster", "prospects"):
        for p in _safe(lambda: list(getattr(team, attr, None) or []), []) or []:
            try:
                if str(getattr(p, "id", "")) == pid:
                    return p
            except Exception:
                continue
    return None


def get_editable_lines(app):
    """Current slots + per-slot eligible roster pools for the editor."""
    gm = _safe(lambda: app.game_manager)
    team = _safe(lambda: gm.user_team) or _safe(lambda: app.user_team)
    if team is None:
        return {"slots": [], "pools": {}, "slot_kinds": {}}
    lineup = _safe(lambda: team.lineup, {}) or {}
    roster = _safe(lambda: list(team.roster), []) or []
    skaters, goalies = [], []
    for p in roster:
        try:
            w = to_web_player(p)
            w["is_goalie"] = _is_goalie_obj(p)
            (goalies if w["is_goalie"] else skaters).append(w)
        except Exception:
            continue
    skaters.sort(key=lambda w: -w.get("overall", 0))
    goalies.sort(key=lambda w: -w.get("overall", 0))
    slots, pools, kinds = [], {}, {}
    for slot in LINE_SLOTS:
        is_g = slot in GOALIE_SLOTS
        kinds[slot] = "goalie" if is_g else "skater"
        pools[slot] = goalies if is_g else skaters
        cur = _safe(lambda: _current_slot_player(lineup, slot))
        wp = None
        if cur is not None:
            try:
                wp = {"id": str(getattr(cur, "id", "")),
                      "name": getattr(cur, "full_name", "?")}
            except Exception:
                wp = None
        pos, num = _slot_parts(slot)
        slots.append({"slot": slot, "pos": pos, "line": num,
                      "player": wp})
    out = {"slots": slots, "pools": pools, "slot_kinds": kinds}
    # Special-teams state for the second editor tab (PP1/PP2/PK1/PK2).
    st_slots, st_pools, st_kinds = [], {}, {}
    for slot in ST_SLOTS:
        st_kinds[slot] = "skater"
        st_pools[slot] = skaters
        cur = _safe(lambda: _st_current_player(lineup, slot))
        wp = None
        if cur is not None:
            try:
                wp = {"id": str(getattr(cur, "id", "")),
                      "name": getattr(cur, "full_name", "?")}
            except Exception:
                wp = None
        unit = ST_SLOT_UNIT.get(slot, "")
        tail = slot.split("_", 1)[1] if "_" in slot else ""
        st_slots.append({"slot": slot, "unit": unit, "pos": tail,
                         "player": wp})
    out["st_slots"] = st_slots
    out["st_pools"] = st_pools
    out["st_slot_kinds"] = st_kinds
    return out


def validate_lines_payload(team, slot_lines):
    """Read-only validation of {slot: player_id}.

    Returns (ok, error, resolved) where resolved = {slot: player|None}.
    Rules mirror the MP _mp_set_lines path: known slots only, every id
    on the club, no player dressed twice, goalies only in net, skaters
    only on skater slots.
    """
    if team is None:
        return False, "No live game.", None
    if not isinstance(slot_lines, dict):
        return False, "Missing lines payload.", None
    resolved, seen = {}, {}
    for slot, pid in slot_lines.items():
        if slot not in LINE_SLOTS:
            return False, f"Unknown slot: {slot}.", None
        pid = "" if pid in (None, "None") else str(pid).strip()
        if not pid:
            resolved[slot] = None
            continue
        p = _roster_lookup(team, pid)
        if p is None:
            return False, "A selected player isn't on your club.", None
        name = _safe(lambda: getattr(p, "full_name", "A player"), "A player")
        if pid in seen:
            return False, (f"{name} is dressed twice -- "
                           "each player skates one slot."), None
        is_g = _is_goalie_obj(p)
        if slot in GOALIE_SLOTS and not is_g:
            return False, f"{name} isn't a goalie.", None
        if slot not in GOALIE_SLOTS and is_g:
            return False, (f"{name} is a goalie -- "
                           "skaters only on skater slots."), None
        seen[pid] = slot
        resolved[slot] = p
    for slot in LINE_SLOTS:
        resolved.setdefault(slot, None)
    return True, "", resolved


def apply_lines_payload(team, resolved):
    """REAL line application: nested shape + quick_sim.flatten_lineup.

    The same machinery the desktop editor and _mp_set_lines use: nested
    Forwards/Defense/Goalies of player objects, then flatten_lineup adds
    the flat F1_LW..G2 keys the sim reads. Special-teams keys ride along
    untouched. Returns (ok, message).
    """
    if team is None:
        return False, "No live game."
    try:
        from quick_sim import flatten_lineup
    except Exception:
        return False, "Lineup machinery unavailable."
    nested = {
        "Forwards": [[resolved.get(f"LW{i}"), resolved.get(f"C{i}"),
                      resolved.get(f"RW{i}")] for i in (1, 2, 3, 4)],
        "Defense": [[resolved.get(f"LD{i}"), resolved.get(f"RD{i}")]
                    for i in (1, 2, 3)],
        "Goalies": [resolved.get("G1"), resolved.get("G2")],
    }
    # Preserve anything else on the old lineup (special teams), the way
    # _mp_set_lines carries PP/PK along when supplied.
    try:
        old = dict(getattr(team, "lineup", None) or {})
        for k, v in old.items():
            if k not in nested and not _FLAT_KEY_RE.match(str(k)):
                nested[k] = v
    except Exception:
        pass
    try:
        team.lineup = flatten_lineup(nested)
    except Exception as e:
        return False, f"Could not save lines: {e}."
    return True, "Lines saved."


# ----------------------------------------------------------------------
# Special-teams editor (PP1/PP2/PK1/PK2)
#
# The sim reads team.lineup nested keys
#   {"PP1": {"Forwards": [LW, C, RW], "Defense": [LD, RD]},
#    "PK1": {"Forwards": [LW, RW],    "Defense": [LD, RD]}, ...}
# exactly like the desktop CleanEditLinesView and
# simulation._ensure_default_lineup write them: PP = 3F+2D (5 skaters),
# PK = 2F+2D (4 skaters). The web editor uses per-position slot labels
# (PP1_LW, PP1_C, ..., PK1_RW, ...) and converts to that nested shape.
# ----------------------------------------------------------------------

ST_UNITS = {
    "PP1": ["PP1_LW", "PP1_C", "PP1_RW", "PP1_LD", "PP1_RD"],
    "PP2": ["PP2_LW", "PP2_C", "PP2_RW", "PP2_LD", "PP2_RD"],
    "PK1": ["PK1_LW", "PK1_RW", "PK1_LD", "PK1_RD"],
    "PK2": ["PK2_LW", "PK2_RW", "PK2_LD", "PK2_RD"],
}
ST_SLOTS = [s for slots in ST_UNITS.values() for s in slots]
ST_SLOT_UNIT = {s: u for u, slots in ST_UNITS.items() for s in slots}
_ST_POS_ORDER = {"LW": 0, "C": 1, "RW": 2, "LD": 0, "RD": 1}


def _st_slot_pos(slot):
    """'PP1_LW' -> 'LW'."""
    parts = str(slot or "").split("_", 1)
    return parts[1] if len(parts) == 2 else ""


def _st_current_player(lineup, slot):
    """Player object currently on a special-teams slot."""
    try:
        unit = ST_SLOT_UNIT.get(slot)
        if not unit or not isinstance(lineup, dict):
            return None
        udata = lineup.get(unit) or {}
        if not isinstance(udata, dict):
            return None
        fwd = udata.get("Forwards") or []
        dfn = udata.get("Defense") or []
        pos = _st_slot_pos(slot)
        if pos == "LW":
            return fwd[0] if len(fwd) > 0 else None
        if pos == "C":
            return fwd[1] if len(fwd) > 1 else None
        if pos == "RW":
            # PP forwards read [LW, C, RW]; PK forwards read [LW, RW].
            idx = 2 if unit.startswith("PP") else 1
            return fwd[idx] if len(fwd) > idx else None
        if pos == "LD":
            return dfn[0] if len(dfn) > 0 else None
        if pos == "RD":
            return dfn[1] if len(dfn) > 1 else None
    except Exception:
        return None
    return None


def validate_st_payload(team, st_lines):
    """Read-only validation of {st_slot: player_id}.

    Returns (ok, error, resolved) where resolved = {slot: player|None}.
    Rules: known slots only, every id on the club, skaters only (no
    goalies), no player on two special-teams jobs anywhere, and each
    unit is either fully filled (PP: 5, PK: 4) or fully empty -- a
    cleared unit falls back to the sim's default special-teams units.
    """
    if team is None:
        return False, "No live game.", None
    if not isinstance(st_lines, dict):
        return False, "Missing special-teams payload.", None
    resolved, seen = {}, {}
    for slot, pid in st_lines.items():
        if slot not in ST_SLOTS:
            return False, f"Unknown slot: {slot}.", None
        pid = "" if pid in (None, "None") else str(pid).strip()
        if not pid:
            resolved[slot] = None
            continue
        p = _roster_lookup(team, pid)
        if p is None:
            return False, "A selected player isn't on your club.", None
        name = _safe(lambda: getattr(p, "full_name", "A player"), "A player")
        if pid in seen:
            return False, (f"{name} is already on {seen[pid]} -- "
                           "one player, one special-teams job."), None
        if _is_goalie_obj(p):
            return False, (f"{name} is a goalie -- "
                           "skaters only on special teams."), None
        seen[pid] = ST_SLOT_UNIT.get(slot, slot)
        resolved[slot] = p
    for slot in ST_SLOTS:
        resolved.setdefault(slot, None)
    for unit, slots in ST_UNITS.items():
        filled = sum(1 for s in slots if resolved.get(s) is not None)
        if 0 < filled < len(slots):
            return False, (f"{unit} is incomplete ({filled}/{len(slots)} "
                           f"filled) -- fill every spot or clear the unit."), None
    return True, "", resolved


def apply_st_payload(team, resolved):
    """REAL special-teams application: nested PP/PK units on team.lineup.

    Merges the four units into the existing lineup dict (even-strength
    keys ride along untouched), then quick_sim.flatten_lineup rebuilds
    the flat ES keys the sim reads. A cleared unit is removed so the
    sim falls back to its default special-teams deployment. Returns
    (ok, message).
    """
    if team is None:
        return False, "No live game."
    try:
        from quick_sim import flatten_lineup
    except Exception:
        return False, "Lineup machinery unavailable."
    try:
        nested = dict(getattr(team, "lineup", None) or {})
    except Exception:
        nested = {}
    for unit, slots in ST_UNITS.items():
        fwd = sorted([s for s in slots if _st_slot_pos(s) in ("LW", "C", "RW")],
                     key=lambda s: _ST_POS_ORDER[_st_slot_pos(s)])
        dfn = sorted([s for s in slots if _st_slot_pos(s) in ("LD", "RD")],
                     key=lambda s: _ST_POS_ORDER[_st_slot_pos(s)])
        fw = [resolved.get(s) for s in fwd]
        df = [resolved.get(s) for s in dfn]
        if all(p is None for p in fw + df):
            # Cleared: drop the key so the sim falls back to default units
            # (deployment_policy._unit_players treats missing slots as
            # absent; _ensure_default_lineup rebuilds them for fresh games).
            nested.pop(unit, None)
        else:
            nested[unit] = {"Forwards": fw, "Defense": df}
    try:
        team.lineup = flatten_lineup(nested)
    except Exception as e:
        return False, f"Could not save special teams: {e}."
    return True, "Special teams saved."


@bp.route("/api/lines/set_st", methods=["POST"])
def api_set_st_lines():
    """Validate and queue a special-teams change. Body: {"st": {slot: id}}."""
    data = request.get_json(force=True, silent=True) or {}
    st_lines = data.get("st") if isinstance(data.get("st"), dict) else data
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "No live game."}), 503
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    ok, err, _resolved = validate_st_payload(team, st_lines)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    clean = {s: ("" if st_lines.get(s) in (None, "None") else str(st_lines.get(s) or ""))
             for s in ST_SLOTS if s in st_lines}
    enqueued = enqueue_command("set_st_lines_real", st=clean)
    return jsonify({"ok": enqueued})


@bp.route("/api/lines/editable")
def api_lines_editable():
    live = _live()
    if live is None:
        return jsonify({"slots": [], "pools": {}, "slot_kinds": {}})
    return jsonify(get_editable_lines(live))


@bp.route("/api/lines/set", methods=["POST"])
def api_set_lines():
    """Validate and queue a line change. Body: {slot: player_id} or
    {"lines": {slot: player_id}}. Empty string clears a slot."""
    data = request.get_json(force=True, silent=True) or {}
    slot_lines = data.get("lines") if isinstance(data.get("lines"), dict) else data
    live = _live()
    if live is None:
        return jsonify({"ok": False, "error": "No live game."}), 503
    gm = _resolve_gm(live)
    team = _safe(lambda: gm.user_team) or _safe(lambda: live.user_team)
    ok, err, _resolved = validate_lines_payload(team, slot_lines)
    if not ok:
        return jsonify({"ok": False, "error": err}), 400
    clean = {s: ("" if slot_lines.get(s) in (None, "None") else str(slot_lines.get(s) or ""))
             for s in LINE_SLOTS if s in slot_lines}
    enqueued = enqueue_command("set_lines_real", lines=clean)
    return jsonify({"ok": enqueued})
