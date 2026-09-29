"""Three stars of the game + NHL monthly awards.

Three stars
------------
Selected after every regular-season game on realistic NHL media criteria:
goals and points first, with weight for hat tricks, OT winners, shutouts
and huge save nights. A mild winning-team lean mirrors real voting (the
1st star usually -- not always -- comes from the winning side).

Stars are recorded once, at game-record time, onto ``game_result`` (plain
dicts, save-safe) so the box score, the player card and the monthly
narratives all agree. Each star bumps the player's season star counts
(``player.game_stars``); the 1st star's night is appended to his Signature
Games (``career_moments``) -- the season big-moments list scouts read on
the player card.

Monthly awards
--------------
On the 1st of each month the previous calendar month's NHL Player of the
Month and Rookie of the Month are named from month splits. Splits are
derived as a per-player baseline delta (``player.month_baseline``), so
every sim path -- detailed, quick, lightweight -- feeds the same numbers
with no per-path stat hooks.

Realistic NHL criteria: the top-scoring skater (min 6 GP) takes Player of
the Month unless a goalie (min 4 GP) clears a dominance gate (real voting
hands a goalie the month for ~.930+/7-win type months). Rookie of the
Month is the same contest restricted to rookies. Winners are banked as
accolades, added to Signature Games, and announced in the news.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def _is_goalie(player: Any) -> bool:
    try:
        return getattr(getattr(player, "primary_position", None), "name", "") == "GOALIE"
    except Exception:
        return False


def _full_name(player: Any) -> str:
    name = getattr(player, "full_name", None)
    if name:
        return str(name).strip()
    first = getattr(player, "first_name", "") or ""
    last = getattr(player, "last_name", "") or ""
    return f"{first} {last}".strip() or "Unknown"


def _team_of_pid(home_team: Any, away_team: Any) -> Dict[Any, str]:
    """Map player id -> team name for both clubs."""
    out: Dict[Any, str] = {}
    for team in (home_team, away_team):
        if team is None:
            continue
        tname = getattr(team, "team_name", "") or ""
        for p in getattr(team, "roster", None) or []:
            try:
                out[getattr(p, "id", None)] = tname
            except Exception:
                continue
    return out


# ----------------------------------------------------------------------
# Three stars
# ----------------------------------------------------------------------

def _ot_scorer_id(game_result: Dict[str, Any]) -> Optional[Any]:
    """Player id of the OT winner (period 4 goal). Period 5 is the
    shootout -- its goals don't count in player stats, so no bonus."""
    scorer = None
    for e in game_result.get("notable_events") or []:
        if not isinstance(e, dict):
            continue
        if e.get("event") != "Goal":
            continue
        if (e.get("period", 0) or 0) == 4:
            pl = e.get("player")
            scorer = getattr(pl, "id", None)
    return scorer


def select_three_stars(game_result: Dict[str, Any],
                       home_team: Any = None,
                       away_team: Any = None) -> List[Dict[str, Any]]:
    """Pick the three stars from a recorded game's per-player stats.

    Returns plain dicts (save-safe): player_id, name, team_name, line,
    rank, score. Empty list when the result carries no per-player stats.
    """
    gs = game_result.get("game_stats") or {}
    if not gs:
        return []
    home_score = game_result.get("home_score", 0) or 0
    away_score = game_result.get("away_score", 0) or 0
    winner = game_result.get("winner")
    winner_name = getattr(winner, "team_name", "") if winner is not None else ""
    home_name = getattr(home_team, "team_name", "") if home_team is not None else ""
    ot_id = _ot_scorer_id(game_result)
    team_of = _team_of_pid(home_team, away_team)

    ranked: List[Tuple[float, int, int, int, Any, str, str, str]] = []
    for pid, st in gs.items():
        if not isinstance(st, dict):
            continue
        p = st.get("player")
        if p is None:
            continue
        g = int(st.get("g", 0) or 0)
        a = int(st.get("a", 0) or 0)
        saves = int(st.get("saves", 0) or 0)
        if g + a <= 0 and saves <= 0:
            continue
        tname = team_of.get(getattr(p, "id", pid), "")
        won = bool(tname) and tname == winner_name
        if _is_goalie(p):
            # Shutout: his club allowed nothing.
            if tname == home_name:
                allowed = away_score
            elif away_team is not None and tname == getattr(
                    away_team, "team_name", ""):
                allowed = home_score
            else:
                allowed = None
            shutout = allowed == 0 and saves > 0
            score = saves * 0.12 + (6.0 if shutout else 0.0) \
                + (2.0 if won else 0.0)
            line = f"{saves} saves" + (" (shutout)" if shutout else "")
        else:
            clutch = 1 if getattr(p, "id", pid) == ot_id else 0
            score = (3.0 * g + 2.0 * a
                     + (3.0 if g >= 3 else 0.0)
                     + (3.0 if clutch else 0.0)
                     + (1.0 if won else 0.0))
            line = f"{g} G, {a} A" + (" (OT winner)" if clutch else "")
        ranked.append((score, clutch, g, a, saves, p, tname, line,
                       getattr(p, "id", pid)))

    ranked.sort(key=lambda r: (r[0], r[1], r[2], r[3], r[4]), reverse=True)
    stars = []
    for i, (score, _cl, _g, _a, _s, p, tname, line, pid) in enumerate(ranked[:3]):
        stars.append({
            "player_id": pid,
            "name": _full_name(p),
            "team_name": tname,
            "line": line,
            "rank": i + 1,
            "score": round(score, 2),
        })
    return stars


def _bump_star_counts(player: Any, rank: int) -> None:
    counts = getattr(player, "game_stars", None)
    if not isinstance(counts, dict):
        try:
            player.game_stars = counts = {"first": 0, "second": 0,
                                         "third": 0}
        except Exception:
            return
    key = {1: "first", 2: "second", 3: "third"}.get(rank)
    if key is None:
        return
    try:
        counts[key] = int(counts.get(key, 0) or 0) + 1
    except Exception:
        pass


def _record_first_star_moment(player: Any, star: Dict[str, Any],
                              game_result: Dict[str, Any],
                              home_team: Any, away_team: Any,
                              game_date: Any, playoff: bool = False) -> None:
    """The 1st star's night lands in Signature Games on the player card."""
    tname = star.get("team_name", "")
    home_name = getattr(home_team, "team_name", "") if home_team else ""
    away_name = getattr(away_team, "team_name", "") if away_team else ""
    opp = away_name if tname == home_name else home_name
    hs = game_result.get("home_score", 0) or 0
    aws = game_result.get("away_score", 0) or 0
    if tname == home_name:
        mine, theirs, result = hs, aws, "W"
    else:
        mine, theirs, result = aws, hs, "L"
        if tname == "":
            result = ""
    score_str = f"{mine}-{theirs} {result}".strip()
    dstr = game_date.isoformat() if hasattr(game_date, "isoformat") \
        else str(game_date or "")
    moments = getattr(player, "career_moments", None)
    if not isinstance(moments, list):
        try:
            player.career_moments = moments = []
        except Exception:
            return
    if any(isinstance(m, dict) and m.get("date") == dstr
           and m.get("kind") == "first_star" for m in moments):
        return
    detail = f"{star.get('line', '')} vs {opp} ({score_str})".strip()
    moments.append({
        "date": dstr,
        "kind": "first_star",
        "label": "1st Star of the Game",
        "detail": detail,
        "opp": opp,
        "score": score_str,
        "sig": 25,
        "playoff": bool(playoff),
    })


def record_game_stars(game_result: Dict[str, Any],
                      home_team: Any = None,
                      away_team: Any = None,
                      preseason: bool = False,
                      game_date: Any = None,
                      playoff: bool = False) -> List[Dict[str, Any]]:
    """Select the three stars, stamp them on the result, and record them
    onto the players. Idempotent per game: callers record each game once.
    Preseason exhibitions name no stars."""
    if preseason:
        game_result["three_stars"] = []
        return []
    stars = select_three_stars(game_result, home_team, away_team)
    game_result["three_stars"] = stars
    if not stars:
        return stars
    gs = game_result.get("game_stats") or {}
    by_pid = {}
    for pid, st in gs.items():
        if isinstance(st, dict) and st.get("player") is not None:
            by_pid[pid] = st["player"]
    # Fallback: roster lookup if game_stats lacks the player object.
    for team in (home_team, away_team):
        for p in getattr(team, "roster", None) or [] if team else []:
            by_pid.setdefault(getattr(p, "id", None), p)
    for star in stars:
        p = by_pid.get(star.get("player_id"))
        if p is None:
            continue
        _bump_star_counts(p, star["rank"])
        if star["rank"] == 1:
            _record_first_star_moment(p, star, game_result,
                                      home_team, away_team, game_date,
                                      playoff=playoff)
    return stars


# ----------------------------------------------------------------------
# Signature Games display
# ----------------------------------------------------------------------

_MOMENT_EMOJI = {
    "hat_trick": "\U0001f3a9", "four_point": "\u2b50",
    "five_point": "\U0001f31f", "shutout": "\U0001f9f1",
    "forty_saves": "\U0001f946", "steal": "\U0001f946",
    "iconic_game": "\U0001f3db\ufe0f", "first_star": "\u2b50",
    "player_of_month": "\U0001f3c6", "rookie_of_month": "\U0001f331",
}


def _fmt_moment_date(dstr: Any) -> str:
    try:
        return date.fromisoformat(str(dstr)).strftime("%b %d, %Y")
    except Exception:
        return str(dstr or "")


def signature_game_rows(moments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build display rows for the player card's Signature Games section.

    Repeat 1st-star nights collapse into a single tally+dates row instead
    of one line item per night; everything else renders one row per
    moment, newest first. Pure function -- the UI just renders rows.

    Each row: {"emoji", "line1", "detail", "consumed"}, where consumed is
    how many raw moments the row represents (for the "+ N more" count).
    """
    moms = [m for m in moments or [] if isinstance(m, dict)]
    moms = sorted(moms, key=lambda m: m.get("date", ""), reverse=True)
    first_stars = [m for m in moms if m.get("kind") == "first_star"]
    rows: List[Dict[str, Any]] = []
    agg_done = False
    for m in moms:
        kind = m.get("kind", "")
        if kind == "first_star":
            if agg_done:
                continue
            agg_done = True
            if len(first_stars) == 1:
                rows.append({
                    "emoji": _MOMENT_EMOJI["first_star"],
                    "line1": "\u2b50 1st Star of the Game \u2014 "
                             + _fmt_moment_date(m.get("date", "")),
                    "detail": m.get("detail", ""),
                    "consumed": 1,
                })
            else:
                dates = ", ".join(_fmt_moment_date(x.get("date", ""))
                                  for x in first_stars)
                rows.append({
                    "emoji": _MOMENT_EMOJI["first_star"],
                    "line1": f"\u2b50 1st Star of the Game "
                             f"\u00d7{len(first_stars)}",
                    "detail": dates,
                    "consumed": len(first_stars),
                })
        else:
            line1 = (f"{_MOMENT_EMOJI.get(kind, '\U0001f3d2')} "
                     f"{m.get('label', 'Big night')} \u2014 "
                     f"{_fmt_moment_date(m.get('date', ''))}")
            if m.get("playoff"):
                line1 += " (playoffs)"
            rows.append({
                "emoji": _MOMENT_EMOJI.get(kind, "\U0001f3d2"),
                "line1": line1,
                "detail": m.get("detail", ""),
                "consumed": 1,
            })
    return rows


# ----------------------------------------------------------------------
# Monthly awards
# ----------------------------------------------------------------------

# Fields tracked as a per-player month baseline; production for the month
# is current season stats minus the baseline stamped on the 1st.
_MONTH_FIELDS = ("g", "a", "gp", "w", "so", "saves", "sa", "ga")


def _current_ledger(player: Any) -> Dict[str, int]:
    st = getattr(player, "stats", None)
    return {
        "g": int(getattr(st, "goals", 0) or 0),
        "a": int(getattr(st, "assists", 0) or 0),
        "gp": int(getattr(st, "games_played", 0) or 0),
        "w": int(getattr(st, "wins", 0) or 0),
        "so": int(getattr(st, "shutouts", 0) or 0),
        "saves": int(getattr(st, "saves", 0) or 0),
        "sa": int(getattr(st, "shots_against", 0) or 0),
        "ga": int(getattr(st, "goals_against", 0) or 0),
    }


def month_production(player: Any) -> Tuple[Dict[str, int], bool]:
    """(production, reset_detected). When season stats were reset under us
    (rollover), production is zeros and the caller should just re-stamp."""
    cur = _current_ledger(player)
    base = getattr(player, "month_baseline", None)
    if not isinstance(base, dict):
        base = {}
    prod: Dict[str, int] = {}
    for f in _MONTH_FIELDS:
        b = int(base.get(f, 0) or 0)
        c = cur[f]
        if c < b:
            return {f: 0 for f in _MONTH_FIELDS}, True
        prod[f] = c - b
    return prod, False


def stamp_monthly_baselines(teams: List[Any]) -> None:
    for team in teams or []:
        for p in getattr(team, "roster", None) or []:
            try:
                p.month_baseline = _current_ledger(p)
            except Exception:
                continue


def _goalie_dominant(prod: Dict[str, int]) -> bool:
    """Real-voting bar for a goalie taking a monthly honor outright:
    a ~.930+/7-win type month, or a shutout binge with strong numbers."""
    gp = prod["gp"]
    if gp < 4:
        return False
    svp = prod["saves"] / prod["sa"] if prod["sa"] > 0 else 0.0
    w, so = prod["w"], prod["so"]
    return ((w >= 7 and svp >= 0.930)
            or (w >= 9 and svp >= 0.915)
            or (so >= 3 and svp >= 0.920))


def _skater_line(prod: Dict[str, int]) -> str:
    pts = prod["g"] + prod["a"]
    return f"{pts} points ({prod['g']} G, {prod['a']} A) in {prod['gp']} games"


def _goalie_line(prod: Dict[str, int]) -> str:
    svp = prod["saves"] / prod["sa"] if prod["sa"] > 0 else 0.0
    bits = f"{prod['w']}-{prod['gp'] - prod['w']}"
    extra = f", {prod['so']} SO" if prod["so"] else ""
    return f"{bits}, {svp:.3f} SV%{extra} in {prod['gp']} games"


def select_monthly_winners(teams: List[Any]) -> Tuple[
        Optional[Tuple[Any, Any, str]],
        Optional[Tuple[Any, Any, str]]]:
    """Return ((potm_player, team, line), (rotm_player, team, line)).
    Either may be None when nobody qualifies."""
    skaters: List[Tuple[int, int, Any, Any, Dict[str, int]]] = []
    goalies: List[Tuple[int, float, Any, Any, Dict[str, int]]] = []
    r_skaters: List[Tuple[int, int, Any, Any, Dict[str, int]]] = []
    r_goalies: List[Tuple[int, float, Any, Any, Dict[str, int]]] = []

    for team in teams or []:
        for p in getattr(team, "roster", None) or []:
            try:
                prod, reset = month_production(p)
            except Exception:
                continue
            if reset or prod["gp"] <= 0:
                continue
            rookie = bool(getattr(p, "is_rookie", False))
            if _is_goalie(p):
                if prod["gp"] < 4:
                    continue
                svp = prod["saves"] / prod["sa"] if prod["sa"] > 0 else 0.0
                row = (prod["w"], svp, p, team, prod)
                goalies.append(row)
                if rookie:
                    r_goalies.append(row)
            else:
                if prod["gp"] < 6:
                    continue
                pts = prod["g"] + prod["a"]
                if pts <= 0:
                    continue
                row = (pts, prod["g"], p, team, prod)
                skaters.append(row)
                if rookie:
                    r_skaters.append(row)

    def _best_overall(skat, goal):
        # A dominant goalie month takes the honor outright (real voting
        # does exactly this); otherwise the scoring leader wins.
        dom = [r for r in goal if _goalie_dominant(r[4])]
        if dom:
            dom.sort(key=lambda r: (r[0], r[1]), reverse=True)
            _w, _svp, p, team, prod = dom[0]
            return p, team, _goalie_line(prod)
        if not skat:
            return None
        skat.sort(key=lambda r: (r[0], r[1]), reverse=True)
        _pts, _g, p, team, prod = skat[0]
        return p, team, _skater_line(prod)

    potm = _best_overall(skaters, goalies)
    rotm = _best_overall(r_skaters, r_goalies)
    # A rookie can't win both in the same month -- the senior honor stands.
    if potm and rotm and potm[0] is rotm[0]:
        rotm = None
    return potm, rotm


def monthly_awards_tick(app: Any) -> Optional[Dict[str, Any]]:
    """Run on the 1st of each month: name last month's winners, bank the
    accolades, post the news, re-stamp baselines. Safe to call when the
    league isn't ready yet (no-op)."""
    try:
        from accolades import bank_accolade
    except Exception:
        return None
    league = getattr(app, "league", None)
    teams = [t for t in (getattr(league, "teams", None) or [])
             if getattr(t, "league_name", "National Hockey League")
             == "National Hockey League"]
    if not teams:
        return None
    game_date = getattr(app, "current_date", None) or date.today()
    try:
        prev = game_date.replace(day=1) - timedelta(days=1)
    except Exception:
        return None
    # Playoffs / offseason / preseason months: no awards, but keep the
    # baselines fresh so the next real month measures cleanly.
    if prev.month in (5, 6, 7, 8, 9):
        stamp_monthly_baselines(teams)
        return None
    month_label = prev.strftime("%b %Y")

    potm, rotm = select_monthly_winners(teams)
    dstr = game_date.isoformat() if hasattr(game_date, "isoformat") \
        else str(game_date)
    awarded: Dict[str, Any] = {"month": month_label}

    def _bank(winner, award_key, label, emoji):
        if not winner:
            return
        p, team, line = winner
        tname = getattr(team, "team_name", "") or ""
        try:
            bank_accolade(p, award_key, month_label)
        except Exception:
            pass
        moments = getattr(p, "career_moments", None)
        if not isinstance(moments, list):
            try:
                p.career_moments = moments = []
            except Exception:
                moments = None
        if moments is not None and not any(
                isinstance(m, dict) and m.get("kind") == award_key
                and month_label in str(m.get("detail", ""))
                for m in moments):
            moments.append({
                "date": dstr,
                "kind": award_key,
                "label": label,
                "detail": f"{month_label} -- {line}",
                "sig": 45,
            })
        try:
            app.add_news(
                f"{emoji} {_full_name(p)} ({tname}) named {label} for "
                f"{month_label} -- {line}.")
        except Exception:
            pass
        awarded[award_key] = {"player": _full_name(p), "line": line}

    _bank(potm, "player_of_month", "NHL Player of the Month", "\u2b50")
    _bank(rotm, "rookie_of_month", "NHL Rookie of the Month", "\U0001f331")
    stamp_monthly_baselines(teams)
    return awarded
