# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""D41 Phase 2: the AHL as a REAL background league -- no bloat.

Phase 1 (ahl_system) deliberately kept the AHL as a stat ledger plus
abstract daily standings matchups. Phase 2 advances it to a full league:

  - a real 48-game/team schedule (30 teams -> 720 games, Oct-Apr),
  - ultra-fast team-vs-team game sims (no PBP, no visualizer, no
    narratives),
  - real standings from real scheduled games,
  - a Calder Cup playoff (top 16, best-of-5 series).

Muck's directive: "simming in the background much less important than
nhl sims. we dont want bloat in our game from less priority ahl games".
So everything here is background-cheap: a full AHL season sims in well
under a second, and nothing here touches the NHL roster machinery.

ROSTER ALIASING (the no-conflict guarantee):

  - AHL teams are the 30 level-2 Team shells in league.teams. They own
    NO players of their own.
  - An AHL club's game roster is ALWAYS read dynamically as
    ``ahl_team.parent_team.ahl_roster`` -- the NHL team's farm list,
    the SOLE source of truth. We never copy it, never cache it, never
    migrate players. Callups/senddowns change the list in place and
    the AHL club's lineup updates automatically.
  - Waivers, cap, development, and the per-player stat ledger
    (ahl_system.simulate_ahl_day) are untouched.

PERSISTENCE: everything lives as additive attributes on the league
(pickle saves carry them automatically). Old saves are backfilled
lazily: the first daily tick generates a fresh schedule.

Never raises: every public entry point is try/except guarded.
"""

import math
import random
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# League shape constants
# ---------------------------------------------------------------------------

# 48 games/team keeps it light (real AHL plays 72; Muck: "keep it light").
GAMES_PER_TEAM = 48
# AHL regular-season window mirrors the stat ledger's window in main.py.
SEASON_START_MONTH, SEASON_START_DAY = 10, 1
SEASON_END_MONTH, SEASON_END_DAY = 4, 20
# Calder Cup: top 16 by points, best-of-5 series, 4 rounds.
CALDER_CUP_TEAMS = 16
SERIES_WINS_NEEDED = 3

_AHL_LEAGUE_NAMES = ("American Hockey League",)


# ---------------------------------------------------------------------------
# Team discovery / roster aliasing
# ---------------------------------------------------------------------------

def _is_ahl_shell(team):
    """True for the level-2 AHL Team shells (not NHL clubs)."""
    try:
        if getattr(team, "league_name", "") in _AHL_LEAGUE_NAMES:
            return True
        return int(getattr(team, "league_level", 1) or 1) == 2
    except Exception:
        return False


def ahl_team_list(league):
    """The 30 AHL clubs in stable league.teams order. Never raises."""
    try:
        teams = getattr(league, "teams", None) or []
        return [t for t in teams if _is_ahl_shell(t)]
    except Exception:
        return []


def get_ahl_roster(ahl_team):
    """An AHL club's game roster: the parent NHL club's ``ahl_roster``.

    Read DYNAMICALLY every call -- the same list object the NHL roster
    machinery owns. Never copied, never cached, never migrated. Returns
    [] when there is no parent (never raises).
    """
    try:
        parent = getattr(ahl_team, "parent_team", None)
        if parent is None:
            return []
        roster = getattr(parent, "ahl_roster", None)
        return roster if roster is not None else []
    except Exception:
        return []


def _team_strength(ahl_team):
    """Background-fidelity team strength: avg overall of the farm roster."""
    try:
        total, n = 0.0, 0
        for p in get_ahl_roster(ahl_team) or []:
            try:
                total += float(p.overall_rating())
                n += 1
            except Exception:
                continue
        return (total / n) if n else 65.0
    except Exception:
        return 65.0


# ---------------------------------------------------------------------------
# Schedule
# ---------------------------------------------------------------------------

def _season_bounds(season_year):
    """(first_day, last_day) of the AHL regular season for a season_year."""
    try:
        sy = int(season_year)
    except (TypeError, ValueError):
        from datetime import date as _d
        sy = _d.today().year
    return (date(sy, SEASON_START_MONTH, SEASON_START_DAY),
            date(sy + 1, SEASON_END_MONTH, SEASON_END_DAY))


def _season_label(season_year):
    try:
        y = int(season_year)
        return f"{y}-{str(y + 1)[-2:]}"
    except (TypeError, ValueError):
        return "Season"


def _round_robin_rounds(n_teams, rng):
    """Circle-method rounds; each round every team plays exactly once.

    Returns a list of rounds; each round is a list of (home_idx, away_idx)
    pairs over the 0..n_teams-1 index space. Handles odd counts with a
    bye (pairings against -1 are dropped by the caller).
    """
    order = list(range(n_teams))
    rng.shuffle(order)
    if n_teams % 2:
        order.append(-1)
    m = len(order)
    rounds = []
    arr = order[:]
    for r in range(m - 1):
        pairs = []
        for i in range(m // 2):
            a, b = arr[i], arr[m - 1 - i]
            if a == -1 or b == -1:
                continue  # bye
            # Alternate who hosts so home/away balance across the leg.
            pairs.append((a, b) if r % 2 == 0 else (b, a))
        rounds.append(pairs)
        # Rotate, keeping the first slot fixed.
        arr = [arr[0]] + [arr[-1]] + arr[1:-1]
    return rounds


def generate_ahl_schedule(league):
    """Build a fresh 48-game/team schedule for ``league.season_year``.

    30 teams x 48 / 2 = 720 games, spread Oct 1 - Apr 20 across 48
    "rounds" (one full 29-round home/away-balanced round-robin plus a
    19-round second leg with flipped venues). Stored on the league as a
    list of ``(date_str, home_ahl_idx, away_ahl_idx)`` tuples, with the
    season stamp, fresh standings, an empty played-set, and a cleared
    Calder Cup guard. Deterministic per season_year (seeded locally, so
    the global RNG stream is untouched).

    Resets standings because a new schedule is a new season. Never
    raises.
    """
    try:
        teams = ahl_team_list(league)
        n = len(teams)
        if n < 2:
            return False
        try:
            sy = int(getattr(league, "season_year", None))
        except (TypeError, ValueError):
            from datetime import date as _d
            sy = _d.today().year

        rng = random.Random(sy * 7919 + 13)
        rounds = _round_robin_rounds(n, rng)

        # Second leg: top every team up to exactly GAMES_PER_TEAM (48 =
        # 29 + 19 for the standard 30-club shape), venues flipped. Extra
        # rounds are added one at a time so the count lands exactly on
        # 48 regardless of club-count parity (odd counts get byes).
        all_rounds = list(rounds)

        def _per_team_count(rds):
            return sum(1 for rd in rds for (_a, _b) in rd) * 2 // max(n, 1)

        leg_seed = 0
        while _per_team_count(all_rounds) < GAMES_PER_TEAM and leg_seed <= 8:
            leg = _round_robin_rounds(
                n, random.Random(sy * 104729 + 7 + leg_seed * 101))
            leg_seed += 1
            for rd in leg:
                if _per_team_count(all_rounds) >= GAMES_PER_TEAM:
                    break
                all_rounds.append([(b, a) for (a, b) in rd])

        first, last = _season_bounds(sy)
        total_days = max(1, (last - first).days)
        schedule = []
        for r, rd in enumerate(all_rounds):
            day = first + timedelta(days=int(r * total_days / len(all_rounds)))
            dstr = day.isoformat()
            for (h, a) in rd:
                if 0 <= h < n and 0 <= a < n and h != a:
                    schedule.append((dstr, h, a))

        league.ahl_schedule = schedule
        league.ahl_schedule_season = sy
        league.ahl_schedule_label = _season_label(sy)
        league.ahl_standings = {}
        league.ahl_played = set()
        league.ahl_results = []  # ring buffer of recent finals (UI scores tab)
        league.ahl_calder_done = None
        league.ahl_bracket = None
        return True
    except Exception:
        return False


def ahl_schedule_active(league):
    """True when a Phase 2 schedule is live for the league's season.

    Backfills on old saves / season rollover: if the schedule is missing
    or stamped for a different season_year, a fresh one is generated.
    Returns False only when generation fails (<2 AHL clubs, garbage
    league) -- callers fall back to Phase 1's abstract standings day.
    Never raises.
    """
    try:
        sched = getattr(league, "ahl_schedule", None)
        try:
            sy = int(getattr(league, "season_year", None))
        except (TypeError, ValueError):
            sy = None
        stamped = getattr(league, "ahl_schedule_season", None)
        teams = ahl_team_list(league)
        if (isinstance(sched, list) and len(sched) > 0
                and stamped == sy and len(teams) >= 2):
            return True
        # Missing or stale -> (re)generate.
        return bool(generate_ahl_schedule(league))
    except Exception:
        return False


def backfill_ahl_league(league):
    """Explicit old-save backfill: generate a schedule if none is live.

    Idempotent -- a live schedule is left alone. Never raises.
    """
    try:
        if ahl_schedule_active(league):
            return True
        return bool(generate_ahl_schedule(league))
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Ultra-fast game sim (background only: no PBP, no visualizer, no narrative)
# ---------------------------------------------------------------------------

def _poisson(lam):
    """Small-lambda Poisson sample (Knuth)."""
    try:
        if lam <= 0:
            return 0
        l = math.exp(-lam)
        k, p = 0, 1.0
        while p > l:
            k += 1
            p *= random.random()
        return k - 1
    except Exception:
        return 0


def simulate_ahl_game(home_team, away_team):
    """Sim one AHL game. Returns (home_score, away_score, went_to_ot).

    Team strength = avg overall of the parent club's ahl_roster (read
    live via get_ahl_roster). Poisson-ish goals around a ~3.05 league
    average, scaled by the strength gap, small home-ice edge. Ties go
    to OT (winner +1, loser gets the OTL point). Target <0.001s/game.
    Never raises -- worst case returns a plausible 3-2 final.
    """
    try:
        hs = _team_strength(home_team)
        aws = _team_strength(away_team)
        diff = (hs - aws) + 0.35  # small home-ice edge
        hxg = max(0.6, 3.05 + diff * 0.11)
        axg = max(0.6, 3.05 - diff * 0.11)
        hg = _poisson(hxg)
        ag = _poisson(axg)
        ot = False
        if hg == ag:
            ot = True
            # OT winner weighted by the strength gap (Elo-lite).
            p_home = 1.0 / (1.0 + 10 ** (-diff / 6.0))
            if random.random() < p_home:
                hg += 1
            else:
                ag += 1
        return int(hg), int(ag), bool(ot)
    except Exception:
        return 3, 2, False


# ---------------------------------------------------------------------------
# Standings (real games -> real records)
# ---------------------------------------------------------------------------

_RECORD_KEYS = ("w", "l", "otl", "pts", "gf", "ga", "gp")


def _ensure_standings(league):
    """The league's Phase 2 standings dict: {ahl_idx: record}. Idempotent."""
    try:
        st = getattr(league, "ahl_standings", None)
        if not isinstance(st, dict):
            st = {}
            league.ahl_standings = st
        return st
    except Exception:
        return {}


def _rec(st, idx):
    rec = st.get(idx)
    if not isinstance(rec, dict):
        rec = {k: 0 for k in _RECORD_KEYS}
        st[idx] = rec
    else:
        for k in _RECORD_KEYS:
            if k not in rec:
                rec[k] = 0
    return rec


def update_ahl_standings(league, home_idx, away_idx, home_score, away_score,
                         went_ot=False):
    """Apply one final score to the league's AHL standings.

    2 pts for a win; OT loser gets 1 pt (OTL). Regulation loser gets 0.
    GF/GA and GP move for both clubs. Never raises.
    """
    try:
        st = _ensure_standings(league)
        hr, ar = _rec(st, home_idx), _rec(st, away_idx)
        hs, aws = int(home_score), int(away_score)
        hr["gp"] += 1
        ar["gp"] += 1
        hr["gf"] += hs
        hr["ga"] += aws
        ar["gf"] += aws
        ar["ga"] += hs
        if hs == aws:
            # Shouldn't happen (OT always breaks ties) -- treat as draw.
            hr["otl"] += 1
            ar["otl"] += 1
            hr["pts"] += 1
            ar["pts"] += 1
            return True
        winner, loser = (hr, ar) if hs > aws else (ar, hr)
        winner["w"] += 1
        winner["pts"] += 2
        if went_ot:
            loser["otl"] += 1
            loser["pts"] += 1
        else:
            loser["l"] += 1
        return True
    except Exception:
        return False


def _sort_key(item):
    idx, rec = item
    try:
        return (int(rec.get("pts", 0)), int(rec.get("w", 0)),
                int(rec.get("gf", 0)) - int(rec.get("ga", 0)),
                int(rec.get("gf", 0)))
    except Exception:
        return (0, 0, 0, 0)


def get_ahl_standings(league):
    """Sorted Phase 2 standings: [(ahl_idx, record)] by pts, W, GD, GF.

    Every AHL club appears, even at 0 GP. Never raises.
    """
    try:
        st = _ensure_standings(league)
        teams = ahl_team_list(league)
        rows = [(i, _rec(st, i)) for i in range(len(teams))]
        rows.sort(key=_sort_key, reverse=True)
        return rows
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Results & schedule queries (UI: scores tab, team view)
# ---------------------------------------------------------------------------

_AHL_RESULTS_CAP = 120  # ring buffer: enough for ~2 weeks of daily scores


def _record_result(league, date_str, home_idx, away_idx, home_score,
                   away_score, went_ot=False):
    """Append one final to the league's recent-results ring buffer."""
    try:
        buf = getattr(league, "ahl_results", None)
        if not isinstance(buf, list):
            buf = []
            league.ahl_results = buf
        buf.append({
            "date": str(date_str or ""),
            "home": int(home_idx), "away": int(away_idx),
            "home_score": int(home_score), "away_score": int(away_score),
            "ot": bool(went_ot),
        })
        while len(buf) > _AHL_RESULTS_CAP:
            del buf[0]
        return True
    except Exception:
        return False


def get_ahl_recent_results(league, n=15):
    """Newest-first list of recent AHL finals (dicts). Never raises."""
    try:
        buf = getattr(league, "ahl_results", None) or []
        return list(reversed(buf[-n:]))
    except Exception:
        return []


def get_ahl_upcoming(league, current_date, n=15):
    """Next n unplayed scheduled games on/after current_date.

    Returns dicts: date, home_idx, away_idx, home_name, away_name.
    Never raises.
    """
    try:
        sched = getattr(league, "ahl_schedule", None) or []
        played = getattr(league, "ahl_played", None)
        if not isinstance(played, set):
            played = set()
        today = _datestr(current_date)
        teams = ahl_team_list(league)
        out = []
        for i, game in enumerate(sched):
            try:
                if i in played:
                    continue
                dstr, hi, ai = game[0], int(game[1]), int(game[2])
                if today and dstr < today:
                    continue
                if not (0 <= hi < len(teams) and 0 <= ai < len(teams)):
                    continue
                out.append({
                    "date": dstr, "home_idx": hi, "away_idx": ai,
                    "home_name": _tname(teams, hi),
                    "away_name": _tname(teams, ai),
                })
                if len(out) >= n:
                    break
            except Exception:
                continue
        return out
    except Exception:
        return []


def get_ahl_team_schedule(league, ahl_idx, current_date, n=10):
    """Upcoming games for one AHL club (by ahl_team_list index)."""
    try:
        import ahl_league as _self
        sched = getattr(league, "ahl_schedule", None) or []
        played = getattr(league, "ahl_played", None)
        if not isinstance(played, set):
            played = set()
        today = _datestr(current_date)
        teams = ahl_team_list(league)
        out = []
        for i, game in enumerate(sched):
            try:
                if i in played:
                    continue
                dstr, hi, ai = game[0], int(game[1]), int(game[2])
                if hi != ahl_idx and ai != ahl_idx:
                    continue
                if today and dstr < today:
                    continue
                opp = ai if hi == ahl_idx else hi
                out.append({
                    "date": dstr,
                    "opponent": _tname(teams, opp),
                    "home": hi == ahl_idx,
                })
                if len(out) >= n:
                    break
            except Exception:
                continue
        return out
    except Exception:
        return []


def _tname(teams, idx):
    """AHL club display name by index. Never raises."""
    try:
        t = teams[idx]
        name = getattr(t, "team_name", None)
        if name:
            return str(name)
        parent = getattr(t, "parent_team", None)
        pname = getattr(parent, "team_name", "") if parent else ""
        return f"{pname} (AHL)" if pname else f"AHL club {idx}"
    except Exception:
        return f"AHL club {idx}"


# ---------------------------------------------------------------------------
# Daily hook: sim today's scheduled games
# ---------------------------------------------------------------------------

def _datestr(d):
    try:
        if hasattr(d, "isoformat"):
            return d.isoformat()[:10]
        s = str(d or "")
        return s[:10]
    except Exception:
        return ""


def simulate_ahl_scheduled_day(league, current_date):
    """Sim every scheduled AHL game dated on/before today that hasn't run.

    Called from the daily maintenance path (next to
    ahl_system.simulate_ahl_day, whose per-player stat rolls are
    untouched). Catch-up safe: if days were skipped, all unplayed games
    up to today run. When the last scheduled game finishes, the Calder
    Cup trigger is checked. Returns games simmed. Never raises.
    """
    try:
        if not ahl_schedule_active(league):
            return 0
        sched = getattr(league, "ahl_schedule", None) or []
        played = getattr(league, "ahl_played", None)
        if not isinstance(played, set):
            played = set()
            league.ahl_played = played
        teams = ahl_team_list(league)
        if len(teams) < 2:
            return 0
        today = _datestr(current_date)
        if not today:
            return 0
        n = len(teams)
        simmed = 0
        for i, game in enumerate(sched):
            try:
                if i in played:
                    continue
                dstr, hi, ai = game[0], int(game[1]), int(game[2])
                if dstr > today:
                    continue
                if not (0 <= hi < n and 0 <= ai < n and hi != ai):
                    played.add(i)  # corrupt entry: skip forever
                    continue
                hs, aws, ot = simulate_ahl_game(teams[hi], teams[ai])
                update_ahl_standings(league, hi, ai, hs, aws, ot)
                played.add(i)
                simmed += 1
                # Record the final for the UI scores tab (ring buffer).
                try:
                    _record_result(league, dstr, hi, ai, hs, aws, ot)
                except Exception:
                    pass
            except Exception:
                continue
        if len(played) >= len(sched) and len(sched) > 0:
            try:
                maybe_run_calder_cup(league, current_date)
            except Exception:
                pass
        return simmed
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Calder Cup playoffs
# ---------------------------------------------------------------------------

def _sim_series(home_idx, away_idx, teams, wins_needed=SERIES_WINS_NEEDED):
    """Best-of-5 series, 2-2-1 home format (higher seed hosts 1,2,5).

    Returns (winner_idx, loser_idx, games_played). Never raises.
    """
    try:
        hw = aw = gp = 0
        # Game slots: higher seed hosts games 1, 2, 5.
        while hw < wins_needed and aw < wins_needed and gp < 7:
            gp += 1
            higher_home = gp in (1, 2, 5)
            h, a = (home_idx, away_idx) if higher_home else (away_idx, home_idx)
            try:
                hs, aws, _ot = simulate_ahl_game(teams[h], teams[a])
            except Exception:
                hs, aws = 3, 2
            if (hs > aws and h == home_idx) or (aws > hs and a == home_idx):
                hw += 1
            else:
                aw += 1
        if hw >= wins_needed:
            return home_idx, away_idx, gp
        if aw >= wins_needed:
            return away_idx, home_idx, gp
        # Defensive: award it to the higher seed.
        return home_idx, away_idx, gp
    except Exception:
        return home_idx, away_idx, 3


def _bracket_pairings(seeds):
    """First-round pairings for 16 seeds: 1v16, 8v9, 4v13, 5v12, ..."""
    order = [0, 15, 7, 8, 3, 12, 4, 11, 1, 14, 6, 9, 2, 13, 5, 10]
    return [(seeds[order[i]], seeds[order[i + 1]])
            for i in range(0, 16, 2)]


def run_calder_cup(league):
    """Run the Calder Cup: top 16 by points, 4 rounds, best-of-5.

    Records the champion on the league (``ahl_champions`` history +
    ``ahl_bracket``) and posts one headline to the user's inbox. The
    ``ahl_calder_done`` guard makes it once-per-season. Returns a dict
    with champion/runner-up info, or None. Never raises.
    """
    try:
        teams = ahl_team_list(league)
        if len(teams) < CALDER_CUP_TEAMS:
            return None
        try:
            sy = int(getattr(league, "season_year", None))
        except (TypeError, ValueError):
            from datetime import date as _d
            sy = _d.today().year
        label = getattr(league, "ahl_schedule_label", None) or _season_label(sy)
        if getattr(league, "ahl_calder_done", None) == label:
            return None

        standings = get_ahl_standings(league)
        seeds = [idx for idx, _rec in standings[:CALDER_CUP_TEAMS]]
        if len(seeds) < CALDER_CUP_TEAMS:
            return None

        bracket_rounds = []
        alive = _bracket_pairings(seeds)
        champion = runner_up = None
        for rnd in range(4):
            winners = []
            rnd_results = []
            for (hi, ai) in alive:
                w, l, gp = _sim_series(hi, ai, teams)
                winners.append(w)
                rnd_results.append({"home": hi, "away": ai,
                                    "winner": w, "games": gp})
                if rnd == 3:
                    champion, runner_up = w, l
            bracket_rounds.append(rnd_results)
            # Fixed bracket: winner of series 0 faces winner of series 1...
            alive = [(winners[i], winners[i + 1])
                     for i in range(0, len(winners) - 1, 2)]

        def _tname(i):
            try:
                return str(getattr(teams[i], "team_name", f"AHL club {i}"))
            except Exception:
                return f"AHL club {i}"

        def _pname(i):
            try:
                p = getattr(teams[i], "parent_team", None)
                return str(getattr(p, "team_name", "")) if p else ""
            except Exception:
                return ""

        info = {"season": label,
                "champion_idx": champion,
                "champion": _tname(champion),
                "parent_club": _pname(champion),
                "runner_up": _tname(runner_up)}
        league.ahl_bracket = {"season": label, "rounds": bracket_rounds,
                              "champion_idx": champion,
                              "runner_up_idx": runner_up}
        hist = getattr(league, "ahl_champions", None)
        if not isinstance(hist, list):
            hist = []
            league.ahl_champions = hist
        hist.append(info)
        league.ahl_calder_done = label

        # Trophy case: stamp the Cup onto the champion roster + AHL staff
        # so it follows them through their individual histories.
        try:
            _bank_calder_accolades(teams[champion], label)
        except Exception:
            pass

        # The champion headline: one inbox note for the user. Light by
        # design -- no per-series narratives.
        try:
            _post_calder_headline(league, info)
        except Exception:
            pass
        return info
    except Exception:
        return None


def _bank_calder_accolades(ahl_team, season_label):
    """Bank 'calder_cup' accolades on the champion club's roster and AHL
    staff -- the players' and coaches' permanent trophy case (their
    individual histories, same mechanism as Stanley Cup banking).

    The roster is the parent NHL club's live ``ahl_roster`` (playoff
    roster at championship time); the staff are the parent club's
    ``assignment == "ahl"`` staff (AHL head coach, assistants, goalie
    coach, GM). Idempotent: ``bank_accolade`` dedupes on (award, year).
    Never raises.
    """
    try:
        import accolades as _acc
    except Exception:
        return
    try:
        for p in get_ahl_roster(ahl_team) or []:
            try:
                _acc.bank_accolade(p, "calder_cup", season_label)
            except Exception:
                continue
    except Exception:
        pass
    try:
        parent = getattr(ahl_team, "parent_team", None)
        for stf in getattr(parent, "staff", None) or []:
            try:
                if str(getattr(stf, "assignment", "") or "").lower() != "ahl":
                    continue
                _acc.bank_accolade(stf, "calder_cup", season_label)
            except Exception:
                continue
    except Exception:
        pass


def _post_calder_headline(league, info):
    """One 'champion crowned' inbox note for the user's club."""
    try:
        user_team = None
        for t in getattr(league, "teams", None) or []:
            try:
                if getattr(t, "is_user_team", False):
                    user_team = t
                    break
            except Exception:
                continue
        if user_team is None:
            return
        inbox = getattr(user_team, "inbox", None)
        if inbox is None:
            return
        from game_classes import EmailMessage
        champ = info.get("champion", "AHL club")
        parent = info.get("parent_club", "")
        runner = info.get("runner_up", "")
        season = info.get("season", "")
        body = (f"The {champ} are Calder Cup champions ({season}), "
                f"defeating the {runner} in the final."
                + (f" The {champ} are the top affiliate of the {parent}."
                   if parent else ""))
        msg = EmailMessage(
            sender="AHL Wire", sender_type="Media",
            subject=f"🏆 {champ} win the Calder Cup",
            content=body, category="League", priority=2)
        try:
            inbox.add_message(msg)
        except Exception:
            pass
    except Exception:
        pass


def maybe_run_calder_cup(league, current_date):
    """Fire the Calder Cup once the AHL season is over.

    Triggers when every scheduled game has been played OR the date is
    past the AHL regular-season end (Apr 20). Once-per-season via the
    ``ahl_calder_done`` guard. Never raises.
    """
    try:
        try:
            sy = int(getattr(league, "season_year", None))
        except (TypeError, ValueError):
            return None
        label = getattr(league, "ahl_schedule_label", None) or _season_label(sy)
        if getattr(league, "ahl_calder_done", None) == label:
            return None
        sched = getattr(league, "ahl_schedule", None) or []
        played = getattr(league, "ahl_played", None) or set()
        complete = len(sched) > 0 and len(played) >= len(sched)
        past_end = False
        try:
            _first, last = _season_bounds(sy)
            today = _datestr(current_date)
            past_end = bool(today) and today > last.isoformat()
        except Exception:
            pass
        # Never crown a champion from a schedule nobody played (e.g. a
        # save first opened mid-offseason): the Cup needs real games.
        if not complete and len(played) == 0:
            return None
        if complete or past_end:
            return run_calder_cup(league)
        return None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Season rollover + backfill entry points
# ---------------------------------------------------------------------------

def ahl_season_rollover(league):
    """Roll the AHL league into a fresh season.

    Called (guarded) from League.end_of_season after season_year has
    incremented: first a backstop Calder Cup for the season just ended
    (in case the daily trigger never fired), then a fresh 48-game
    schedule + zeroed standings for the new season. Never raises.
    """
    try:
        # Backstop: crown a champion from the old season's standings
        # before the reset wipes them. Only when real games were played
        # (a schedule generated mid-offseason has none -- no champion).
        try:
            old_label = getattr(league, "ahl_schedule_label", None)
            old_played = getattr(league, "ahl_played", None) or set()
            if (old_label is not None
                    and getattr(league, "ahl_calder_done", None) != old_label
                    and getattr(league, "ahl_schedule", None)
                    and len(old_played) > 0):
                run_calder_cup(league)
        except Exception:
            pass
        generate_ahl_schedule(league)
        return True
    except Exception:
        return False
