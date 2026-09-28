"""
Coaching tactics foundation — true NHL systems, EHM-style depth.

What EHM got right (per the sim-engine research brief): tactics organized by
phase and zone, expressed as *biases* on the engine rather than scripts, and
tendency attributes (passing tendency, aggression, flair, work rate) treated
as first-class citizens that make systems visible on the ice.

This module goes one step further: every category carries true NHL systems
with real exemplars, an overall coach philosophy layer, and full power-play /
penalty-kill catalogs. Minimum six options per playstyle, so every team can
be true to its identity — or copy what's working for someone else.

Engine contract
--------------
Each system resolves to plain multipliers via ``resolve_team_tactics()``:

    {
      "attack":   1.0,   # scales this team's goal expectancy
      "defense":  1.0,   # scales the OPPONENT's goal expectancy (<1 = stingy)
      "pace":     1.0,   # scales total events in games this team plays
      "pp":       1.0,   # scales this team's power-play conversion
      "pk":       1.0,   # scales this team's penalty kill (>1 = better kill)
      "sh_threat":1.0,   # shorthanded counterattack threat
      "physical": 1.0,   # hits / PIM / fight flavor
      "fit":      1.0,   # roster<->system fit (0.92..1.08)
      "familiarity": 85, # 0-100, new systems take time to learn
    }

``matchup_modifiers(home, away)`` combines two resolved profiles into the
numbers the sim actually applies:

    {"home_goals": m, "away_goals": m, "pace": m,
     "home_pp": m, "away_pp": m}

Unfamiliar or ill-fitting systems have their edges muted toward 1.0 — a
team mid-transition plays like a team thinking too much.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Offensive systems (7)
# ---------------------------------------------------------------------------

OFFENSIVE_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "rush_attack": {
        "name": "Up-Tempo Rush",
        "blurb": ("Stretch the ice and attack off the rush. Defensemen join, "
                  "wingers fly the zone, and the team trades chances "
                  "willingly. When the legs are there it's breathtaking; "
                  "when they're not, it's track-meet hockey."),
        "exemplars": ["Colorado Avalanche", "New Jersey Devils"],
        "attack": 1.06, "pace": 1.14, "shot_vol": 1.10, "shot_qual": 1.00, "physical": 0.90,
        "wants": {"skating": 1.3, "shooting": 1.2, "puckhandling": 1.2,
                  "flair": 1.1, "shoot_pass_tendency": 1.3},
    },
    "heavy_cycle": {
        "name": "Heavy Cycle",
        "blurb": ("Own the walls, own the puck, own the game. Forwards grind "
                  "low, defensemen hold the line, and chances come from "
                  "point shots through traffic and second efforts. "
                  "Exhausting to play against for 60 minutes."),
        "exemplars": ["Vegas Golden Knights", "Los Angeles Kings (2012-14)"],
        "attack": 1.04, "pace": 0.94, "shot_vol": 0.95, "shot_qual": 1.08, "physical": 1.30,
        "wants": {"strength": 1.3, "checking": 1.1, "work_rate": 1.2,
                  "hitting_tendency": 1.2, "flair": 0.7},
    },
    "dump_chase": {
        "name": "North-South / Dump & Chase",
        "blurb": ("Get it in, get it back, get it to the net. No cute "
                  "entries, no east-west risk — just pucks deep, bodies on "
                  "defensemen, and a forecheck that punishes every breakout. "
                  "Old school, and proud of it."),
        "exemplars": ["Philadelphia Flyers", "Nashville Predators"],
        "attack": 1.00, "pace": 1.05, "shot_vol": 1.05, "shot_qual": 0.97, "physical": 1.15,
        "wants": {"skating": 1.2, "hitting_tendency": 1.3,
                  "aggressiveness": 1.2, "work_rate": 1.3, "flair": 0.6},
    },
    "counterattack": {
        "name": "Counterattack",
        "blurb": ("Absorb, frustrate, then strike. The team gives up the "
                  "perimeter, clogs the middle, and turns the first bad "
                  "pass into a 2-on-1 the other way. Low-event hockey until "
                  "it suddenly isn't."),
        "exemplars": ["New York Islanders", "St. Louis Blues (2019)"],
        "attack": 1.02, "pace": 0.90, "shot_vol": 0.88, "shot_qual": 1.10, "physical": 0.95,
        "wants": {"skating": 1.3, "anticipation": 1.2, "positioning": 1.2,
                  "decisions": 1.2, "flair": 0.8},
    },
    "net_front": {
        "name": "Crash the Net",
        "blurb": ("Everything goes to the blue paint. Screens, tips, "
                  "rebounds, greasy goals — the prettiest play is the one "
                  "that goes in off somebody's shin pad. Goalies hate "
                  "this team."),
        "exemplars": ["Florida Panthers", "Boston Bruins"],
        "attack": 1.05, "pace": 1.02, "shot_vol": 1.12, "shot_qual": 1.02, "physical": 1.20,
        "wants": {"strength": 1.2, "bravery": 1.3, "shooting": 1.2,
                  "hitting_tendency": 1.1, "flair": 0.7},
    },
    "skill_possession": {
        "name": "Skill Possession",
        "blurb": ("The puck is a treasure and turnovers are sins. Controlled "
                  "entries, seam passes, give-and-go below the dots — the "
                  "power play stretched across five-on-five. Needs elite "
                  "hands; without them it's perimeter passing into a loss."),
        "exemplars": ["Edmonton Oilers", "Tampa Bay Lightning"],
        "attack": 1.07, "pace": 1.06, "shot_vol": 1.00, "shot_qual": 1.06, "physical": 0.85,
        "wants": {"passing": 1.3, "puckhandling": 1.3, "flair": 1.3,
                  "shoot_pass_tendency": 0.4, "anticipation": 1.1},
    },
    "balanced": {
        "name": "Balanced / Read & React",
        "blurb": ("No dogma. Take what the game gives: rush when it's there, "
                  "cycle when it isn't. The system is the players reading "
                  "the play — which means it rises and falls on hockey IQ."),
        "exemplars": ["Dallas Stars", "Winnipeg Jets"],
        "attack": 1.00, "pace": 1.00, "shot_vol": 1.00, "shot_qual": 1.00, "physical": 1.00,
        "wants": {"decisions": 1.1, "teamwork": 1.1, "work_rate": 1.1,
                  "skating": 1.1},
    },
}

# ---------------------------------------------------------------------------
# Defensive systems (7)
# ---------------------------------------------------------------------------

DEFENSIVE_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "neutral_trap": {
        "name": "1-2-2 Neutral Zone Trap",
        "blurb": ("The Lemaire special. Four skaters form a wall through the "
                  "neutral zone and dare you to beat them with skill. "
                  "Devils hockey won three Cups this way — and emptied "
                  "buildings doing it."),
        "exemplars": ["New Jersey Devils (1995-2003)", "Minnesota Wild"],
        "defense": 0.88, "pace": 0.86, "risk": 0.90, "physical": 0.9,
    },
    "trap_131": {
        "name": "1-3-1 Neutral Zone",
        "blurb": ("One forechecker funnels, three across the middle take "
                  "away the carry, one back. Modern trap — less passive than "
                  "the 1-2-2, same suffocating idea through center ice."),
        "exemplars": ["Tampa Bay Lightning", "Los Angeles Kings"],
        "defense": 0.90, "pace": 0.90, "risk": 0.92, "physical": 0.9,
    },
    "left_wing_lock": {
        "name": "Left Wing Lock",
        "blurb": ("Bowman's machine. The left winger drops to the blue line "
                  "on every possession change, creating a five-man wall "
                  "without ever looking passive. Structure as identity."),
        "exemplars": ["Detroit Red Wings (1990s)", "Vegas Golden Knights"],
        "defense": 0.93, "pace": 0.94, "risk": 0.95, "physical": 1.0,
    },
    "aggressive_man": {
        "name": "Aggressive 2-1-2 / Man-on-Man",
        "blurb": ("Hunt the puck everywhere. Two forecheckers deep, "
                  "defensemen step up at their own blue line, and the "
                  "D-zone is man-on-man with no hiding. Creates turnovers "
                  "in bunches — and gives up the odd breakaway."),
        "exemplars": ["Carolina Hurricanes", "Florida Panthers"],
        "defense": 0.96, "pace": 1.12, "risk": 1.15, "physical": 1.15,
    },
    "passive_box": {
        "name": "Collapsing Box",
        "blurb": ("Protect the house. Four skaters sag to the slot, block "
                  "everything, and let the goalie see the perimeter. "
                  "Bend-don't-break taken literally — low danger against, "
                  "low pressure for."),
        "exemplars": ["New York Islanders", "St. Louis Blues"],
        "defense": 0.90, "pace": 0.96, "risk": 0.92, "physical": 1.0,
    },
    "hybrid": {
        "name": "Modern Hybrid",
        "blurb": ("Read-based defending: zone until a trigger, then man. "
                  "Switches on picks, layers in the slot, activates when "
                  "the puck is vulnerable. The league's default — and "
                  "only as good as the reads."),
        "exemplars": ["Dallas Stars", "Edmonton Oilers"],
        "defense": 0.94, "pace": 1.00, "risk": 1.00, "physical": 1.0,
    },
    "pressure_swarm": {
        "name": "D-Zone Swarm / Puck Pressure",
        "blurb": ("Two men on every puck carrier below the dots. The zone "
                  "is chaos by design — win it back in three seconds or "
                  "chase for thirty. Not for the faint of heart, or the "
                  "slow of foot."),
        "exemplars": ["Toronto Maple Leafs (Keefe era)", "Ottawa Senators"],
        "defense": 0.97, "pace": 1.08, "risk": 1.10, "physical": 1.1,
    },
}

# ---------------------------------------------------------------------------
# Overall coach philosophies (6)
# ---------------------------------------------------------------------------

PHILOSOPHIES: Dict[str, Dict[str, Any]] = {
    "offense_first": {
        "name": "Run and Gun",
        "blurb": ("Score one more than them. Defensemen pinch, the fourth "
                  "line gets offensive-zone starts, and 'backcheck' is a "
                  "suggestion. Electric when it works."),
        "attack": 1.03, "defense": 1.02, "pace": 1.05, "physical": 1.0,
    },
    "defense_first": {
        "name": "Defense Wins",
        "blurb": ("Structure over everything. Lines roll, risks get benched, "
                  "and 2-1 is a perfect game. The room buys in or the room "
                  "gets traded."),
        "attack": 0.98, "defense": 0.95, "pace": 0.95, "physical": 1.0,
    },
    "heavy_identity": {
        "name": "Heavy Hockey",
        "blurb": ("Finish every check, win every wall, make them dread the "
                  "third period. The forecheck is the system and the "
                  "penalty kill feeds off the crowd."),
        "attack": 1.01, "defense": 0.98, "pace": 1.02, "physical": 1.25,
    },
    "possession": {
        "name": "Puck Possession",
        "blurb": ("Analytics-driven: entries with control, exits with "
                  "support, shots from the right places. The process is "
                  "trusted even when the bounces aren't."),
        "attack": 1.03, "defense": 0.97, "pace": 1.00, "physical": 0.95,
    },
    "development": {
        "name": "Development First",
        "blurb": ("The kids play through mistakes. Systems are kept simple "
                  "so young legs can think fast, and the future matters as "
                  "much as tonight. Veterans may grumble."),
        "attack": 0.99, "defense": 1.01, "pace": 1.03, "physical": 1.0,
        "youth_growth": 1.15,
    },
    "pragmatist": {
        "name": "Pragmatist",
        "blurb": ("No system is sacred. Match the opponent, ride the hot "
                  "hand, change on the fly. Players call it trust; "
                  "traditionalists call it no identity at all."),
        "attack": 1.00, "defense": 1.00, "pace": 1.00, "physical": 1.0,
        "adaptability": 1.30,
    },
}

# ---------------------------------------------------------------------------
# Power play systems (7)
# ---------------------------------------------------------------------------

POWERPLAY_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "umbrella": {
        "name": "Umbrella",
        "blurb": ("Three high, two low — the classic. Point shots through "
                  "screens, one-timers from the circles, chaos in front. "
                  "Simple, proven, everywhere."),
        "exemplars": ["Boston Bruins", "Dallas Stars"],
        "pp": 1.05, "pp_shots": 1.10,
    },
    "one_three_one": {
        "name": "1-3-1",
        "blurb": ("The Tampa invention that took over the league. A "
                  "quarterback up top, a sniper in his office, a bumper "
                  "in the middle — every rotation opens a one-timer lane. "
                  "Still the gold standard."),
        "exemplars": ["Tampa Bay Lightning", "Edmonton Oilers"],
        "pp": 1.10, "pp_shots": 1.05,
    },
    "overload": {
        "name": "Overload",
        "blurb": ("Stack one side and outnumber the kill. Quick puck "
                  "movement, the seam pass, the backdoor tap-in. "
                  "Devastating against passive boxes."),
        "exemplars": ["Colorado Avalanche", "Toronto Maple Leafs"],
        "pp": 1.06, "pp_shots": 1.05,
    },
    "spread": {
        "name": "Spread",
        "blurb": ("Two defensemen up top, three forwards low and wide. "
                  "Maximum shooting lanes from the points, maximum space "
                  "down low. Old school, still works with the right arms."),
        "exemplars": ["Washington Capitals", "Pittsburgh Penguins"],
        "pp": 1.02, "pp_shots": 1.15,
    },
    "net_crash": {
        "name": "Net-Front Crash",
        "blurb": ("Two bodies parked on the goalie and pucks funneled "
                  "there. Tips, rebounds, jam plays. Ugly on the "
                  "whiteboard, beautiful on the scoresheet."),
        "exemplars": ["Florida Panthers", "Vegas Golden Knights"],
        "pp": 1.04, "pp_shots": 1.12,
    },
    "shoot_first": {
        "name": "Point Barrage",
        "blurb": ("Volume is the strategy. Everything to the net from "
                  "everywhere, traffic in front, and the law of averages "
                  "does the rest. Wears penalty killers down to nothing."),
        "exemplars": ["Carolina Hurricanes", "Buffalo Sabres"],
        "pp": 1.03, "pp_shots": 1.20,
    },
    "motion": {
        "name": "Motion / Rotation",
        "blurb": ("Nobody stands still. Constant rotation, drop-pass "
                  "entries at speed, and the kill chasing shadows. Needs "
                  "elite skaters and brains — without them it's just "
                  "skating in circles."),
        "exemplars": ["New Jersey Devils", "Chicago Blackhawks"],
        "pp": 1.07, "pp_shots": 1.00,
    },
}

# ---------------------------------------------------------------------------
# Penalty kill systems (6)
# ---------------------------------------------------------------------------

PENALTY_KILL_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "diamond": {
        "name": "Diamond Force",
        "blurb": ("Force everything to the perimeter from a tight diamond. "
                  "Takes away the middle, concedes the points, and clears "
                  "with prejudice. The league's bread and butter."),
        "exemplars": ["Tampa Bay Lightning", "Boston Bruins"],
        "pk": 1.04, "sh_threat": 1.0,
    },
    "passive_box": {
        "name": "Passive Box",
        "blurb": ("Four across, sagging low, shot lanes filled with shins. "
                  "Dare them to beat the goalie clean from distance. "
                  "Boring, disciplined, brutally effective with the right "
                  "goalie."),
        "exemplars": ["New York Islanders", "St. Louis Blues"],
        "pk": 1.05, "sh_threat": 0.8,
    },
    "wedge_plus_one": {
        "name": "Wedge + 1",
        "blurb": ("Three form the wedge low, one pressures the puck up "
                  "top. The modern compromise: structure underneath, "
                  "disruption on top, and no free looks anywhere."),
        "exemplars": ["Dallas Stars", "Winnipeg Jets"],
        "pk": 1.06, "sh_threat": 1.0,
    },
    "aggressive_swarm": {
        "name": "Aggressive Swarm",
        "blurb": ("Carolina's religion. Pressure the puck carrier "
                  "everywhere, even shorthanded — two men on the half-wall "
                  "before the pass is made. Creates shorthanded breakaways "
                  "and the occasional disaster."),
        "exemplars": ["Carolina Hurricanes", "Florida Panthers"],
        "pk": 1.03, "sh_threat": 1.5,
    },
    "czech_press": {
        "name": "Czech Press",
        "blurb": ("A 1-2-1 that hunts in the neutral zone before the power "
                  "play even sets up. Disrupts entries, forces dump-ins, "
                  "and turns kills into counterattacks. High risk, high "
                  "theatre."),
        "exemplars": ["Ottawa Senators", "Buffalo Sabres"],
        "pk": 1.04, "sh_threat": 1.3,
    },
    "split": {
        "name": "Split / Hybrid",
        "blurb": ("Reads the formation and morphs: diamond against the "
                  "umbrella, box against the overload. Smart and flexible — "
                  "right up until a misread leaves someone wide open."),
        "exemplars": ["Colorado Avalanche", "Vegas Golden Knights"],
        "pk": 1.02, "sh_threat": 1.1,
    },
}

def _normalize_catalogs() -> None:
    """Scale every scoring-relevant catalog so the SEEDED league is neutral.

    The 32 NHL seeds are the reference mix: with every team on its
    day-one identity, league-wide scoring and pace sit exactly at the
    engine's calibrated level. Relative differences between systems are
    preserved, so copying the trap still slows the whole league down --
    that's the dynamic story, not calibration drift.
    """
    seeds = list(NHL_TEAM_TACTICS.values())
    n = len(seeds)

    def wmean(fn):
        return sum(fn(sd) for sd in seeds) / n

    # Combined attack = offense x philosophy; defense = defense x philosophy.
    # _apply_edge is linear, so normalizing raw means fixes edged means too.
    a_mean = wmean(lambda sd: OFFENSIVE_SYSTEMS[sd["offense"]]["attack"]
                   * PHILOSOPHIES[sd["philosophy"]]["attack"])
    d_mean = wmean(lambda sd: DEFENSIVE_SYSTEMS[sd["defense"]]["defense"]
                   * PHILOSOPHIES[sd["philosophy"]]["defense"])
    pp_mean = wmean(lambda sd: POWERPLAY_SYSTEMS[sd["pp"]]["pp"])
    pk_mean = wmean(lambda sd: PENALTY_KILL_SYSTEMS[sd["pk"]]["pk"])
    for sys in OFFENSIVE_SYSTEMS.values():
        sys["attack"] /= a_mean
    for sys in DEFENSIVE_SYSTEMS.values():
        sys["defense"] /= d_mean
    for sys in POWERPLAY_SYSTEMS.values():
        sys["pp"] /= pp_mean
    for sys in PENALTY_KILL_SYSTEMS.values():
        sys["pk"] /= pk_mean

    # _apply_edge is linear, so normalizing the seed-weighted arithmetic
    # mean fixes the edged mean too. (The GameSim matchup takes a geometric
    # mean across the pair; with pace clustered near 1.0 that lands within
    # a percent of neutral -- well inside tolerance.)
    pf = wmean(lambda sd: OFFENSIVE_SYSTEMS[sd["offense"]]["pace"]
               * DEFENSIVE_SYSTEMS[sd["defense"]]["pace"]
               * PHILOSOPHIES[sd["philosophy"]]["pace"])
    # Three catalogs multiply into one combined pace: split the correction
    # across them with the cube root.
    pf3 = pf ** (1.0 / 3.0)
    for cat in (OFFENSIVE_SYSTEMS, DEFENSIVE_SYSTEMS, PHILOSOPHIES):
        for sys in cat.values():
            sys["pace"] /= pf3

    # Physicality feeds the hit engine, not scoring, but the same logic
    # applies: the seeded league should throw an average number of hits.
    ph_mean = wmean(lambda sd: OFFENSIVE_SYSTEMS[sd["offense"]]
                    .get("physical", 1.0)
                    * DEFENSIVE_SYSTEMS[sd["defense"]].get("physical", 1.0)
                    * PHILOSOPHIES[sd["philosophy"]].get("physical", 1.0))
    for sys in OFFENSIVE_SYSTEMS.values():
        if "physical" in sys:
            sys["physical"] /= ph_mean


# ---------------------------------------------------------------------------
# Seeded NHL identities — every team true to itself on day one
# ---------------------------------------------------------------------------

NHL_TEAM_TACTICS: Dict[str, Dict[str, str]] = {
    "Anaheim Ducks":           {"offense": "rush_attack",     "defense": "hybrid",         "pp": "one_three_one", "pk": "diamond",         "philosophy": "development"},
    "Boston Bruins":           {"offense": "heavy_cycle",     "defense": "hybrid",         "pp": "umbrella",      "pk": "diamond",         "philosophy": "heavy_identity"},
    "Buffalo Sabres":          {"offense": "rush_attack",     "defense": "aggressive_man", "pp": "umbrella",      "pk": "diamond",         "philosophy": "offense_first"},
    "Calgary Flames":          {"offense": "heavy_cycle",     "defense": "passive_box",    "pp": "overload",      "pk": "wedge_plus_one", "philosophy": "heavy_identity"},
    "Carolina Hurricanes":     {"offense": "rush_attack",     "defense": "aggressive_man", "pp": "one_three_one", "pk": "aggressive_swarm","philosophy": "possession"},
    "Chicago Blackhawks":      {"offense": "rush_attack",     "defense": "hybrid",         "pp": "one_three_one", "pk": "diamond",         "philosophy": "development"},
    "Colorado Avalanche":      {"offense": "rush_attack",     "defense": "aggressive_man", "pp": "one_three_one", "pk": "aggressive_swarm","philosophy": "offense_first"},
    "Columbus Blue Jackets":   {"offense": "balanced",        "defense": "hybrid",         "pp": "umbrella",      "pk": "diamond",         "philosophy": "pragmatist"},
    "Dallas Stars":            {"offense": "skill_possession","defense": "hybrid",         "pp": "umbrella",      "pk": "passive_box",     "philosophy": "possession"},
    "Detroit Red Wings":       {"offense": "balanced",        "defense": "hybrid",         "pp": "overload",      "pk": "diamond",         "philosophy": "pragmatist"},
    "Edmonton Oilers":         {"offense": "skill_possession","defense": "hybrid",         "pp": "one_three_one", "pk": "diamond",         "philosophy": "offense_first"},
    "Florida Panthers":        {"offense": "heavy_cycle",     "defense": "aggressive_man", "pp": "net_crash",     "pk": "aggressive_swarm","philosophy": "heavy_identity"},
    "Los Angeles Kings":       {"offense": "counterattack",   "defense": "neutral_trap",   "pp": "umbrella",      "pk": "wedge_plus_one", "philosophy": "defense_first"},
    "Minnesota Wild":          {"offense": "counterattack",   "defense": "hybrid",         "pp": "overload",      "pk": "passive_box",     "philosophy": "pragmatist"},
    "Montreal Canadiens":      {"offense": "rush_attack",     "defense": "hybrid",         "pp": "umbrella",      "pk": "diamond",         "philosophy": "development"},
    "Nashville Predators":     {"offense": "dump_chase",      "defense": "passive_box",    "pp": "umbrella",      "pk": "diamond",         "philosophy": "defense_first"},
    "New Jersey Devils":       {"offense": "rush_attack",     "defense": "hybrid",         "pp": "one_three_one", "pk": "aggressive_swarm","philosophy": "offense_first"},
    "New York Islanders":      {"offense": "dump_chase",      "defense": "passive_box",    "pp": "net_crash",     "pk": "passive_box",     "philosophy": "defense_first"},
    "New York Rangers":        {"offense": "balanced",        "defense": "hybrid",         "pp": "one_three_one", "pk": "diamond",         "philosophy": "pragmatist"},
    "Ottawa Senators":         {"offense": "rush_attack",     "defense": "aggressive_man", "pp": "umbrella",      "pk": "diamond",         "philosophy": "offense_first"},
    "Philadelphia Flyers":     {"offense": "dump_chase",      "defense": "aggressive_man", "pp": "net_crash",     "pk": "aggressive_swarm","philosophy": "heavy_identity"},
    "Pittsburgh Penguins":     {"offense": "balanced",        "defense": "hybrid",         "pp": "umbrella",      "pk": "diamond",         "philosophy": "pragmatist"},
    "San Jose Sharks":         {"offense": "rush_attack",     "defense": "hybrid",         "pp": "umbrella",      "pk": "diamond",         "philosophy": "development"},
    "Seattle Kraken":          {"offense": "counterattack",   "defense": "hybrid",         "pp": "overload",      "pk": "wedge_plus_one", "philosophy": "pragmatist"},
    "St. Louis Blues":         {"offense": "heavy_cycle",     "defense": "passive_box",    "pp": "overload",      "pk": "passive_box",     "philosophy": "heavy_identity"},
    "Tampa Bay Lightning":     {"offense": "skill_possession","defense": "hybrid",         "pp": "one_three_one", "pk": "diamond",         "philosophy": "possession"},
    "Toronto Maple Leafs":     {"offense": "skill_possession","defense": "hybrid",         "pp": "umbrella",      "pk": "diamond",         "philosophy": "offense_first"},
    "Utah Mammoth":            {"offense": "balanced",        "defense": "hybrid",         "pp": "overload",      "pk": "diamond",         "philosophy": "development"},
    "Vancouver Canucks":       {"offense": "rush_attack",     "defense": "hybrid",         "pp": "umbrella",      "pk": "aggressive_swarm","philosophy": "pragmatist"},
    "Vegas Golden Knights":    {"offense": "heavy_cycle",     "defense": "aggressive_man", "pp": "overload",      "pk": "passive_box",     "philosophy": "heavy_identity"},
    "Washington Capitals":     {"offense": "balanced",        "defense": "passive_box",    "pp": "one_three_one", "pk": "diamond",         "philosophy": "pragmatist"},
    "Winnipeg Jets":           {"offense": "counterattack",   "defense": "passive_box",    "pp": "umbrella",      "pk": "wedge_plus_one", "philosophy": "defense_first"},
}

DEFAULT_TACTICS: Dict[str, str] = {
    "offense": "balanced", "defense": "hybrid",
    "pp": "umbrella", "pk": "diamond", "philosophy": "pragmatist",
}


_normalize_catalogs()


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

def _get(d: Any, key: str, default: Any = 0.0) -> float:
    try:
        return float(getattr(d, key, default) or 0.0)
    except (TypeError, ValueError):
        return float(default)


def team_tactics(team: Any) -> Dict[str, str]:
    """This team's five tactic choices, with sane defaults."""
    raw = getattr(team, "tactics", None) or {}
    out = dict(DEFAULT_TACTICS)
    if isinstance(raw, dict):
        for k in out:
            v = raw.get(k)
            if v:
                out[k] = v
    return out


def ensure_team_tactics(team: Any) -> Dict[str, str]:
    """Seed a team's tactics (NHL identity if known) and familiarity."""
    try:
        if not getattr(team, "tactics", None):
            name = getattr(team, "team_name", "") or ""
            team.tactics = dict(NHL_TEAM_TACTICS.get(name, DEFAULT_TACTICS))
            try:
                _c = _coach_for(team)
                team.tactics_installed_by = getattr(_c, "id", None) if _c else None
            except Exception:
                pass
        if getattr(team, "tactics_familiarity", None) is None:
            team.tactics_familiarity = 85
        _bust_tactics_cache(team)
    except Exception:
        pass
    return team_tactics(team)


def _bust_tactics_cache(team: Any) -> None:
    try:
        team._tactics_cache = None
    except Exception:
        pass


def set_team_system(team: Any, category: str, system_key: str,
                  mid_game: bool = False) -> bool:
    """Change one of the five systems. New systems take time to learn.

    mid_game=True: a softer familiarity hit for intermission adjustments --
    the room is already warm, but new reads mid-game are still messy.
    """
    catalog = {"offense": OFFENSIVE_SYSTEMS, "defense": DEFENSIVE_SYSTEMS,
               "pp": POWERPLAY_SYSTEMS, "pk": PENALTY_KILL_SYSTEMS,
               "philosophy": PHILOSOPHIES}.get(category)
    if catalog is None or system_key not in catalog:
        return False
    try:
        ensure_team_tactics(team)
        if team.tactics.get(category) == system_key:
            return True
        team.tactics[category] = system_key
        # Learning curve: the room has to re-learn its reads.
        fam = _get(team, "tactics_familiarity", 85)
        if mid_game:
            team.tactics_familiarity = max(35.0, fam - 12)
        else:
            phil = team_tactics(team).get("philosophy")
            floor = 55 if phil == "pragmatist" else 45
            team.tactics_familiarity = max(
                floor, min(fam, 45) if fam > 45 else fam - 10)
        _bust_tactics_cache(team)
    except Exception:
        return False
    return True


def get_tactics_control(team: Any) -> str:
    """Who owns the whiteboard: 'coach' (default) or 'gm'."""
    try:
        c = getattr(team, "tactics_control", None)
        return c if c in ("coach", "gm") else "coach"
    except Exception:
        return "coach"


def set_tactics_control(team: Any, who: str) -> None:
    try:
        team.tactics_control = "gm" if who == "gm" else "coach"
    except Exception:
        pass


def install_coach_systems(team: Any, coach: Any,
                          reason: str = "hired") -> Dict[str, str]:
    """A new voice installs HIS systems. The room starts learning (fam 55).

    Used on head-coach hires and as the lazy backstop for AI teams.
    Never fires while the GM owns the whiteboard.
    """
    installed: Dict[str, str] = {}
    try:
        if get_tactics_control(team) != "coach":
            return installed
        prefs = ensure_coach_tactics(coach)
        ensure_team_tactics(team)
        for cat in ("offense", "defense", "pp", "pk", "philosophy"):
            if prefs.get(cat) and team.tactics.get(cat) != prefs[cat]:
                team.tactics[cat] = prefs[cat]
                installed[cat] = prefs[cat]
        team.tactics_familiarity = 55.0
        try:
            team.tactics_installed_by = getattr(coach, "id", None)
        except Exception:
            pass
        _bust_tactics_cache(team)
    except Exception:
        pass
    return installed


def maybe_install_coach_systems(team: Any) -> Dict[str, str]:
    """Backstop: if the head coach changed since systems were installed,
    the new coach puts his stamp on the whiteboard (AI teams included)."""
    try:
        coach = _coach_for(team)
        if coach is None:
            return {}
        if getattr(team, "tactics_installed_by", None) == getattr(coach, "id", None):
            return {}
        return install_coach_systems(team, coach, reason="new_voice")
    except Exception:
        return {}


def save_preferred_tactics(team: Any) -> Dict[str, str]:
    """The GM's saved template: one click to get back to his hockey."""
    try:
        ensure_team_tactics(team)
        team.preferred_tactics = dict(team_tactics(team))
        return dict(team.preferred_tactics)
    except Exception:
        return {}


def get_preferred_tactics(team: Any) -> Optional[Dict[str, str]]:
    try:
        p = getattr(team, "preferred_tactics", None)
        return dict(p) if p else None
    except Exception:
        return None


def system_tradeoffs(category: str, system_key: str) -> str:
    """One-line expected tradeoff vs league average, e.g. 'Pace +12% . Shots +10% . Physical -18%'."""
    catalog = {"offense": OFFENSIVE_SYSTEMS, "defense": DEFENSIVE_SYSTEMS,
               "pp": POWERPLAY_SYSTEMS, "pk": PENALTY_KILL_SYSTEMS,
               "philosophy": PHILOSOPHIES}.get(category, {})
    sys = catalog.get(system_key)
    if not sys:
        return ""
    labels = [("pace", "Pace"), ("shot_vol", "Shots"), ("shot_qual", "Quality"),
              ("attack", "Attack"), ("suppress", "Suppress"), ("physical", "Physical"),
              ("pp_conv", "PP"), ("pk_kill", "PK"), ("sh_threat", "SH threat")]
    bits = []
    for key, label in labels:
        v = sys.get(key)
        if v is None:
            continue
        pct = round((v - 1.0) * 100)
        if abs(pct) >= 3:
            bits.append(f"{label} {'+' if pct > 0 else ''}{pct}%")
    return " . ".join(bits) if bits else "Balanced profile"


def ai_intermission_adjustment(team: Any, score_diff: int) -> Optional[Dict[str, str]]:
    """Between periods, a coach who owns the whiteboard may adjust.

    Personality-gated: adaptable coaches chase the game when losing;
    defensive minds protect a big lead. Returns
    {category, old_key, new_key, line} or None.
    """
    try:
        import random as _random
        coach = _coach_for(team)
        if coach is None:
            return None
        if get_tactics_control(team) != "coach":
            return None
        try:
            import reputation_system as _rs
            style = _rs.coach_style(coach).get("label", "Balanced")
        except Exception:
            style = "Balanced"
        adapt = float(getattr(coach, "adaptability", 50) or 50)
        tk = team_tactics(team)
        cname = str(getattr(coach, "full_name", "Coach")).split()[-1]
        tname = getattr(team, "team_name", "the club")

        if score_diff <= -2:
            # Chasing the game: open it up, once the room has seen a period.
            p = 0.15 + adapt / 250.0
            if _random.random() > p:
                return None
            if tk.get("philosophy") != "offense_first":
                return {"category": "philosophy", "old_key": tk["philosophy"],
                        "new_key": "offense_first",
                        "line": (f"{tname} are opening it up -- {cname} has switched "
                                 f"to an attack-first philosophy chasing the game.")}
            if tk.get("offense") != "rush_attack":
                return {"category": "offense", "old_key": tk["offense"],
                        "new_key": "rush_attack",
                        "line": (f"{cname} is stretching the ice -- {tname} "
                                 f"to an up-tempo rush attack.")}
            return None
        if score_diff >= 3 and style in ("Tactician", "Drill Sergeant"):
            # Protecting a lead: a defensive mind locks it down.
            p = 0.10 + adapt / 400.0
            if _random.random() > p:
                return None
            if tk.get("philosophy") != "defense_first":
                return {"category": "philosophy", "old_key": tk["philosophy"],
                        "new_key": "defense_first",
                        "line": (f"{cname} is locking it down -- {tname} "
                                 f"to a defense-first shell protecting the lead.")}
            if tk.get("defense") not in ("neutral_trap", "trap_131"):
                return {"category": "defense", "old_key": tk["defense"],
                        "new_key": "neutral_trap",
                        "line": (f"{tname} are clogging the neutral zone -- "
                                 f"{cname} has gone to the trap.")}
            return None
        return None
    except Exception:
        return None


def tick_tactics_familiarity(team: Any, amount: float = 4.0) -> None:
    """Call once per game: the room learns the system.

    Assistant buy-in: a franchise icon teaching the system gets the room
    there faster (the Coffey effect) -- see assistant_coaches.
    """
    try:
        try:
            import assistant_coaches as _ac
            amount += _ac.assistant_familiarity_bonus(team)
        except Exception:
            pass
        fam = _get(team, "tactics_familiarity", 85)
        team.tactics_familiarity = max(0.0, min(95.0, fam + amount))
        _bust_tactics_cache(team)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Fit: tendency attributes are first-class citizens
# ---------------------------------------------------------------------------

def player_system_fit(player: Any, offense_key: str) -> float:
    """0.6..1.2 — how well this skater's game suits the offensive system.

    A sniper with 90 speed flies in a rush attack and drowns in a
    dump-and-chase grinder's role. Uses the real tendency attributes:
    shoot_pass_tendency, hitting_tendency, flair, work_rate, aggressiveness.
    """
    sys = OFFENSIVE_SYSTEMS.get(offense_key) or OFFENSIVE_SYSTEMS["balanced"]
    wants = sys.get("wants", {})
    if not wants:
        return 1.0
    # Signed preferences: weight > 1 wants the attribute HIGH (a skater's
    # 90 speed flies in a rush attack); weight < 1 wants it LOW (a
    # dump-and-chase room has no use for 90 flair). Weight == 1 is neutral
    # and contributes nothing. Tendencies are first-class:
    # shoot_pass_tendency is SHOOT tendency (high = shooter), so a
    # skill-possession system at 0.4 wants passers while a rush attack at
    # 1.3 wants shooters.
    total = 0.0
    weight = 0.0
    for attr, w in wants.items():
        if w == 1.0:
            continue
        val = max(0.0, min(100.0, _get(player, attr, 50)))
        score = val / 100.0 if w > 1.0 else (100.0 - val) / 100.0
        total += score * abs(w - 1.0)
        weight += abs(w - 1.0)
    if weight <= 0:
        return 1.0
    avg = total / weight  # 0..1, higher = better fit
    return max(0.6, min(1.2, 0.6 + avg * 0.6))


def team_system_fit(team: Any) -> float:
    """Roster-average fit to the offensive system, 0.92..1.08."""
    try:
        tk = team_tactics(team).get("offense", "balanced")
        roster = getattr(team, "roster", None) or []
        skaters = [p for p in roster
                   if not str(getattr(p, "primary_position", "")).upper()
                   .startswith("G")]
        if not skaters:
            return 1.0
        avg = sum(player_system_fit(p, tk) for p in skaters) / len(skaters)
        # 0.6..1.2 maps to 0.92..1.08
        return max(0.92, min(1.08, 0.92 + (avg - 0.6) * (0.16 / 0.6)))
    except Exception:
        return 1.0


def coach_tactics_fit(coach: Any, team: Any) -> float:
    """0..1 — does the coach's preferred hockey match the room's systems?"""
    if coach is None:
        return 0.7
    try:
        prefs = getattr(coach, "tactics_prefs", None) or {}
        mine = team_tactics(team)
        score, n = 0.0, 0
        for cat in ("offense", "defense", "pp", "pk", "philosophy"):
            want = prefs.get(cat)
            if want:
                n += 1
                if want == mine.get(cat):
                    score += 1.0
        return (score / n) if n else 0.7
    except Exception:
        return 0.7


# ---------------------------------------------------------------------------
# Resolution: systems -> engine numbers
# ---------------------------------------------------------------------------

def _familiarity_factor(team: Any) -> float:
    """0.6..1.0 — new systems play muted until learned."""
    fam = _get(team, "tactics_familiarity", 85)
    return 0.6 + 0.4 * max(0.0, min(100.0, fam)) / 100.0


def _apply_edge(mult: float, factor: float) -> float:
    """Mute a multiplier's edge toward 1.0 by factor (0..1)."""
    return 1.0 + (mult - 1.0) * factor


# Coach style -> preferred systems. A Drill Sergeant wants structure
# and heaviness; a Player's Coach wants skill and freedom. Used to seed a
# new coach's tactics_prefs so his hockey has an identity on day one.
STYLE_PREFS: Dict[str, Dict[str, str]] = {
    "Drill Sergeant": {"offense": "dump_chase", "defense": "passive_box",
                       "pp": "net_crash", "pk": "passive_box",
                       "philosophy": "defense_first"},
    "Player's Coach":  {"offense": "skill_possession", "defense": "hybrid",
                       "pp": "motion", "pk": "diamond",
                       "philosophy": "offense_first"},
    "Tactician":       {"offense": "counterattack", "defense": "neutral_trap",
                       "pp": "one_three_one", "pk": "wedge_plus_one",
                       "philosophy": "possession"},
    "Motivator":       {"offense": "rush_attack", "defense": "aggressive_man",
                       "pp": "shoot_first", "pk": "aggressive_swarm",
                       "philosophy": "heavy_identity"},
    "Developer":       {"offense": "rush_attack", "defense": "hybrid",
                       "pp": "umbrella", "pk": "diamond",
                       "philosophy": "development"},
    "Balanced":        {"offense": "balanced", "defense": "hybrid",
                       "pp": "umbrella", "pk": "diamond",
                       "philosophy": "pragmatist"},
}


def default_coach_prefs(coach: Any) -> Dict[str, str]:
    """A coach's preferred systems, derived from his coaching style."""
    try:
        import reputation_system as _rs
        style = _rs.coach_style(coach).get("label", "Balanced")
    except Exception:
        style = "Balanced"
    return dict(STYLE_PREFS.get(style, STYLE_PREFS["Balanced"]))


def ensure_coach_tactics(coach: Any) -> Dict[str, str]:
    """Seed a coach's system preferences from his style (idempotent)."""
    try:
        if not getattr(coach, "tactics_prefs", None):
            coach.tactics_prefs = default_coach_prefs(coach)
        return dict(coach.tactics_prefs)
    except Exception:
        return dict(STYLE_PREFS["Balanced"])


def _coach_for(team: Any) -> Any:
    try:
        for stf in getattr(team, "staff", []) or []:
            if "Head Coach" in str(getattr(getattr(stf, "role", None),
                                           "value", "")):
                return stf
    except Exception:
        pass
    return None


def resolve_team_tactics(team: Any) -> Dict[str, float]:
    """Collapse a team's five systems into engine multipliers.

    Memoized per (systems, familiarity, coach prefs): systems only change
    between games, so one resolution serves the whole game.
    """
    tk = team_tactics(team)
    fam_raw = _get(team, "tactics_familiarity", 85)
    coach = _coach_for(team)
    prefs = ensure_coach_tactics(coach) if coach is not None else {}
    cache_key = (tk["offense"], tk["defense"], tk["pp"], tk["pk"],
                 tk["philosophy"], round(fam_raw, 1),
                 tuple(sorted(prefs.items())))
    try:
        ck, cv = getattr(team, "_tactics_cache", (None, None))
        if ck == cache_key and isinstance(cv, dict):
            return cv
    except Exception:
        pass
    off = OFFENSIVE_SYSTEMS.get(tk["offense"], OFFENSIVE_SYSTEMS["balanced"])
    dfn = DEFENSIVE_SYSTEMS.get(tk["defense"], DEFENSIVE_SYSTEMS["hybrid"])
    phi = PHILOSOPHIES.get(tk["philosophy"], PHILOSOPHIES["pragmatist"])
    pp = POWERPLAY_SYSTEMS.get(tk["pp"], POWERPLAY_SYSTEMS["umbrella"])
    pk = PENALTY_KILL_SYSTEMS.get(tk["pk"], PENALTY_KILL_SYSTEMS["diamond"])

    fam = _familiarity_factor(team)
    fit = team_system_fit(team)

    # A coach fighting the room's systems dulls everything slightly.
    try:
        cfit = coach_tactics_fit(coach, team)
        coach_factor = 0.97 + 0.03 * cfit
    except Exception:
        coach_factor = 1.0

    attack = _apply_edge(off["attack"] * phi["attack"] * fit, fam) * coach_factor
    defense = _apply_edge(dfn["defense"] * phi["defense"], fam) * coach_factor
    pace = _apply_edge(off["pace"] * dfn["pace"] * phi["pace"], fam)
    pace = max(0.85, min(1.18, pace))
    out = {
        "attack": attack,
        "defense": defense,
        "pace": pace,
        "pp": _apply_edge(pp["pp"], fam),
        "pk": _apply_edge(pk["pk"], fam),
        "sh_threat": pk.get("sh_threat", 1.0),
        "physical": (off.get("physical", 1.0) * dfn.get("physical", 1.0)
                       * phi.get("physical", 1.0)),
        "fit": fit,
        "familiarity": _get(team, "tactics_familiarity", 85),
    }
    try:
        team._tactics_cache = (cache_key, out)
    except Exception:
        pass
    return out


def matchup_modifiers(home: Any, away: Any) -> Dict[str, float]:
    """The numbers the sim applies for this game.

    home_goals / away_goals scale each side's goal expectancy; pace scales
    total events; home_pp / away_pp scale power-play conversion.
    """
    h = resolve_team_tactics(home)
    a = resolve_team_tactics(away)
    # Geometric: a trap team drags the tempo down more than a rush team
    # lifts it -- (1+x)(1-x) < 1.
    pace = (h["pace"] * a["pace"]) ** 0.5
    return {
        # your attack vs their structure
        "home_goals": h["attack"] * a["defense"],
        "away_goals": a["attack"] * h["defense"],
        "pace": pace,
        # your power play vs their kill (pk>1 suppresses: invert around 1)
        "home_pp": h["pp"] * (2.0 - a["pk"]),
        "away_pp": a["pp"] * (2.0 - h["pk"]),
        "home_sh_threat": h["sh_threat"],
        "away_sh_threat": a["sh_threat"],
        "physical": (h["physical"] + a["physical"]) / 2.0,
    }


# ---------------------------------------------------------------------------
# Copycat league: steal what wins
# ---------------------------------------------------------------------------

# Categories coaches steal, weighted: special teams first, always.
COPYCAT_WEIGHTS = (("pp", 0.35), ("pk", 0.30), ("offense", 0.20),
                   ("defense", 0.15))


def offseason_copycat(league: Any, rng=None) -> list:
    """One offseason pass: AI teams copy the Cup champion's systems.

    Every AI team (never the user's, never the champs) may adopt one of
    the champion's systems -- usually the power play or penalty kill, the
    two things coaches steal first. Stubborn rooms copy less: low coach
    adaptability and high control_need both drag the odds down, because
    personality is a major factor in *likelihood*. Adopting a system
    costs familiarity (see set_team_system) -- copying isn't free.

    Returns [(team_name, category, system_key)] for the news feed.
    """
    import random as _random
    rng = rng or _random
    copied = []
    try:
        teams = list(getattr(league, "teams", None) or [])
        bracket = getattr(league, "playoff_bracket", None)
        champ = getattr(bracket, "stanley_cup_champion", None)
        if champ is None or not teams:
            return copied
        if isinstance(champ, str):
            by_name = {getattr(t, "team_name", ""): t for t in teams}
            champ = by_name.get(champ)
        if champ is None:
            return copied
        champ_sys = team_tactics(champ)
        cats, weights = zip(*COPYCAT_WEIGHTS)
        for team in teams:
            try:
                if team is champ:
                    continue
                if getattr(team, "is_user_team", False):
                    continue
                mine = team_tactics(team)
                # Stubborn rooms don't copy: adaptability opens minds,
                # control_need closes them.
                coach = _coach_for(team)
                adapt = float(getattr(coach, "adaptability", 65) or 65)
                ctrl = float(getattr(coach, "control_need", 50) or 50)
                p = 0.18 * (0.5 + adapt / 130.0) * (1.1 - ctrl / 200.0)
                if rng.random() >= p:
                    continue
                # Weighted pick, then roll off categories the champ
                # doesn't improve on.
                order = list(rng.choices(cats, weights=weights, k=len(cats)))
                for cat in order:
                    want = champ_sys.get(cat)
                    if want and mine.get(cat) != want:
                        if set_team_system(team, cat, want):
                            copied.append((getattr(team, "team_name", "?"),
                                           cat, want))
                        break
            except Exception:
                continue
    except Exception:
        pass
    return copied


# ---------------------------------------------------------------------------
# Presentation helpers
# ---------------------------------------------------------------------------

def describe_team_tactics(team: Any) -> List[str]:
    """Human-readable identity lines for UI / media."""
    tk = team_tactics(team)
    catalogs = {"offense": OFFENSIVE_SYSTEMS, "defense": DEFENSIVE_SYSTEMS,
                "pp": POWERPLAY_SYSTEMS, "pk": PENALTY_KILL_SYSTEMS,
                "philosophy": PHILOSOPHIES}
    labels = {"offense": "Offense", "defense": "Defense", "pp": "Power play",
              "pk": "Penalty kill", "philosophy": "Philosophy"}
    lines = []
    for cat in ("philosophy", "offense", "defense", "pp", "pk"):
        sys = catalogs[cat].get(tk[cat], {})
        lines.append(f"{labels[cat]}: {sys.get('name', tk[cat])}")
    return lines


