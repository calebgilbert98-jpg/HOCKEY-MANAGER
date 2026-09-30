#!/usr/bin/env python3
"""B1 talent-hierarchy regression + measurement harness.

DIAGNOSIS (2026-09-29, pre-composites):
  deployment_policy.py docstring (lines 415-417, 431) claims an 85 OVR
  max-heater can never pass a 93 OVR max-cold for any coaching style.
  Measured: the inversion happens, and at vibe extremes all six styles
  behave IDENTICALLY -- style modulation is dead where it matters most.

  Root causes (line refs in deployment_policy.py):
  (a) FORM DOUBLE-COUNT: the base term (lines 450-451:
      perf = 80 + 20*form-shape at 10% weight) counts form, AND the heater
      bonus (lines 494-497: heater_m = 1 + 0.08*heat01*recency_w inside the
      vibe product) counts it again. Kink signature: d(score)/d(form) jumps
      14.8x at form=50 (0.000101 below -> 0.001500 above).
  (b) CLAMP RAILS wider than the talent gap: the vibe clamp [0.95, 1.05] is
      a 10.5% spread; the 85-vs-93 talent gap is only 8.6%. So a max-vibes
      85 beats a min-vibes 93 at ANY form -- crossover threshold 0.0 for all
      six styles, stubborn and adaptable alike. Vibes alone erase the gap;
      form is incidental. At the rails every style computes the same
      numbers, which is the unrealistic part.

STATUS: B1 CLOSED 2026-09-30. Formula rewrite implemented in
  deployment_policy.py: form single-counted (heater_m removed from the
  vibe product; form enters once, smoothly, via the base perf term scaled
  by style x adaptability form_sens), style-dependent vibe clamps
  (4.1%-6.4% spread, always below the 85-vs-93 gap of 8.4%), false
  docstring rewritten. X1-X4 flipped from xcheck to hard check() --
  all green: kink 1.0x, drill_sergeant unreachable, ordering
  ds(unreachable) > stubborn(93.5) > adaptable(60.8) > players_coach(55.8),
  pc crossover needs genuine heat (55.8 in (50, 100]).

PROTOCOL NOTE: measurements drive _player_deployment_score directly with
  neutral-vs-tilted vibe protocols. If Track 2 moves form into the
  composites module, revisit the fake-player plumbing (mesh_form source).

Run headless:  DISPLAY=:99 python3 qa_talent_hierarchy.py
Exit code 0 = all guards green. XFAIL lines are the OPEN B1 acceptance
set -- they encode Muck's desired end-state and fail until the rewrite.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import deployment_policy as dp
from deployment_policy import _player_deployment_score, leverage_score

fails = []
xfailed = []
xpassed = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name
          + (f"  -- {detail}" if detail else ""), flush=True)
    if not cond:
        fails.append(name)


def xcheck(name, cond, detail=""):
    """Desired end-state assertion. Expected to FAIL while B1 is open;
    flip to check() once the formula rewrite lands."""
    tag = "XFAIL " if not cond else "XPASS(UNEXPECTED) "
    print(tag + name + (f"  -- {detail}" if detail else ""), flush=True)
    if not cond:
        xfailed.append(name)
    else:
        xpassed.append(name)


# ---------------------------------------------------------------------------
# Fakes: identical players/coaches except for the axes under test, so every
# non-form vibe term cancels in comparisons and only form/OVR/style move.
# ---------------------------------------------------------------------------

class _P:
    def __init__(self, ovr, form, morale=50, att=50):
        self._ovr = ovr
        self.mesh_form = form
        self.morale = morale
        self.coachability = att
        self.work_ethic = att
        self.determination = att
        self.age = 26
        self.archetype = ""
        self.coach_bonds = {}
        self.usage_featured = False

    def overall_rating(self):
        return self._ovr


_COACH_BASE = dict(motivating=65, discipline=65, man_management=65,
                   tactical_knowledge=65, game_preparation=65,
                   leadership=65, working_with_youngsters=65,
                   player_development=65, adaptability=65)

# Attribute presets that force each reputation_system.coach_style() key
# (verified: coach_style returns the requested key for each).
_STYLE_ATTRS = {
    "drill_sergeant": dict(discipline=95, man_management=40),
    "players_coach": dict(man_management=95, discipline=40),
    "tactician": dict(tactical_knowledge=95, game_preparation=95),
    "motivator": dict(motivating=95, leadership=95),
    "developer": dict(working_with_youngsters=95, player_development=95),
    "balanced": {},
}

_STYLES = ["drill_sergeant", "motivator", "tactician",
           "players_coach", "developer", "balanced"]


class _C:
    def __init__(self, style, adaptability=65):
        d = dict(_COACH_BASE)
        d.update(_STYLE_ATTRS[style])
        d["adaptability"] = adaptability
        self.__dict__.update(d)
        self.id = "coach-b1"
        self.reputation = 50


_ADVICE = {"keys": set(), "featured_ids": set()}


def score(ovr, form, style, adaptability=65, morale=50, att=50):
    """_player_deployment_score with everything neutral except OVR/form and
    the coach's style/adaptability. direction="neutral" skips team reads."""
    coach = _C(style, adaptability)
    return _player_deployment_score(_P(ovr, form, morale, att), coach,
                                   style, _ADVICE, team=None,
                                   direction="neutral")


def crossover_threshold(style, adaptability=65):
    """Vibe-tilted protocol: heater at max morale/attitude, cold at min,
    cold form pinned at -100. Returns the minimum heater form in [0, 100]
    where the 85 passes the 93, or None if unreachable. None == +inf."""
    cold = score(93, -100, style, adaptability, morale=0, att=0)
    if score(85, 100, style, adaptability, morale=100, att=100) <= cold:
        return None
    lo, hi = 0.0, 100.0
    for _ in range(28):
        mid = (lo + hi) / 2.0
        if score(85, mid, style, adaptability,
                morale=100, att=100) > cold:
            hi = mid
        else:
            lo = mid
    return hi


# ---------------------------------------------------------------------------
# MEASUREMENT (prints the current-state numbers for the record)
# ---------------------------------------------------------------------------
print("== M1 clean protocol: neutral non-form vibes, cold form=-100 ==")
print(f"{'style':14} {'heater85@100':>12} {'cold93@-100':>11} {'inversion%':>10}")
for s in _STYLES:
    h = score(85, 100, s)
    c = score(93, -100, s)
    print(f"{s:14} {h:12.4f} {c:11.4f} {(h / c - 1) * 100:+10.2f}")
print("   (negative everywhere: no crossover at neutral vibes today)")
print()

print("== M2 crossover thresholds, vibe-tilted protocol ==")
print(f"{'style':14} {'threshold':>10}")
for s in _STYLES:
    t = crossover_threshold(s)
    print(f"{s:14} {'unreachable' if t is None else f'{t:.1f}':>10}")
for adapt, label in ((20, "stubborn(bal)"), (90, "adaptable(bal)")):
    t = crossover_threshold("balanced", adapt)
    print(f"{label:14} {'unreachable' if t is None else f'{t:.1f}':>10}")
print("   (0.0 everywhere today: vibes alone erase the 8.6% gap -- B1)")
print()

print("== M3 form double-count kink: d(score)/d(form) around form=50 ==")
s_lo = (score(85, 49, "balanced") - score(85, 30, "balanced")) / 19.0
s_hi = (score(85, 70, "balanced") - score(85, 51, "balanced")) / 19.0
print(f"slope(30->49)={s_lo:.6f}  slope(51->70)={s_hi:.6f}  "
      f"ratio={s_hi / s_lo:.1f}x  (single-count target ~1x)")
print()

print("== M4 max transient inversion, full sweep ==")
mx, arg = 0.0, None
for s in _STYLES:
    for adapt in (20, 65, 90):
        for fh in range(0, 101, 5):
            for fc in range(-100, 1, 5):
                a = score(85, fh, s, adapt, morale=100, att=100)
                b = score(93, fc, s, adapt, morale=0, att=0)
                if a > b:
                    r = a / b - 1.0
                    if r > mx:
                        mx, arg = r, (s, adapt, fh, fc)
print(f"max inversion {mx * 100:.2f}% at style={arg[0]} adapt={arg[1]} "
      f"heater_form={arg[2]} cold_form={arg[3]}")
print()

print("== M5 composition: where each system's heater reward lives ==")
c_bal = _C("balanced")
q_hot = _player_deployment_score(_P(85, 100), c_bal, "balanced",
                                _ADVICE, team=None, direction="neutral")
q_neu = _player_deployment_score(_P(85, 0), c_bal, "balanced",
                                _ADVICE, team=None, direction="neutral")
l_hot = leverage_score(_P(85, 100), c_bal, style_key="balanced")
l_neu = leverage_score(_P(85, 0), c_bal, style_key="balanced")
print(f"quantity (deployment score) heater/neutral = {q_hot / q_neu:.4f} "
      f"(bounded by the vibe clamp -- minutes)")
print(f"quality  (leverage score)   heater/neutral = {l_hot / l_neu:.4f} "
      f"(may swing to 1.30 -- minute QUALITY: OZ starts, mismatches)")
print("   distinct dimensions: minutes vs minute-quality. The double-")
print("   reward to avoid is form counted twice INSIDE quantity (B1a).")
print()

def _fmt_t(t):
    return "unreachable" if t is None else f"{t:.1f}"


print("== M6 DRAFT crossover targets (post-merge design; ordering is the "
      "contract, absolute forms are illustrative) ==")
print(f"{'style':16} {'today':>10} {'target':>28}")
_targets = [
    ("drill_sergeant", "unreachable",
     "trust hierarchy barely budges"),
    ("motivator", "unreachable",
     "motivation != hot-hand chasing"),
    ("tactician", "max heat only / unreachable",
     "matchups over streaks"),
    ("developer", "~85+",
     "youth reps, not vet hot hands"),
    ("balanced", "~75",
     "middle of the road"),
    ("players_coach", "~60-70",
     "rides the hot hand sooner"),
    ("stubborn (adapt<45)", "harder than adaptable",
     "recency_w 0.2: sticks with his guys"),
    ("adaptable (adapt>65)", "easier than stubborn",
     "recency_w 1.3: embraces recency"),
]
for s in _STYLES:
    t = crossover_threshold(s)
    tgt = dict((k, v) for k, v, _ in _targets)[s]
    print(f"{s:16} {('%.1f' % t) if t is not None else 'unreachable':>10} "
          f"{tgt:>28}")
print(f"{'stubborn(bal)':16} {_fmt_t(crossover_threshold('balanced', 20)):>10} "
      f"{'harder than adaptable':>28}")
print(f"{'adaptable(bal)':16} {_fmt_t(crossover_threshold('balanced', 90)):>10} "
      f"{'easier than stubborn':>28}")
print("   required ordering: drill_sergeant > stubborn > adaptable > "
      "players_coach")
print()

# ---------------------------------------------------------------------------
# GUARDS -- must hold today AND after the rewrite
# ---------------------------------------------------------------------------
print("== guards ==")
# G1: equal-form strict ordering per style (the claim that already holds).
g1_ok = True
for s in _STYLES:
    for f in (-75, -25, 0, 25, 75):
        if not (score(75, f, s) < score(92, f, s)
                and score(85, f, s) < score(93, f, s)):
            g1_ok = False
check("G1 equal-form strict ordering per style (75v92, 85v93)",
      g1_ok, "forms -75..75, all 6 styles")

# G2: any inversion stays transient and bounded (<=5%).
check("G2 max transient inversion <= 5%", mx <= 0.05,
      f"measured {mx * 100:.2f}%")

# G3: form is monotone at fixed OVR (the honest part of the form signal).
g3_ok = all(score(85, -100, s) < score(85, 0, s) < score(85, 100, s)
            for s in _STYLES)
check("G3 form monotone at fixed OVR per style", g3_ok)

# G4: quantity heater premium stays in the 5%-class per style. Principled
# bound: vibe-clamp 1.05 x base form-shape effect (~1.012) = 1.0626.
g4_worst = max(score(85, 100, s) / score(85, 0, s) for s in _STYLES)
check("G4 quantity heater/neutral premium <= 1.065 per style",
      g4_worst <= 1.065, f"worst {g4_worst:.4f}")

# G5: composition split -- quality may swing harder than quantity, and the
# leverage kill-switch never feeds back into quantity.
g5_ratio = (l_hot / l_neu) > (q_hot / q_neu)
dp.LEVERAGE_ENABLED = False
q_hot_off = _player_deployment_score(
    _P(85, 100), c_bal, "balanced", _ADVICE, team=None, direction="neutral")
dp.LEVERAGE_ENABLED = True
check("G5 leverage=quality only: quality premium > quantity premium, "
      "quantity identical with leverage on/off",
      g5_ratio and q_hot_off == q_hot,
      f"quality {l_hot / l_neu:.3f} vs quantity {q_hot / q_neu:.3f}")
print()

# ---------------------------------------------------------------------------
# B1-OPEN acceptance set -- desired end-state, fails until the rewrite
# ---------------------------------------------------------------------------
print("== B1-OPEN (expected failures until the formula rewrite) ==")
# X1: single-count form -- no 15x slope kink at form=50.
check("X1 form single-counted: slope kink at form=50 <= 4x",
       s_hi / s_lo <= 4.0, f"today {s_hi / s_lo:.1f}x")

# X2: drill sergeant's trust hierarchy barely budges -- crossover
# effectively unreachable within the full form range.
t_ds = crossover_threshold("drill_sergeant")
check("X2 drill_sergeant crossover unreachable (vibe-tilted)",
       t_ds is None, f"today threshold {_fmt_t(t_ds)}")

# X3: crossover difficulty ordering:
# drill_sergeant > stubborn > adaptable > players_coach.
t_stub = crossover_threshold("balanced", 20)
t_adapt = crossover_threshold("balanced", 90)
t_pc = crossover_threshold("players_coach")
inf = float("inf")
tds = inf if t_ds is None else t_ds
tst = inf if t_stub is None else t_stub
tad = inf if t_adapt is None else t_adapt
tpc = inf if t_pc is None else t_pc
check("X3 crossover ordering ds > stubborn > adaptable > players_coach",
       tds > tst > tad > tpc and tds == inf and tpc < inf,
       f"today ds={_fmt_t(t_ds)} stub={_fmt_t(t_stub)} "
       f"adapt={_fmt_t(t_adapt)} pc={_fmt_t(t_pc)}")

# X4: players' coach rides the hot hand -- but it must BE a hot hand:
# crossover needs genuine heat (form > 50), never vibes alone at form 0.
check("X4 players_coach crossover needs genuine heat (50 < t <= 100)",
       t_pc is not None and 50.0 < t_pc <= 100.0, f"today t={_fmt_t(t_pc)}")

print()
print(f"guards failed: {len(fails)}  XFAIL(open): {len(xfailed)}  "
      f"XPASS(unexpected): {len(xpassed)}")
if xpassed:
    print("UNEXPECTED XPASS (investigate -- behavior changed):",
          xpassed)
sys.exit(1 if fails else 0)
