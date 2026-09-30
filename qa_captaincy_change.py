"""QA: voluntary captaincy changes.

- Fantasy draft picks strip letters (no two-C rosters).
- assess_deposition: personality/situation drive acceptance.
- roll_tier: tier distribution follows acceptance.
- apply_deposition: letters + tiered effects + news; compromise softens.
- Extreme: trade request vs GM grudge; grudge decay + clear-the-air.
- AI torch-passing: conservative, headless, Cup champs untouched.
- New fields survive save/load.
"""
import os
import random
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name} {detail}")


import captaincy_change as cc
from game_classes import League, Team, Player


def mkplayer(name, age, leadership, letter="", controversy=20,
             happiness=70, determination=60, tenure=0):
    p = Player(name.split()[0], name.split()[1], age, "C", 9,
               captaincy=letter)
    p.leadership = leadership
    p.stats.games_played = 82
    p.stats.goals = 20
    p.stats.assists = 30
    p.controversy = controversy
    p.happiness = happiness
    p.determination = determination
    p.captain_tenure_years = tenure
    return p


def mkteam(name, roster):
    t = Team(name, name + "ville", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.roster = roster
    t.ahl_roster = []
    return t


def mkleague(teams, standings=None):
    lg = League("NHL")
    lg.season_year = 2028
    lg.teams = teams
    lg.standings = standings or {
        t.team_name: {"W": 41, "L": 33, "OTL": 8} for t in teams}
    return lg


# --- 1. fantasy draft strips letters -------------------------------------
from fantasy_draft import FantasyDraftManager, DraftConfiguration

t1 = mkteam("Alphas", [])
t2 = mkteam("Betas", [])
star = mkplayer("Star Player", 28, 90, letter="C", tenure=3)
mgr = FantasyDraftManager(
    [t1, t2], [star,
               mkplayer("Role Player", 30, 60),
               mkplayer("Kid Prospect", 20, 55)],
    DraftConfiguration(rounds=2))
ok = mgr.make_pick(star)
check("draft pick strips the C", ok and star.captaincy == ""
      and star.captain_tenure_years == 0,
      f"letter={star.captaincy!r}")
check("drafted player lands on a team",
      star.team_name in ("Alphas", "Betas"), star.team_name)

# --- 2. assessment --------------------------------------------------------
old_loyal = mkplayer("Loyal Vet", 34, 74, letter="C", controversy=15,
                     happiness=75, determination=80, tenure=5)
new_star = mkplayer("Young Star", 24, 92, controversy=10)
new_star.stats.goals = 45
new_star.stats.assists = 55  # 100 pts: plainly more worthy
team = mkteam("Testers", [old_loyal, new_star])
lg = mkleague([team], {"Testers": {"W": 30, "L": 45, "OTL": 7}})  # losing
info = cc.assess_deposition(old_loyal, new_star, team, lg)
check("big gap + losing: high acceptance",
      info["acceptance"] > 0.6, str(info["acceptance"]))
check("reasons mention the gap",
      any("more worthy" in r or "plainly passed" in r
          for r in info["reasons"]), str(info["reasons"]))

old_vol = mkplayer("Hot Head", 30, 78, letter="C", controversy=85,
                   happiness=60, determination=50, tenure=6)
new_ok = mkplayer("Decent Guy", 28, 76, controversy=20)
team2 = mkteam("Winners", [old_vol, new_ok])
lg2 = mkleague([team2], {"Winners": {"W": 55, "L": 20, "OTL": 7}})  # winning
info2 = cc.assess_deposition(old_vol, new_ok, team2, lg2)
check("volatile tenured captain, no gap, winning: low acceptance",
      info2["acceptance"] < 0.45, str(info2["acceptance"]))

# --- 3. tier distribution --------------------------------------------------
rng = random.Random(7)
tiers_hi = [cc.roll_tier(0.9, rng) for _ in range(400)]
tiers_lo = [cc.roll_tier(0.1, rng) for _ in range(400)]
check("high acceptance: mostly graceful/grumbles",
      sum(t in ("graceful", "grumbles") for t in tiers_hi) > 340,
      str(sum(t in ("graceful", "grumbles") for t in tiers_hi)))
check("low acceptance: mostly pushback/extreme",
      sum(t in ("pushback", "extreme") for t in tiers_lo) > 300,
      str(sum(t in ("pushback", "extreme") for t in tiers_lo)))

# --- 4. apply per tier ------------------------------------------------------
def fresh_pair():
    o = mkplayer("Old Captain", 33, 76, letter="C", controversy=25,
                 happiness=70, determination=65, tenure=4)
    n = mkplayer("New Captain", 26, 88, controversy=15)
    t = mkteam("Club", [o, n])
    return t, o, n

t, o, n = fresh_pair()
rep = cc.apply_deposition(t, o, n, "graceful", talked=True)
check("graceful: letters swap",
      o.captaincy == "" and n.captaincy == "C",
      f"{o.captaincy}/{n.captaincy}")
check("graceful: mild effects + news",
      rep["tier"] == "graceful" and len(rep["news"]) == 1
      and o.happiness == 65, f"{rep['tier']} hap={o.happiness}")

t, o, n = fresh_pair()
rep = cc.apply_deposition(t, o, n, "grumbles", talked=True)
check("grumbles: morale/happiness dip",
      o.morale == 65 and o.happiness == 58, f"{o.morale}/{o.happiness}")

t, o, n = fresh_pair()
rep = cc.apply_deposition(t, o, n, "pushback", talked=False)
check("pushback: controversy + trade-risk bump",
      o.controversy == 37 and o.trade_request_risk == 15,
      f"{o.controversy}/{o.trade_request_risk}")
check("pushback: cold announcement noted",
      any("never saw it coming" in l for l in rep["lines"]))

t, o, n = fresh_pair()
rep = cc.apply_deposition(t, o, n, "pushback", talked=True,
                          compromise_alternate=True)
check("compromise: tier softened, keeps an A",
      rep["tier"] == "grumbles" and o.captaincy == "A"
      and n.captaincy == "C", f"{rep['tier']} {o.captaincy}")

# extreme: hothead demands a trade
t, o, n = fresh_pair()
o.controversy = 80
rep = cc.apply_deposition(t, o, n, "extreme", talked=False)
check("extreme hothead: trade request",
      rep.get("extreme_kind") == "trade_request"
      and getattr(o, "transfer_requested", False) is True)

# extreme: loyal soldier goes cold (grudge)
t, o, n = fresh_pair()
o.controversy = 15
try:
    from reputation_system import ensure_reputation_fields
    ensure_reputation_fields(o)
except Exception:
    pass
rep = cc.apply_deposition(t, o, n, "extreme", talked=False)
check("extreme loyalist: GM grudge",
      rep.get("extreme_kind") == "gm_grudge"
      and cc.gm_grudge(o) == 85.0, f"{rep.get('extreme_kind')}")
check("grudge caps happiness",
      o.happiness <= 45, str(o.happiness))

# --- 5. grudge decay + clear the air ---------------------------------------
g0 = cc.gm_grudge(o)
g1 = cc.decay_gm_grudge(o, 0.62)   # winning
o._gm_grudge = 85.0
g2 = cc.decay_gm_grudge(o, 0.40)   # losing
check("winning decays faster", g1 < g2, f"{g1} vs {g2}")
o._gm_grudge = 60.0
rng2 = random.Random(1)
res = cc.clear_the_air(o, t, mkleague([t]))
check("clear-the-air returns a verdict",
      isinstance(res["success"], bool) and len(res["lines"]) == 1)

# --- 6. AI torch-passing ----------------------------------------------------
class StubRng:
    def __init__(self, vals):
        self.vals = list(vals)

    def random(self):
        return self.vals.pop(0) if self.vals else 0.5


# young established captain, no worthy successor -> no change
young_c = mkplayer("Young C", 25, 84, letter="C", tenure=3)
mate = mkplayer("Mate Seven", 27, 70)
tai = mkteam("Aiclub", [young_c, mate])
lai = mkleague([tai])
rep = cc.ai_consider_captaincy_change(tai, lai, rng=StubRng([0.1]))
check("AI leaves a young captain alone", rep is None)

# fading veteran + plainly worthier young star -> change
old_c = mkplayer("Fading Vet", 36, 74, letter="C", controversy=20,
                 tenure=4)
succ = mkplayer("Heir Apparent", 24, 90, controversy=15)
tai2 = mkteam("Aiclub2", [old_c, succ, mkplayer("Depth Guy", 29, 62)])
lai2 = mkleague([tai2])
rep = cc.ai_consider_captaincy_change(tai2, lai2, "2028-07-01",
                                      rng=StubRng([0.1, 0.99]))
check("AI passes the torch when plainly right",
      rep is not None and succ.captaincy == "C"
      and old_c.captaincy in ("", "A"),
      str(None if rep is None else rep["tier"]))

# Cup champ captain is never touched
champ_c = mkplayer("Champ C", 36, 74, letter="C", tenure=4)
succ2 = mkplayer("Heir Two", 24, 92)
tchamp = mkteam("Champs", [champ_c, succ2])
lchamp = mkleague([tchamp])


class Bracket:
    stanley_cup_champion = tchamp


lchamp.playoff_bracket = Bracket()
rep = cc.ai_consider_captaincy_change(tchamp, lchamp, rng=StubRng([0.0]))
check("AI never strips a Cup-winning captain", rep is None)

# --- 7. save/load round-trip -------------------------------------------------
from save_load_system import GameSaveManager as SaveLoadSystem

t3, o3, n3 = fresh_pair()
o3._gm_grudge = 72.5
o3._gm_grudge_since = "2028-11-01"
o3._grudge_talk_stamp = "2028-11"
lg3 = mkleague([t3])
gm = SimpleNamespace(league=lg3, league_history=None,
                     narrative_ledger=None)
saver = SaveLoadSystem(gm)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "cc_test.save")
check("save succeeds", saver.save_game(path))
gm2 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
loader = SaveLoadSystem(gm2)
check("load succeeds", loader.load_game(path))
o3b = [p for p in gm2.league.teams[0].roster
       if "Old" in p.full_name][0]
check("grudge survives load", cc.gm_grudge(o3b) == 72.5,
      str(cc.gm_grudge(o3b)))
check("talk stamp survives load",
      getattr(o3b, "_grudge_talk_stamp", "") == "2028-11")

# --- 8. established gating ----------------------------------------------------
fresh_c = mkplayer("Just Named", 28, 85, letter="C", tenure=0)
check("tenure-0 captain is not established",
      cc.is_established_captain(fresh_c) is False)
check("tenured captain is established",
      cc.is_established_captain(o3) is True)

print(f"\n{PASS} passed, {FAIL} failed")
if FAILURES:
    print("failures:", FAILURES)
sys.exit(1 if FAIL else 0)
