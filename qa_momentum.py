"""QA for readable momentum (momentum.py + sim wiring + pull-timing risk).
Headless."""
import sys

sys.path.insert(0, '/home/hatch/workspace/HOCKEY-MANAGER')

passed = failed = 0


def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")


import momentum as mm


class FakeTeam:
    def __init__(self, name):
        self.team_name = name


class FakeSim:
    """Duck-typed GameSim surface that momentum.py reads."""

    def __init__(self):
        self.home_team = FakeTeam("Home")
        self.away_team = FakeTeam("Away")
        self.period = 1
        self.clock = 1200.0
        self._crowd_energy = 50.0
        self._crowd_mood = 30.0
        self._momentum_events = []
        self.momentum = None  # no story enum on the fake


def tick(sim, secs):
    sim.clock -= secs
    while sim.clock <= 0 and sim.period < 3:
        sim.clock += 1200.0
        sim.period += 1


# --- basic scoring -----------------------------------------------------------
s = FakeSim()
check("neutral start ~ crowd lean only",
      abs(mm.score(s) - 15 * 0.5 * 0.3) < 1.0)
mm.observe(s, "goal", s.home_team)
check("goal moves needle home", mm.score(s) > 20)
mm.observe(s, "goal", s.away_team)
check("offsetting goals ~ neutral", abs(mm.score(s)) < 12)

# --- decay --------------------------------------------------------------------
s = FakeSim()
mm.observe(s, "goal", s.home_team)
fresh = mm.score(s)
tick(s, 240)   # one half-life
half = mm.score(s)
# rolling part halves; crowd lean (constant) stays
check("decay roughly halves event weight",
      abs((half - 2.25) - (fresh - 2.25) * 0.5) < 3.0)
tick(s, 1200)
check("old events die out", abs(mm.score(s) - 2.25) < 3.0)

# --- clamp --------------------------------------------------------------------
import enum as _enum
class _GM(_enum.Enum):
    HH = 0; H = 1; SH = 2; E = 3; SA = 4; A = 5; AA = 6  # heavily-home(0)..away(6)
s = FakeSim()
s.momentum = _GM.HH  # story base also maxed
for _ in range(12):
    mm.observe(s, "goal", s.home_team)
check("clamped at +100", mm.score(s) == 100.0)
check("label onslaught", "onslaught" in mm.label(mm.score(s), "Home", "Away"))

# --- crowd amplification -------------------------------------------------------
s1, s2 = FakeSim(), FakeSim()
s1._crowd_energy, s1._crowd_mood = 95.0, 90.0   # loud, behind home
s2._crowd_energy, s2._crowd_mood = 95.0, -90.0  # loud, hostile to home
mm.observe(s1, "high_danger", s1.home_team)
mm.observe(s2, "high_danger", s2.home_team)
check("loud supportive building amplifies",
      mm.score(s1) > mm.score(s2))

# --- drivers -------------------------------------------------------------------
s = FakeSim()
s._crowd_energy, s._crowd_mood = 85.0, 80.0
mm.observe(s, "high_danger", s.home_team)
mm.observe(s, "high_danger", s.home_team)
mm.observe(s, "high_danger", s.home_team)
d = mm.drivers(s)
check("chance cluster driver",
      any("3 dangerous chances" in x for x in d))
check("crowd driver", any("roaring" in x for x in d))
s3 = FakeSim()
s3._crowd_energy, s3._crowd_mood = 15.0, 0.0
check("quiet building reads", any("Quiet" in x for x in mm.drivers(s3)))

# --- risk appetite: the ONLY mechanical output ----------------------------------
s = FakeSim()
check("neutral risk ~ 1.0", abs(mm.risk_appetite(s, s.home_team) - 1.0) < 0.02)
for _ in range(10):
    mm.observe(s, "goal", s.home_team)
rh = mm.risk_appetite(s, s.home_team)
ra = mm.risk_appetite(s, s.away_team)
check("surging team riskier", rh > 1.0)
check("team on heels safer", ra < 1.0)
check("risk bounded", 0.75 <= rh <= 1.25 and 0.75 <= ra <= 1.25)

# --- read_momentum shape ---------------------------------------------------------
r = mm.read_momentum(s)
check("reading shape",
      set(r) == {"score", "label", "drivers", "risk_home", "risk_away"})
check("reading label matches",
      r["label"] == mm.label(r["score"], "Home", "Away"))

# --- no conversion touch: public API is read + risk only ---------------------------
import inspect as _inspect
import inspect as _inspect2
_pub = {n for n, f in vars(mm).items()
        if _inspect2.isfunction(f) and f.__module__ == "momentum"
        and not n.startswith("_")}
check("public API is read/risk only",
      _pub <= {"observe", "score", "drivers", "label", "risk_appetite",
               "read_momentum"})
check("risk takes team, not shooter/goalie",
      list(_inspect.signature(mm.risk_appetite).parameters) == ["sim", "team"])

# --- sim wiring present ------------------------------------------------------------
sim_src = open('/home/hatch/workspace/HOCKEY-MANAGER/simulation.py').read()
for site in ('_mom_observe(self, "goal"',
             '_mom_observe2(self, "high_danger"',
             '_mom_observe3(self, "oz_entry"',
             '_mom_observe4(self, "fight"',
             '_mom_observe5(self, "big_hit"',
             '_mom_observe6(self, "big_save"'):
    check(f"wired: {site}", site in sim_src)
check("pull timing reads risk",
      "pull_windows" in sim_src
      and "risk_appetite" in open(
          '/home/hatch/workspace/HOCKEY-MANAGER/goalie_pull.py').read())

# --- visualizer wiring present -------------------------------------------------------
viz_src = open('/home/hatch/workspace/HOCKEY-MANAGER/pbp_visual_sim.py').read()
check("viz reads fused momentum", "_momentum_reading" in viz_src)
check("viz driver panel", "WHAT'S DRIVING THE MOMENTUM" in viz_src)
check("viz strip clickable", "_toggle_momentum_panel" in viz_src)

# --- pull-timing math sanity -----------------------------------------------------------
s = FakeSim()
s.period, s.clock = 3, 130.0  # 2:10 left, down 1


class PullSim(FakeSim):
    home_score = 2
    away_score = 3

    def __init__(self):
        super().__init__()
        self.period, self.clock = 3, 130.0  # 2:10 left in the 3rd

    def _is_team_on_penalty_kill(self, team):
        return False


# replicate _pull_eligible threshold logic
def eligible(sim, team):
    from momentum import risk_appetite as _risk
    extra = max(-15, min(15, int(round(60.0 * (_risk(sim, team) - 1.0)))))
    return sim.clock <= 120 + extra


ps = PullSim()
check("neutral: not yet (2:10 > 2:00)", eligible(ps, ps.home_team) is False)
for _ in range(4):
    mm.observe(ps, "goal", ps.home_team)  # onslaught despite trailing
check("surging: pulls early", eligible(ps, ps.home_team) is True)
ps2 = PullSim()
for _ in range(14):
    mm.observe(ps2, "high_danger", ps2.away_team)  # sustained pressure on heels
ps2.clock = 115.0  # inside the normal 2:00 window...
check("heels: ...waits anyway (risk-low)", eligible(ps2, ps2.home_team) is False)
ps2.clock = 105.0  # ...but still pulls when it truly matters
check("heels: pulls when late enough", eligible(ps2, ps2.home_team) is True)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
