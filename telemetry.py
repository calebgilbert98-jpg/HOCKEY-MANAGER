"""Beta telemetry for Puck Dynasty.

Every simulated game appends one compact JSON record to
``telemetry/games.jsonl`` (local file, no network, no personal data --
player names in this game are fictional). The more games beta testers
play, the clearer the picture of what the sim gets right and wrong.

``analyze_telemetry.py`` reads the log and compares league averages
against NHL benchmarks, flagging whatever drifts off.

The sim calls :func:`log_game` automatically at the end of every game
(see ``GameSim._emit_telemetry``). It never raises: telemetry must not
be able to break a game.
"""

import json
import os
import subprocess
import uuid
from datetime import datetime, timezone

TELEMETRY_VERSION = 1

# Per-game NHL benchmarks (2023-24-ish averages, both teams combined
# unless noted). analyze_telemetry.py flags deviations from these.
NHL_BENCHMARKS = {
    # metric: (low, high, label, hint when out of range)
    "goals": (5.5, 6.8, "total goals",
              "scoring is off -- check xG model, goalie save%, shot volume"),
    "shots": (56, 66, "shots on goal",
              "shot volume is off -- check event pacing / chance generation"),
    "shooting_pct": (8.0, 11.0, "shooting %",
                     "finishing is off -- check xG and save probability"),
    "save_pct": (0.895, 0.915, "save %",
                 "goalies are off -- check save model"),
    "penalties": (6.0, 8.5, "penalties",
                  "penalty rate is off -- tune BACKGROUND_PENALTY_PROB / hit-path penalties"),
    "pim": (12.0, 20.0, "PIM",
            "penalty minutes are off -- check infraction lengths"),
    "pp_opps": (6.0, 8.5, "power plays (total)",
                "PP opportunity count is off -- follows penalty rate"),
    "pp_pct": (17.0, 24.0, "power-play %",
               "PP conversion is off -- check PP shot volume and man-advantage xG"),
    "icings": (1.5, 4.5, "icings",
               "icing rate is off -- check _maybe_icing probability"),
    "offsides": (1.5, 5.0, "offsides",
                 "offside rate is off -- check zone-entry whistle probability"),
    "hits": (35, 55, "hits",
             "hit rate is off -- check hitting tendency / battle resolution"),
    "fights": (0.1, 0.6, "fights",
               "fight rate is off -- check Fighting infraction weight"),
    "penalty_shots": (0.0, 0.15, "penalty shots",
                      "penalty-shot rate is off -- check breakaway foul hook"),
    "faceoff_pct": (47.0, 53.0, "faceoff win % (home)",
                    "faceoffs skewed -- check faceoff resolution (should be ~50/50)"),
}


def _repo_root():
    return os.path.dirname(os.path.abspath(__file__))


def get_log_path():
    d = os.path.join(_repo_root(), "telemetry")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "games.jsonl")


def _sim_version():
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_repo_root(), capture_output=True, text=True, timeout=5)
        if out.returncode == 0 and out.stdout.strip():
            dirty = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=_repo_root(), capture_output=True, text=True, timeout=5)
            suffix = "-dirty" if dirty.stdout.strip() else ""
            return out.stdout.strip() + suffix
    except Exception:
        pass
    return "unknown"


def _goalie_line(sim, team):
    """Aggregate the goalies who actually played for one team."""
    saves = shots_against = goals_against = 0
    for stats in sim.game_stats.values():
        player = stats.get("player")
        if player is None:
            continue
        pos = getattr(getattr(player, "primary_position", None), "value", "")
        if pos != "G":
            continue
        if getattr(player, "team_name", None) != team.team_name:
            continue
        if stats.get("shots_against", 0) == 0 and stats.get("saves", 0) == 0:
            continue
        saves += stats.get("saves", 0)
        shots_against += stats.get("shots_against", 0)
        goals_against += stats.get("goals_against", 0)
    sv = saves / shots_against if shots_against else 0.0
    return {"saves": saves, "shots_against": shots_against,
            "goals_against": goals_against, "sv_pct": round(sv, 4)}


def build_game_record(sim):
    """Build the telemetry dict for a finished GameSim. Pure function."""
    teams = {}
    for team in (sim.home_team, sim.away_team):
        ts = sim.team_stats.get(team.team_name, {})
        is_home = team == sim.home_team
        pim = sim.home_pim_called if is_home else sim.away_pim_called
        pens = sim.home_penalties_called if is_home else sim.away_penalties_called
        xg = 0.0
        try:
            xg = float(sim.expected_goals.get(team.team_name, 0.0))
        except Exception:
            pass
        fo_w = ts.get("faceoffs_won", 0)
        fo_l = ts.get("faceoffs_lost", 0)
        shots = ts.get("shots_on_goal", 0)
        goals = sim.home_score if team == sim.home_team else sim.away_score
        pp_opps = ts.get("power_play_opportunities", 0)
        pp_goals = ts.get("power_play_goals", 0)
        teams[team.team_name] = {
            "goals": goals,
            "shots": shots,
            "attempts": ts.get("shot_attempts", 0),
            "shooting_pct": round(100.0 * goals / shots, 2) if shots else 0.0,
            "penalties": pens,
            "pim": pim,
            "pp_opps": pp_opps,
            "pp_goals": pp_goals,
            "pp_pct": round(100.0 * pp_goals / pp_opps, 1) if pp_opps else 0.0,
            "pk_opps": ts.get("penalty_kill_opportunities", 0),
            "pk_ga": ts.get("penalty_kill_goals_against", 0),
            "hits": ts.get("hits", 0),
            "takeaways": ts.get("takeaways", 0),
            "giveaways": ts.get("giveaways", 0),
            "blocked": ts.get("blocked_shots_by_team", 0),
            "faceoffs_won": fo_w,
            "faceoffs_lost": fo_l,
            "faceoff_pct": round(100.0 * fo_w / (fo_w + fo_l), 1) if fo_w + fo_l else 50.0,
            "xg": round(xg, 2),
            "goalie": _goalie_line(sim, team),
        }

    log_text = "\n".join(str(e) for e in sim.game_log)
    went_ot = getattr(sim, "period", 3) > 3
    went_so = "SHOOTOUT_START" in log_text or "shootout" in log_text.lower()

    return {
        "v": TELEMETRY_VERSION,
        "sim": _sim_version(),
        "ts": datetime.now(timezone.utc).isoformat(),
        "game_id": uuid.uuid4().hex[:12],
        "playoff": bool(getattr(sim, "is_playoff", False)),
        "ot": went_ot,
        "shootout": went_so,
        "home": sim.home_team.team_name,
        "away": sim.away_team.team_name,
        "home_score": sim.home_score,
        "away_score": sim.away_score,
        "teams": teams,
        "penalties": getattr(sim, "penalties_called", 0),
        "misconducts": getattr(sim, "misconducts_called", 0),
        "icings": getattr(sim, "icings_called", 0),
        "offsides": getattr(sim, "offsides_called", 0),
        "fights": getattr(sim, "fights_called", 0),
        "penalty_shots": getattr(sim, "penalty_shots_called", 0),
    }


def log_game(sim):
    """Append one game's record to telemetry/games.jsonl. Never raises."""
    try:
        record = build_game_record(sim)
        with open(get_log_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass
