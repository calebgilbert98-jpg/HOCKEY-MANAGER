#!/usr/bin/env python3
"""qa_factor_parity.py -- factor-level parity: lightweight vs AdvancedGameSim.

Beyond aggregate distributions: perturb ONE factor at a time on deep-copied
team pairs and measure the marginal effect (delta vs baseline) in EACH
engine. Both engines read the same team/player attributes, so the same
perturbation operator applies to both; only the engines' internal
weighting differs -- which is exactly what we are measuring.

Perturbation operators (documented, shared by both engines):
  talent+8 (home) : +8 to every rated attribute of all home skaters (cap 100)
  weak goalie     : away starter's goalie attributes all -> 30
  elite goalie    : home starter's goalie attributes all -> 95
  toxic room      : all home players' morale -> 15
  trap vs trap    : both teams tactic_even_strength = 'Very Defensive'
  rush vs rush    : both teams tactic_even_strength = 'Very Offensive'

Design notes:
  - One fixed representative pair (median-strength home vs median away).
  - Deep-copy the pair fresh for EVERY game (both engines mutate teams via
    injuries); reseed per game index AFTER copy/setup (CRN: baseline and
    variant share the seed within an engine, so deltas are low-variance).
  - preseason=True for the lightweight (skips the per-player stat pass).
  - AdvancedGameSim stdout (injury prints) is suppressed during runs.

Usage: python3 qa_factor_parity.py [--quick]
  --quick: 100 games/variant/engine. Default: 400.
Exit 0 = all factor deltas within tolerance, 1 = any failure.
"""
import sys, os, copy, random, io, statistics
from contextlib import redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SEED = 20260929
N = 500
QUICK = "--quick" in sys.argv
if QUICK:
    N = 150

# Tolerances on |lightweight_delta - advanced_delta| per factor (goals/game)
TOL_TALENT = 0.25
TOL_GOALIE = 0.10
TOL_MORALE = 0.10
TOL_TACTICS = 0.25

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((name, cond, detail))
    print(f"[{PASS if cond else FAIL}] {name}" + (f" -- {detail}" if detail else ""))


SKATER_ATTRS = [
    "skating", "shooting", "shooting_accuracy", "shooting_power",
    "wristshot", "slapshot", "one_timer", "backhand", "passing",
    "passing_accuracy", "passing_creativity", "deking", "stickhandling",
    "vision", "hockey_iq", "offensive_awareness", "defensive_awareness",
    "off_the_puck", "composure", "endurance", "determination", "faceoffs",
    "faceoff_wins", "loose_puck", "screen_shots", "strength", "checking",
    "bodycheck", "shot_blocking", "pokecheck", "anticipation",
    "aggressiveness", "balance", "pressure_player",
]
GOALIE_ATTRS = [
    "goaltending", "reflexes", "positioning", "rebound_control",
    "puck_handling", "glove_hand", "stick_side", "breakaway_skill",
    "confidence", "focus", "composure",
]


def _is_goalie(p):
    return getattr(getattr(p, "primary_position", None), "name", "") == "GOALIE"


def _bump(p, attrs, delta=None, set_to=None):
    for a in attrs:
        try:
            v = getattr(p, a, None)
            if not isinstance(v, (int, float)):
                continue
            nv = set_to if set_to is not None else v + delta
            setattr(p, a, max(1, min(100, int(round(nv)))))
        except Exception:
            pass


def _starter_goalie(team):
    """The goalie who would start: lineup Goalies[0], else best by overall."""
    try:
        lineup = getattr(team, "lineup", None) or {}
        gs = lineup.get("Goalies") or []
        if gs and gs[0] is not None:
            return gs[0]
    except Exception:
        pass
    gs = [p for p in team.roster if _is_goalie(p)]
    gs.sort(key=lambda p: p.overall_rating(), reverse=True)
    return gs[0] if gs else None


# variant -> function(home, away)
def v_talent8(h, a):
    for p in h.roster:
        if not _is_goalie(p):
            _bump(p, SKATER_ATTRS, delta=8)


def _all_goalies(team):
    return [p for p in team.roster if _is_goalie(p)]


def v_weak_goalie(h, a):
    # Nerf EVERYTHING: the lightweight dresses the best healthy goalie,
    # the event sim dresses lineup Goalies[0] -- the only way both face
    # the same goaltending is no un-nerfed goalie left on the roster.
    for g in _all_goalies(a):
        _bump(g, GOALIE_ATTRS, set_to=30)


def v_elite_goalie(h, a):
    for g in _all_goalies(h):
        _bump(g, GOALIE_ATTRS, set_to=95)


def v_toxic(h, a):
    for p in h.roster:
        try:
            p.morale = 15
        except Exception:
            pass


def v_trap(h, a):
    h.tactic_even_strength = "Very Defensive"
    a.tactic_even_strength = "Very Defensive"


def v_rush(h, a):
    h.tactic_even_strength = "Very Offensive"
    a.tactic_even_strength = "Very Offensive"


VARIANTS = [
    ("baseline", None),
    ("talent+8 (home)", v_talent8),
    ("weak goalie (away 30)", v_weak_goalie),
    ("elite goalie (home 95)", v_elite_goalie),
    ("toxic room (home)", v_toxic),
    ("trap vs trap", v_trap),
    ("rush vs rush", v_rush),
]


def run_lightweight(gui, lw, h, a):
    gui._strength_cache = {}
    _w, _l, (hs, ag), _ot = lw(h, a, preseason=True)
    return hs, ag


def run_advanced(h, a, lg):
    from quick_sim import AdvancedGameSim
    with redirect_stdout(io.StringIO()):
        sim = AdvancedGameSim(h, a, league=lg)
        _w, _l, (hs, ag), _ev, _not = sim.run()
    return hs, ag


def main():
    random.seed(SEED)
    from database_generator import generate_database
    from playtest_driver import nhl_teams

    print("generating league ...")
    lg = generate_database("Small")
    teams = nhl_teams(lg)
    print(f"league ready: {len(teams)} NHL teams")

    import main as main_mod
    gui = main_mod.HockeyManagerGUI.__new__(main_mod.HockeyManagerGUI)
    gui._strength_cache = {}
    gui.notable_events = []
    gui.add_news = None
    gui.app = None
    gui.league = lg
    lw = main_mod.HockeyManagerGUI._simulate_game_lightweight.__get__(gui)

    # Representative matchups: random pairs across the league (same approach
    # as qa_sim_parity) so factor deltas are league-average marginal
    # effects, not quirks of one pairing.
    random.seed(SEED + 777)
    pairs = []
    while len(pairs) < N:
        h, a = random.choice(teams), random.choice(teams)
        if h is not a:
            pairs.append((h.team_name, a.team_name))
    by_name = {t.team_name: t for t in teams}
    print(f"{len(pairs)} random pairs")

    # Sanity: achieved overall deltas of the attribute operators
    h_probe, a_probe = copy.deepcopy(by_name[pairs[0][0]]), copy.deepcopy(by_name[pairs[0][1]])
    pre = sum(p.overall_rating() for p in h_probe.roster
              if not _is_goalie(p)) / max(1, sum(
                  1 for p in h_probe.roster if not _is_goalie(p)))
    v_talent8(h_probe, a_probe)
    post = sum(p.overall_rating() for p in h_probe.roster
               if not _is_goalie(p)) / max(1, sum(
                   1 for p in h_probe.roster if not _is_goalie(p)))
    print(f"talent+8 operator: home skater avg overall {pre:.1f} -> {post:.1f} "
          f"(delta {post-pre:+.1f})")
    g_pre = _starter_goalie(a_probe).overall_rating()
    v_weak_goalie(h_probe, a_probe)
    print(f"weak-goalie operator: away starter {_starter_goalie(a_probe).overall_rating()} "
          f"(was {g_pre})")
    g_pre = _starter_goalie(h_probe).overall_rating()
    v_elite_goalie(h_probe, a_probe)
    print(f"elite-goalie operator: home starter {_starter_goalie(h_probe).overall_rating()} "
          f"(was {g_pre})")

    # engine: 0=lightweight, 1=advanced
    deltas = {}  # (engine, variant) -> (d_home, d_away, se_home, se_away)
    base_means = {}
    for e_idx, e_name in ((0, "lightweight"), (1, "advanced")):
        print(f"\n== {e_name} ==")
        # baseline games first (also gives the home-ice edge row)
        base_hg, base_ag = [], []
        for i, (hn, an) in enumerate(pairs):
            h, a = copy.deepcopy(by_name[hn]), copy.deepcopy(by_name[an])
            random.seed(SEED + e_idx * 1_000_000 + i)
            if e_idx == 0:
                hs, ag = run_lightweight(gui, lw, h, a)
            else:
                hs, ag = run_advanced(h, a, lg)
            base_hg.append(hs)
            base_ag.append(ag)
        bh = sum(base_hg) / N
        ba = sum(base_ag) / N
        base_means[e_name] = (bh, ba)
        print(f"  baseline: home {bh:.3f} / away {ba:.3f} "
              f"(home edge {bh-ba:+.3f})")
        for v_idx, (v_name, v_fn) in enumerate(VARIANTS[1:], start=1):
            dh, da = [], []
            for i, (hn, an) in enumerate(pairs):
                h, a = copy.deepcopy(by_name[hn]), copy.deepcopy(by_name[an])
                v_fn(h, a)
                # CRN: same seed as baseline game i within this engine
                random.seed(SEED + e_idx * 1_000_000 + i)
                if e_idx == 0:
                    hs, ag = run_lightweight(gui, lw, h, a)
                else:
                    hs, ag = run_advanced(h, a, lg)
                dh.append(hs - base_hg[i])
                da.append(ag - base_ag[i])
            mh = sum(dh) / N
            ma = sum(da) / N
            seh = statistics.pstdev(dh) / (N ** 0.5) if N > 1 else 0.0
            sea = statistics.pstdev(da) / (N ** 0.5) if N > 1 else 0.0
            deltas[(e_name, v_name)] = (mh, ma, seh, sea)
            print(f"  {v_name:22s} d_home={mh:+.3f} (se {seh:.3f}) "
                  f"d_away={ma:+.3f} (se {sea:.3f})")

    print("\n--- factor-delta table (variant minus baseline, goals/game) ---")
    print(f"  {'factor':22s} {'adv d_home':>10s} {'light d_home':>12s} "
          f"{'adv d_away':>10s} {'light d_away':>12s}")
    all_ok = True
    for v_idx, (v_name, _v) in enumerate(VARIANTS[1:], start=1):
        ah, aa, _, _ = deltas[("advanced", v_name)]
        lh, la, _, _ = deltas[("lightweight", v_name)]
        print(f"  {v_name:22s} {ah:+10.3f} {lh:+12.3f} {aa:+10.3f} {la:+12.3f}")
    # home-ice edge row (baseline home minus away within each engine)
    lbh, lba = base_means["lightweight"]
    abh, aba = base_means["advanced"]
    print(f"  {'home-ice edge':22s} {abh-aba:+10.3f} {lbh-lba:+12.3f} "
          f"{'--':>10s} {'--':>12s}   (baseline home-away margin)")

    print("\n--- factor parity checks (|light delta - adv delta|) ---")
    def frow(label, v_name, tol, which="both"):
        ah, aa, _, _ = deltas[("advanced", v_name)]
        lh, la, _, _ = deltas[("lightweight", v_name)]
        parts = []
        ok = True
        if which in ("both", "home"):
            d = abs(lh - ah)
            parts.append(f"home {d:.3f} (tol {tol})")
            ok &= d <= tol
        if which in ("both", "away"):
            d = abs(la - aa)
            parts.append(f"away {d:.3f} (tol {tol})")
            ok &= d <= tol
        check(label, ok, f"{v_name}: " + ", ".join(parts)
              + f"  [adv {ah:+.3f}/{aa:+.3f} vs light {lh:+.3f}/{la:+.3f}]")
        return ok

    ok = True
    ok &= frow("talent+8 own-scoring response", "talent+8 (home)", TOL_TALENT, "home")
    ok &= frow("talent+8 opponent suppression", "talent+8 (home)", TOL_TALENT, "away")
    ok &= frow("weak goalie response", "weak goalie (away 30)", TOL_GOALIE, "home")
    ok &= frow("elite goalie response", "elite goalie (home 95)", TOL_GOALIE, "away")
    ok &= frow("toxic room response", "toxic room (home)", TOL_MORALE, "home")
    ok &= frow("trap-vs-trap total response", "trap vs trap", TOL_TACTICS, "both")
    ok &= frow("rush-vs-rush total response", "rush vs rush", TOL_TACTICS, "both")

    n_fail = sum(1 for _n, c, _d in results if not c)
    print(f"\n{len(results) - n_fail}/{len(results)} checks green")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
