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
        ovrs = sorted((p.overall_rating() for p in (team.roster or [])
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
    # Playoff run from the stashed board facts.
    try:
        if board_facts.get("won_cup"):
            lines.append("STANLEY CUP CHAMPIONS.")
        elif board_facts.get("playoff_rounds_won"):
            r = board_facts["playoff_rounds_won"]
            lines.append(f"Won {r} playoff round{'' if r == 1 else 's'}.")
        elif board_facts.get("made_playoffs"):
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
    skaters = [p for p in (team.roster or [])
               if not _is_goalie(p) and _num(getattr(p, "games_played", 0)) >= 20]
    goalies = [p for p in (team.roster or [])
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
        name = getattr(p, "name", "Unknown")
        line = f"{name}: {_skater_line(p)}"
        if d is not None and d >= 8:
            line += f" ({d:+.0f} vs career pace -- career year)"
        elif getattr(p, "is_rookie", False):
            line += " (rookie)"
        out.append(line)
    for p in sorted(goalies,
                    key=lambda p: float(getattr(p, "save_percentage", 0) or 0),
                    reverse=True)[:1]:
        name = getattr(p, "name", "Unknown")
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
            name = getattr(p, "name", "Unknown")
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
                or r.get("player") in (team.roster or [])][:3]
        for r in mine:
            p = r["player"]
            name = getattr(p, "name", "Unknown")
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
        my_names = {getattr(p, "name", "") for p in (team.roster or [])}
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
                name = getattr(p, "name", "Unknown")
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

def build_review(app):
    """Assemble every section. Returns {"subject", "lines", "scores"}."""
    team = getattr(app, "user_team", None)
    league = getattr(app, "league", None)
    if team is None or league is None:
        return None
    year = _num(getattr(league, "season_year", 0))
    label = season_label(year)
    standings = getattr(league, "standings", None) or {}
    predictions = getattr(league, "preseason_predictions", None) or {}
    board_facts = getattr(app, "_season_review_board", None) or {}

    sections = []  # (title, lines)

    header, meta = _header_lines(team, standings, predictions, year)
    sections.append(("THE YEAR IN ONE LINE", header))

    story = _story_lines(app, team, year, board_facts)
    if story:
        sections.append(("STORY OF THE SEASON", story))

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

    prospects = _prospect_lines(team)
    if prospects:
        sections.append(("PIPELINE REPORT (rights held, non-NHL)", [f"- {l}" for l in prospects]))

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
    return {"subject": f"{label} Season Review: {team.team_name}",
            "lines": lines,
            "scores": {n: s for n, s, _ in scores},
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
                                  "longest_win_streak": streak})
            except Exception:
                continue
    except Exception:
        pass


def deliver_season_review(app):
    """Build the review, send it to the inbox, bank the season stories.

    Call BEFORE League.end_of_season() wipes per-season stats.
    """
    try:
        review = build_review(app)
        if not review:
            return False
        # Last-season snapshot for every affiliated player (pre-wipe).
        try:
            team = app.user_team
            stash_last_season_lines(
                list(team.roster or []) + list(getattr(team, "ahl_roster", None) or [])
                + list(getattr(team, "prospects", None) or []))
        except Exception:
            pass
        _record_season_stories(app, review)

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
        return True
    except Exception:
        return False
