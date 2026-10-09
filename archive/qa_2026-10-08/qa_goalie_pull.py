# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA for goalie-pull / 6-on-5 timing (goalie_pull.py + wiring). Headless."""
import sys
import types

sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


import goalie_pull as gp


def coach(name, **attrs):
    c = types.SimpleNamespace(first_name=name, last_name="Coach")
    for k, v in attrs.items():
        setattr(c, k, v)
    return c


class FakeTeam:
    def __init__(self, name):
        self.team_name = name


class FakeSim:
    def __init__(self, home, away, hcoach=None, acoach=None):
        self.home_team = home
        self.away_team = away
        self._home_coach = hcoach
        self._away_coach = acoach
        self._momentum_events = []
        self.period = 3
        self.clock = 100
        self.home_score = 1
        self.away_score = 2
        self.player_fatigue = {}
        self._log = []

    def _get_on_ice(self, team):
        return []

    def _log_event(self, msg, et):
        self._log.append((et, msg))

    def _emit_pbp(self, et, **kw):
        self._log.append(("pbp:" + et, kw))


home = FakeTeam("Home")
away = FakeTeam("Away")

# --- styles ----------------------------------------------------------------------
check("none coach -> balanced", gp.pull_style(None)["style"] == "balanced")
c1 = coach("Same", motivating=50, adaptability=50,
           level_of_discipline=50, defensive_coaching=50)
check("deterministic", gp.pull_style(c1) == gp.pull_style(coach("Same")))
agg = coach("Same", motivating=95, adaptability=95,
            level_of_discipline=10, defensive_coaching=10)
con = coach("Same", motivating=10, adaptability=10,
            level_of_discipline=95, defensive_coaching=95)
order = ["conservative", "balanced", "aggressive"]
check("attributes nudge style",
      order.index(gp.pull_style(agg)["style"])
      > order.index(gp.pull_style(con)["style"]))
check("style keys", all(k in gp.pull_style(c1)
                        for k in ("style", "down1", "down2", "nz_draw",
                                  "timeout_eager")))

# --- windows -----------------------------------------------------------------------
sim = FakeSim(home, away, hcoach=agg, acoach=con)
d1h, d2h, sh = gp.pull_windows(sim, home)
d1a, d2a, sa = gp.pull_windows(sim, away)
check("windows clamped sane",
      30 <= d1h <= 180 and 20 <= d2h <= 90 and 30 <= d1a <= 180)
check("aggressive pulls earlier", d1h >= d1a and d2h >= d2a)
check("down2 < down1", d2h < d1h and d2a < d1a)
check("coach_for home/away",
      gp.coach_for(sim, home) is agg and gp.coach_for(sim, away) is con)

# --- timeout lifecycle ---------------------------------------------------------------
check("timeout available", gp.timeout_available(sim, home))
check("use timeout", gp.use_timeout(sim, home, "test") is True)
check("timeout spent", not gp.timeout_available(sim, home))
check("second use refused", gp.use_timeout(sim, home, "test") is False)
check("boost once", gp.timeout_faceoff_boost(sim, home) == 8.0
      and gp.timeout_faceoff_boost(sim, home) == 0.0)
check("pending pull once",
      gp.timeout_pending_pull(sim, home) is True
      and gp.timeout_pending_pull(sim, home) is False)
check("timeout logged",
      any(e == "TIMEOUT" for e, _ in sim._log))

# --- timeout decision ------------------------------------------------------------------
import random
_real_random = random.random
random.random = lambda: 0.0  # eagerness always passes
try:
    sim2 = FakeSim(home, away, hcoach=agg, acoach=con)
    sim2.home_score, sim2.away_score = 2, 1  # away trails by 1
    check("timeout before late OZ draw",
          gp.maybe_timeout_before_draw(sim2, away, 31.0) is True)
    sim3 = FakeSim(home, away, hcoach=con, acoach=con)
    sim3.home_score, sim3.away_score = 2, 1
    check("conservative skips NZ draw",
          gp.maybe_timeout_before_draw(sim3, away, 100.0) is False)
    # find a coach whose attributes land on genuinely aggressive
    agg2 = None
    for i in range(50):
        cand = coach(f"Aggro{i}", motivating=95, adaptability=95,
                     level_of_discipline=10, defensive_coaching=10)
        if gp.pull_style(cand)["style"] == "aggressive":
            agg2 = cand
            break
    check("test coach is aggressive", agg2 is not None)
    sim4 = FakeSim(home, away, hcoach=agg2, acoach=agg2)
    sim4.home_score, sim4.away_score = 2, 1
    check("aggressive takes NZ draw",
          gp.maybe_timeout_before_draw(sim4, away, 100.0) is True)
    sim5 = FakeSim(home, away, hcoach=agg, acoach=agg)
    sim5.period = 2
    check("no timeout before 3rd", gp.maybe_timeout_before_draw(sim5, away, 169.0) is False)
    sim6 = FakeSim(home, away, hcoach=agg, acoach=agg)
    sim6.clock = 150
    check("no timeout outside 2:00",
          gp.maybe_timeout_before_draw(sim6, away, 169.0) is False)
    sim7 = FakeSim(home, away, hcoach=agg, acoach=agg)
    sim7.home_score, sim7.away_score = 3, 1  # away leads
    check("no timeout when leading",
          gp.maybe_timeout_before_draw(sim7, away, 169.0) is False)
    sim8 = FakeSim(home, away, hcoach=agg, acoach=agg)
    sim8.home_score, sim8.away_score = 2, 1
    check("no timeout for DZ draw",
          gp.maybe_timeout_before_draw(sim8, away, 169.0) is False)
finally:
    random.random = _real_random

# --- wiring --------------------------------------------------------------------------------
sim_src = open('/home/hatch/workspace/HOCKEY-MANAGER/simulation.py').read()
check("eligible uses coach windows", "pull_windows" in sim_src)
check("timeout decision wired", "maybe_timeout_before_draw" in sim_src)
check("faceoff boost wired", "timeout_faceoff_boost" in sim_src)
check("NZ pull branch", 'nz_draw' in sim_src)
check("PK guard kept", "never pull while shorthanded" in sim_src)
check("down-3 guard kept", "if deficit > 2:" in sim_src)
viz_src = open('/home/hatch/workspace/HOCKEY-MANAGER/pbp_visual_sim.py').read()
check("viz timeout handler", 'et == "timeout"' in viz_src)
check("timeout highlighted", '"timeout"' in viz_src)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
