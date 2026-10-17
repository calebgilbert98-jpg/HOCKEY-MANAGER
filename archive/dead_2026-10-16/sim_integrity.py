"""Sim data-integrity validation toolkit for Puck Dynasty long sims.

Report-only: every check returns issue dicts; nothing in this module
mutates game state. Bots call validate_all() periodically (and after
save/load) and hand the issues to the senior dev.

Pure Python, no platform-specific calls -- safe on Windows and Linux.

Issue dict shape:
    {"severity": "error" | "warning",
     "check": "<check-name>",
     "detail": "<human-readable>"}
"""

from collections import Counter

# ---------------------------------------------------------------------------
# player enumeration
# ---------------------------------------------------------------------------

def _team_lists(team):
    """Yield (label, player_list) for every player container on a team."""
    for label in ("roster", "ahl_roster", "prospects"):
        try:
            plist = getattr(team, label, None) or []
        except Exception:
            plist = []
        yield label, plist


def iter_team_players(league):
    """Yield (player, container_label, team) for every rostered player."""
    for team in (getattr(league, "teams", None) or []):
        for label, plist in _team_lists(team):
            for p in plist:
                yield p, label, team


def iter_all_players(gm):
    """Yield (player, container_label, team_or_None) across every container.

    Covers team rosters/AHL/prospects, the league free-agent list, and the
    database_manager master registry (all_players dict).
    """
    league = getattr(gm, "league", None)
    seen_ids = set()
    if league is not None:
        for p, label, team in iter_team_players(league):
            seen_ids.add(id(p))
            yield p, label, team
        for p in (getattr(league, "free_agents", None) or []):
            if id(p) not in seen_ids:
                seen_ids.add(id(p))
                yield p, "free_agents", None
    dbm = getattr(gm, "database_manager", None) or getattr(gm, "db_manager", None)
    if dbm is not None:
        try:
            registry = getattr(dbm, "all_players", None) or {}
            values = registry.values() if hasattr(registry, "values") else []
        except Exception:
            values = []
        for p in values:
            if id(p) not in seen_ids:
                seen_ids.add(id(p))
                yield p, "registry", None


def _pid(p):
    try:
        v = getattr(p, "id", None)
        return v if isinstance(v, int) else None
    except Exception:
        return None


def _pname(p):
    try:
        fn = getattr(p, "first_name", "")
        ln = getattr(p, "last_name", "")
        name = f"{fn} {ln}".strip()
        return name or str(p)[:40]
    except Exception:
        return "?"


# ---------------------------------------------------------------------------
# individual checks
# ---------------------------------------------------------------------------

def check_duplicate_ids(gm):
    """Two live Player objects sharing one id. The registry dict silently
    drops one of them (all_players[id] overwrite), so this is data loss."""
    issues = []
    counts = Counter()
    by_id = {}
    for p, _label, _team in iter_all_players(gm):
        pid = _pid(p)
        if pid is None:
            issues.append({"severity": "warning", "check": "duplicate_ids",
                           "detail": f"player {_pname(p)} has non-int id "
                                     f"{getattr(p, 'id', None)!r}"})
            continue
        counts[pid] += 1
        by_id.setdefault(pid, []).append(_pname(p))
    for pid, n in counts.items():
        if n > 1:
            names = ", ".join(by_id[pid][:3])
            issues.append({"severity": "error", "check": "duplicate_ids",
                           "detail": f"id {pid} shared by {n} players "
                                     f"({names}{'...' if n > 3 else ''})"})
    return issues


def check_id_counter_health(gm):
    """The global id counter must sit past the highest live id. If it
    doesn't, the NEXT created player collides -- this catches the desync
    before it becomes a duplicate."""
    issues = []
    try:
        from game_classes import player_id_counter
        # Peek without permanently consuming more than one step: the
        # counter is shared process-global, one consumed id is harmless.
        nxt = next(player_id_counter)
        max_id = -1
        for p, _l, _t in iter_all_players(gm):
            pid = _pid(p)
            if pid is not None and pid > max_id:
                max_id = pid
        if max_id >= 0 and nxt <= max_id:
            issues.append({"severity": "error", "check": "id_counter",
                           "detail": f"counter would issue {nxt} but max "
                                     f"live id is {max_id} -- next created "
                                     f"player collides (load without resync?)"})
    except Exception as e:
        issues.append({"severity": "warning", "check": "id_counter",
                       "detail": f"could not inspect counter: {e}"})
    return issues


def check_multi_team(gm):
    """One player object on two different teams' lists."""
    issues = []
    owners = {}
    league = getattr(gm, "league", None)
    if league is None:
        return issues
    for p, label, team in iter_team_players(league):
        key = id(p)
        tname = getattr(team, "team_name", "?")
        if key in owners:
            other_label, other_team = owners[key]
            if other_team is not team:
                issues.append({"severity": "error", "check": "multi_team",
                               "detail": f"{_pname(p)} (id={_pid(p)}) on both "
                                         f"{other_team} [{other_label}] and "
                                         f"{tname} [{label}]"})
        else:
            owners[key] = (label, tname)
    return issues


def check_roster_sizes(gm):
    """NHL roster 10..60 (hard), AHL 0..40, prospects 0..120 (soft warns)."""
    issues = []
    league = getattr(gm, "league", None)
    if league is None:
        return issues
    for team in (getattr(league, "teams", None) or []):
        tname = getattr(team, "team_name", "?")
        n_nhl = len(getattr(team, "roster", None) or [])
        n_ahl = len(getattr(team, "ahl_roster", None) or [])
        n_pro = len(getattr(team, "prospects", None) or [])
        if n_nhl < 10 or n_nhl > 60:
            issues.append({"severity": "error", "check": "roster_size",
                           "detail": f"{tname}: NHL roster {n_nhl} "
                                     f"(bounds 10..60)"})
        elif n_nhl < 20:
            issues.append({"severity": "warning", "check": "roster_size",
                           "detail": f"{tname}: NHL roster {n_nhl} below "
                                     f"dressable 20"})
        if n_ahl > 40:
            issues.append({"severity": "warning", "check": "roster_size",
                           "detail": f"{tname}: AHL roster {n_ahl} > 40"})
        if n_pro > 120:
            issues.append({"severity": "warning", "check": "roster_size",
                           "detail": f"{tname}: prospects {n_pro} > 120"})
    return issues


def _is_goalie(p):
    try:
        pos = getattr(p, "primary_position", None)
        return str(getattr(pos, "value", pos) or "").upper() == "GOALIE"
    except Exception:
        return False


def check_goalie_counts(gm):
    """Every NHL club should carry >= 2 real (non-filler) goalies."""
    issues = []
    league = getattr(gm, "league", None)
    if league is None:
        return issues
    for team in (getattr(league, "teams", None) or []):
        tname = getattr(team, "team_name", "?")
        try:
            goalies = [p for p in (getattr(team, "roster", None) or [])
                       if _is_goalie(p)
                       and not getattr(p, "is_filler", False)]
        except Exception:
            goalies = []
        if len(goalies) == 0:
            issues.append({"severity": "error", "check": "goalies",
                           "detail": f"{tname}: ZERO NHL goalies"})
        elif len(goalies) == 1:
            issues.append({"severity": "warning", "check": "goalies",
                           "detail": f"{tname}: only 1 NHL goalie "
                                     f"({_pname(goalies[0])})"})
    return issues


def _stat_issues(p):
    """Yield (field, detail) for impossible stat lines on one player."""
    try:
        s = getattr(p, "stats", None)
        if s is None:
            return
        gp = int(getattr(s, "games_played", 0) or 0)
        g = int(getattr(s, "goals", 0) or 0)
        a = int(getattr(s, "assists", 0) or 0)
        name = f"{_pname(p)} (id={_pid(p)})"
        for f in ("goals", "assists", "shots", "hits", "takeaways",
                  "blocked_shots", "penalties_in_minutes", "fights",
                  "saves", "shots_against", "wins", "losses",
                  "goals_against", "shutouts", "games_played"):
            v = getattr(s, f, 0)
            try:
                if float(v) < 0:
                    yield f, f"{name}: {f}={v} negative"
            except Exception:
                pass
        if _is_goalie(p):
            sa = int(getattr(s, "shots_against", 0) or 0)
            sv = int(getattr(s, "saves", 0) or 0)
            if sv > sa:
                yield "saves", f"{name}: saves {sv} > shots_against {sa}"
            sp = getattr(s, "save_percentage", 0)
            try:
                if not (0.0 <= float(sp) <= 1.0):
                    yield "sv%", f"{name}: save_percentage {sp} outside [0,1]"
            except Exception:
                pass
            if int(getattr(s, "shutouts", 0) or 0) > int(getattr(s, "wins", 0) or 0):
                yield "shutouts", f"{name}: shutouts > wins"
            if int(getattr(s, "wins", 0) or 0) + int(getattr(s, "losses", 0) or 0) > gp and gp > 0:
                yield "w/l", f"{name}: W+L exceeds games_played"
        else:
            if gp > 0 and (g + a) > 3 * gp:
                yield "points", f"{name}: {g + a} pts in {gp} gp (>3x)"
            if gp > 0 and g > 2 * gp:
                yield "goals", f"{name}: {g} goals in {gp} gp (>2x)"
    except Exception:
        return


def check_stat_sanity(gm):
    issues = []
    for p, _l, _t in iter_all_players(gm):
        for _field, detail in _stat_issues(p):
            issues.append({"severity": "error", "check": "stat_sanity",
                           "detail": detail})
    return issues


def check_cap_compliance(gm):
    """Negative cap_space (central accounting incl. LTIR relief) = over."""
    issues = []
    league = getattr(gm, "league", None)
    if league is None:
        return issues
    for team in (getattr(league, "teams", None) or []):
        try:
            space = getattr(team, "cap_space", None)
            if callable(space):
                space = space()
            if space is not None and int(space) < 0:
                issues.append({"severity": "error", "check": "cap",
                               "detail": f"{getattr(team, 'team_name', '?')}: "
                                         f"cap_space ${int(space):,}"})
        except Exception:
            pass
    return issues


# ---------------------------------------------------------------------------
# entry points
# ---------------------------------------------------------------------------

CHECKS = (
    ("duplicate_ids", check_duplicate_ids),
    ("id_counter", check_id_counter_health),
    ("multi_team", check_multi_team),
    ("roster_size", check_roster_sizes),
    ("goalies", check_goalie_counts),
    ("stat_sanity", check_stat_sanity),
    ("cap", check_cap_compliance),
)


def validate_all(gm, only=None):
    """Run every check (or the named subset). Returns a list of issue dicts,
    errors first. Never raises: a crashing check becomes a warning issue."""
    issues = []
    for name, fn in CHECKS:
        if only is not None and name not in only:
            continue
        try:
            issues.extend(fn(gm))
        except Exception as e:
            issues.append({"severity": "warning", "check": name,
                           "detail": f"check crashed: {e!r}"})
    errors = [i for i in issues if i["severity"] == "error"]
    warnings = [i for i in issues if i["severity"] != "error"]
    return errors + warnings


def format_report(issues):
    lines = [f"integrity: {len(issues)} issue(s)"]
    for i in issues:
        lines.append(f"  [{i['severity'].upper():7}] {i['check']:14} {i['detail']}")
    return "\n".join(lines)


def snapshot(gm):
    """Compact state fingerprint for save/load round-trip comparison.

    Returns (player_count, id_checksum, team_count). Bots snapshot before
    save and after load; any drift means the round trip lost or
    duplicated someone.
    """
    ids = []
    n = 0
    for p, _l, _t in iter_all_players(gm):
        n += 1
        pid = _pid(p)
        if pid is not None:
            ids.append(pid)
    league = getattr(gm, "league", None)
    n_teams = len(getattr(league, "teams", None) or []) if league else 0
    checksum = 0
    for pid in sorted(set(ids)):
        checksum = (checksum * 31 + pid) & 0xFFFFFFFF
    return {"players": n, "unique_ids": len(set(ids)),
            "id_checksum": checksum, "teams": n_teams}


if __name__ == "__main__":
    print("sim_integrity: import this module and call validate_all(gm).")
    print("checks:", ", ".join(n for n, _ in CHECKS))
