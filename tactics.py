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
# Even-strength modules — the three-zone playbook.
#
# A team's 5v5 identity is five independent choices: how you forecheck, how
# you defend the neutral zone, how you protect your own zone, how you attack
# theirs, and how you break the puck out. Defense in the modern NHL starts
# 200 feet away at the opposing goal line; offense is about breaking
# structural integrity before the opponent sets. Each module resolves to
# biases on the engine (attack/defense/pace/shot volume/shot quality/
# physicality); resolve_team_tactics() multiplies the five modules into the
# numbers the sim applies. _normalize_catalogs() keeps the SEEDED league
# exactly neutral, so relative differences are story, not calibration drift.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Forecheck systems — pressure without the puck in the offensive zone
# ---------------------------------------------------------------------------

FORECHECK_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "forecheck_122": {
        "name": "1-2-2 Forecheck",
        "blurb": ("The modern standard. F1 pressures the puck carrier and "
                  "forces him down one side, F2/F3 form a second wall through "
                  "the neutral zone, and the D hold the line. It doesn't "
                  "always produce turnovers, but it clogs the middle, denies "
                  "clean entries, and starves odd-man rushes. Risk mitigation "
                  "as identity."),
        "exemplars": ["Pittsburgh Penguins", "Tampa Bay Lightning",
                      "Vegas Golden Knights"],
        "attack": 1.00, "defense": 0.97, "pace": 0.98,
        "shot_vol": 1.00, "shot_qual": 1.00, "physical": 1.00,
        "wants": {"anticipation": 1.2, "positioning": 1.2, "work_rate": 1.2,
                  "decisions": 1.1},
    },
    "forecheck_212_swarm": {
        "name": "2-1-2 Swarm Forecheck",
        "blurb": ("Two forwards hunt the puck deep behind the goal line, a "
                  "third supports in the slot, and the defensemen pinch "
                  "aggressively down the walls. Suffocate the breakout "
                  "before it starts, force panicked rims, and live in their "
                  "zone. Demands elite conditioning and mobile defensemen — "
                  "and accepts the odd breakaway against."),
        "exemplars": ["Colorado Avalanche", "Florida Panthers",
                      "Carolina Hurricanes"],
        "attack": 1.04, "defense": 1.03, "pace": 1.08,
        "shot_vol": 1.05, "shot_qual": 1.01, "physical": 1.15,
        "wants": {"skating": 1.3, "aggressiveness": 1.2, "stamina": 1.2,
                  "checking": 1.1, "work_rate": 1.2},
    },
}

# ---------------------------------------------------------------------------
# Neutral zone & transition philosophies — the 80-foot battleground
# ---------------------------------------------------------------------------

NEUTRAL_ZONE_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "nz_trap_131": {
        "name": "1-3-1 Neutral Zone Trap",
        "blurb": ("The Red Line Restrictor. One forward pressures near "
                  "center, a horizontal wall of three takes away the carry, "
                  "one defenseman stays home. Maximum spatial compression — "
                  "the opponent dumps it in or tries a seam pass into "
                  "coverage. Strangles speed teams; bores everyone else."),
        "exemplars": ["Tampa Bay Lightning", "Montreal Canadiens"],
        "attack": 0.98, "defense": 0.93, "pace": 0.90,
        "shot_vol": 0.97, "shot_qual": 1.00, "physical": 0.95,
        "wants": {"positioning": 1.3, "anticipation": 1.2, "decisions": 1.2,
                  "discipline": 1.1},
    },
    "nz_regroup": {
        "name": "Controlled Regroup & Wave Attack",
        "blurb": ("Patience over panic. Against a set neutral-zone structure "
                  "the carrier circles back, drops to a trailing defenseman, "
                  "and all five re-establish speed and spacing. Possession "
                  "is an asset — never surrendered cheaply on a blind "
                  "dump-in. The wave comes at you with numbers, again and "
                  "again."),
        "exemplars": ["Colorado Avalanche", "Edmonton Oilers"],
        "attack": 1.02, "defense": 1.00, "pace": 1.00,
        "shot_vol": 1.00, "shot_qual": 1.03, "physical": 0.95,
        "wants": {"passing": 1.3, "puckhandling": 1.2, "skating": 1.2,
                  "decisions": 1.1},
    },
    "nz_counterpress": {
        "name": "NZ Delay & Pinch (Counter-Press)",
        "blurb": ("Turn the neutral zone into a killing field. Weak-side "
                  "forwards step up and pinch passing lanes the moment the "
                  "opponent tries a short-area transition — attack the "
                  "breakout at its inception instead of waiting at your own "
                  "blue line. Chaos for them, chances for you."),
        "exemplars": ["Carolina Hurricanes", "Toronto Maple Leafs"],
        "attack": 1.03, "defense": 1.01, "pace": 1.07,
        "shot_vol": 1.03, "shot_qual": 1.01, "physical": 1.05,
        "wants": {"anticipation": 1.3, "skating": 1.2, "aggressiveness": 1.2,
                  "checking": 1.1},
    },
}

# ---------------------------------------------------------------------------
# Defensive-zone coverage — protecting the house
# ---------------------------------------------------------------------------

DZONE_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "dz_hybrid": {
        "name": "Hybrid Man-to-Man Coverage",
        "blurb": ("The modern default below the circles: defenders track "
                  "their checks aggressively up the wall and into the "
                  "corners, while weak-side players collapse to zone. "
                  "Suffocates time and space near the crease and kills slot "
                  "passes — but it only works if the reads are elite."),
        "exemplars": ["Vegas Golden Knights", "Boston Bruins"],
        "attack": 1.00, "defense": 0.96, "pace": 1.00,
        "shot_vol": 1.00, "shot_qual": 0.96, "physical": 1.00,
        "wants": {"anticipation": 1.3, "positioning": 1.2, "decisions": 1.2,
                  "skating": 1.1},
    },
    "dz_box": {
        "name": "Passive Box-Plus-One",
        "blurb": ("Four skaters form a tight box around the low slot while "
                  "one forward tracks the puck on the perimeter. Protect the "
                  "royal road at all costs, force everything outside, and "
                  "let the goalie see clean shots. Bend-don't-break, taken "
                  "literally — low danger against, low pressure for."),
        "exemplars": ["Dallas Stars", "New York Islanders"],
        "attack": 0.98, "defense": 0.92, "pace": 0.95,
        "shot_vol": 0.98, "shot_qual": 0.94, "physical": 1.05,
        "wants": {"bravery": 1.3, "positioning": 1.2, "strength": 1.1,
                  "shot_blocking": 1.2},
    },
    "dz_slide_match": {
        "name": "Aggressive Slide & Match",
        "blurb": ("Track your man anywhere below the hash marks. Mirror his "
                  "cuts, swap on screens without a word, and never let an "
                  "elite shooter catch and release clean. Takes away time "
                  "and space entirely — and punishes any defender who can't "
                  "skate."),
        "exemplars": ["Vegas Golden Knights", "Carolina Hurricanes"],
        "attack": 1.01, "defense": 0.95, "pace": 1.04,
        "shot_vol": 1.00, "shot_qual": 0.97, "physical": 1.05,
        "wants": {"skating": 1.3, "stamina": 1.2, "anticipation": 1.2,
                  "aggressiveness": 1.1},
    },
}

# ---------------------------------------------------------------------------
# Offensive-zone attack — breaking structural integrity
# ---------------------------------------------------------------------------

OZONE_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "oz_micro": {
        "name": "Controlled Micro-Transitions",
        "blurb": ("No blind chips. Quick D-to-D movement, stretch passes to "
                  "flying forwards, and regroups that turn into controlled "
                  "entries with speed and possession — which multiply "
                  "scoring-chance probability over a 50/50 dump chase. "
                  "Let the defensemen skate or push the pace dynamically."),
        "exemplars": ["Colorado Avalanche", "Tampa Bay Lightning"],
        "attack": 1.04, "defense": 1.00, "pace": 1.00,
        "shot_vol": 1.00, "shot_qual": 1.06, "physical": 0.95,
        "wants": {"passing": 1.3, "puckhandling": 1.3, "skating": 1.2,
                  "flair": 1.2, "decisions": 1.1},
    },
    "oz_cycle": {
        "name": "Cycle & Point-Shot Volume",
        "blurb": ("Heavy loops down low, short passes through the office "
                  "behind the net, and low-to-high feeds that activate the "
                  "defensemen for point shots through traffic. Wear the "
                  "opposing D down physically and mentally — make the big "
                  "man bend over for forty minutes and he'll break in the "
                  "third."),
        "exemplars": ["St. Louis Blues", "Florida Panthers",
                      "Vegas Golden Knights"],
        "attack": 1.03, "defense": 0.99, "pace": 0.95,
        "shot_vol": 0.98, "shot_qual": 1.08, "physical": 1.25,
        "wants": {"strength": 1.3, "work_rate": 1.2, "bravery": 1.1,
                  "puckhandling": 1.1, "flair": 0.7},
    },
    "oz_flow": {
        "name": "Five-Man Flow",
        "blurb": ("Positionless rotation: the defenseman pinches deep, the "
                  "center drops to cover the point, and nobody is where the "
                  "coverage chart says they should be. Forces traditional "
                  "man-to-man and zone schemes into rushed hand-offs — and "
                  "broken coverage in the slot."),
        "exemplars": ["Toronto Maple Leafs", "New Jersey Devils"],
        "attack": 1.02, "defense": 1.01, "pace": 1.03,
        "shot_vol": 1.02, "shot_qual": 1.03, "physical": 1.00,
        "wants": {"skating": 1.2, "passing": 1.2, "flair": 1.2,
                  "anticipation": 1.1, "decisions": 1.1},
    },
    "oz_rush": {
        "name": "Stretch & Speed (Rush Offense)",
        "blurb": ("Drive the wingers wide to pull defensemen deep, open the "
                  "middle for the trailer, and hit the seam before the "
                  "defense sets its feet. Speed beats structure — enter "
                  "against unorganized coverage and the chaos is yours. "
                  "Track-meet hockey when the legs are there."),
        "exemplars": ["Colorado Avalanche", "Edmonton Oilers"],
        "attack": 1.05, "defense": 1.02, "pace": 1.10,
        "shot_vol": 1.08, "shot_qual": 1.00, "physical": 0.90,
        "wants": {"skating": 1.3, "shoot_pass_tendency": 1.3, "flair": 1.1,
                  "shooting": 1.2},
    },
    "oz_netfront": {
        "name": "Net-Front Saturation",
        "blurb": ("When clean cross-seam plays dry up — playoff hockey, "
                  "sticks and bodies in every lane — manufacture uglier "
                  "chaos. Point shots aimed at shin pads, two forwards "
                  "crashing the crease, garbage goals off screens, tips, "
                  "and rebounds. Goalies hate this team."),
        "exemplars": ["St. Louis Blues", "Florida Panthers",
                      "Vegas Golden Knights"],
        "attack": 1.04, "defense": 1.00, "pace": 1.02,
        "shot_vol": 1.10, "shot_qual": 1.02, "physical": 1.20,
        "wants": {"bravery": 1.3, "strength": 1.2, "work_rate": 1.2,
                  "deflections": 1.2, "flair": 0.7},
    },
}

# ---------------------------------------------------------------------------
# Breakout systems — how the puck leaves your zone
# ---------------------------------------------------------------------------

BREAKOUT_SYSTEMS: Dict[str, Dict[str, Any]] = {
    "bo_controlled": {
        "name": "Controlled Breakout",
        "blurb": ("D-to-D, short support, and clean exits with numbers. "
                  "Never surrender possession cheaply — the breakout is the "
                  "first pass of the attack, not an escape. Patient, "
                  "repeatable, and kind to defensemen who think the game."),
        "exemplars": ["Tampa Bay Lightning", "Dallas Stars"],
        "attack": 1.01, "defense": 0.99, "pace": 0.99,
        "shot_vol": 1.00, "shot_qual": 1.01, "physical": 0.95,
        "wants": {"passing": 1.3, "decisions": 1.2, "puckhandling": 1.2,
                  "positioning": 1.1},
    },
    "bo_stretch": {
        "name": "Stretch Pass Breakout",
        "blurb": ("High forwards and home-run passes. One touch out of the "
                  "zone and the winger is behind their D before the gap "
                  "closes — or the pass is picked and you're defending a "
                  "2-on-1. Maximum verticality, maximum variance."),
        "exemplars": ["Colorado Avalanche", "Edmonton Oilers"],
        "attack": 1.03, "defense": 1.02, "pace": 1.05,
        "shot_vol": 1.02, "shot_qual": 1.02, "physical": 0.95,
        "wants": {"passing": 1.3, "skating": 1.2, "flair": 1.1,
                  "anticipation": 1.1},
    },
    "bo_direct": {
        "name": "Direct / Chip & Chase",
        "blurb": ("Up and out, then win the race. Chip it past the pinching "
                  "defenseman, get it deep, and let the forecheck go to "
                  "work. Concedes the pretty entry for territorial pressure "
                  "— simple, honest, and exhausting to defend."),
        "exemplars": ["Philadelphia Flyers", "Nashville Predators"],
        "attack": 1.00, "defense": 1.00, "pace": 1.03,
        "shot_vol": 1.03, "shot_qual": 0.98, "physical": 1.10,
        "wants": {"skating": 1.2, "work_rate": 1.3, "aggressiveness": 1.2,
                  "strength": 1.1},
    },
}

# ---------------------------------------------------------------------------
# Unified identities — the doc's Phase 4. A coach doesn't pick modules at
# random; he builds a closed-loop system where every action triggers a
# predictable reaction. One click installs all seven modules.
# ---------------------------------------------------------------------------

IDENTITY_PRESETS: Dict[str, Dict[str, Any]] = {
    "chaos_pressure": {
        "name": "Chaos & Pressure",
        "tagline": "High event — pin them deep, overwhelm with numbers",
        "blurb": ("The 2-1-2 swarm suffocates breakouts, the rush attack "
                  "strikes before coverages set, and aggressive man-to-man "
                  "takes away time and space everywhere. You accept the "
                  "odd-man rushes against because the system generates "
                  "three times the offensive-zone touches it allows."),
        "exemplars": ["Carolina Hurricanes", "Florida Panthers"],
        "modules": {
            "forecheck": "forecheck_212_swarm",
            "neutral_zone": "nz_counterpress",
            "dzone": "dz_slide_match",
            "ozone": "oz_rush",
            "breakout": "bo_stretch",
            "pp": "shoot_first",
            "pk": "aggressive_swarm",
        },
    },
    "stranglehold": {
        "name": "Stranglehold",
        "tagline": "Low event — defensive chess, suffocate with the lead",
        "blurb": ("The 1-3-1 trap compresses the neutral zone, controlled "
                  "regroups refuse to surrender possession, and the passive "
                  "box protects the royal road at all costs. Turn the game "
                  "into a chess match: refuse to beat yourself, limit "
                  "transition, and strangle third periods with a lead."),
        "exemplars": ["New York Islanders", "Dallas Stars"],
        "modules": {
            "forecheck": "forecheck_122",
            "neutral_zone": "nz_trap_131",
            "dzone": "dz_box",
            "ozone": "oz_cycle",
            "breakout": "bo_controlled",
            "pp": "umbrella",
            "pk": "passive_box",
        },
    },
    "hybrid_transition": {
        "name": "Hybrid Transition",
        "tagline": "The modern standard — balanced, read-based, lethal",
        "blurb": ("What most multi-cup teams actually play. The 1-2-2 "
                  "forecheck without over-committing, micro-transitions "
                  "that enter with control, hybrid coverage keyed on reads, "
                  "and elite skating defensemen flipping defense into "
                  "quick-strike offense. No extremes — just answers."),
        "exemplars": ["Tampa Bay Lightning", "Vegas Golden Knights"],
        "modules": {
            "forecheck": "forecheck_122",
            "neutral_zone": "nz_regroup",
            "dzone": "dz_hybrid",
            "ozone": "oz_micro",
            "breakout": "bo_controlled",
            "pp": "one_three_one",
            "pk": "diamond",
        },
    },
}

# ---------------------------------------------------------------------------
# Category metadata — the seven whiteboard rows, in presentation order.
# ---------------------------------------------------------------------------

ES_CATEGORIES = (
    ("forecheck", "Forecheck", "FORECHECK_SYSTEMS"),
    ("neutral_zone", "Neutral Zone", "NEUTRAL_ZONE_SYSTEMS"),
    ("dzone", "D-Zone Coverage", "DZONE_SYSTEMS"),
    ("ozone", "O-Zone Attack", "OZONE_SYSTEMS"),
    ("breakout", "Breakout", "BREAKOUT_SYSTEMS"),
)
ST_CATEGORIES = (
    ("pp", "Power Play", "POWERPLAY_SYSTEMS"),
    ("pk", "Penalty Kill", "PENALTY_KILL_SYSTEMS"),
)
ALL_CATEGORIES = ES_CATEGORIES + ST_CATEGORIES

# Fast lookup: category key -> catalog dict (filled after PP/PK defined below).
CATALOGS: Dict[str, Dict[str, Dict[str, Any]]] = {}


def _register_catalogs() -> None:
    CATALOGS.update({
        "forecheck": FORECHECK_SYSTEMS,
        "neutral_zone": NEUTRAL_ZONE_SYSTEMS,
        "dzone": DZONE_SYSTEMS,
        "ozone": OZONE_SYSTEMS,
        "breakout": BREAKOUT_SYSTEMS,
        "pp": POWERPLAY_SYSTEMS,
        "pk": PENALTY_KILL_SYSTEMS,
    })


# ---------------------------------------------------------------------------
# System families & tactical counters — the hockey-answer layer.
#
# Every system belongs to a philosophical family: "pressure" (hunt the puck,
# high event, chaos) or "structure" (patience, layers, low event), with
# "balanced" systems fitting either room. Families preserve playstyle
# identity: a Chaos & Pressure team answers with pressure, a Stranglehold
# team answers with structure. Cross-family answers only happen when the
# coach is highly adaptable or the room is getting shelled (dire intel).
#
# TACTICAL_COUNTERS maps a system key -> (answer_category, answer_key,
# reason). Keys are unique across catalogs so one flat table covers all
# seven modules. This is the table AI coaches consult when the intel says
# one of your systems is beating them.
# ---------------------------------------------------------------------------

SYSTEM_FAMILIES: Dict[str, str] = {
    # forecheck
    "forecheck_122": "structure",
    "forecheck_212_swarm": "pressure",
    # neutral zone
    "nz_trap_131": "structure",
    "nz_regroup": "structure",
    "nz_counterpress": "pressure",
    # d-zone
    "dz_hybrid": "balanced",
    "dz_box": "structure",
    "dz_slide_match": "pressure",
    # o-zone
    "oz_micro": "balanced",
    "oz_cycle": "structure",
    "oz_flow": "balanced",
    "oz_rush": "pressure",
    "oz_netfront": "pressure",
    # breakout
    "bo_controlled": "structure",
    "bo_stretch": "pressure",
    "bo_direct": "pressure",
    # power play
    "umbrella": "structure",
    "one_three_one": "structure",
    "overload": "structure",
    "spread": "balanced",
    "net_crash": "pressure",
    "shoot_first": "pressure",
    "motion": "balanced",
    # penalty kill
    "diamond": "pressure",
    "passive_box": "structure",
    "wedge_plus_one": "balanced",
    "aggressive_swarm": "pressure",
    "czech_press": "pressure",
    "split": "balanced",
}

# Identity presets -> family (used for philosophy compatibility).
PRESET_FAMILIES: Dict[str, str] = {
    "chaos_pressure": "pressure",
    "stranglehold": "structure",
    "hybrid_transition": "balanced",
}

TACTICAL_COUNTERS: Dict[str, tuple] = {
    # ---- vs your power play: the PK that takes away its money look ----
    "umbrella":      ("pk", "passive_box",
                      "the box takes away the royal road the umbrella wants"),
    "one_three_one": ("pk", "wedge_plus_one",
                      "the +1 pressures the high forward who runs the 1-3-1"),
    "overload":      ("pk", "split",
                      "the split takes away the overloaded side"),
    "spread":        ("pk", "diamond",
                      "the diamond forces the spread to the perimeter"),
    "net_crash":     ("pk", "passive_box",
                      "the box collapses on the net-front traffic"),
    "shoot_first":   ("pk", "czech_press",
                      "the press takes away the point barrage"),
    "motion":        ("pk", "aggressive_swarm",
                      "the swarm disrupts the rotation before it sets"),
    # ---- vs your forecheck: the breakout that beats it ----
    "forecheck_212_swarm": ("breakout", "bo_controlled",
                            "short safe exits — don't feed the swarm"),
    "forecheck_122":       ("breakout", "bo_stretch",
                            "beat the passive 1-2-2 up the ice"),
    # ---- vs your neutral zone: the answer ----
    "nz_trap_131":     ("breakout", "bo_direct",
                        "chip it past the trap — never carry into the 1-3-1"),
    "nz_counterpress": ("breakout", "bo_stretch",
                        "stretch them before the pinch arrives"),
    "nz_regroup":      ("neutral_zone", "nz_counterpress",
                        "pinch their regroup and force the turnover"),
    # ---- vs your O-zone: the D-zone coverage ----
    "oz_cycle":    ("dzone", "dz_slide_match",
                    "slide and match the cycle man-for-man"),
    "oz_rush":     ("dzone", "dz_hybrid",
                    "hybrid clogs the rush lanes through the middle"),
    "oz_netfront": ("dzone", "dz_box",
                    "the box protects the house"),
    "oz_flow":     ("dzone", "dz_hybrid",
                    "hybrid takes away the middle of the five-man flow"),
    "oz_micro":    ("dzone", "dz_slide_match",
                    "match their micro-movement step for step"),
    # ---- vs your breakout: the forecheck / NZ that eats it ----
    "bo_stretch":    ("forecheck", "forecheck_122",
                      "the 1-2-2 sits in the stretch lanes"),
    "bo_controlled": ("forecheck", "forecheck_212_swarm",
                      "swarm the short controlled exits"),
    "bo_direct":     ("neutral_zone", "nz_trap_131",
                      "the trap eats chip-and-chase alive"),
    # ---- vs your penalty kill: the PP that picks it apart ----
    "passive_box":      ("pp", "shoot_first",
                         "point barrage through the passive box"),
    "diamond":          ("pp", "spread",
                         "the spread stretches the diamond's rotations"),
    "wedge_plus_one":   ("pp", "overload",
                         "overload the side away from the +1"),
    "aggressive_swarm": ("pp", "umbrella",
                         "the umbrella keeps the puck above the swarm"),
    "czech_press":      ("pp", "motion",
                         "rotation escapes the press"),
    "split":            ("pp", "one_three_one",
                         "the 1-3-1 attacks the split's seam"),
    # ---- vs your D-zone: the O-zone attack that solves it ----
    "dz_box":         ("ozone", "oz_cycle",
                       "the cycle pulls the box out of the house"),
    "dz_hybrid":      ("ozone", "oz_flow",
                       "five-man flow overloads the hybrid reads"),
    "dz_slide_match": ("ozone", "oz_micro",
                       "micro-transitions beat man-matching with misdirection"),
}


def system_family(system_key: str) -> str:
    """Philosophical family of a system: pressure / structure / balanced."""
    return SYSTEM_FAMILIES.get(system_key, "balanced")


def team_family(team: Any) -> str:
    """A team's philosophical family from its identity preset, else the
    majority family of its installed modules."""
    try:
        ident = matching_identity(team)
        if ident and ident in PRESET_FAMILIES:
            return PRESET_FAMILIES[ident]
        tk = team_tactics(team)
        fams = [system_family(k) for k in tk.values()]
        # balanced modules don't vote
        votes = [f for f in fams if f != "balanced"]
        if not votes:
            return "balanced"
        return "pressure" if votes.count("pressure") >= votes.count("structure") \
            else "structure"
    except Exception:
        return "balanced"


def families_compatible(team_fam: str, system_key: str) -> bool:
    """Can this team install this system without betraying its philosophy?
    Balanced is the universal donor — it fits any room."""
    sys_fam = system_family(system_key)
    return (team_fam == "balanced" or sys_fam == "balanced"
            or team_fam == sys_fam)


# ---------------------------------------------------------------------------
# Save migration — the old flat offense/defense/philosophy model maps onto
# the zone modules. Old saves load and translate once, then play on.
# ---------------------------------------------------------------------------

_LEGACY_OFFENSE_MAP = {
    # legacy offense -> {module category: new system}
    "rush_attack":    {"ozone": "oz_rush", "breakout": "bo_stretch"},
    "heavy_cycle":    {"ozone": "oz_cycle"},
    "dump_chase":     {"ozone": "oz_netfront", "breakout": "bo_direct"},
    "counterattack":  {"ozone": "oz_flow", "neutral_zone": "nz_counterpress"},
    "net_front":      {"ozone": "oz_netfront"},
    "skill_possession": {"ozone": "oz_micro"},
    "balanced":       {"ozone": "oz_flow"},
}
_LEGACY_DEFENSE_MAP = {
    "neutral_trap":   {"neutral_zone": "nz_trap_131"},
    "trap_131":       {"neutral_zone": "nz_trap_131"},
    "left_wing_lock": {"forecheck": "forecheck_122"},
    "aggressive_man": {"forecheck": "forecheck_212_swarm",
                       "dzone": "dz_slide_match"},
    "passive_box":    {"dzone": "dz_box"},
    "hybrid":         {"dzone": "dz_hybrid"},
    "pressure_swarm": {"forecheck": "forecheck_212_swarm",
                       "neutral_zone": "nz_counterpress"},
}
_LEGACY_PHILOSOPHY_MAP = {
    # philosophy nudges the forecheck/attack when nothing else claimed them
    "offense_first":  {"forecheck": "forecheck_212_swarm"},
    "defense_first":  {"neutral_zone": "nz_trap_131"},
    "heavy_identity": {"ozone": "oz_cycle"},
    "possession":     {"ozone": "oz_micro"},
    "development":    {"breakout": "bo_stretch"},
    "pragmatist":     {},
}

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

_register_catalogs()


def _normalize_catalogs() -> None:
    """Scale every scoring-relevant catalog so the SEEDED league is neutral.

    The 32 NHL seeds are the reference mix: with every team on its
    day-one identity, league-wide scoring and pace sit exactly at the
    engine's calibrated level. Relative differences between systems are
    preserved, so copying the trap still slows the whole league down --
    that's the dynamic story, not calibration drift.

    Combined attack = forecheck x neutral_zone x ozone x breakout, so the
    seed-weighted mean of that FULL product is divided out of the ozone
    catalog (same for defense via the d-zone catalog). _apply_edge is
    linear, so normalizing the raw product mean fixes the edged mean too.
    Pace multiplies five catalogs: the product mean is split across them
    with the 5th root (within a percent of neutral -- well inside
    tolerance, as the matchup takes a geometric mean across the pair).
    """
    ES_ALL = (FORECHECK_SYSTEMS, NEUTRAL_ZONE_SYSTEMS, DZONE_SYSTEMS,
              OZONE_SYSTEMS, BREAKOUT_SYSTEMS)

    seeds = list(NHL_TEAM_TACTICS.values())
    n = len(seeds)

    def wmean(fn):
        return sum(fn(sd) for sd in seeds) / n

    # Attack: center the full four-module product via the ozone catalog.
    a_prod = wmean(lambda sd: FORECHECK_SYSTEMS[sd["forecheck"]]["attack"]
                   * NEUTRAL_ZONE_SYSTEMS[sd["neutral_zone"]]["attack"]
                   * OZONE_SYSTEMS[sd["ozone"]]["attack"]
                   * BREAKOUT_SYSTEMS[sd["breakout"]]["attack"])
    for sys in OZONE_SYSTEMS.values():
        sys["attack"] /= a_prod
    # Defense: center the full three-module product via the d-zone catalog.
    d_prod = wmean(lambda sd: FORECHECK_SYSTEMS[sd["forecheck"]]["defense"]
                   * NEUTRAL_ZONE_SYSTEMS[sd["neutral_zone"]]["defense"]
                   * DZONE_SYSTEMS[sd["dzone"]]["defense"])
    for sys in DZONE_SYSTEMS.values():
        sys["defense"] /= d_prod
    sv_prod = wmean(lambda sd: FORECHECK_SYSTEMS[sd["forecheck"]]["shot_vol"]
                    * NEUTRAL_ZONE_SYSTEMS[sd["neutral_zone"]]["shot_vol"]
                    * DZONE_SYSTEMS[sd["dzone"]]["shot_vol"]
                    * OZONE_SYSTEMS[sd["ozone"]]["shot_vol"]
                    * BREAKOUT_SYSTEMS[sd["breakout"]]["shot_vol"])
    for sys in OZONE_SYSTEMS.values():
        sys["shot_vol"] /= sv_prod
    sq_prod = wmean(lambda sd: FORECHECK_SYSTEMS[sd["forecheck"]]["shot_qual"]
                    * NEUTRAL_ZONE_SYSTEMS[sd["neutral_zone"]]["shot_qual"]
                    * DZONE_SYSTEMS[sd["dzone"]]["shot_qual"]
                    * OZONE_SYSTEMS[sd["ozone"]]["shot_qual"]
                    * BREAKOUT_SYSTEMS[sd["breakout"]]["shot_qual"])
    for sys in OZONE_SYSTEMS.values():
        sys["shot_qual"] /= sq_prod
    pp_mean = wmean(lambda sd: POWERPLAY_SYSTEMS[sd["pp"]]["pp"])
    pk_mean = wmean(lambda sd: PENALTY_KILL_SYSTEMS[sd["pk"]]["pk"])
    for sys in POWERPLAY_SYSTEMS.values():
        sys["pp"] /= pp_mean
    for sys in PENALTY_KILL_SYSTEMS.values():
        sys["pk"] /= pk_mean

    # Pace multiplies five catalogs: split the correction with the 5th root.
    pf = wmean(lambda sd: FORECHECK_SYSTEMS[sd["forecheck"]]["pace"]
               * NEUTRAL_ZONE_SYSTEMS[sd["neutral_zone"]]["pace"]
               * DZONE_SYSTEMS[sd["dzone"]]["pace"]
               * OZONE_SYSTEMS[sd["ozone"]]["pace"]
               * BREAKOUT_SYSTEMS[sd["breakout"]]["pace"])
    pf5 = pf ** (1.0 / 5.0)
    for cat in ES_ALL:
        for sys in cat.values():
            sys["pace"] /= pf5

    # Physicality feeds the hit engine: same logic, 5th root.
    ph_mean = wmean(lambda sd: FORECHECK_SYSTEMS[sd["forecheck"]]
                    .get("physical", 1.0)
                    * NEUTRAL_ZONE_SYSTEMS[sd["neutral_zone"]]
                    .get("physical", 1.0)
                    * DZONE_SYSTEMS[sd["dzone"]].get("physical", 1.0)
                    * OZONE_SYSTEMS[sd["ozone"]].get("physical", 1.0)
                    * BREAKOUT_SYSTEMS[sd["breakout"]]
                    .get("physical", 1.0))
    ph5 = ph_mean ** (1.0 / 5.0)
    for cat in ES_ALL:
        for sys in cat.values():
            if "physical" in sys:
                sys["physical"] /= ph5


# ---------------------------------------------------------------------------
# Seeded NHL identities — every team true to itself on day one
# ---------------------------------------------------------------------------

NHL_TEAM_TACTICS: Dict[str, Dict[str, str]] = {
    # Every club seeded to its real-world identity. Doc tie-ins honored:
    # 1-2-2 forecheck -> PIT/TBL/VGK; swarm -> COL/FLA/CAR; 1-3-1 trap ->
    # TBL/MTL; regroup -> COL/EDM; slide&match D -> VGK/CAR; passive box ->
    # DAL/NYI; cycle/volume -> STL/FLA/VGK; rush -> COL/EDM; 1-3-1 PP ->
    # TBL/WSH.
    "Anaheim Ducks":           {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "one_three_one", "pk": "diamond"},
    "Boston Bruins":           {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_cycle",    "breakout": "bo_direct",    "pp": "umbrella",      "pk": "diamond"},
    "Buffalo Sabres":          {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "umbrella",      "pk": "diamond"},
    "Calgary Flames":          {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_counterpress", "dzone": "dz_box",        "ozone": "oz_cycle",    "breakout": "bo_direct",    "pp": "overload",      "pk": "wedge_plus_one"},
    "Carolina Hurricanes":     {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_counterpress", "dzone": "dz_slide_match","ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "one_three_one", "pk": "aggressive_swarm"},
    "Chicago Blackhawks":      {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_controlled","pp": "one_three_one", "pk": "diamond"},
    "Colorado Avalanche":      {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_regroup",      "dzone": "dz_slide_match","ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "one_three_one", "pk": "aggressive_swarm"},
    "Columbus Blue Jackets":   {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_controlled","pp": "umbrella",      "pk": "diamond"},
    "Dallas Stars":            {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_box",        "ozone": "oz_micro",    "breakout": "bo_controlled","pp": "umbrella",      "pk": "passive_box"},
    "Detroit Red Wings":       {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_controlled","pp": "overload",      "pk": "diamond"},
    "Edmonton Oilers":         {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "one_three_one", "pk": "diamond"},
    "Florida Panthers":        {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_counterpress", "dzone": "dz_hybrid",     "ozone": "oz_cycle",    "breakout": "bo_direct",    "pp": "net_crash",     "pk": "aggressive_swarm"},
    "Los Angeles Kings":       {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_box",        "ozone": "oz_cycle",    "breakout": "bo_controlled","pp": "umbrella",      "pk": "wedge_plus_one"},
    "Minnesota Wild":          {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_hybrid",     "ozone": "oz_cycle",    "breakout": "bo_direct",    "pp": "overload",      "pk": "passive_box"},
    "Montreal Canadiens":      {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "umbrella",      "pk": "diamond"},
    "Nashville Predators":     {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_counterpress", "dzone": "dz_box",        "ozone": "oz_netfront", "breakout": "bo_direct",    "pp": "umbrella",      "pk": "diamond"},
    "New Jersey Devils":       {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "one_three_one", "pk": "aggressive_swarm"},
    "New York Islanders":      {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_box",        "ozone": "oz_netfront", "breakout": "bo_direct",    "pp": "net_crash",     "pk": "passive_box"},
    "New York Rangers":        {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_controlled","pp": "one_three_one", "pk": "diamond"},
    "Ottawa Senators":         {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_counterpress", "dzone": "dz_slide_match","ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "umbrella",      "pk": "diamond"},
    "Philadelphia Flyers":     {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_counterpress", "dzone": "dz_slide_match","ozone": "oz_netfront", "breakout": "bo_direct",    "pp": "net_crash",     "pk": "aggressive_swarm"},
    "Pittsburgh Penguins":     {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_controlled","pp": "umbrella",      "pk": "diamond"},
    "San Jose Sharks":         {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "umbrella",      "pk": "diamond"},
    "Seattle Kraken":          {"forecheck": "forecheck_122",       "neutral_zone": "nz_counterpress", "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_controlled","pp": "overload",      "pk": "wedge_plus_one"},
    "St. Louis Blues":         {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_box",        "ozone": "oz_cycle",    "breakout": "bo_direct",    "pp": "overload",      "pk": "passive_box"},
    "Tampa Bay Lightning":     {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_hybrid",     "ozone": "oz_micro",    "breakout": "bo_controlled","pp": "one_three_one", "pk": "diamond"},
    "Toronto Maple Leafs":     {"forecheck": "forecheck_212_swarm", "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_flow",     "breakout": "bo_stretch",   "pp": "umbrella",      "pk": "diamond"},
    "Utah Mammoth":            {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "overload",      "pk": "diamond"},
    "Vancouver Canucks":       {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_hybrid",     "ozone": "oz_rush",     "breakout": "bo_stretch",   "pp": "umbrella",      "pk": "aggressive_swarm"},
    "Vegas Golden Knights":    {"forecheck": "forecheck_122",       "neutral_zone": "nz_counterpress", "dzone": "dz_slide_match","ozone": "oz_cycle",    "breakout": "bo_direct",    "pp": "overload",      "pk": "passive_box"},
    "Washington Capitals":     {"forecheck": "forecheck_122",       "neutral_zone": "nz_regroup",      "dzone": "dz_box",        "ozone": "oz_netfront", "breakout": "bo_direct",    "pp": "one_three_one", "pk": "diamond"},
    "Winnipeg Jets":           {"forecheck": "forecheck_122",       "neutral_zone": "nz_trap_131",     "dzone": "dz_box",        "ozone": "oz_cycle",    "breakout": "bo_controlled","pp": "umbrella",      "pk": "wedge_plus_one"},
}


DEFAULT_TACTICS: Dict[str, str] = dict(
    IDENTITY_PRESETS["hybrid_transition"]["modules"])


_register_catalogs()
_normalize_catalogs()


# ---------------------------------------------------------------------------
# Accessors
# ---------------------------------------------------------------------------

def _get(d: Any, key: str, default: Any = 0.0) -> float:
    try:
        return float(getattr(d, key, default) or 0.0)
    except (TypeError, ValueError):
        return float(default)


def _migrate_legacy_tactics(raw: Dict[str, str]) -> Dict[str, str]:
    """Translate the old flat offense/defense/philosophy model onto the
    zone modules. Old saves load and translate once, then play on."""
    out: Dict[str, str] = {}
    leg_off = _LEGACY_OFFENSE_MAP.get(raw.get("offense", ""), {})
    leg_def = _LEGACY_DEFENSE_MAP.get(raw.get("defense", ""), {})
    leg_phi = _LEGACY_PHILOSOPHY_MAP.get(raw.get("philosophy", ""), {})
    for src in (leg_off, leg_def, leg_phi):
        for cat, key in src.items():
            out.setdefault(cat, key)
    return out


def team_tactics(team: Any) -> Dict[str, str]:
    """This team's seven module choices, with sane defaults.

    Saves from the old flat model (offense/defense/philosophy) are
    migrated onto the zone modules on read."""
    raw = getattr(team, "tactics", None) or {}
    out = dict(DEFAULT_TACTICS)
    if isinstance(raw, dict):
        if any(k in raw for k in ("offense", "defense", "philosophy")):
            for k, v in _migrate_legacy_tactics(raw).items():
                out[k] = v
        for k in out:
            v = raw.get(k)
            if v and v in CATALOGS.get(k, {}):
                out[k] = v
    return out


def apply_identity_preset(team: Any, preset_key: str) -> bool:
    """One click: install a unified identity (Phase 4) across all modules.

    The room learns it like any system change -- familiarity drops and
    rebuilds. Returns False for an unknown preset."""
    preset = IDENTITY_PRESETS.get(preset_key)
    if not preset:
        return False
    try:
        ensure_team_tactics(team)
        modules = preset["modules"]
        changed = [c for c in modules
                   if team.tactics.get(c) != modules[c]]
        if not changed:
            return True
        for c in changed:
            team.tactics[c] = modules[c]
        fam = _get(team, "tactics_familiarity", 85)
        team.tactics_familiarity = max(40.0, min(fam, 45)
                                       if fam > 45 else fam - 10)
        _bust_tactics_cache(team)
    except Exception:
        return False
    return True


def matching_identity(team: Any) -> Optional[str]:
    """If the team's modules exactly match a preset, its key; else None."""
    try:
        tk = team_tactics(team)
        for key, preset in IDENTITY_PRESETS.items():
            if all(tk.get(c) == preset["modules"].get(c)
                   for c in preset["modules"]):
                return key
    except Exception:
        pass
    return None


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
    catalog = CATALOGS.get(category)
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
            team.tactics_familiarity = max(
                45.0, min(fam, 45) if fam > 45 else fam - 10)
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
        for cat, _label, _attr in ALL_CATEGORIES:
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
    catalog = CATALOGS.get(category, {})
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
            # Chasing the game: stretch the ice, then hunt the puck.
            p = 0.15 + adapt / 250.0
            if _random.random() > p:
                return None
            if tk.get("ozone") != "oz_rush":
                return {"category": "ozone", "old_key": tk["ozone"],
                        "new_key": "oz_rush",
                        "line": (f"{cname} is stretching the ice -- {tname} "
                                 f"to a rush attack chasing the game.")}
            if tk.get("forecheck") != "forecheck_212_swarm":
                return {"category": "forecheck",
                        "old_key": tk["forecheck"],
                        "new_key": "forecheck_212_swarm",
                        "line": (f"{tname} are hunting in twos -- {cname} "
                                 f"has sent the swarm after the puck.")}
            return None
        if score_diff >= 3 and style in ("Tactician", "Drill Sergeant"):
            # Protecting a lead: a defensive mind locks it down.
            p = 0.10 + adapt / 400.0
            if _random.random() > p:
                return None
            if tk.get("neutral_zone") != "nz_trap_131":
                return {"category": "neutral_zone",
                        "old_key": tk["neutral_zone"],
                        "new_key": "nz_trap_131",
                        "line": (f"{tname} are clogging the neutral zone -- "
                                 f"{cname} has gone to the 1-3-1 trap.")}
            if tk.get("dzone") != "dz_box":
                return {"category": "dzone", "old_key": tk["dzone"],
                        "new_key": "dz_box",
                        "line": (f"{cname} is locking it down -- {tname} "
                                 f"to a passive box protecting the lead.")}
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

def player_system_fit(player: Any, system_key: str,
                      category: str = "ozone") -> float:
    """0.6..1.2 -- how well this skater's game suits a system module.

    A sniper with 90 speed flies in a rush attack and drowns in a
    chip-and-chase grinder's role. Uses the real tendency attributes:
    shoot_pass_tendency, hitting_tendency, flair, work_rate, aggressiveness.
    """
    catalog = CATALOGS.get(category, OZONE_SYSTEMS)
    sys = catalog.get(system_key) or next(iter(catalog.values()))
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
    """Roster-average fit to the O-zone attack system, 0.92..1.08."""
    try:
        tk = team_tactics(team).get("ozone", "oz_micro")
        roster = getattr(team, "roster", None) or []
        skaters = [p for p in roster
                   if not str(getattr(p, "primary_position", "")).upper()
                   .startswith("G")]
        if not skaters:
            return 1.0
        avg = sum(player_system_fit(p, tk, "ozone")
                    for p in skaters) / len(skaters)
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
        for cat, _label, _attr in ALL_CATEGORIES:
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
    "Drill Sergeant": {"forecheck": "forecheck_122",
                       "neutral_zone": "nz_trap_131",
                       "dzone": "dz_box", "ozone": "oz_cycle",
                       "breakout": "bo_direct",
                       "pp": "net_crash", "pk": "passive_box"},
    "Player's Coach":  {"forecheck": "forecheck_122",
                       "neutral_zone": "nz_regroup",
                       "dzone": "dz_hybrid", "ozone": "oz_flow",
                       "breakout": "bo_stretch",
                       "pp": "motion", "pk": "diamond"},
    "Tactician":       {"forecheck": "forecheck_122",
                       "neutral_zone": "nz_trap_131",
                       "dzone": "dz_hybrid", "ozone": "oz_micro",
                       "breakout": "bo_controlled",
                       "pp": "one_three_one", "pk": "wedge_plus_one"},
    "Motivator":       {"forecheck": "forecheck_212_swarm",
                       "neutral_zone": "nz_counterpress",
                       "dzone": "dz_slide_match", "ozone": "oz_rush",
                       "breakout": "bo_stretch",
                       "pp": "shoot_first", "pk": "aggressive_swarm"},
    "Developer":       {"forecheck": "forecheck_122",
                       "neutral_zone": "nz_regroup",
                       "dzone": "dz_hybrid", "ozone": "oz_rush",
                       "breakout": "bo_stretch",
                       "pp": "umbrella", "pk": "diamond"},
    "Balanced":        dict(DEFAULT_TACTICS),
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


# --- shot-volume calibration vs real NHL (2016-17..2025-26, via StatMuse) ---
# Real league: ~29.5 SOG/team/game; team-season means run ~24.5 (worst) to
# ~34 (best), std ~2. Playoffs dip lower; single games in the low teens
# happen a few times a season league-wide.
# SHOT_LIFT raises the sim's base chance-gen to real volume. SHOT_VOL_DAMPEN
# compresses the cross-team spread so trap teams sit ~25 not ~11.
# SHOT_QUAL_TRADEOFF dilutes per-shot quality as volume rises (extra shots
# are worse shots) -- scoring stays in the 2.7-3.6 band.
SHOT_LIFT = 1.38
SHOT_VOL_DAMPEN = 0.35
SHOT_QUAL_TRADEOFF = 0.35
SHOT_LIFT_DILUTION = SHOT_LIFT ** SHOT_QUAL_TRADEOFF  # ~1.119


def resolve_team_tactics(team: Any) -> Dict[str, float]:
    """Collapse a team's seven modules into engine multipliers.

    attack  = forecheck x neutral_zone x ozone x breakout
    defense = forecheck x neutral_zone x dzone   (lower = stingier)
    pace    = all five even-strength modules multiplied
    Special teams resolve separately. Familiarity mutes every edge
    toward 1.0 -- a team mid-transition plays like a team thinking.

    Memoized per (systems, familiarity, coach prefs): systems only change
    between games, so one resolution serves the whole game.
    """
    tk = team_tactics(team)
    fam_raw = _get(team, "tactics_familiarity", 85)
    coach = _coach_for(team)
    prefs = ensure_coach_tactics(coach) if coach is not None else {}
    cache_key = (tuple(tk.get(c[0], "") for c in ALL_CATEGORIES),
                 round(fam_raw, 1), tuple(sorted(prefs.items())))
    try:
        ck, cv = getattr(team, "_tactics_cache", (None, None))
        if ck == cache_key and isinstance(cv, dict):
            return cv
    except Exception:
        pass

    def _sys(cat, fallback):
        return CATALOGS[cat].get(tk.get(cat), CATALOGS[cat][fallback])

    fc = _sys("forecheck", "forecheck_122")
    nz = _sys("neutral_zone", "nz_regroup")
    dz = _sys("dzone", "dz_hybrid")
    oz = _sys("ozone", "oz_micro")
    bo = _sys("breakout", "bo_controlled")
    pp = _sys("pp", "umbrella")
    pk = _sys("pk", "diamond")

    fam = _familiarity_factor(team)
    fit = team_system_fit(team)

    # A coach fighting the room's systems dulls everything slightly.
    try:
        cfit = coach_tactics_fit(coach, team)
        coach_factor = 0.97 + 0.03 * cfit
    except Exception:
        coach_factor = 1.0

    attack = _apply_edge(fc["attack"] * nz["attack"] * oz["attack"]
                         * bo["attack"] * fit, fam) * coach_factor
    defense = _apply_edge(fc["defense"] * nz["defense"] * dz["defense"],
                          fam) * coach_factor
    pace = _apply_edge(fc["pace"] * nz["pace"] * dz["pace"] * oz["pace"]
                       * bo["pace"], fam)
    pace = max(0.85, min(1.18, pace))
    vol_raw = (fc["shot_vol"] * nz["shot_vol"] * dz["shot_vol"]
               * oz["shot_vol"] * bo["shot_vol"])
    qual_raw = (fc["shot_qual"] * nz["shot_qual"] * dz["shot_qual"]
                * oz["shot_qual"] * bo["shot_qual"])
    # Dampen the cross-team volume spread (sqrt) and trade volume for
    # quality: high-volume systems generate more, worse shots -- the extra
    # attempts are point shots and bad angles, not grade-A looks.
    shot_vol = _apply_edge(vol_raw ** SHOT_VOL_DAMPEN, fam)
    shot_qual = _apply_edge(qual_raw / (vol_raw ** SHOT_QUAL_TRADEOFF), fam)
    out = {
        "attack": attack,
        "defense": defense,
        "pace": pace,
        "shot_vol": shot_vol,
        "shot_qual": shot_qual,
        "pp": _apply_edge(pp["pp"], fam),
        "pk": _apply_edge(pk["pk"], fam),
        "sh_threat": pk.get("sh_threat", 1.0),
        "physical": (fc.get("physical", 1.0) * nz.get("physical", 1.0)
                     * dz.get("physical", 1.0) * oz.get("physical", 1.0)
                     * bo.get("physical", 1.0)),
        "fit": fit,
        "familiarity": _get(team, "tactics_familiarity", 85),
        "identity": matching_identity(team),
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
        "home_shot_vol": h["shot_vol"],
        "away_shot_vol": a["shot_vol"],
        "home_shot_qual": h["shot_qual"],
        "away_shot_qual": a["shot_qual"],
        "physical": (h["physical"] + a["physical"]) / 2.0,
    }


# ---------------------------------------------------------------------------
# Copycat league: steal what wins
# ---------------------------------------------------------------------------

# Categories coaches steal, weighted: special teams first, always.
# ---------------------------------------------------------------------------
# Tactical intel — per-opponent tracking of system effectiveness.
#
# After every game vs the user's team, the AI files what the user ran and
# how well it worked: goals, shots, PP%. plan_adaptation (adaptive_rivals)
# reads this to answer the specific system that's beating them, not just
# "they score a lot". Coaches don't overreact to one game: nothing fires
# until a system has hurt them across 2+ meetings.
# ---------------------------------------------------------------------------

_INTEL_MEETINGS_CAP = 5

# Effectiveness thresholds that trigger a hockey answer. PP% is the most
# sensitive (league average ~20%); even-strength answers need sustained
# shelling because goals are noisier. Defensive answers (your PK / D-zone
# is stifling them) key off their goals per game vs you.
_INTEL_PP_THRESHOLD = 0.27
_INTEL_GPG_THRESHOLD = 3.8
_INTEL_GA_THRESHOLD = 2.4
_INTEL_MIN_MEETINGS = 2


def record_tactical_intel(ai_team: Any, user_team: Any, user_goals: int,
                          ai_goals: int = 0,
                          user_shots: Optional[int] = None,
                          user_pp_pct: Optional[float] = None) -> None:
    """File one meeting's intel: the user's systems and their effectiveness
    against this AI team. Never raises; inert without teams."""
    try:
        user_name = getattr(user_team, "team_name", None)
        if not user_name:
            return
        intel = getattr(ai_team, "tactical_intel", None)
        if not isinstance(intel, dict):
            intel = {}
        meetings = intel.get(user_name)
        if not isinstance(meetings, list):
            meetings = []
        meetings.append({
            "systems": dict(team_tactics(user_team)),
            "g": int(user_goals or 0),
            "ga": int(ai_goals or 0),
            "sog": user_shots,
            "pp_pct": user_pp_pct,
        })
        intel[user_name] = meetings[-_INTEL_MEETINGS_CAP:]
        ai_team.tactical_intel = intel
    except Exception:
        pass


def get_tactical_intel(ai_team: Any, user_team: Any) -> list:
    """Recent meetings vs this user, oldest first. Empty list if none."""
    try:
        user_name = getattr(user_team, "team_name", "")
        intel = getattr(ai_team, "tactical_intel", None) or {}
        meetings = intel.get(user_name, [])
        return list(meetings) if isinstance(meetings, list) else []
    except Exception:
        return []


def damaging_user_systems(ai_team: Any, user_team: Any) -> list:
    """Which of the user's CURRENT systems are hurting this AI team?

    Returns [(category, system_key, heat)] sorted by heat desc, where heat
    is effectiveness relative to the answer threshold (>1.0 = answerable).
    Only systems with 2+ meetings of intel qualify — one bad night isn't
    a trend, and real coaches know it.
    """
    out = []
    try:
        meetings = get_tactical_intel(ai_team, user_team)
        if len(meetings) < _INTEL_MIN_MEETINGS:
            return out
        current = team_tactics(user_team)
        for cat, sys_key in current.items():
            if cat not in CATALOGS or not sys_key:
                continue
            # Meetings where the user ran this exact system in this category.
            rel = [m for m in meetings
                   if isinstance(m.get("systems"), dict)
                   and m["systems"].get(cat) == sys_key]
            if len(rel) < _INTEL_MIN_MEETINGS:
                continue
            if cat == "pp":
                vals = [m["pp_pct"] for m in rel
                        if m.get("pp_pct") is not None]
                if not vals:
                    continue
                avg = sum(vals) / len(vals)
                heat = avg / _INTEL_PP_THRESHOLD
            elif cat in ("pk", "dzone"):
                # Your PK / D-zone is stifling them: their goals vs you
                # are the signal (lower = hotter).
                vals = [m.get("ga", 0) for m in rel]
                avg = sum(vals) / len(vals)
                if avg <= 0:
                    continue
                heat = _INTEL_GA_THRESHOLD / avg
            else:
                vals = [m.get("g", 0) for m in rel]
                avg = sum(vals) / len(vals)
                heat = avg / _INTEL_GPG_THRESHOLD
            if heat > 1.0:
                out.append((cat, sys_key, heat))
        out.sort(key=lambda t: t[2], reverse=True)
    except Exception:
        pass
    return out


COPYCAT_WEIGHTS = (("pp", 0.30), ("pk", 0.25), ("ozone", 0.20),
                   ("forecheck", 0.15), ("dzone", 0.10))


# Historical echoes for the copycat news feed: when a style sweeps the
# league, the story writes itself the way it did in real life.
BLUEPRINT_LORE: Dict[str, str] = {
    "nz_trap_131": "the way the whole league chased Lemaire's trap after '95",
    "forecheck_212_swarm": "echoes of the '17-18 Golden Knights — everyone talked about it, few could skate it",
    "one_three_one": "everyone wants Tampa's 1-3-1 on the man advantage",
    "oz_cycle": "the Kings' heavy cycle blueprint — you need the horses to play it",
    "umbrella": "the default setting of the modern power play",
    "dz_box": "the Islanders' house-first gospel",
}


def _blueprint_heat(league: Any, champ: Any, champ_sys: Dict[str, str]) -> float:
    """How hot is the champion's blueprint? Real copycat dynamics:

    - A repeat champion (or the same core systems winning again) is a
      DYNASTY blueprint (heat 1.8) — this is the Lemaire trap scenario,
      three Cups in nine years, the league had no choice but to answer.
    - A first-time winner is INTRIGUING (heat 1.0) — the Vegas scenario:
      talked about all summer, rarely fully copied.
    Heat is tracked on the league so dynasties build over seasons.
    """
    try:
        champ_name = getattr(champ, "team_name", "?")
        core = frozenset(champ_sys.get(c, "") for c in
                         ("forecheck", "neutral_zone", "ozone", "pp"))
        last_champ = getattr(league, "_last_cup_champ", None)
        last_core = getattr(league, "_last_champ_core", None)
        dynasties = getattr(league, "_blueprint_dynasties", None) or {}
        # This title extends a run if the same team repeats or the same
        # core systems win again (a philosophy proving it travels).
        run = 1
        if last_champ == champ_name:
            run = int(dynasties.get(champ_name, 1)) + 1
        elif last_core is not None and last_core == core:
            run = 2  # same philosophy, new flag-bearer
        dynasties[champ_name] = run
        league._blueprint_dynasties = dynasties
        league._last_cup_champ = champ_name
        league._last_champ_core = core
        return 1.8 if run >= 2 else 1.0
    except Exception:
        return 1.0


def _roster_fits_system(team: Any, category: str, system_key: str,
                        threshold: float = 0.78) -> bool:
    """Can this roster actually play the system? You can't trap without
    smart centers or swarm without fast wingers — copying what you can't
    play is how coaches get fired."""
    try:
        roster = getattr(team, "roster", None) or []
        skaters = [p for p in roster
                   if not str(getattr(p, "primary_position", ""))
                   .upper().startswith("G")]
        if not skaters:
            return True
        avg = sum(player_system_fit(p, system_key, category)
                  for p in skaters[:20]) / min(len(skaters), 20)
        # player_system_fit is 0.6..1.2; 0.78 ≈ a room that can survive it.
        return avg >= threshold
    except Exception:
        return True


def offseason_copycat(league: Any, rng=None) -> list:
    """One offseason pass: AI teams may steal from the Cup champion's
    blueprint — but like real life, slowly and selectively.

    Real copycat dynamics (the history of winners):
    - One Cup makes a style INTRIGUING (Vegas '18: talked about, rarely
      copied). Sustained winning makes it a DYNASTY blueprint (Lemaire's
      trap: three Cups, the league had to answer). Heat gates the odds.
    - Teams steal PIECES, not identities — usually the PP, PK, or
      forecheck, the three things coaches actually lift first.
    - Philosophy filters everything: a Stranglehold room doesn't install
      a 2-1-2 swarm. Cross-family theft needs a highly adaptable coach.
    - Personnel is destiny: rooms that can't skate the system don't take
      it, no matter how shiny the Cup is.
    - Stubborn veteran coaches (low adaptability, high control need) would
      rather retire than change — and often do.
    - At most 3 teams adopt per summer. The league never moves as one.

    Adopting a system costs familiarity (see set_team_system) — copying
    isn't free. Returns [(team_name, category, system_key, lore_line)].
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
        heat = _blueprint_heat(league, champ, champ_sys)
        cats, weights = zip(*COPYCAT_WEIGHTS)
        for team in teams:
            try:
                if len(copied) >= 3:
                    break
                if team is champ:
                    continue
                if getattr(team, "is_user_team", False):
                    continue
                mine = team_tactics(team)
                coach = _coach_for(team)
                adapt = float(getattr(coach, "adaptability", 65) or 65)
                ctrl = float(getattr(coach, "control_need", 50) or 50)
                # The immovables: low adaptability + high control need =
                # the coach retires before he changes (Trotz/Lemaire types).
                if adapt < 40 and ctrl > 60:
                    continue
                # Base 6%: copycat is a slow league-wide drift, not a stampede.
                # Heat (dynasty blueprint) up to ~1.8x; adaptability opens
                # minds, control_need closes them.
                p = (0.06 * heat * (0.5 + adapt / 130.0)
                     * (1.1 - ctrl / 200.0))
                if rng.random() >= p:
                    continue
                fam = team_family(team)
                # Weighted pick, then roll off categories the champ doesn't
                # improve on — filtered by philosophy and personnel.
                order = list(rng.choices(cats, weights=weights, k=len(cats)))
                for cat in order:
                    want = champ_sys.get(cat)
                    if not want or mine.get(cat) == want:
                        continue
                    # Philosophy: stay in your family's lane unless the
                    # coach is genuinely malleable (adapt >= 80).
                    if (not families_compatible(fam, want)) and adapt < 80:
                        continue
                    # Personnel: don't steal what the room can't skate.
                    if not _roster_fits_system(team, cat, want):
                        continue
                    if set_team_system(team, cat, want):
                        lore = BLUEPRINT_LORE.get(want, "")
                        copied.append((getattr(team, "team_name", "?"),
                                       cat, want, lore))
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
    """Human-readable identity lines for UI / media.

    Leads with the unified identity (Phase 4) when the modules match a
    preset, then lists the seven module choices."""
    tk = team_tactics(team)
    labels = {"forecheck": "Forecheck", "neutral_zone": "Neutral zone",
              "dzone": "D-zone", "ozone": "O-zone attack",
              "breakout": "Breakout", "pp": "Power play",
              "pk": "Penalty kill"}
    lines = []
    ident = matching_identity(team)
    if ident:
        preset = IDENTITY_PRESETS[ident]
        lines.append(f"Identity: {preset['name']} -- {preset['tagline']}")
    for cat, _label, _attr in ALL_CATEGORIES:
        sys = CATALOGS[cat].get(tk.get(cat), {})
        lines.append(f"{labels[cat]}: {sys.get('name', tk.get(cat))}")
    return lines


