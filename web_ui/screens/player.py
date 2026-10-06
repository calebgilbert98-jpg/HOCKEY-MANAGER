"""Player profile screen: 1:1 port of the v0.18.4 Tkinter PlayerProfile
(modern_profile.py, 1932 lines, FM24-style, 7 tabs).

Header: portrait, name, pills (position, archetype, age, talent tier,
condition, injury, hot/cold form), team + contract strip, rights + league
strip. Tabs: Overview | Health | Analytics | Personality | Scout Report |
Dynamics | History.

All data is computed server-side in /api/player/<pid> and rendered by
player.js. Every read is defensive: a missing module or attribute degrades
to an "unavailable" note, never a 500.
"""
from flask import Blueprint, jsonify, render_template

from web_ui.bridge import player_portrait

bp = Blueprint("player", __name__)


def _live():
    from web_ui.bridge import _web_app_ref
    return _web_app_ref


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def _fmt_money(v):
    try:
        v = int(v or 0)
    except Exception:
        return "--"
    return f"${v:,}"


def _to100(v):
    return _safe(lambda: __import__("game_classes").to_100_scale(v), 50) or 50


# -- attribute field lists (verbatim from modern_profile.py) ----------------
_SKATER_TECHNICAL = [
    ("Shooting", "shooting"), ("Shot Accuracy", "shooting_accuracy"),
    ("Shot Power", "shooting_power"), ("Wrist Shot", "wristshot"),
    ("Slap Shot", "slapshot"), ("One Timer", "one_timer"),
    ("Backhand", "backhand"), ("Deflections", "deflections"),
    ("Passing", "passing"), ("Pass Accuracy", "passing_accuracy"),
    ("Passing Creativity", "passing_creativity"),
    ("Puck Handling", "puck_handling"), ("Stickhandling", "stickhandling"),
    ("Deking", "deking"), ("Off. Positioning", "offensive_positioning"),
    ("Faceoffs", "faceoffs"), ("First Pass", "first_pass"),
    ("Breakout Passes", "breakout_passes"),
    ("Puck Protection", "puck_protection"), ("Loose Puck", "loose_puck"),
    ("Pokecheck", "pokecheck"),
]
_SKATER_MENTAL = [
    ("Vision", "vision"), ("Hockey IQ", "hockey_iq"),
    ("Anticipation", "anticipation"), ("Decisions", "decision_making"),
    ("Off. Awareness", "off_the_puck"),
    ("Def. Awareness", "defensive_awareness"),
    ("Creativity", "creativity"), ("Determination", "determination"),
    ("Composure", "composure"), ("Confidence", "confidence"),
    ("Focus", "focus"), ("Pressure Player", "pressure_player"),
    ("Teamwork", "teamwork"), ("Discipline", "discipline"),
    ("Flair", "flair"), ("Work Ethic", "work_ethic"),
    ("Coachability", "coachability"), ("Adaptability", "adaptability"),
]
_SKATER_PHYSICAL = [
    ("Skating", "skating"), ("Speed", "speed"), ("Agility", "agility"),
    ("Balance", "balance"), ("Strength", "strength"),
    ("Stamina", "stamina"), ("Endurance", "endurance"),
    ("Durability", "durability"), ("Injury Proneness", "injury_proneness"),
    ("Aggression", "aggressiveness"), ("Checking", "checking"),
    ("Bodycheck", "bodycheck"), ("Shot Blocking", "shot_blocking"),
    ("Forechecking", "forechecking"), ("Screening", "screen_shots"),
    ("Work Rate", "work_rate"), ("Shoot Tendency", "shoot_pass_tendency"),
    ("Hitting Tendency", "hitting_tendency"),
]
_GOALIE_TECHNICAL = [
    ("Goaltending", "goaltending"), ("Positioning", "positioning"),
    ("Reflexes", "reflexes"), ("Glove Hand", "glove_hand"),
    ("Stick Side", "stick_side"), ("Rebound Ctrl", "rebound_control"),
    ("Breakaway Skill", "breakaway_skill"),
    ("Puck Handling", "puck_handling"), ("Passing", "passing"),
]
_GOALIE_MENTAL = [
    ("Anticipation", "anticipation"), ("Decisions", "decision_making"),
    ("Vision", "vision"), ("Focus", "focus"),
    ("Determination", "determination"), ("Composure", "composure"),
    ("Confidence", "confidence"), ("Teamwork", "teamwork"),
    ("Discipline", "discipline"), ("Work Ethic", "work_ethic"),
    ("Adaptability", "adaptability"),
]
_GOALIE_PHYSICAL = [
    ("Skating", "skating"), ("Speed", "speed"), ("Agility", "agility"),
    ("Balance", "balance"), ("Strength", "strength"),
    ("Stamina", "stamina"), ("Endurance", "endurance"),
    ("Durability", "durability"), ("Injury Proneness", "injury_proneness"),
    ("Aggression", "aggressiveness"),
]

_SKATER_COMPOSITES = [
    ("chance_creation", "Chance Creation"), ("finishing", "Finishing"),
    ("skating", "Skating"), ("defensive_play", "Defensive Play"),
    ("physicality", "Physicality"), ("faceoff", "Faceoffs"),
    ("puck_retrieval", "Puck Retrieval"), ("discipline", "Discipline"),
]
_GOALIE_COMPOSITES = [
    ("goalie_save", "Goaltending"), ("skating", "Skating"),
    ("puck_retrieval", "Puck Retrieval"), ("discipline", "Discipline"),
]


def _is_goalie(p):
    return "GOALIE" in str(_safe(lambda: getattr(p, "primary_position", ""),
                                 "")).upper()


def _find_player(pid):
    """Search all league teams (roster, ahl_roster, prospects); returns
    (player, team, list_name) or (None, None, None)."""
    live = _live()
    gm = _safe(lambda: getattr(live, "game_manager", None))
    league = _safe(lambda: getattr(gm, "league", None)) or _safe(lambda: getattr(live, "league", None))
    teams = _safe(lambda: list(getattr(league, "teams", []) or []), []) or []
    user_team = _safe(lambda: getattr(gm, "user_team", None)) or _safe(lambda: getattr(live, "user_team", None))
    if user_team is not None and all(t is not user_team for t in teams):
        teams = [user_team] + teams
    for team in teams:
        for lname in ("roster", "ahl_roster", "prospects"):
            lst = _safe(lambda: list(getattr(team, lname, []) or []), []) or []
            for p in lst:
                if str(_safe(lambda: getattr(p, "id", ""), "")) == str(pid):
                    return p, team, lname
    return None, None, None


def _league_of(team, p):
    """Best-effort league label: NHL / AHL / Europe / Junior / Free Agent."""
    try:
        if team is not None:
            for attr, label in (("roster", "NHL"), ("ahl_roster", "AHL")):
                lst = getattr(team, attr, None) or []
                if any(q is p for q in lst):
                    return label
        tn = str(getattr(p, "team_name", "") or "")
        if tn.lower() == "europe":
            return "Europe"
        rt = str(getattr(p, "rights_type", "") or "").upper()
        if rt in ("CHL", "NCAA", "EUROPE"):
            return {"CHL": "CHL", "NCAA": "NCAA",
                    "EUROPE": "Europe"}.get(rt, rt)
        jl = str(getattr(p, "junior_league", "") or "").strip()
        if jl:
            return jl
        if not tn or tn.lower() == "free agent":
            return "Free Agent"
        return tn
    except Exception:
        return ""


def _contract_type_label(p):
    """ELC / 2-way / NMC / NTC / M-NTC / UFA / RFA label."""
    try:
        c = getattr(p, "contract", None)
        labels = []
        if c is not None and getattr(c, "entry_level", False):
            labels.append("ELC")
        if c is not None and getattr(c, "two_way", False):
            labels.append("2-way")
        if c is not None and getattr(c, "no_movement_clause", False):
            labels.append("NMC")
        elif c is not None and getattr(c, "no_trade_clause", False):
            labels.append("NTC")
        elif c is not None and int(getattr(c, "modified_ntc_teams", 0) or 0) > 0:
            labels.append("M-NTC")
        try:
            import rfa_system as _rs
            if _rs.is_ufa(p):
                labels.append("UFA")
            elif _rs.is_rfa(p):
                labels.append("RFA")
        except Exception:
            pass
        return " / ".join(labels)
    except Exception:
        return ""


def _history_season_label(season):
    try:
        y = int(season)
        return f"{y}-{str(y + 1)[-2:]}"
    except Exception:
        return str(season)


# ======================================================================
# section builders — each returns JSON-safe data or {"unavailable": ...}
# ======================================================================

def _build_header(p, team, user_team=None):
    import game_classes as _gc
    try:
        import condition_ui as _cu
    except Exception:
        _cu = None
    try:
        from attribute_composites import (talent_tier_color,
                                          talent_tier_for_player)
    except Exception:
        talent_tier_for_player = talent_tier_color = None

    pid = str(_safe(lambda: getattr(p, "id", ""), ""))
    try:
        name = f"{p.first_name} {p.last_name}"
    except Exception:
        name = str(_safe(lambda: getattr(p, "full_name", "Unknown Player"),
                         "Unknown Player"))
    pills = []
    pos = _safe(lambda: _gc.position_label(p), "?")
    if pos:
        pills.append({"text": pos, "kind": "pos"})
    arch = _safe(lambda: getattr(p, "archetype", None))
    if arch:
        pills.append({"text": str(arch), "kind": "arch"})
    pills.append({"text": f"Age {_safe(lambda: getattr(p, 'age', '?'), '?')}",
                  "kind": "age"})
    tier = None
    if talent_tier_for_player is not None:
        tier = _safe(lambda: talent_tier_for_player(p))
    if tier:
        color = _safe(lambda: talent_tier_color(tier), "#9aa3b2")
        pills.append({"text": tier, "kind": "tier", "fg": color})
    if _cu is not None:
        cond = _safe(lambda: _cu.get_condition(p), None)
        if cond is not None:
            pills.append({"text": f"{cond} {_cu.condition_label(cond)}",
                          "kind": "condition",
                          "fg": _cu.condition_color(cond)})
        inj = _safe(lambda: _cu.injury_status(p))
        if inj:
            pills.append({"text": inj, "kind": "injury", "fg": "#f85149"})
    form = _safe(lambda: float(getattr(p, "mesh_form", 0) or 0), 0.0)
    if abs(form) > 1.0:
        form = form / 100.0
    if form >= 0.5:
        pills.append({"text": "🔥 Hot hand", "kind": "form", "fg": "#ff9e4a"})
    elif form <= -0.5:
        pills.append({"text": "❄ Cold", "kind": "form", "fg": "#7aa2f7"})

    team_name = (_safe(lambda: getattr(team, "team_name", None))
                 or str(_safe(lambda: getattr(p, "team_name", ""),
                              "") or "Free Agent"))
    contract = _safe(lambda: getattr(p, "contract", None))
    salary = (_safe(lambda: getattr(p, "salary", None))
              or _safe(lambda: getattr(contract, "salary", None)))
    years = (_safe(lambda: getattr(p, "contract_years", None))
             or _safe(lambda: getattr(contract, "years_remaining", None)))
    strip = [team_name]
    if salary:
        strip.append(f"${int(salary):,} / yr")
    if years is not None:
        strip.append(f"{years} yr{'s' if years != 1 else ''} left")
    ct = _contract_type_label(p)
    if ct:
        strip.append(ct)

    rights_bits = []
    lg = _league_of(team, p)
    if lg:
        rights_bits.append(f"League: {lg}")
    rt_team = str(_safe(lambda: getattr(p, "rights_team", ""), "") or "").strip()
    if rt_team:
        rt_type = str(_safe(lambda: getattr(p, "rights_type", ""),
                            "") or "").strip()
        rt_exp = _safe(lambda: getattr(p, "rights_expiry_year", 0), 0) or 0
        r = f"Rights: {rt_team}"
        if rt_type:
            r += f" ({rt_type})"
        if rt_exp:
            r += f" thru {rt_exp}"
        rights_bits.append(r)

    pos_str = str(_safe(lambda: getattr(p, "primary_position", ""), "") or "")
    pos_u = pos_str.upper()
    pos_class = "G" if "GOALIE" in pos_u else (
        "D" if "DEFENSE" in pos_u else "F")
    jersey = _safe(lambda: int(getattr(p, "jersey_number", 0) or 0), 0)
    # Editable only for players on the user's own club (NHL + AHL share
    # the number pool) -- desktop assign_jersey_number only touches
    # user_team rosters too.
    jersey_editable = _safe(
        lambda: any(p is q
                    for attr in ("roster", "ahl_roster")
                    for q in (getattr(user_team, attr, None) or [])),
        False)
    return {
        "id": pid,
        "portrait": player_portrait(pid),
        "name": name,
        "team_name": team_name,
        "pos_class": pos_class,
        "initials": _safe(
            lambda: f"{p.first_name[0]}{p.last_name[0]}".upper(), "?"),
        "pills": pills,
        "strip": strip,
        "rights_strip": rights_bits,
        "jersey": jersey,
        "jersey_editable": jersey_editable,
    }


def _build_overview(p, team):
    import game_classes as _gc
    goalie = _is_goalie(p)
    out = {"goalie": goalie}
    # --- Season stats cards ---
    st = _safe(lambda: getattr(p, "stats", None))
    if goalie:
        items = [
            ("GP", _safe(lambda: getattr(st, "games_played", 0), 0)),
            ("W", _safe(lambda: getattr(st, "wins", 0), 0)),
            ("SV%", _safe(
                lambda: f"{getattr(st, 'save_percentage', 0):.3f}", ".000")),
            ("GAA", _safe(
                lambda: f"{getattr(st, 'goals_against_average', 0):.2f}",
                "0.00")),
        ]
    else:
        g = _safe(lambda: getattr(st, "goals", 0), 0)
        a = _safe(lambda: getattr(st, "assists", 0), 0)
        items = [
            ("GP", _safe(lambda: getattr(st, "games_played", 0), 0)),
            ("G", g), ("A", a), ("PTS", g + a),
        ]
    out["stats_cards"] = [{"label": k, "value": str(v)} for k, v in items]
    # --- Per-team splits ---
    splits = _safe(lambda: list(_gc.current_season_splits(p)), []) or []
    splits = [s for s in splits
              if isinstance(s, dict) and int(s.get("gp", 0) or 0) > 0]
    out["splits"] = splits
    out["show_splits"] = len({s.get("team") for s in splits
                              if s.get("team")}) > 1
    # --- Contract card ---
    rows = []
    team_name = (_safe(lambda: getattr(team, "team_name", None))
                 or str(_safe(lambda: getattr(p, "team_name", ""),
                              "") or "Free Agent"))
    rows.append(["Club", team_name])
    rows.append(["League", _league_of(team, p) or "--"])
    c = _safe(lambda: getattr(p, "contract", None))
    if c is not None:
        sal = _safe(lambda: getattr(c, "salary", 0), 0) or 0
        rows.append(["Salary", _fmt_money(sal) if sal else "--"])
        yrs = _safe(lambda: getattr(c, "years_remaining", None))
        rows.append(["Term",
                     f"{yrs} yr{'s' if yrs != 1 else ''} left"
                     if yrs is not None else "--"])
        ct = _contract_type_label(p)
        rows.append(["Type", ct or "--"])
        sb = _safe(lambda: getattr(c, "signing_bonus", 0), 0) or 0
        if sb:
            rows.append(["Signing bonus", _fmt_money(sb)])
        if _safe(lambda: getattr(c, "two_way", False), False):
            ahl = _safe(lambda: getattr(c, "ahl_salary", 0), 0) or 0
            rows.append(["AHL salary", _fmt_money(ahl) if ahl else "--"])
        clauses = []
        if _safe(lambda: getattr(c, "no_movement_clause", False), False):
            clauses.append("NMC")
        if _safe(lambda: getattr(c, "no_trade_clause", False), False):
            clauses.append("NTC")
        mntc = _safe(lambda: int(getattr(c, "modified_ntc_teams", 0) or 0), 0)
        if mntc:
            clauses.append(f"M-NTC ({mntc} teams)")
        if clauses:
            rows.append(["Clauses", ", ".join(clauses)])
    rt_team = str(_safe(lambda: getattr(p, "rights_team", ""), "") or "").strip()
    if rt_team:
        rt_type = str(_safe(lambda: getattr(p, "rights_type", ""),
                            "") or "").strip()
        rt_exp = _safe(lambda: getattr(p, "rights_expiry_year", 0), 0) or 0
        r = rt_team
        if rt_type:
            r += f" ({rt_type})"
        if rt_exp:
            r += f" -- thru {rt_exp}"
        rows.append(["Rights", r])
    dy = _safe(lambda: getattr(p, "draft_year", None))
    dp = str(_safe(lambda: getattr(p, "draft_position", ""), "") or "").strip()
    if dy or dp:
        rows.append(["Drafted", f"{dy or '?'} {dp}".strip()])
    if not rows:
        rows.append(["Contract", "No contract on file"])
    out["contract_rows"] = [{"k": k, "v": v} for k, v in rows]
    # --- Composites ---
    try:
        import attribute_composites as _ac
        comp = _ac.get_composite_ratings(p)
        labels = _GOALIE_COMPOSITES if goalie else _SKATER_COMPOSITES
        comps = []
        for key, label in labels:
            if key in comp:
                comps.append({"label": label, "value": _to100(comp[key])})
        out["composites"] = comps
    except Exception:
        out["composites"] = None  # module missing -> hide card
    # --- Attribute groups ---
    groups = [("Technical", _GOALIE_TECHNICAL if goalie else _SKATER_TECHNICAL),
              ("Mental", _GOALIE_MENTAL if goalie else _SKATER_MENTAL),
              ("Physical", _GOALIE_PHYSICAL if goalie else _SKATER_PHYSICAL)]
    out_groups = []
    for gname, attrs in groups:
        rows_a = []
        for label, field in attrs:
            val = _safe(lambda: getattr(p, field, None))
            if val is None and field in ("offensive_positioning",
                                         "defensive_positioning"):
                val = _safe(lambda: getattr(p, "positioning", None))
            if val is None:
                continue
            rows_a.append({"label": label, "value": _to100(val)})
        out_groups.append({"name": gname, "attrs": rows_a})
    out["attr_groups"] = out_groups
    return out


def _build_health(p):
    try:
        import condition_ui as _cu
    except Exception:
        _cu = None
    out = {}
    cond = _safe(lambda: _cu.get_condition(p), None) if _cu else None
    if cond is not None:
        out["condition"] = {
            "value": cond,
            "label": _safe(lambda: _cu.condition_label(cond), ""),
            "color": _safe(lambda: _cu.condition_color(cond), "#8fd14f"),
        }
    injured = bool(_safe(lambda: getattr(p, "is_injured", False), False))
    status = _safe(lambda: _cu.injury_status(p)) if _cu else None
    out["injured"] = injured
    if injured and status:
        out["status"] = {"text": f"🚑 {status}", "fg": "#f85149"}
    elif injured:
        out["status"] = {"text": "🚑 Injured", "fg": "#f85149"}
    else:
        out["status"] = {"text": "✅ Healthy", "fg": "#3fb950"}
    prone = _safe(lambda: getattr(p, "injury_proneness",
                                  getattr(p, "injury_prone", 50)), 50)
    try:
        prone = int(prone or 0)
    except Exception:
        prone = 50
    dur = max(0, min(100, 100 - prone))
    dlab = "Durable" if prone <= 25 else ("Average" if prone <= 55 else
                                          "Fragile")
    dcol = "#3fb950" if prone <= 25 else ("#f4f6fb" if prone <= 55 else
                                          "#d29922")
    out["durability"] = {"value": dur, "label": dlab, "color": dcol}
    # active injury
    if injured:
        itype = str(_safe(lambda: getattr(p, "injury_type", "Injured"),
                          "Injured") or "Injured").strip() or "Injured"
        n = _safe(lambda: int(getattr(p, "games_remaining_injured", 0) or 0),
                  0)
        region = None
        conc = False
        last_inj = _safe(lambda: str(getattr(p, "last_injury", "") or ""), "")
        if last_inj and last_inj != "None":
            region = last_inj
        # concussion flag from injury type text
        if "concussion" in itype.lower():
            conc = True
        out["active_injury"] = {
            "type": itype, "games_remaining": n,
            "region": region, "concussion": conc,
        }
    # history — built from real Player fields (no injury_history list exists)
    entries = []
    last_inj = _safe(lambda: str(getattr(p, "last_injury", "") or ""), "")
    inj_type = _safe(lambda: str(getattr(p, "injury_type", "") or ""), "")
    if last_inj and last_inj != "None":
        bits = inj_type if inj_type and inj_type != "None" else "Injury"
        bits += f" ({last_inj})"
        entries.append(bits)
    out["injury_history"] = entries
    out["career_games_missed"] = _safe(
        lambda: int(getattr(p, "career_games_missed", 0) or 0), 0)
    out["days_missed"] = _safe(lambda: int(getattr(p, "days_missed", 0) or 0),
                               0)
    out["career_concussions"] = _safe(
        lambda: int(getattr(p, "career_concussions", 0) or 0), 0)
    return out


def _build_personality(p, team):
    # Core attributes are on the player object — always available.
    # The reputation system only enhances with computed fields.
    rs = None
    try:
        import reputation_system as _rs
        _rs.ensure_reputation_fields(p)
        rs = _rs
    except Exception:
        pass
    try:
        import player_decision as _pd
        _pd.ensure_decision_fields(p)
    except Exception:
        pass
    att = _safe(lambda: rs.describe_attitude(p), None)
    ff = _safe(lambda: rs.fan_favourite_score(p, team), {}) or {}
    att_colors = {
        "Volatile": "#f85149", "Fiery": "#d29922",
        "Emotional": "#d29922", "Even-keeled": "#3fb950",
        "Model professional": "#58a6ff",
    }
    amb_labels = {"cup": "Stanley Cup", "money": "Money",
                  "ice_time": "Ice Time", "stability": "Stability",
                  "home": "Hometown"}
    amb = amb_labels.get(_safe(lambda: getattr(p, "ambition", ""), "") or "",
                         "")
    rep = _safe(lambda: int(getattr(p, "reputation", 0) or 0), 0)
    lead = _safe(lambda: int(getattr(p, "leadership", 0) or 0), 0)
    rep_line = f"Reputation  {rep}/100   •   Leadership  {lead}/100"
    if amb:
        rep_line += f"   •   Ambition: {amb}"
    reasons = _safe(lambda: list(ff.get("reasons", []) or []), []) or []
    return {
        "attitude": att,
        "attitude_color": att_colors.get(att, "#9aa3b2"),
        "fans_tier": _safe(lambda: ff.get("tier"), ""),
        "morale": _to100(_safe(lambda: getattr(p, "morale", 50), 50)),
        "happiness": _to100(_safe(lambda: getattr(p, "happiness", 50), 50)),
        "loyalty": _to100(_safe(lambda: getattr(p, "loyalty", 50), 50)),
        "rep_line": rep_line,
        "why_fans_care": reasons[:2],
    }


def _build_dynamics(p, team, league):
    try:
        import reputation_system as rs
        rs.ensure_reputation_fields(p)
    except Exception:
        return {"unavailable": True}
    out = {}
    roster = _safe(lambda: list(getattr(team, "roster", []) or []), []) or []
    if roster:
        tiers = _safe(lambda: rs.team_hierarchy(roster), {}) or {}
        for tname, ps in tiers.items():
            try:
                if p in ps:
                    out["room_tier"] = tname
                    break
            except Exception:
                continue
    coach = None
    try:
        for s in (getattr(team, "staff", []) or []):
            if str(getattr(getattr(s, "role", None), "name", "")) == \
                    "HEAD_COACH":
                coach = s
                break
    except Exception:
        pass
    if coach is not None:
        resp = _safe(lambda: rs.player_coach_response(p, coach), None)
        if isinstance(resp, dict):
            out["coach_fit"] = resp.get("response", "Neutral")
        elif resp is not None:
            out["coach_fit"] = str(resp)
    risk = _safe(lambda: rs.trade_request_risk(p), None)
    if risk is not None:
        if risk >= 0.5:
            out["trade_risk"] = {"text": "Trade risk: HIGH", "fg": "#f85149"}
        elif risk >= 0.3:
            out["trade_risk"] = {"text": "Trade risk: elevated",
                                 "fg": "#d29922"}
    friends = _safe(lambda: rs.get_friends(p, roster), []) or []
    fnames = []
    for f in friends:
        pl = f.get("player") if isinstance(f, dict) else None
        if pl is not None:
            fnames.append(_safe(
                lambda: f"{pl.first_name} {pl.last_name}", "?"))
    out["friends"] = fnames
    rivals = _safe(lambda: rs.get_rivals(p, roster, league), []) or []
    rnames = []
    for d in rivals:
        if isinstance(d, dict):
            rnames.append(f"{d.get('name', '?')} ({d.get('origin', '?')})")
    out["rivals"] = rnames
    bonds = []
    bonds_src = _safe(lambda: getattr(p, "coach_bonds", None), None)
    if isinstance(bonds_src, dict):
        for _cid, story in list(bonds_src.items())[:3]:
            bonds.append(str(story))
    elif isinstance(bonds_src, (list, tuple)):
        for story in list(bonds_src)[:3]:
            bonds.append(str(story))
    out["coach_bonds"] = bonds
    return out


def _basic_analytics_fallback(p, goalie):
    """Simple rate stats from season totals when advanced metrics fail."""
    gp = _safe(lambda: int(getattr(p, "games_played", 0) or 0), 0) or 1
    if goalie:
        w = _safe(lambda: int(getattr(p, "wins", 0) or 0), 0)
        sv = _safe(lambda: float(getattr(p, "save_pct", 0) or 0), 0)
        gaa = _safe(lambda: float(getattr(p, "gaa", 0) or 0), 0)
        rows = [["Wins", str(w), ""], ["Save %", f"{sv:.3f}", ""],
                ["GAA", f"{gaa:.2f}", ""]]
        title = "Goaltending — Basic"
    else:
        g = _safe(lambda: int(getattr(p, "goals", 0) or 0), 0)
        a = _safe(lambda: int(getattr(p, "assists", 0) or 0), 0)
        pts = g + a
        sog = _safe(lambda: int(getattr(p, "shots", 0) or 0), 0)
        sh_pct = (g / sog * 100) if sog else 0
        rows = [["Goals / game", f"{g / gp:.2f}", ""],
                ["Points / game", f"{pts / gp:.2f}", ""],
                ["Shooting %", f"{sh_pct:.1f}%", ""],
                ["Shots", str(sog), ""]]
        title = "Offense — Basic"
    return {"goalie": goalie,
            "sections": [{"title": title, "rows": rows}],
            "shots": [], "n_games": 0}


def _build_analytics(p, live, team):
    try:
        import advanced_metrics as am
    except Exception:
        am = None
    goalie = _is_goalie(p)
    _gm_l = _safe(lambda: getattr(live, "game_manager", None))
    lens_team = _safe(lambda: getattr(_gm_l, "user_team", None)) or _safe(lambda: getattr(live, "user_team", None)) or team
    date_str = str(_safe(lambda: getattr(live, "current_date", ""), ""))
    lens = None
    try:
        if lens_team is not None:
            if goalie:
                lens = am.display_goalie_metrics(p, lens_team, date_str)
            else:
                lens = am.display_skater_metrics(p, lens_team, date_str)
    except Exception:
        lens = None

    def _val(field, fallback):
        try:
            if lens is not None and field in lens.values:
                return lens.values[field]
        except Exception:
            pass
        return fallback

    def _with_ci(field, text, pct100=False):
        try:
            if lens is not None and field in lens.ci:
                ci = lens.ci[field]
                if text.rstrip().endswith("%"):
                    if pct100:
                        return f"{text} ±{ci:.1f} pts"
                    return f"{text} ±{ci * 100:.1f} pts"
                return f"{text} ±{ci:.1f}"
        except Exception:
            pass
        return text

    def _gloss(key):
        return _safe(lambda: am.GLOSSARY.get(key, ""), "")

    import dataclasses as _dc
    lens_info = None
    if lens is not None:
        lens_info = {
            "tier": _safe(lambda: lens.tier, ""),
            "as_of": _safe(lambda: lens.as_of, ""),
            "lag_days": _safe(lambda: lens.lag_days, 0),
        }
    sections = []
    try:
        if goalie:
            m = _dc.asdict(am.goalie_advanced(p))
            sections = [
                {"title": "Goaltending — Above Expected", "rows": [
                    ["GSAx", _with_ci("gsax",
                                     f"{_val('gsax', m['gsax']):+.1f}"),
                     _gloss("GSAx")],
                    ["GSAA", f"{_val('gsaa', m['gsaa']):+.1f}",
                     _gloss("GSAA")],
                    ["High-danger SV%",
                     _with_ci("hdsv_pct",
                              f"{_val('hdsv_pct', m['hdsv_pct']):.3f}"),
                     _gloss("HDSV%")],
                    ["Quality-start %",
                     _with_ci("qs_pct",
                              f"{_val('qs_pct', m['qs_pct']):.1%}"),
                     _gloss("QS%")],
                ]},
                {"title": "Workload", "rows": [
                    ["Save %", f"{_val('sv_pct', m['sv_pct']):.3f}", ""],
                    ["GAA", f"{_val('gaa', m['gaa']):.2f}", ""],
                    ["Shots against / 60",
                     f"{_val('sa_per60', m['sa_per60']):.1f}", ""],
                ]},
            ]
        else:
            m = _dc.asdict(am.skater_advanced(p))
            sections = [
                {"title": "Offense — Finishing & Creation", "rows": [
                    ["Shooting %",
                     f"{_val('sh_pct', m['sh_pct']):.1f}%",
                     _gloss("SH%")],
                    ["Individual xG",
                     _with_ci("ixg", f"{_val('ixg', m['ixg']):.1f}"),
                     _gloss("ixG")],
                    ["Goals / 60", f"{_val('g_per60', m['g_per60']):.2f}",
                     ""],
                    ["Points / 60", f"{_val('p_per60', m['p_per60']):.2f}",
                     _gloss("P/60")],
                    ["Game Score", f"{_val('game_score', m['game_score']):.1f}",
                     _gloss("Game Score")],
                ]},
                {"title": "Possession — Driving Play", "rows": [
                    ["Corsi %",
                     _with_ci("cf_pct",
                              f"{_val('cf_pct', m['cf_pct']):.1f}%", True),
                     _gloss("CF%")],
                    ["Fenwick %",
                     _with_ci("ff_pct",
                              f"{_val('ff_pct', m['ff_pct']):.1f}%", True),
                     _gloss("FF%")],
                    ["Expected-goal share",
                     _with_ci("xgf_pct",
                              f"{_val('xgf_pct', m['xgf_pct']):.1f}%", True),
                     _gloss("xGF%")],
                    ["Offensive-zone starts",
                     _with_ci("oz_pct",
                              f"{_val('oz_pct', m['oz_pct']):.1f}%", True),
                     _gloss("OZ%")],
                ]},
                {"title": "Defense & Luck", "rows": [
                    ["PDO",
                     _with_ci("pdo", f"{_val('pdo', m['pdo']):.3f}"),
                     _gloss("PDO")],
                    ["Hits", str(int(_val("hits", m["hits"]))), ""],
                    ["Blocked shots",
                     str(int(_val("blocks", m["blocks"]))), ""],
                ]},
            ]
    except Exception as e:
        # Fall back to basic rate stats computed from season totals
        # instead of showing nothing.
        return _basic_analytics_fallback(p, goalie)
    # --- shot map (real tracking data, last 10 simulated games) ---
    shots = []
    try:
        pid = getattr(p, "id", None)
        pname = _safe(lambda: getattr(p, "full_name", ""), "") or ""
        games = list(_safe(lambda: getattr(team, "analytics_games", None)
                           or [], []) or [])
        for rec in games:
            if not isinstance(rec, dict):
                continue
            for s in (rec.get("shots") or []):
                if not isinstance(s, dict):
                    continue
                if pid is not None and s.get("shooter_id") == pid:
                    shots.append(s)
                elif pname and s.get("shooter") == pname:
                    shots.append(s)
        n_games = len(games)
    except Exception:
        n_games = 0
    clean = []
    for s in shots:
        try:
            clean.append({
                "x": float(s.get("x", 160) or 160),
                "y": float(s.get("y", 42.5) or 42.5),
                "xg": float(s.get("xg", 0) or 0),
                "outcome": str(s.get("outcome", "") or ""),
            })
        except Exception:
            continue
    return {
        "goalie": goalie,
        "lens": lens_info,
        "sections": sections,
        "shots": clean,
        "games_kept": n_games,
    }


def _build_scout(p, live, user_team):
    try:
        import scout_perception as _sp
    except Exception:
        _sp = None
    out = {}
    # --- NHL readiness ---
    try:
        import prospect_development as pd
        base = pd.callup_readiness(p)
        score, deltas = pd.situational_readiness(p, user_team)
        drows = []
        for label, d in deltas:
            drows.append({"label": label, "delta": round(d, 1),
                          "sign": "+" if d > 0 else ""})
        out["readiness"] = {
            "score": round(score, 0), "base": round(base, 0),
            "deltas": drows,
        }
    except Exception as e:
        out["readiness"] = {"unavailable": str(e)}
    # --- Scout report (perceived only — never true attributes) ---
    try:
        scout, report = _sp.resolve_tab_scout(user_team, p)
    except Exception as e:
        return {**out, "report": {"unavailable": str(e)}}
    if scout is None:
        return {**out, "report": None}  # JS shows "report unavailable"
    try:
        import analytics_scouting as _as
        record = _safe(lambda: _as.scout_record_line(scout),
                       "no graded calls yet") or "no graded calls yet"
    except Exception:
        record = "no graded calls yet"
    comp_lines = []
    try:
        comps = _sp.perceived_composites(p, scout, report)
        for key, val in (comps or {}).items():
            label = _safe(lambda: _sp.composite_label(key), key)
            if isinstance(val, tuple):
                comp_lines.append(f"{label} {val[0]:.0f}-{val[1]:.0f}")
            else:
                comp_lines.append(f"{label} {val:.0f}")
    except Exception:
        pass
    strengths, weaknesses = _safe(
        lambda: _sp.perceived_strengths_weaknesses(p, scout, report),
        ([], []))
    try:
        import scouting as _sc
        pot = _safe(lambda: _sc.report_potential_display(report, p), "?")
    except Exception:
        pot = "?"
    notes = ""
    if report and _safe(lambda: getattr(report, "notes", ""), ""):
        notes = str(report.notes)[:600]
    out["report"] = {
        "scout": _safe(lambda: _sp.scout_display_name(scout), "?"),
        "record": record,
        "accuracy": _safe(lambda: getattr(report, "accuracy", "F"),
                          "F") if report else "F",
        "viewings": _safe(lambda: getattr(report, "viewings", 0),
                          0) if report else 0,
        "composites": comp_lines,
        "potential": pot,
        "strengths": [str(s) for s in (strengths or [])],
        "weaknesses": [str(w) for w in (weaknesses or [])],
        "notes": notes,
    }
    return out


def _build_history(p, goalie):
    import game_classes as _gc
    out = {}
    by_season = {}
    for s in (_safe(lambda: getattr(p, "season_history", None), []) or []):
        if isinstance(s, dict):
            by_season.setdefault(s.get("season"), []).append(s)
    seasons = sorted((s for s in by_season if s is not None), reverse=True)
    live = [s for s in (_safe(lambda: list(_gc.current_season_splits(p)),
                              []) or [])
            if isinstance(s, dict) and int(s.get("gp", 0) or 0) > 0]

    def stint_line(st):
        team = st.get("team", "???")
        gp = int(st.get("gp", 0) or 0)
        if goalie:
            w = int(st.get("w", 0) or 0)
            l = int(st.get("l", 0) or 0)
            sa = int(st.get("sa", 0) or 0)
            sv = int(st.get("sv", 0) or 0)
            return [team, f"{gp} GP", f"{w}-{l}",
                    f"{(sv / sa if sa else 0.0):.3f} SV%"]
        g = int(st.get("g", 0) or 0)
        a = int(st.get("a", 0) or 0)
        return [team, f"{gp} GP", f"{g} G", f"{a} A", f"{g + a} PTS"]

    def season_tot(stints):
        if len(stints) <= 1 or goalie:
            return None
        tg = sum(int(s.get("g", 0) or 0) for s in stints)
        ta = sum(int(s.get("a", 0) or 0) for s in stints)
        tgp = sum(int(s.get("gp", 0) or 0) for s in stints)
        return f"TOT   {tgp} GP   {tg} G   {ta} A   {tg + ta} PTS"

    blocks = []
    for s in seasons:
        stints = by_season.get(s, [])
        blocks.append({
            "label": _history_season_label(s),
            "live": False,
            "stints": [stint_line(st) for st in stints],
            "tot": season_tot(stints),
        })
    if live:
        blocks.append({
            "label": "Current season",
            "live": True,
            "stints": [stint_line(st) for st in live],
            "tot": season_tot(live),
        })
    out["seasons"] = blocks
    # career totals
    all_stints = []
    for s in seasons:
        all_stints.extend(by_season.get(s, []))
    if all_stints:
        tgp = sum(int(s.get("gp", 0) or 0) for s in all_stints)
        if goalie:
            tw = sum(int(s.get("w", 0) or 0) for s in all_stints)
            tl = sum(int(s.get("l", 0) or 0) for s in all_stints)
            tsv = sum(int(s.get("sv", 0) or 0) for s in all_stints)
            tsa = sum(int(s.get("sa", 0) or 0) for s in all_stints)
            tso = sum(int(s.get("so", 0) or 0) for s in all_stints)
            out["career"] = (f"CAREER  {tgp} GP   {tw}-{tl}   "
                             f"{(tsv / tsa if tsa else 0.0):.3f} SV%   "
                             f"{tso} SO")
        else:
            tg = sum(int(s.get("g", 0) or 0) for s in all_stints)
            ta = sum(int(s.get("a", 0) or 0) for s in all_stints)
            tpim = sum(int(s.get("pim", 0) or 0) for s in all_stints)
            out["career"] = (f"CAREER  {tgp} GP   {tg} G   {ta} A   "
                             f"{tg + ta} PTS   {tpim} PIM")
    # playoffs
    phist = [pl for pl in (_safe(lambda: getattr(p, "playoff_history", None),
                                 []) or [])
             if isinstance(pl, dict) and int(pl.get("gp", 0) or 0) > 0]
    cur = _safe(lambda: getattr(p, "playoff_stats", None))
    if cur is not None and _safe(lambda: int(
            getattr(cur, "games_played", 0) or 0), 0) > 0:
        phist.append({
            "season": "Current",
            "gp": _safe(lambda: int(getattr(cur, "games_played", 0) or 0), 0),
            "g": _safe(lambda: int(getattr(cur, "goals", 0) or 0), 0),
            "a": _safe(lambda: int(getattr(cur, "assists", 0) or 0), 0),
            "pim": _safe(lambda: int(getattr(cur, "penalties_in_minutes",
                                             0) or 0), 0),
            "w": _safe(lambda: int(getattr(cur, "wins", 0) or 0), 0),
            "l": _safe(lambda: int(getattr(cur, "losses", 0) or 0), 0),
            "sv": _safe(lambda: int(getattr(cur, "saves", 0) or 0), 0),
            "sa": _safe(lambda: int(getattr(cur, "shots_against", 0) or 0),
                        0),
            "so": _safe(lambda: int(getattr(cur, "shutouts", 0) or 0), 0),
            "live": True,
        })
    phist.sort(key=lambda pl: (0 if pl.get("season") == "Current" else 1,
                               -(pl["season"]
                                 if isinstance(pl.get("season"), int)
                                 else 0)))
    rows = []
    for pl in phist:
        lbl = ("Current playoffs  (in progress)"
               if pl.get("season") == "Current"
               else _history_season_label(pl.get("season")))
        gp = int(pl.get("gp", 0) or 0)
        if goalie:
            w = int(pl.get("w", 0) or 0)
            l = int(pl.get("l", 0) or 0)
            sv = int(pl.get("sv", 0) or 0)
            sa = int(pl.get("sa", 0) or 0)
            rows.append(f"{lbl}: {gp} GP   {w}-{l}   "
                        f"{(sv / sa if sa else 0.0):.3f} SV%")
        else:
            g = int(pl.get("g", 0) or 0)
            a = int(pl.get("a", 0) or 0)
            rows.append(f"{lbl}: {gp} GP   {g} G   {a} A   {g + a} PTS")
    out["playoffs"] = rows
    return out


@bp.route("/player/<pid>")
def player_page(pid):
    return render_template("player.html", pid=pid)


@bp.route("/api/player/<pid>")
def api_player(pid):
    live = _live()
    if live is None:
        return jsonify({"error": "no game"}), 503
    p, team, list_name = _find_player(pid)
    if p is None:
        return jsonify({"error": "not found"}), 404
    goalie = _is_goalie(p)
    gm = _safe(lambda: getattr(live, "game_manager", None))
    user_team = _safe(lambda: getattr(gm, "user_team", None)) or _safe(lambda: getattr(live, "user_team", None))
    league = _safe(lambda: getattr(gm, "league", None)) or _safe(lambda: getattr(live, "league", None))
    data = {
        "id": str(pid),
        "list": list_name,
        "team_name": (_safe(lambda: getattr(team, "team_name", None))
                      or str(_safe(lambda: getattr(p, "team_name", ""),
                                   "") or "Free Agent")),
        "goalie": goalie,
    }
    data["header"] = _build_header(p, team, user_team=user_team)
    data["overview"] = _build_overview(p, team)
    data["health"] = _build_health(p)
    data["personality"] = _build_personality(p, team)
    data["dynamics"] = _build_dynamics(p, team, league)
    try:
        data["analytics"] = _build_analytics(p, live, team)
    except Exception as e:
        data["analytics"] = {"unavailable": str(e)}
    try:
        data["scout"] = _build_scout(p, live, user_team)
    except Exception as e:
        data["scout"] = {"unavailable": str(e)}
    data["history"] = _build_history(p, goalie)
    return jsonify(data)
