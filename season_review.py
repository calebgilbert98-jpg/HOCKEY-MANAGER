# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""End-of-season review card (Muck's spec, 2026-09-28).

One inbox email at season's end that tells the story of the year:
the record vs expectations, the big moments (from the narrative
ledger), the players who stood out and the ones who had a tough go,
the story of the season (streaks, awards), a report card on every
non-NHL player whose rights the club holds, and a four-corner season
score -- media, fans, owner, room.

Continuity machinery lives here too:
- snapshot_preseason_predictions(): taken at the season rollover from
  opening-night roster strength. Next year's review grades every club
  against it ("vs media expectations").
- stash_last_season_lines(): per-player season stat snapshot, taken
  BEFORE League.end_of_season() wipes per-season stats. Lets future
  reviews compare against last year instead of just career pace.
- deliver_season_review() also records a season_story ledger event per
  team, so future seasons (and headline callbacks) can reference "last
  year's collapse" / "the defending champions".

Everything is defensive: any missing data source skips its section
rather than breaking delivery.
"""

from datetime import date

SEASON_STORY_WEIGHT = 45


# ----------------------------------------------------------------------
# Small helpers
# ----------------------------------------------------------------------

def season_label(year):
    """2026 -> '2026-27'."""
    try:
        y = int(year)
    except (TypeError, ValueError):
        return "Season"
    return f"{y}-{str(y + 1)[-2:]}"


def _grade(score):
    """0-100 -> letter."""
    try:
        s = float(score)
    except (TypeError, ValueError):
        return "N/A"
    if s >= 93:
        return "A"
    if s >= 85:
        return "A-"
    if s >= 78:
        return "B+"
    if s >= 70:
        return "B"
    if s >= 62:
        return "B-"
    if s >= 55:
        return "C+"
    if s >= 47:
        return "C"
    if s >= 40:
        return "C-"
    if s >= 32:
        return "D"
    return "F"


def _num(v, default=0):
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return default


def _is_goalie(p):
    try:
        pos = str(getattr(p, "primary_position", "")).lower()
    except Exception:
        pos = ""
    return "goalie" in pos or _num(getattr(p, "saves", 0)) > 0


def _skater_line(p):
    gp = _num(getattr(p, "games_played", 0))
    return (f"{_num(getattr(p, 'goals', 0))}G "
            f"{_num(getattr(p, 'assists', 0))}A "
            f"{_num(getattr(p, 'points', 0))}Pts in {gp} GP")


def _career_ppg(p):
    """Career points-per-game excluding the current season."""
    cg = _num(getattr(p, "career_games", 0)) - _num(getattr(p, "games_played", 0))
    cp = _num(getattr(p, "career_points", 0)) - _num(getattr(p, "points", 0))
    if cg <= 0:
        return None
    return cp / cg


# ----------------------------------------------------------------------
# Continuity machinery
# ----------------------------------------------------------------------

def roster_strength(team):
    """Opening-night roster strength: mean overall of the best 20."""
    try:
        ovrs = sorted((p.overall_rating() for p in (getattr(team, "roster", None) or [])
                       if hasattr(p, "overall_rating")),
                      reverse=True)[:20]
        if not ovrs:
            return 0.0
        return sum(ovrs) / len(ovrs)
    except Exception:
        return 0.0


def snapshot_preseason_predictions(league):
    """Rank every NHL club by opening-night roster strength.

    Called at the end of League.end_of_season() (new season_year, final
    rosters). Stored as plain data on the league so it pickles with the
    save: {team_name: {"rank": n, "strength": x, "season": year}}.
    """
    try:
        teams = [t for t in (getattr(league, "teams", None) or [])
                 if getattr(t, "league_name", "") == "National Hockey League"]
        ranked = sorted(teams, key=roster_strength, reverse=True)
        season = int(getattr(league, "season_year", 0) or 0)
        league.preseason_predictions = {
            t.team_name: {"rank": i + 1,
                          "strength": round(roster_strength(t), 1),
                          "season": season}
            for i, t in enumerate(ranked)
        }
    except Exception:
        pass


def stash_last_season_lines(players):
    """Snapshot this season's stat line onto each player (pre-wipe).

    Stored as p.last_season = {"gp","g","a","pts","plus_minus","w","sv_pct",
    "gaa","shutouts"}. Lets next year's review (and any UI) compare
    against last year, not just career totals.
    """
    for p in players or []:
        try:
            p.last_season = {
                "gp": _num(getattr(p, "games_played", 0)),
                "g": _num(getattr(p, "goals", 0)),
                "a": _num(getattr(p, "assists", 0)),
                "pts": _num(getattr(p, "points", 0)),
                "plus_minus": _num(getattr(p, "plus_minus", 0)),
                "w": _num(getattr(p, "wins", 0)),
                "sv_pct": getattr(p, "save_percentage", 0) or 0,
                "gaa": getattr(p, "goals_against_avg", 0) or 0,
                "shutouts": _num(getattr(p, "shutouts", 0)),
            }
        except Exception:
            pass


# ----------------------------------------------------------------------
# Section builders (each returns a list of text lines; empty = skip)
# ----------------------------------------------------------------------

def _header_lines(team, standings, predictions, year):
    st = (standings or {}).get(team.team_name, {})
    w = _num(st.get("W", st.get("Wins", getattr(team, "wins", 0))))
    l = _num(st.get("L", st.get("Losses", getattr(team, "losses", 0))))
    otl = _num(st.get("OTL", getattr(team, "ot_losses", 0)))
    pts = w * 2 + otl
    # Final rank from the ordered standings dict, else points sort.
    rank = None
    try:
        ordered = sorted(
            ((n, (s.get("W", 0)) * 2 + s.get("OTL", 0))
             for n, s in (standings or {}).items()),
            key=lambda x: x[1], reverse=True)
        for i, (n, _p) in enumerate(ordered, 1):
            if n == team.team_name:
                rank = i
                break
    except Exception:
        pass
    pred = (predictions or {}).get(team.team_name, {})
    pred_rank = pred.get("rank")
    lines = [f"Record: {w}-{l}-{otl} ({pts} pts)"]
    if rank:
        lines[0] += f" -- finished {rank}{_ord(rank)} in the league"
    if pred_rank and rank:
        diff = pred_rank - rank
        if diff > 0:
            lines.append(f"Media preseason poll had them {pred_rank}{_ord(pred_rank)}: "
                         f"finished {diff} spot(s) ABOVE expectations.")
        elif diff < 0:
            lines.append(f"Media preseason poll had them {pred_rank}{_ord(pred_rank)}: "
                         f"finished {-diff} spot(s) BELOW expectations.")
        else:
            lines.append(f"Media preseason poll had them {pred_rank}{_ord(pred_rank)}: "
                         f"right on the number.")
    return lines, {"w": w, "l": l, "otl": otl, "pts": pts,
                   "rank": rank, "pred_rank": pred_rank}


def _ord(n):
    if 10 <= n % 100 <= 20:
        s = "th"
    else:
        s = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return s


def _bracket_playoff_result(app, team):
    """(made_playoffs, rounds_won, won_cup) from the ACTUAL playoff bracket.

    The single source of truth for playoff participation. board_facts can
    go stale or contradict itself (a team both missing and making the
    playoffs); the bracket never lies. Returns (False, 0, False) when no
    bracket is available.
    """
    try:
        tname = getattr(team, "team_name", "") or ""
        if not tname:
            return False, 0, False
        league = getattr(app, "league", None)
        bracket = getattr(league, "playoff_bracket", None)
        if bracket is None:
            return False, 0, False
        made, rounds = False, 0
        for series_list in (getattr(bracket, "playoff_series", {}) or {}).values():
            for s in series_list or []:
                t1 = getattr(getattr(s, "team1", None), "team_name", None)
                t2 = getattr(getattr(s, "team2", None), "team_name", None)
                if tname not in (t1, t2):
                    continue
                made = True
                if getattr(getattr(s, "winner", None), "team_name", None) == tname:
                    rounds += 1
        champ = getattr(bracket, "stanley_cup_champion", None)
        won_cup = getattr(champ, "team_name", None) == tname
        return made, rounds, won_cup
    except Exception:
        return False, 0, False


def _story_lines(app, team, year, board_facts):
    """Big moments: streaks, ledger highlights, playoff run."""
    lines = []
    try:
        streak = _num(getattr(team, "longest_win_streak", 0))
        if streak >= 5:
            lines.append(f"Longest win streak: {streak} games.")
        elif streak >= 3:
            lines.append(f"Best run of the year: {streak} straight wins.")
    except Exception:
        pass
    # Playoff run -- gated on ACTUAL bracket participation, not board_facts
    # (which once claimed a 17th-place team both missed and made it).
    try:
        _made, _rounds, _cup = _bracket_playoff_result(app, team)
        if _cup:
            lines.append("STANLEY CUP CHAMPIONS.")
        elif _rounds > 0:
            lines.append(f"Won {_rounds} playoff round{'' if _rounds == 1 else 's'}.")
        elif _made:
            lines.append("Made the playoffs, out in round one.")
        else:
            lines.append("Missed the playoffs.")
    except Exception:
        pass
    # Ledger highlights: top-weight moments involving this club.
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app)
        kinds = {"incident", "hat_trick", "blowout", "goalie_steal",
                 "ot_thriller", "shutout", "outdoor_game", "milestone"}
        evs = [e for e in (led.events or [])
               if e.get("season") == year
               and team.team_name in (e.get("teams") or [])
               and e.get("kind") in kinds]
        evs.sort(key=lambda e: e.get("weight", 0), reverse=True)
        for e in evs[:5]:
            txt = (e.get("text") or "").strip()
            if txt:
                lines.append(f"- {txt}")
    except Exception:
        pass
    return lines


def _standout_lines(team):
    """Stood out / tough go, judged vs career pace."""
    skaters = [p for p in (getattr(team, "roster", None) or [])
               if not _is_goalie(p) and _num(getattr(p, "games_played", 0)) >= 20]
    goalies = [p for p in (getattr(team, "roster", None) or [])
               if _is_goalie(p) and _num(getattr(p, "games_played", 0)) >= 15]
    out, tough = [], []

    def _expected_diff(p):
        cppg = _career_ppg(p)
        if cppg is None:
            return None
        gp = _num(getattr(p, "games_played", 0))
        return _num(getattr(p, "points", 0)) - cppg * gp

    scored = sorted(skaters, key=lambda p: _num(getattr(p, "points", 0)),
                    reverse=True)
    for p in scored:
        if len(out) >= 3:
            break
        d = _expected_diff(p)
        if d is not None and d < -5:
            continue  # deep below pace: that's the tough-go list, not this one
        name = _ff_tag(p, team, getattr(p, "full_name", "Unknown"))
        line = f"{name}: {_skater_line(p)}"
        if d is not None and d >= 8:
            line += f" ({d:+.0f} vs career pace -- career year)"
        elif getattr(p, "is_rookie", False):
            line += " (rookie)"
        out.append(line)
    for p in sorted(goalies,
                    key=lambda p: float(getattr(p, "save_percentage", 0) or 0),
                    reverse=True)[:1]:
        name = _ff_tag(p, team, getattr(p, "full_name", "Unknown"))
        out.append(f"{name}: {_num(getattr(p, 'wins', 0))}W, "
                   f"{getattr(p, 'save_percentage', 0)} SV%, "
                   f"{getattr(p, 'goals_against_avg', 0)} GAA")

    cands = []
    for p in skaters:
        if _num(getattr(p, "games_played", 0)) < 30:
            continue
        d = _expected_diff(p)
        if d is not None:
            cands.append((d, p))
    cands.sort(key=lambda x: x[0])
    for d, p in cands[:3]:
        if d < -5:
            name = getattr(p, "full_name", "Unknown")
            tough.append(f"{name}: {_skater_line(p)} ({d:+.0f} vs career pace)")
    return out, tough


def _rookie_lines(app, team, year):
    lines = []
    try:
        from awards_race import calder_race
        league = app.league
        players = league.get_all_players() if hasattr(league, "get_all_players") else []
        race = calder_race(list(players), season_year=year)
        mine = [r for r in race
                if getattr(r.get("player"), "team_name", "") == team.team_name
                or r.get("player") in (getattr(team, "roster", None) or [])][:3]
        for r in mine:
            p = r["player"]
            name = getattr(p, "full_name", "Unknown")
            if r.get("goalie"):
                lines.append(f"{name}: {r.get('wins', 0)}W, {r.get('sv_pct', 0)} SV% "
                             f"(Calder race)")
            else:
                lines.append(f"{name}: {r.get('goals', 0)}G {r.get('points', 0)}Pts "
                             f"(Calder race)")
        # League rookie goal leader (the "rookie with 50 goals" beat).
        skaters = [r for r in race if not r.get("goalie")]
        if skaters:
            top = max(skaters, key=lambda r: r.get("goals", 0))
            if top.get("goals", 0) >= 20:
                name = getattr(top["player"], "name", "Unknown")
                lines.append(f"League rookie goal leader: {name} "
                             f"({top.get('goals', 0)} goals)")
    except Exception:
        pass
    return lines


def _award_lines(app, team, year):
    lines = []
    try:
        hist = getattr(app, "league_history", None)
        season = hist.get_season(year) if hist else None
        awards = (season or {}).get("awards") or {}
        if not awards:
            return lines
        my_names = {getattr(p, "name", "") for p in (getattr(team, "roster", None) or [])}
        for award, winner in awards.items():
            wname = winner if isinstance(winner, str) else getattr(winner, "name", str(winner))
            star = " <-- YOURS" if wname in my_names else ""
            if award in ("Hart", "Art Ross", "Rocket Richard", "Norris",
                         "Vezina", "Selke", "Calder", "Conn Smythe"):
                lines.append(f"{award}: {wname}{star}")
    except Exception:
        pass
    return lines


def _prospect_rating(summary):
    """Outlook label from the development summary."""
    try:
        gap = summary.get("potential_gap", 0) or 0
        cur = summary.get("current_overall", 0) or 0
        if cur >= 80 or gap >= 12:
            return "Blue-chip"
        if gap >= 7:
            return "On track"
        if gap >= 3:
            return "Project"
        return "Long shot"
    except Exception:
        return "Prospect"


def _prospect_lines(team):
    lines = []
    try:
        from player_development_system import PlayerDevelopmentEngine
        pds = PlayerDevelopmentEngine()
        prospects = list(getattr(team, "prospects", None) or [])
        if not prospects:
            return ["No prospects under contract."]
        # Sort by potential, best first.
        def _pot(p):
            try:
                s = pds.get_player_development_summary(p)
                return s.get("potential_overall", 0) or 0
            except Exception:
                return 0
        for p in sorted(prospects, key=_pot, reverse=True)[:12]:
            try:
                name = getattr(p, "full_name", "Unknown")
                age = getattr(p, "age", "?")
                s = pds.get_player_development_summary(p)
                cur = s.get("current_overall", "?")
                pot = s.get("potential_overall", "?")
                outlook = _prospect_rating(s)
                extra = ""
                try:
                    txt = pds.get_development_outlook(p)
                    if txt:
                        extra = f" -- {str(txt)[:90]}"
                except Exception:
                    pass
                lines.append(f"{name} ({age}): {cur} -> {pot} [{outlook}]{extra}")
            except Exception:
                continue
        if len(prospects) > 12:
            lines.append(f"...and {len(prospects) - 12} more in the system.")
    except Exception:
        pass
    return lines


# ----------------------------------------------------------------------
# Year-end beats (2026-09-30): discipline, mandate, stars, leadership,
# transactions, bench. Each returns text lines; empty = skip the section.
# ----------------------------------------------------------------------

def _discipline_lines(app, team, year):
    """DoPS suspensions, repeat offenders, goalie runs, missed-call reviews."""
    lines = []
    ystr = str(year)
    # A season spans two calendar years (Oct year -> Apr year+1).
    season_years = {ystr}
    try:
        season_years.add(str(int(year) + 1))
    except (TypeError, ValueError):
        pass
    roster = list(getattr(team, "roster", None) or [])
    susp_by_player = {}
    missed = []
    for p in roster:
        hist = getattr(p, "controversy_history", None) or []
        for e in hist:
            if not isinstance(e, dict):
                continue
            etype = str(e.get("type", "") or "").lower()
            edate = str(e.get("date", "") or "")
            if season_years and not any(y in edate for y in season_years):
                continue
            if etype == "suspension":
                susp_by_player.setdefault(
                    getattr(p, "full_name", "Unknown"), []).append(e)
            elif "missed" in etype or "dops" in etype or "review" in etype:
                desc = str(e.get("description", "") or "").strip()
                if desc:
                    missed.append((getattr(p, "full_name", "Unknown"), desc))
    for name, evs in sorted(susp_by_player.items(),
                            key=lambda kv: len(kv[1]), reverse=True):
        n = len(evs)
        desc = str(evs[0].get("description", "") or "").strip()
        tag = f" -- repeat offender ({n}x)" if n >= 2 else ""
        line = f"- {name}: suspended {n} time{'s' if n != 1 else ''}{tag}"
        if desc:
            line += f" ({desc[:80]})"
        lines.append(line)
    # Goalie runs from the narrative ledger.
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app)
        runs = [e for e in (getattr(led, "events", None) or [])
                if e.get("season") == year
                and team.team_name in (e.get("teams") or [])
                and "goalie" in str(e.get("text", "") or "").lower()]
        for e in runs[:3]:
            txt = str(e.get("text", "") or "").strip()
            if txt:
                lines.append(f"- {txt[:110]}")
    except Exception:
        pass
    for name, desc in missed[:3]:
        lines.append(f"- DoPS review ({name}): {desc[:100]}")
    return lines


def _mandate_lines(app, team, board_facts):
    """Preseason mandate, quarterly check-ins, final outcome, coach trust.

    User's club only -- other clubs have no mandate on file.
    """
    if team is not getattr(app, "user_team", None):
        return []
    mandate = getattr(team, "season_mandate", None)
    if not isinstance(mandate, dict):
        return []
    lines = []
    exp = mandate.get("expectation")
    if exp:
        lines.append(f"- Preseason mandate: {exp}.")
    for key, label in (("alignment", "Alignment"),
                       ("identity", "Identity"),
                       ("rookie_stance", "Rookie stance")):
        val = mandate.get(key)
        if val:
            lines.append(f"- {label}: {val}.")
    checkins = mandate.get("checkins") or []
    for c in checkins:
        if not isinstance(c, dict):
            continue
        q = c.get("quarter", "?")
        notes = c.get("notes") or []
        note = str(notes[0])[:90] if notes else ""
        topics = c.get("topics") or []
        topic = str(topics[0]) if topics else ""
        detail = note or topic
        lines.append(f"- Check-in Q{q}:{(' ' + detail) if detail else ''}")
    # Final outcome vs the board's reckoning.
    try:
        bf_exp = (board_facts or {}).get("expectation")
        if bf_exp:
            lines.append(f"- Final board verdict: mandate was '{bf_exp}'.")
    except Exception:
        pass
    try:
        from coach_checkins import get_head_coach
        coach = get_head_coach(team)
        trust = getattr(coach, "gm_trust", None) if coach is not None else None
        if trust is not None:
            cname = getattr(coach, "name", None) or getattr(
                coach, "full_name", "head coach")
            lines.append(f"- GM trust in {cname}: {int(trust)}/100.")
    except Exception:
        pass
    return lines


def _stars_lines(app, team, year):
    """Three-stars leaders, monthly awards, All-Star nods."""
    lines = []
    roster = list(getattr(team, "roster", None) or [])
    try:
        from stars import weighted_star_count
    except Exception:
        return []
    ranked = []
    for p in roster:
        try:
            w = float(weighted_star_count(p) or 0)
        except Exception:
            w = 0.0
        if w > 0:
            ranked.append((w, p))
    ranked.sort(key=lambda x: x[0], reverse=True)
    for w, p in ranked[:3]:
        name = getattr(p, "full_name", "Unknown")
        try:
            gs = getattr(p, "game_stars", None) or {}
            brk = (f"{_num(gs.get('first'))}x1st "
                   f"{_num(gs.get('second'))}x2nd "
                   f"{_num(gs.get('third'))}x3rd")
        except Exception:
            brk = ""
        lines.append(f"- {name}: {w:.2f} weighted stars"
                     + (f" ({brk})" if brk else ""))
    # Monthly awards banked on career_accolades this season.
    season_years = {str(year)}
    try:
        season_years.add(str(int(year) + 1))
    except (TypeError, ValueError):
        pass
    for p in roster:
        for acc in (getattr(p, "career_accolades", None) or []):
            if not isinstance(acc, dict):
                continue
            key = str(acc.get("award", "") or "").lower()
            if key not in ("player_of_month", "rookie_of_month"):
                continue
            if not any(y in str(acc.get("year", "") or "")
                       for y in season_years):
                continue
            label = ("NHL Player of the Month"
                     if key == "player_of_month"
                     else "NHL Rookie of the Month")
            lines.append(f"- {label}: {getattr(p, 'name', 'Unknown')} "
                         f"({acc.get('year', '')})")
    # All-Star selections from the league rosters.
    try:
        league = getattr(app, "league", None)
        rosters = getattr(league, "all_star_rosters", None) or {}
        sel = rosters.get(season_label(year)) or {}
        if sel:
            mine = {id(p) for p in roster}
            names = {getattr(p, "name", "") for p in roster}
            for _div, groups in sel.items():
                if not isinstance(groups, dict):
                    continue
                for slot in ("captain", "skaters", "goalies"):
                    ps = groups.get(slot)
                    if ps is None:
                        continue
                    if not isinstance(ps, list):
                        ps = [ps]
                    for sp in ps:
                        try:
                            if (id(sp) in mine
                                    or getattr(sp, "name", "") in names):
                                tag = " (All-Star captain)" if slot == "captain" \
                                    else " (All-Star)"
                                lines.append(
                                    f"- {getattr(sp, 'name', 'Unknown')}{tag}")
                        except Exception:
                            continue
    except Exception:
        pass
    return lines


def _ff_tag(p, team, name):
    """Append the fan-favourite marker when it applies."""
    try:
        from reputation_system import is_fan_favourite
        if is_fan_favourite(p, team):
            return f"{name} (fan favourite)"
    except Exception:
        pass
    return name


def _leadership_lines(team):
    """Current captain + alternates. Never claims the letter changed hands."""
    lines = []
    try:
        roster = list(getattr(team, "roster", None) or [])
        caps = [p for p in roster
                if str(getattr(p, "captaincy", "") or "").upper() == "C"]
        alts = [p for p in roster
                if str(getattr(p, "captaincy", "") or "").upper() == "A"]
        if caps:
            p = caps[0]
            name = getattr(p, "full_name", "Unknown")
            yrs = _num(getattr(p, "captain_tenure_years", 0))
            line = (f"Captain: {name} "
                    f"({yrs} year{'s' if yrs != 1 else ''} wearing the C)")
            if alts:
                anames = ", ".join(getattr(a, "full_name", "?") for a in alts[:2])
                line += f"; alternates: {anames}"
            lines.append(line)
        elif alts:
            anames = ", ".join(getattr(a, "full_name", "?") for a in alts[:2])
            lines.append(f"No captain named; alternates: {anames}.")
    except Exception:
        pass
    return lines


def _transaction_lines(app, team, year):
    """Dated trade wire involving this club this season. Logs only."""
    lines = []
    # A season spans two calendar years (Oct year -> Apr year+1), same as
    # the discipline beat: a March deadline deal belongs to this season.
    season_years = {str(year)}
    try:
        season_years.add(str(int(year) + 1))
    except (TypeError, ValueError):
        pass
    me = getattr(team, "team_name", "")
    try:
        gm = getattr(app, "game_manager", None)
        trades = list(getattr(gm, "trade_history", None) or [])
        mine = []
        for t in trades:
            try:
                if me and me not in (getattr(t, "team_a", ""),
                                     getattr(t, "team_b", "")):
                    continue
                tdate = str(getattr(t, "date", "") or "")
                if season_years and not any(y in tdate for y in season_years):
                    continue
                mine.append(t)
            except Exception:
                continue
        mine.sort(key=lambda t: str(getattr(t, "date", "") or ""),
                  reverse=True)
        for t in mine[:8]:
            summ = str(getattr(t, "summary", "") or "").strip()
            tdate = str(getattr(t, "date", "") or "")
            if summ:
                lines.append(f"- {tdate}: {summ}"[:160])
    except Exception:
        pass
    # Deadline-day activity log (no summaries there -- keep it brief).
    try:
        dm = getattr(app, "trade_deadline_manager", None)
        if dm is None:
            from trade_deadline_manager import get_deadline_manager
            dm = get_deadline_manager()
        for e in (getattr(dm, "trade_activity_log", None) or []):
            if not isinstance(e, dict):
                continue
            if me and me not in (e.get("teams_involved") or []):
                continue
            # Belt-and-braces: the log drains at the offseason rollover, but
            # never show a stale deadline entry from another season.
            ts = e.get("timestamp")
            if ts is not None and season_years:
                if not any(y in str(ts) for y in season_years):
                    continue
            teams = " vs ".join(x for x in (e.get("teams_involved") or [])
                                if x)
            npc = _num(e.get("players_count"))
            lines.append(f"- Deadline: {teams} ({npc} players moved)")
            if len(lines) >= 8:
                break
    except Exception:
        pass
    return lines[:8]


def _bench_lines(app):
    """Staff breakthrough headlines. Prefers the pre-drain snapshot."""
    try:
        news = getattr(app, "_season_review_staff_news", None)
        if not news:
            league = getattr(app, "league", None)
            news = getattr(league, "staff_breakthrough_news", None)
        return [f"- {str(m)}"[:160] for m in (news or [])[:6]
                if str(m or "").strip()]
    except Exception:
        return []

# ----------------------------------------------------------------------
# Four-corner season score: media / fans / owner / room
# ----------------------------------------------------------------------

def _media_score(pred_rank, rank):
    """100 = wildly exceeded the preseason poll; 0 = collapsed."""
    if not pred_rank or not rank:
        return None, "no preseason poll on file"
    diff = pred_rank - rank  # positive = beat the poll
    score = max(0, min(100, 60 + diff * 4))
    note = (f"picked {pred_rank}{_ord(pred_rank)}, finished {rank}{_ord(rank)}"
            + (f" ({diff:+d})" if diff else " (right on it)"))
    return score, note


def _fans_score(app, team, header, board_facts):
    """Synthesized: dynamics-feed tone + record vs expectation."""
    score, notes = 55.0, []
    try:
        from reputation_system import get_dynamics_feed
        feed = get_dynamics_feed(team, limit=40) or []
        ups = sum(1 for e in feed if e.get("tone") == "up")
        downs = sum(1 for e in feed if e.get("tone") == "down")
        total = ups + downs
        if total:
            score = 20 + 60 * (ups / total)
            notes.append(f"room/fan feed: {ups} cheers, {downs} groans")
    except Exception:
        pass
    # Expectation swing: making/missing the dance moves the building.
    try:
        if board_facts.get("won_cup"):
            score = min(100, score + 30)
            notes.append("a Cup parade buys a lot of love")
        elif board_facts.get("made_playoffs"):
            score = min(100, score + 10)
        else:
            score = max(0, score - 12)
            notes.append("missing the playoffs stings")
    except Exception:
        pass
    return round(score, 1), "; ".join(notes) or "quiet year in the stands"


def _owner_score(board_facts):
    """Straight from the board's own reckoning."""
    if not board_facts:
        return None, "no board review on file"
    exp = board_facts.get("expectation") or "?"
    delta = board_facts.get("delta", 0) or 0
    conf = board_facts.get("confidence")
    # delta is the confidence move; map -20..+20 -> 30..95
    score = max(0, min(100, 62 + float(delta) * 1.6))
    note = f"mandate was '{exp}'"
    if conf is not None:
        note += f"; confidence now {conf}/100 ({delta:+.0f})"
    return round(score, 1), note


def _room_score(team):
    try:
        chem = _num(getattr(team, "team_chemistry", 50))
        roster = team.roster or []
        avg_morale = (sum(_num(getattr(p, "morale", 70)) for p in roster)
                      / max(1, len(roster)))
        score = chem * 0.55 + avg_morale * 0.45
        return round(score, 1), f"chemistry {chem}/100, avg morale {avg_morale:.0f}"
    except Exception:
        return 50.0, "no room data"


# ----------------------------------------------------------------------
# Assembly + delivery
# ----------------------------------------------------------------------

def _origin_label(origin):
    o = str(origin or "").lower()
    if o == "regional":
        return "regional hatred"
    if o == "playoff":
        return "playoff history"
    if o == "declared":
        return "declared bad blood"
    if o == "trade":
        return "trade fallout"
    return o or "bad blood"


def _rivalry_lines(app, team, year):
    """Bad blood report: locked rivals / heating up / new this season.

    Locked = structural hate (user-declared, regional, or intensity >= 70):
    these barely cool off in decay. Heating up = simmering at 40-69.
    New = first declared within the last 12 months.
    """
    try:
        from reputation_system import get_rivalries_for
    except Exception:
        return []
    try:
        league = getattr(app, "league", None)
        rivalries = list(getattr(league, "rivalries", None) or [])
        mine = [r for r in get_rivalries_for(rivalries, team, 1)
                if isinstance(r, dict) and r.get("kind") == "team_team"]
    except Exception:
        return []
    if not mine:
        return ["- No real bad blood yet -- every game is just a game."]
    me = getattr(team, "team_name", "")
    try:
        today = getattr(app, "current_date", None)
        today = today.date() if hasattr(today, "date") else today
        if not hasattr(today, "year"):
            raise ValueError
    except Exception:
        today = date.today()
    recent_cutoff = date(today.year - 1, today.month, today.day)
    locked, heating, new = [], [], []
    for r in mine:
        other = r.get("b_name") if r.get("a_name") == me else r.get("a_name")
        inten = _num(r.get("intensity", 0))
        origin = _origin_label(r.get("origin"))
        story = str(r.get("story", "") or "").strip()
        snippet = (story[:72] + "...") if len(story) > 72 else story
        detail = f"{origin}" + (f" -- {snippet}" if snippet else "")
        try:
            rdate = date.fromisoformat(str(r.get("date", ""))[:10])
        except Exception:
            rdate = None
        is_recent = bool(rdate is not None and rdate >= recent_cutoff)
        if r.get("user_declared") or str(r.get("origin", "")).lower() == "regional" or inten >= 70:
            locked.append((other, inten, detail))
        elif is_recent:
            new.append((other, inten, detail))
        elif inten >= 40:
            heating.append((other, inten, detail))
    lines = []
    for other, inten, detail in locked[:4]:
        lines.append(f"- {other} ({inten}) -- LOCKED RIVAL: {detail}")
    for other, inten, detail in new[:3]:
        lines.append(f"- {other} ({inten}) -- new this season: {detail}")
    for other, inten, detail in heating[:3]:
        lines.append(f"- {other} ({inten}) -- heating up: {detail}")
    return lines


_NARRATIVE_KIND_LABELS = {
    "hot_seat": "Hot seat", "leadership": "Leadership", "goalie": "Crease",
    "trade_rumor": "Trade rumor", "prospect_watch": "Prospect watch",
    "trust_process": "Trust the process", "cup_window": "Cup window",
    "legacy_chase": "Legacy chase", "deadline_race": "Deadline race",
}


def _injury_lines(app, team, year):
    """IR/LTIR casualty list at season's end + relief used. Never raises."""
    lines = []
    try:
        import ir_system as _ir
    except Exception:
        return []
    try:
        cur = getattr(app, "current_date", None)
        ltir = _ir.ltir_players(team)
        irp = _ir.ir_players(team)
        if not ltir and not irp:
            return []
        def _nm(p):
            return str(getattr(p, "full_name", None)
                       or getattr(p, "last_name", "Unknown"))
        for p in sorted(ltir, key=lambda p: _ir.days_on_ir(p, cur),
                        reverse=True)[:4]:
            inj = str(getattr(p, "injury_type", "") or "injury")
            days = _ir.days_on_ir(p, cur)
            lines.append(f"- {_nm(p)} -- LTIR ({inj}, {days}d on reserve).")
        for p in sorted(irp, key=lambda p: _ir.days_on_ir(p, cur),
                        reverse=True)[:3]:
            inj = str(getattr(p, "injury_type", "") or "injury")
            days = _ir.days_on_ir(p, cur)
            lines.append(f"- {_nm(p)} -- IR ({inj}, {days}d on reserve).")
        try:
            relief = int(_ir.ltir_relief(team) or 0)
        except Exception:
            relief = 0
        if relief > 0:
            lines.append(f"LTIR cap relief carried at year's end: ${relief:,}.")
    except Exception:
        pass
    return lines


def _storyline_lines(app, team, year):
    """Season-long narrative arcs and how they ended. Never raises."""
    lines = []
    try:
        league = getattr(app, "league", None)
        narrs = [n for n in (getattr(league, "media_narratives", None) or [])
                 if getattr(n, "team_name", "") == team.team_name]
        if not narrs:
            return []
        ranked = sorted(narrs,
                        key=lambda n: float(getattr(n, "heat", 0) or 0),
                        reverse=True)[:4]
        for n in ranked:
            title = str(getattr(n, "title", "") or "").strip()
            if not title:
                continue
            kind = str(getattr(n, "kind", "") or "")
            label = _NARRATIVE_KIND_LABELS.get(kind, kind.replace("_", " "))
            heat = float(getattr(n, "heat", 0) or 0)
            if heat >= 60:
                tail = "still burning"
            elif heat >= 30:
                tail = "simmering into the offseason"
            else:
                tail = "fizzled out"
            prefix = f"{label}: " if label else ""
            lines.append(f"- {prefix}{title} -- {tail}.")
    except Exception:
        pass
    return lines


def _rivalry_watch_lines(app, team, year):
    """League's hottest feud + this club's key on-ice flashpoints.

    Complements BAD BLOOD REPORT (per-team heat detail) with the
    league-wide picture and the year's defining incidents.
    Never raises.
    """
    lines = []
    me = getattr(team, "team_name", "")
    try:
        league = getattr(app, "league", None)
        rivalries = list(getattr(league, "rivalries", None) or [])
        best = None
        for r in rivalries:
            try:
                if not isinstance(r, dict) or r.get("kind") != "team_team":
                    continue
                inten = _num(r.get("intensity", 0))
                if best is None or inten > best[0]:
                    a = str(r.get("a_name", ""))
                    b = str(r.get("b_name", ""))
                    if a and b:
                        best = (inten, a, b)
            except Exception:
                continue
        if best and best[0] >= 40:
            inten, a, b = best
            tag = "the league's fiercest feud" if {a, b} != {me} and me not in (a, b) else "your fiercest feud"
            lines.append(f"- Hottest rivalry ({inten:.0f}): {a} vs {b} -- {tag}.")
    except Exception:
        pass
    # Defining on-ice flashpoints from the ledger.
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app)
        kinds = {"brawl_game", "incident"}
        evs = [e for e in (led.events or [])
               if e.get("season") == year
               and me in (e.get("teams") or [])
               and e.get("kind") in kinds]
        evs.sort(key=lambda e: e.get("weight", 0), reverse=True)
        for e in evs[:2]:
            txt = (e.get("text") or "").strip()
            if txt:
                txt = (txt[:110] + "...") if len(txt) > 110 else txt
                lines.append(f"- Flashpoint: {txt}")
    except Exception:
        pass
    return lines


def _milestone_lines(app, team, year):
    """Records broken and career achievements. Never raises."""
    lines = []
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app)
        evs = [e for e in (led.events or [])
               if e.get("season") == year
               and team.team_name in (e.get("teams") or [])
               and e.get("kind") == "milestone"]
        evs.sort(key=lambda e: e.get("weight", 0), reverse=True)
        for e in evs[:5]:
            txt = (e.get("text") or "").strip()
            if txt:
                lines.append(f"- {txt}.")
        if not lines:
            return []
    except Exception:
        return []
    return lines


def _history_lines(app, team, year):
    """Where this season sits in franchise history. Never raises."""
    lines = []
    try:
        hist = getattr(app, "league_history", None)
        seasons = list(getattr(hist, "seasons", None) or []) if hist else []
        if not seasons:
            return []
        champ = prev_champ = None
        for s in seasons:
            try:
                y = int(s.get("year", 0) or 0)
            except Exception:
                continue
            if y == year:
                champ = s.get("champion")
            elif y == year - 1:
                prev_champ = s.get("champion")
        me = getattr(team, "team_name", "")
        if champ and prev_champ:
            if champ == prev_champ:
                lines.append(f"- Back-to-back: {champ} repeat as champions.")
            else:
                lines.append(f"- {prev_champ}'s reign ends; {champ} crowned.")
        elif champ:
            lines.append(f"- {champ} lift the Cup.")
        last_cup = None
        for s in sorted(seasons, key=lambda s: _num(s.get("year", 0)),
                        reverse=True):
            if s.get("champion") == me:
                try:
                    last_cup = int(s.get("year", 0) or 0)
                except Exception:
                    last_cup = None
                break
        if last_cup is None:
            lines.append("- Still chasing the franchise's first Cup.")
        else:
            drought = year - last_cup
            if drought <= 0:
                lines.append("- Champions. Enjoy it -- dynasties are rare.")
            elif drought == 1:
                lines.append(f"- Defending champions (won {last_cup}).")
            else:
                lines.append(f"- {drought} years since the {last_cup} Cup.")
    except Exception:
        pass
    return lines


def _club_board_facts(app, team, year):
    """Minimal season facts for a non-user club (Cup win flag).

    The user's club gets the full stashed board review; every other club
    still gets its own card with whatever the archives can prove.
    """
    facts = {}
    try:
        hist = getattr(app, "league_history", None)
        season = hist.get_season(year) if hist else None
        if season:
            facts["won_cup"] = season.get("champion") == team.team_name
    except Exception:
        pass
    return facts


def build_review(app, team=None):
    """Assemble every section. Returns {"subject", "lines", "scores"}.

    team defaults to the user's club; pass any NHL club to build that
    club's own card for its respective history.
    """
    team = team or getattr(app, "user_team", None)
    league = getattr(app, "league", None)
    if team is None or league is None:
        return None
    year = _num(getattr(league, "season_year", 0))
    label = season_label(year)
    standings = getattr(league, "standings", None) or {}
    predictions = getattr(league, "preseason_predictions", None) or {}
    if team is getattr(app, "user_team", None):
        board_facts = getattr(app, "_season_review_board", None) or {}
    else:
        board_facts = _club_board_facts(app, team, year)

    sections = []  # (title, lines)

    header, meta = _header_lines(team, standings, predictions, year)
    sections.append(("THE YEAR IN ONE LINE", header))

    leaders = _leadership_lines(team)
    if leaders:
        sections.append(("LEADERSHIP", leaders))

    story = _story_lines(app, team, year, board_facts)
    if story:
        sections.append(("STORY OF THE SEASON", story))

    mandate = _mandate_lines(app, team, board_facts)
    if mandate:
        sections.append(("MANDATE REPORT", mandate))

    blood = _rivalry_lines(app, team, year)
    if blood:
        sections.append(("BAD BLOOD REPORT", blood))

    rwatch = _rivalry_watch_lines(app, team, year)
    if rwatch:
        sections.append(("RIVALRY WATCH", rwatch))

    arcs = _storyline_lines(app, team, year)
    if arcs:
        sections.append(("SEASON STORYLINES", arcs))

    inj = _injury_lines(app, team, year)
    if inj:
        sections.append(("INJURY REPORT", inj))

    miles = _milestone_lines(app, team, year)
    if miles:
        sections.append(("MILESTONES", miles))

    hist = _history_lines(app, team, year)
    if hist:
        sections.append(("HISTORICAL CONTEXT", hist))

    discipline = _discipline_lines(app, team, year)
    if discipline:
        sections.append(("DISCIPLINE REPORT", discipline))

    out, tough = _standout_lines(team)
    if out:
        sections.append(("STOOD OUT", [f"- {l}" for l in out]))
    if tough:
        sections.append(("TOUGH GO", [f"- {l}" for l in tough]))

    rookies = _rookie_lines(app, team, year)
    if rookies:
        sections.append(("ROOKIE WATCH", [f"- {l}" for l in rookies]))

    awards = _award_lines(app, team, year)
    if awards:
        sections.append(("HARDWARE", [f"- {l}" for l in awards]))

    stars = _stars_lines(app, team, year)
    if stars:
        sections.append(("STARS & NODS", stars))

    prospects = _prospect_lines(team)
    if prospects:
        sections.append(("PIPELINE REPORT (rights held, non-NHL)", [f"- {l}" for l in prospects]))

    wire = _transaction_lines(app, team, year)
    if wire:
        sections.append(("TRANSACTION WIRE", wire))

    bench = _bench_lines(app)
    if bench:
        sections.append(("BEHIND THE BENCH", bench))

    # Four-corner score.
    scores = []
    ms, mn = _media_score(meta["pred_rank"], meta["rank"])
    if ms is not None:
        scores.append(("Media", ms, mn))
    fs, fn = _fans_score(app, team, meta, board_facts)
    scores.append(("Fans", fs, fn))
    os_, on = _owner_score(board_facts)
    if os_ is not None:
        scores.append(("Owner", os_, on))
    rs, rn = _room_score(team)
    scores.append(("Room", rs, rn))
    if scores:
        comp = sum(s for _, s, _ in scores) / len(scores)
        slines = [f"- {name}: {_grade(s)} ({s:.0f}) -- {note}"
                  for name, s, note in scores]
        slines.append(f"SEASON GRADE: {_grade(comp)} ({comp:.0f})")
        sections.append(("HOW THE SEASON NETTED OUT", slines))

    # Render.
    lines = [f"{label} SEASON REVIEW -- {team.team_name}", ""]
    for title, ls in sections:
        lines.append(title)
        lines.extend(ls)
        lines.append("")
    score_map = {n: s for n, s, _ in scores}
    if score_map:
        score_map["composite"] = sum(score_map.values()) / len(score_map)
    return {"subject": f"{label} Season Review: {team.team_name}",
            "lines": lines,
            "scores": score_map,
            "meta": meta, "year": year, "label": label}


def _record_season_stories(app, review):
    """One season_story ledger event per NHL club -- next year's lore."""
    try:
        from narrative_ledger import get_ledger
        led = get_ledger(app)
        league = app.league
        year = review["year"]
        standings = getattr(league, "standings", None) or {}
        predictions = getattr(league, "preseason_predictions", None) or {}
        for t in (getattr(league, "teams", None) or []):
            if getattr(t, "league_name", "") != "National Hockey League":
                continue
            try:
                st = standings.get(t.team_name, {})
                w = _num(st.get("W", 0))
                l = _num(st.get("L", 0))
                otl = _num(st.get("OTL", 0))
                pred = (predictions.get(t.team_name) or {}).get("rank")
                streak = _num(getattr(t, "longest_win_streak", 0))
                if t.team_name == getattr(app.user_team, "team_name", None):
                    headline = review["lines"][2] if len(review["lines"]) > 2 else ""
                elif w >= 45:
                    headline = f"{t.team_name} roll to {w} wins"
                elif w <= 30 and w > 0:
                    headline = f"{t.team_name} crater to {w} wins"
                elif streak >= 8:
                    headline = f"{t.team_name} rip off {streak} straight"
                else:
                    headline = f"{t.team_name} finish {w}-{l}-{otl}"
                led.record(kind="season_story", weight=SEASON_STORY_WEIGHT,
                           teams=[t.team_name], text=headline, season=year,
                           facts={"w": w, "l": l, "otl": otl,
                                  "predicted_rank": pred,
                                  "longest_win_streak": streak,
                                  **_season_story_extra_facts(app, t)})
            except Exception:
                continue
    except Exception:
        pass


def _season_story_extra_facts(app, team):
    """Enrich the season_story ledger event so next year's lore can
    reference this season's injuries, arcs, milestones and feuds.
    Never raises; returns {} on any failure."""
    facts = {}
    try:
        import ir_system as _ir
        try:
            facts["ltir_relief"] = int(_ir.ltir_relief(team) or 0)
        except Exception:
            pass
        try:
            facts["ir_count"] = len(_ir.ir_players(team))
            facts["ltir_count"] = len(_ir.ltir_players(team))
        except Exception:
            pass
    except Exception:
        pass
    try:
        league = getattr(app, "league", None)
        narrs = [n for n in (getattr(league, "media_narratives", None) or [])
                 if getattr(n, "team_name", "") == getattr(team, "team_name", "")]
        if narrs:
            top = max(narrs, key=lambda n: float(getattr(n, "heat", 0) or 0))
            facts["top_storyline_kind"] = str(getattr(top, "kind", "") or "")
            facts["top_storyline"] = str(getattr(top, "title", "") or "")[:120]
    except Exception:
        pass
    try:
        from narrative_ledger import get_ledger
        from reputation_system import get_rivalries_for
        led = get_ledger(app)
        me = getattr(team, "team_name", "")
        try:
            miles = sum(1 for e in (led.events or [])
                        if e.get("kind") == "milestone"
                        and me in (e.get("teams") or []))
            facts["milestones"] = miles
        except Exception:
            pass
        try:
            league = getattr(app, "league", None)
            rivalries = list(getattr(league, "rivalries", None) or [])
            mine = [r for r in get_rivalries_for(rivalries, team, 1)
                    if isinstance(r, dict) and r.get("kind") == "team_team"]
            if mine:
                top_r = max(mine, key=lambda r: _num(r.get("intensity", 0)))
                other = (top_r.get("b_name") if top_r.get("a_name") == me
                         else top_r.get("a_name"))
                facts["hottest_rival"] = str(other or "")
                facts["hottest_rival_heat"] = _num(top_r.get("intensity", 0))
        except Exception:
            pass
    except Exception:
        pass
    return facts


def _archive_review(team, review):
    """Store the card on the team for its own respective history.

    Keyed by season year so every season keeps its own card, readable
    from any later season (League History -> Season Reviews).
    """
    try:
        archive = getattr(team, "season_reviews", None)
        if archive is None:
            archive = {}
            team.season_reviews = archive
        archive[review["year"]] = {
            "season": review["year"],
            "label": review["label"],
            "lines": list(review["lines"]),
            "scores": dict(review["scores"]),
            "meta": dict(review["meta"]),
        }
    except Exception:
        pass


def _email_review(app, review):
    """Send the user's own card to their inbox."""
    from game_classes import EmailMessage
    msg = EmailMessage(
        sender="League Office",
        sender_type="League",
        subject=review["subject"],
        content="\n".join(review["lines"]),
        category="League",
        is_important=True,
        is_milestone=True,
        priority=3,
        game_date_sent=getattr(app, "current_date", None) or date.today(),
    )
    app.send_email_to_user(msg)


def deliver_season_review(app):
    """Build every club's card, email the user's, bank the season stories.

    Each NHL club's report is retained on that club's own history
    (team.season_reviews), so every season from here on stays readable
    from League History -> Season Reviews.

    Call BEFORE League.end_of_season() wipes per-season stats.
    """
    try:
        league = getattr(app, "league", None)
        user_team = getattr(app, "user_team", None)
        clubs = [t for t in (getattr(league, "teams", None) or [])
                 if getattr(t, "league_name", "") == "National Hockey League"]
        if not clubs and user_team is not None:
            clubs = [user_team]
        user_review = None
        for team in clubs:
            try:
                review = build_review(app, team)
            except Exception:
                continue
            if not review:
                continue
            _archive_review(team, review)
            if team is user_team:
                user_review = review
                # Last-season snapshot for every affiliated player (pre-wipe).
                try:
                    stash_last_season_lines(
                        list(getattr(team, "roster", None) or [])
                        + list(getattr(team, "ahl_roster", None) or [])
                        + list(getattr(team, "prospects", None) or []))
                except Exception:
                    pass
        if user_review is None:
            return False
        _record_season_stories(app, user_review)
        _email_review(app, user_review)
        return True
    except Exception:
        return False
if __name__ == "__main__":  # pd-standalone: import check only, never sims
    import sys as _pd_sys
    _pd_sys.exit(0)


