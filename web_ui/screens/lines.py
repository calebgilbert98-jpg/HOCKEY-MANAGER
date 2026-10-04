"""Lines screen: line combinations (read-only v1).

Shows app.user_team.lineup (Dict[str, Player]) grouped into forward lines
1-4, defensive pairs 1-3, and goalies. A future `set_lines` command will
enable web editing; until then this is a read-only display.
"""
import re
from flask import Blueprint, jsonify, render_template
from web_ui.bridge import _safe, to_web_player

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
    team = _safe(lambda: app.user_team)
    if team is None:
        return {"units": [], "roster": []}
    lineup = _safe(lambda: team.lineup, {}) or {}
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
