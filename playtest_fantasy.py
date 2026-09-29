#!/usr/bin/env python3
"""playtest_fantasy.py -- headless fantasy draft for the playtest campaign.

run_fantasy_draft(seed) -> dict with league, teams, user_team, gm (a
GameManager.__new__ stub with the real captaincy helpers bound), and an
audit report.

Replicates the production flow headlessly:
  * FantasyDraftManager draft (all-AI picks) + the view-side roster
    assignment (ovr>=40 -> roster, >=35 -> AHL, else prospects)
  * complete_draft() backstop: strip letters league-wide, stamp
    _fantasy_draft_captaincy_deferred
  * first-preseason-game-day phase check via the REAL
    GameManager._opening_night_captaincy_check per team; the armed user
    picker is resolved by naming the three best leaders (what the human
    chooser enforces: exactly 1 C + 2 As, never a goalie).
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_generator import generate_database
from fantasy_draft import FantasyDraftManager
from game_classes import PlayerPosition
from main import GameManager

USER_TEAM_NAME = "Toronto Maple Leafs"


def nhl_teams(lg):
    return [t for t in lg.teams
            if getattr(t, "league_name", "") == "National Hockey League"]


def ovr(p):
    try:
        return p.overall_rating()
    except Exception:
        return 50.0


def is_goalie(p):
    try:
        return p.primary_position == PlayerPosition.GOALIE
    except Exception:
        return False


def collect_players(teams):
    all_players = []
    for team in teams:
        for attr in ("roster", "ahl_roster", "prospects"):
            for p in list(getattr(team, attr, None) or []):
                if hasattr(p, "full_name"):
                    p.former_team = team.team_name
                    all_players.append(p)
    seen, uniq = set(), []
    for p in all_players:
        if p.id not in seen:
            seen.add(p.id)
            uniq.append(p)
    return uniq


def clear_rosters(teams):
    for team in teams:
        for attr in ("roster", "ahl_roster", "prospects"):
            lst = getattr(team, attr, None)
            if isinstance(lst, list):
                lst.clear()
            else:
                setattr(team, attr, [])


def run_fantasy_draft(seed=20260929, verbose=True):
    """Full headless fantasy draft. Returns dict(lg, teams, user, gm, report)."""
    def log(m):
        if verbose:
            print(m, flush=True)

    random.seed(seed)
    log("Generating database...")
    lg = generate_database("Small")
    lg.initialize_standings()
    lg.initialize_all_draft_picks()
    teams = nhl_teams(lg)
    log(f"NHL teams: {len(teams)}")

    pool = collect_players(teams)
    log(f"draft pool: {len(pool)} players")
    clear_rosters(teams)

    mgr = FantasyDraftManager(teams, pool)
    n = 0
    while not mgr.is_draft_complete():
        pick = mgr.get_current_pick()
        player = mgr.make_ai_pick(pick.team)
        if player is None:
            raise RuntimeError(f"draft stalled at pick {mgr.current_pick + 1}")
        if not mgr.make_pick(player):
            raise RuntimeError(f"make_pick failed at pick {mgr.current_pick + 1}")
        # production roster assignment (23-man NHL cap), shared with the UI
        mgr.assign_drafted_player(pick.team, player)
        n += 1
        if n % 320 == 0:
            log(f"  ... {n} picks")
    log(f"draft complete: {n} picks")
    # production post-draft soundness pass (<=23, >=2 goalies per club)
    mgr.normalize_post_draft_rosters()

    # complete_draft() headless equivalents
    gm = GameManager.__new__(GameManager)
    gm.league = lg
    gm.app = None
    gm.pending_fantasy_draft = False
    gm._captaincy_choice_pending = False
    gm._captaincy_checked_phase = None
    user = next(t for t in teams if t.team_name == USER_TEAM_NAME)
    gm.user_team = user
    for t in teams:
        for p in (getattr(t, "roster", None) or []):
            try:
                p.captaincy = ""
                p.captain_tenure_years = 0
                p.alternate_tenure_years = 0
            except Exception:
                pass
    gm._fantasy_draft_captaincy_deferred = True

    # first preseason game day: phase check with the real helpers
    gm._fantasy_draft_captaincy_deferred = False
    for t in teams:
        gm._opening_night_captaincy_check(t, user)
    if getattr(gm, "_captaincy_choice_pending", False):
        cands = sorted([p for p in user.roster if not is_goalie(p)],
                       key=lambda p: getattr(p, "leadership", 50), reverse=True)
        assert len(cands) >= 3, "not enough skaters to name captains"
        cands[0].captaincy = "C"
        cands[1].captaincy = "A"
        cands[2].captaincy = "A"
        gm._captaincy_choice_pending = False
        log(f"user captains: C={cands[0].full_name}, "
            f"A={cands[1].full_name}, {cands[2].full_name}")

    report = audit_rosters(teams)
    return {"lg": lg, "teams": teams, "user": user, "gm": gm,
            "report": report}


def audit_rosters(teams):
    """Soundness audit. Returns (ok, issues, per-team rows)."""
    issues, rows = [], []
    try:
        from salary_cap_system import cap_breakdown
    except Exception:
        cap_breakdown = None
    for t in teams:
        ros = getattr(t, "roster", None) or []
        n = len(ros)
        buckets = {"C": 0, "LW": 0, "RW": 0, "D": 0, "G": 0}
        for p in ros:
            try:
                nm = p.primary_position.name
            except Exception:
                continue
            if nm == "CENTER":
                buckets["C"] += 1
            elif nm == "LEFT_WING":
                buckets["LW"] += 1
            elif nm == "RIGHT_WING":
                buckets["RW"] += 1
            elif nm in ("LEFT_DEFENSE", "RIGHT_DEFENSE", "DEFENSE"):
                buckets["D"] += 1
            elif nm == "GOALIE":
                buckets["G"] += 1
        row = {"team": t.team_name, "roster": n,
               "ahl": len(getattr(t, "ahl_roster", None) or []),
               "prospects": len(getattr(t, "prospects", None) or []),
               "positions": buckets,
               "avg_ovr": round(sum(ovr(p) for p in ros) / max(n, 1), 1)}
        if cap_breakdown:
            try:
                bd = cap_breakdown(t)
                row["cap_hit_M"] = round(bd.get("total", 0) / 1e6, 2)
                row["cap_space_M"] = round(bd.get("space", 0) / 1e6, 2)
            except Exception as e:
                row["cap_error"] = str(e)[:120]
        rows.append(row)
        healthy = [p for p in ros if not getattr(p, "is_injured", False)]
        skaters = [p for p in healthy if not is_goalie(p)]
        # goalies: structural total -- a nicked goalie among two is normal
        goalies = [p for p in ros if is_goalie(p)]
        # injuries are covered by AHL callups, like the real game
        _ahl = getattr(t, "ahl_roster", None) or []
        ahl_skaters = [p for p in _ahl if not is_goalie(p)]
        if not (18 <= n <= 23):
            issues.append((t.team_name, "roster size", f"n={n}"))
        if buckets["G"] < 2:
            issues.append((t.team_name, "goalies", f"G={buckets['G']}"))
        if buckets["C"] < 3:
            issues.append((t.team_name, "centers", f"C={buckets['C']}"))
        if buckets["LW"] < 2 or buckets["RW"] < 2:
            issues.append((t.team_name, "wings",
                           f"LW={buckets['LW']} RW={buckets['RW']}"))
        if buckets["D"] < 6:
            issues.append((t.team_name, "defense", f"D={buckets['D']}"))
        if len(skaters) + len(ahl_skaters) < 18 or len(goalies) < 2:
            issues.append((t.team_name, "cannot dress lineup",
                           f"skaters={len(skaters)}+{len(ahl_skaters)} AHL "
                           f"goalies={len(goalies)}"))
        if row.get("cap_space_M", 0) < -0.01:
            issues.append((t.team_name, "over cap",
                           f"space={row['cap_space_M']}M"))
        if sum(1 for p in ros if getattr(p, "captaincy", "") == "C") != 1:
            issues.append((t.team_name, "captain count != 1", ""))
        ids = [p.id for p in ros]
        if len(ids) != len(set(ids)):
            issues.append((t.team_name, "duplicate players", ""))
    return {"ok": not issues, "issues": issues, "teams": rows}


if __name__ == "__main__":
    seed = int(sys.argv[1]) if len(sys.argv) > 1 else 20260929
    out = run_fantasy_draft(seed)
    rep = out["report"]
    print(f"\nAUDIT {'PASSED' if rep['ok'] else 'FAILED'}: "
          f"{len(rep['issues'])} issues")
    for team, what, detail in rep["issues"]:
        print(f"  [{team}] {what} {detail}")
