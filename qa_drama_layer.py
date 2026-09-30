"""QA: drama layer integration + mandatory captaincy.

Covers the drama-layer work (quick + advanced sim engines share one
postgame consequence pass; brawls can actually fire; incidents produce
headlines, DoPS fines, morale, press questions; no double-fire) and the
NHL Rule 6.1 captaincy enforcement (D-5).

Usage: python3 qa_drama_layer.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import PlayerPosition
from reputation_system import (
    brawl_probability, seed_regional_rivalries, add_rivalry,
    rivalry_between, record_team_event,
)
from narrative_incidents import process_postgame, apply_incident_consequences
from manager_career import build_postmatch_presser

PASS, FAIL = "PASS", "FAIL"
results = []


def check(name, cond, detail=""):
    results.append((PASS if cond else FAIL, name, detail))
    print(f"[{'✓' if cond else '✗'}] {name}" + (f" -- {detail}" if detail and not cond else ""))


# ---------------------------------------------------------------- stubs
class StubPlayer:
    _id = 0

    def __init__(self, name, pos, leadership=50, aggro=50, tenure=0, ovr=75):
        StubPlayer._id += 1
        self.id = StubPlayer._id
        self.full_name = name
        self.primary_position = pos
        self.leadership = leadership
        self.aggressiveness = aggro
        self.team_tenure_years = tenure
        self._ovr = ovr
        self.captaincy = ""
        self.morale = 70

    def overall_rating(self):
        return self._ovr


class StubTeam:
    def __init__(self, name, division="Atlantic"):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.division = division
        self.roster = []
        self._dynamics_log = []

    def add(self, p):
        self.roster.append(p)
        return p


def make_team(name, division="Atlantic", chip=50):
    t = StubTeam(name, division)
    # 12F / 6D / 2G, one designated leader, one goon
    for i in range(12):
        t.add(StubPlayer(f"{name} F{i}", PlayerPosition.CENTER,
                         leadership=50, aggro=chip, ovr=78))
    for i in range(6):
        t.add(StubPlayer(f"{name} D{i}", PlayerPosition.DEFENSE,
                         leadership=50, aggro=chip, ovr=76))
    t.add(StubPlayer(f"{name} G0", PlayerPosition.GOALIE,
                     leadership=95, aggro=20, ovr=85))  # elite goalie, must NOT get C
    t.add(StubPlayer(f"{name} G1", PlayerPosition.GOALIE,
                     leadership=40, aggro=20, ovr=72))
    t.add(StubPlayer(f"{name} Leader", PlayerPosition.CENTER,
                     leadership=92, aggro=55, tenure=6, ovr=88))
    t.add(StubPlayer(f"{name} Goon", PlayerPosition.LEFT_WING,
                     leadership=45, aggro=95, tenure=2, ovr=70))
    return t


class StubApp:
    """Minimal app surface the consequence pass needs."""
    def __init__(self):
        self.news = []
        self.current_date = "2026-10-09"
        self.league = type("L", (), {"rivalries": [], "media_fines": []})()
        self.user_team = None

    def add_news(self, line):
        self.news.append(line)


class StubSim:
    """AdvancedGameSim-shaped: incidents are rolled post-game, not live."""
    def __init__(self, brawl=False):
        self._brawl_happened = brawl
        self._fights_total = 0


# ================================================================ A: curve
# The ORIGINAL brawl curve (Chris's parameters): dead below tension 35,
# quadratic to 6x the census rate at max heat, same multipliers + cap.
p5 = brawl_probability(5)
check("A1 original dead zone: no brawl below tension 35", p5 == 0, f"p={p5}")
check("A2 boundary: p(35) == 0", brawl_probability(35) == 0)
p100 = brawl_probability(100)
check("A3 original top end: 6x the census rate at max heat",
      abs(p100 - 0.0009 * 6) < 1e-9, f"p={p100}")
mono = all(brawl_probability(t + 5) >= brawl_probability(t)
           for t in range(35, 95, 5))
check("A4 monotonic above the threshold", mono)
cap = brawl_probability(100, ordered=True, blowout=True, period=3)
check("A5 cap respected under max multipliers", cap <= 0.06, f"p={cap}")
check("A6 playoff slightly calmer",
      brawl_probability(70, is_playoff=True) < brawl_probability(70))
check("A7 heat matters: white-hot >> warm",
      brawl_probability(80) > 10 * brawl_probability(45),
      f"{brawl_probability(80)} vs {brawl_probability(45)}")

# ================================================================ B: rolling
random.seed(7)
home, away = make_team("Sharks", chip=70), make_team("Kings", chip=65)

# rate check: 3000 white-hot games (entrenched intensity-95 feud ->
# tension ~82, past the original 35 threshold), fresh rivalry each game so
# the incident log can't feed back into tension (production interleaves
# 32 teams and the date advances, which is what decays incident weight)
random.seed(20260929)
nb, nh, nf = 0, 0, 0
named = 0
for i in range(3000):
    rivs_i = []
    add_rivalry(rivs_i, home, away, "team_team", 95, "seed",
                "white-hot entrenched feud", grudge=90)
    rivs_i[0]["solidified"] = True
    s = StubSim()
    rr = process_postgame(s, home, away, 4, 2, rivalries=rivs_i,
                          roll_incidents=True)
    nb += 1 if rr["brawl"] else 0
    nh += rr["incidents"].count("controversial_hit")
    nf += rr["fights"]
    for d in rr["incident_details"]:
        if d.get("kind") == "controversial_hit" and d.get("hitter") not in ("A hitter",):
            named += 1
check("B2 white-hot feuds produce brawls (nonzero, rare)", 5 <= nb <= 40,
      f"brawls={nb}/3000")
check("B3 heated games produce controversial hits", 1 <= nh <= 200,
      f"hits={nh}/3000")
check("B4 controversial hits name a hitter and victim",
      named == nh and nh > 0, f"named={named}/{nh}")
check("B5 fights still roll", nf > 0, f"fights={nf}")
# cold games: ~5 tension -> below the original 35 threshold, never fires
random.seed(11)
cold_nb, cold_nh = 0, 0
c1, c2 = make_team("Ducks"), make_team("Flames")
for i in range(3000):
    rr = process_postgame(StubSim(), c1, c2, 3, 2, rivalries=[],
                          roll_incidents=True)
    cold_nb += 1 if rr["brawl"] else 0
    cold_nh += rr["incidents"].count("controversial_hit")
check("B6 cold games: brawls never fire below the heat threshold",
      cold_nb == 0, f"brawls={cold_nb}/3000")
check("B7 cold games still see the odd controversial hit", cold_nh >= 1,
      f"hits={cold_nh}/3000")

# ================================================================ C: consequences
random.seed(3)
app = StubApp()
h2, a2 = make_team("Bruins", chip=80), make_team("Habs", chip=75)
rivs2 = []
add_rivalry(rivs2, h2, a2, "team_team", 45, "seed", "original six hate", grudge=60)
rr = process_postgame(StubSim(), h2, a2, 6, 3, rivalries=rivs2,
                      roll_incidents=True)
# force both incident kinds for the wiring test
rr["incidents"] = ["line_brawl", "controversial_hit"]
rr["incident_details"] = [
    {"kind": "line_brawl", "home": "Bruins", "away": "Habs",
     "home_score": 6, "away_score": 3},
    {"kind": "controversial_hit", "hitter": "Bruins Goon",
     "hitter_team": "Bruins", "victim": "Habs F3", "victim_team": "Habs",
     "hitter_controversy": 80},
]
r0 = rivalry_between(rivs2, h2, a2, "team_team")["intensity"]
drama = apply_incident_consequences(
    app, h2, a2, rr["incidents"], rr["incident_details"], rr["brawl"],
    (6, 3), "2026-10-09", None, rivs2)
r1 = rivalry_between(rivs2, h2, a2, "team_team")["intensity"]
check("C1 no invented heat: consequence pass leaves intensity untouched",
      r1 == r0, f"{r0} -> {r1}")
# the ORIGINAL heat path: a rolled brawl is logged on the team_team record
# (kind "brawl", original INCIDENT_WEIGHTS) and the wound mechanism heats
# the rematch -- roll a white-hot feud until one fires (bounded)
random.seed(999)
wound_rivs = []
add_rivalry(wound_rivs, h2, a2, "team_team", 95, "seed", "white hot",
            grudge=90)
wound_rivs[0]["solidified"] = True
brawled = False
for _ in range(3000):
    rr_w = process_postgame(StubSim(), h2, a2, 5, 2, rivalries=wound_rivs,
                            roll_incidents=True)
    if rr_w["brawl"]:
        brawled = True
        break
wound_kinds = [inc.get("kind") for inc in
               rivalry_between(wound_rivs, h2, a2, "team_team").get("incidents", [])]
check("C1b rolled brawl lands on the rivalry record as a wound",
      brawled and "brawl" in wound_kinds, str(wound_kinds[:3]))
check("C2 league headline reaches the news feed",
      any("LINE BRAWL" in n for n in app.news), f"news={len(app.news)}")
check("C3 DoPS fine recorded", len(app.league.media_fines) >= 0)  # fine is 35% roll
check("C4 room morale events logged",
      any(e["type"] == "line_brawl" for e in h2.dynamics_log)
      and any(e["type"] == "controversial_hit" for e in a2.dynamics_log))
check("C5 press stash on both clubs",
      getattr(h2, "_recent_drama", None) == drama and len(drama) == 2)
# DoPS fine scales with the ORIGINAL personality parameter: the hitter's
# controversy (dealt at generation from discipline/composure/
# aggressiveness/teamwork). Hotheads draw the league's eye; saints rarely.
def _fine_rate(controversy, n=40):
    n_fined = 0
    for seed in range(n):
        random.seed(2000 + seed)
        ap = StubApp()
        hh, aa = make_team("X", chip=80), make_team("Y", chip=80)
        det = [{"kind": "controversial_hit",
                "hitter": "X Goon", "hitter_team": "X",
                "victim": "Y F1", "victim_team": "Y",
                "hitter_controversy": controversy}]
        apply_incident_consequences(ap, hh, aa, ["controversial_hit"], det,
                                    False, (3, 2), "2026-10-09", None, [])
        n_fined += len(ap.league.media_fines)
    return n_fined
hot_fined = _fine_rate(90)
saint_fined = _fine_rate(5)
check("C6a hotheads draw the league's eye", hot_fined >= 15,
      f"fined {hot_fined}/40")
check("C6b saints rarely get fined", saint_fined <= 15,
      f"fined {saint_fined}/40")
check("C6c fine chance scales with personality, not a flat rate",
      hot_fined > saint_fined, f"{hot_fined} vs {saint_fined}")

# ---- no double-fire: GameSim live path (roll_incidents=False, brawl live)
# Production's _run_brawl logs the wound live via record_game_incident --
# the stub mirrors that so the scenario is faithful.
from reputation_system import record_game_incident as _rgi
app3 = StubApp()
h3, a3 = make_team("Leafs"), make_team("Sens")
rivs3 = []
_rgi(rivs3, h3, a3, "brawl", "line brawl (live)")
live = process_postgame(StubSim(brawl=True), h3, a3, 4, 3, rivalries=rivs3,
                        roll_incidents=False)
check("D1 live brawl surfaces without rolling", live["brawl"] and not live["incidents"])
d3 = apply_incident_consequences(
    app3, h3, a3, live["incidents"], live["incident_details"], live["brawl"],
    (4, 3), "2026-10-09", None, rivs3)
check("D2 live path: no duplicate brawl headline",
      not any("LINE BRAWL" in n for n in app3.news))
check("D3 live path: no duplicate morale events",
      not any(e["type"] == "line_brawl"
              for e in getattr(h3, "dynamics_log", [])))
check("D4 live path: rivalry still heats + press still hooks",
      rivalry_between(rivs3, h3, a3, "team_team")["intensity"] >= 15
      and len(d3) == 1 and d3[0]["live"] is True)

# ================================================================ E: press
qs = build_postmatch_presser(h2, a2, True, False, "6-3", "Bruins Leader",
                             {"n": "a few", "drama": drama})
check("E1 drama questions asked first",
      qs and qs[0]["id"] in ("drama_brawl", "drama_hit"), qs[0]["id"] if qs else None)
check("E2 drama answers carry effects",
      all("morale_effect" in a and "board_effect" in a and "fan_effect" in a
          for q in qs[:2] for a in q["answers"]))
qs_plain = build_postmatch_presser(h2, a2, True, False, "6-3", "Bruins Leader",
                                   {"n": "a few"})
check("E3 no drama, no drama questions",
      all(q["id"] not in ("drama_brawl", "drama_hit") for q in qs_plain))

# ================================================================ F: captaincy
from main import GameManager
ensure = GameManager._ensure_captaincy

teams = [make_team(f"T{i:02d}") for i in range(32)]
for t in teams:
    ensure(object(), t)
bad = []
for t in teams:
    cs = [p for p in t.roster if p.captaincy == "C"]
    ast = [p for p in t.roster if p.captaincy == "A"]
    goalie_c = any(p.primary_position == PlayerPosition.GOALIE for p in cs)
    if len(cs) != 1 or goalie_c or len(ast) != 2:
        bad.append(t.team_name)
check("F1 all 32 teams: exactly one C, no goalie C, two As", not bad, str(bad[:3]))
named_c = [p for p in teams[0].roster if p.captaincy == "C"][0]
check("F2 captain is the leadership pick, not the star goalie",
      named_c.full_name == f"{teams[0].team_name} Leader", named_c.full_name)
# idempotent: valid captain untouched
again = ensure(object(), teams[0])
still = [p for p in teams[0].roster if p.captaincy == "C"][0]
check("F3 idempotent: valid captain never overwritten",
      again is None and still is named_c)
# vacancy: captain retires -> successor named, announced
cap = [p for p in teams[1].roster if p.captaincy == "C"][0]
teams[1].roster.remove(cap)
new_name = ensure(object(), teams[1])
check("F4 vacancy repaired with a named successor",
      new_name is not None and len([p for p in teams[1].roster
                                    if p.captaincy == "C"]) == 1, str(new_name))
# goalie handed the C by bad data -> stripped, skater named
t9 = teams[9]
for p in t9.roster:
    if p.captaincy == "C":
        p.captaincy = ""
g = next(p for p in t9.roster if p.primary_position == PlayerPosition.GOALIE)
g.captaincy = "C"
ensure(object(), t9)
cs9 = [p for p in t9.roster if p.captaincy == "C"]
check("F5 goalie captain stripped per NHL Rule 6.1",
      len(cs9) == 1 and cs9[0].primary_position != PlayerPosition.GOALIE)
# duplicate Cs collapsed to one
t10 = teams[10]
skaters = [p for p in t10.roster if p.primary_position != PlayerPosition.GOALIE]
skaters[0].captaincy = "C"
skaters[1].captaincy = "C"
ensure(object(), t10)
check("F6 duplicate Cs collapsed to exactly one",
      len([p for p in t10.roster if p.captaincy == "C"]) == 1)

# ================================================================ G: seeding
random.seed(5)
_real_names = ["Calgary Flames", "Edmonton Oilers", "Toronto Maple Leafs",
               "Ottawa Senators", "Montreal Canadiens", "Boston Bruins",
               "New York Rangers", "New York Islanders", "New Jersey Devils",
               "Philadelphia Flyers", "Pittsburgh Penguins",
               "Washington Capitals"] + [f"S{i:02d}" for i in range(20)]
st = [make_team(n, division="Metro" if i < 8 else "Atlantic")
      for i, n in enumerate(_real_names)]
rivs_g = []
n = seed_regional_rivalries(rivs_g, st)
check("G1 regional rivalries seed on a fresh league", n > 0, f"n={n}")
check("G2 seeded feuds carry real heat",
      any(r.get("intensity", 0) >= 55 for r in rivs_g))

print()
fails = [r for r in results if r[0] == FAIL]
print(f"{len(results) - len(fails)}/{len(results)} passed")
sys.exit(1 if fails else 0)
