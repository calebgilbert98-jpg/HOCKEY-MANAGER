"""QA: analytics matter for signed minor-leaguers (AHL), light edition.

Covers:
  1. prospect_advanced() reads AHL farm seasons (NHLe, expectation,
     plus/minus) -- the same light metrics as junior prospects, no
     NHL-grade shot tracking.
  2. find_prospect_standouts(kind="AHL") finds the AHL gem and labels
     the result "AHL", not "PROSPECT".
  3. League-aware risks: no "old for the level" for a 22yo in the AHL
     (men's league); it still fires for a 20yo in juniors. Translation
     risk wording names the AHL.
  4. scout_prospect_tips(kind="AHL"): a good scout names the real AHL
     standout; tip shape matches pro tips; bad-scout ghosts use
     AHL-flavored reasons.
  5. Ledger: record_tip_call snapshots the farm season; grade_tip_ledger
     finds AHLers on ahl_roster and grades on farm production movement
     (hit when it rises, miss when it collapses) -- and credits the
     scout's track record.
  6. Trade valuation: a filed AHL tip raises scout_adjusted_value.
  7. Speed: scanning 600 AHLers stays fast (the monthly pass must not
     slow the game).

Run: python3 qa_analytics_ahl.py
"""
import random
import sys
import time

sys.path.insert(0, ".")

from game_classes import Player, PlayerPosition, Team
import advanced_metrics as am
import analytics_scouting as asc

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def make_ahler(age=22, ovr_attr=65):
    p = Player(first_name="Test", last_name=f"Ahl{random.randint(0, 999999)}",
               age=age, primary_position=PlayerPosition.LEFT_WING)
    import inspect, re
    attrs = sorted(set(re.findall(r"self\.([a-z_]+)",
                                  inspect.getsource(Player.overall_rating))))
    for a in attrs:
        try:
            setattr(p, a, ovr_attr)
        except Exception:
            pass
    p.team_name = "Rival Club"
    return p


def set_farm(p, league, gp, pts, pm):
    ppg = pts / gp if gp else 0.0
    p.farm_season = {"league": league, "gp": gp, "g": pts // 2,
                     "a": pts - pts // 2, "pts": pts,
                     "ppg": round(ppg, 3), "plus_minus": pm}


# --- 1. prospect_advanced on AHL seasons --------------------------------------
gem = make_ahler(age=22)
gem.draft_round = 5
set_farm(gem, "AHL", 50, 55, 22)
m = am.prospect_advanced(gem)
check("ahl: AHL season translates to NHLe",
      abs(m.nhle_ppg - round(55 / 50 * 0.44, 3)) < 0.01,
      f"nhle_ppg={m.nhle_ppg}")
check("ahl: gem beats age+overall expectation",
      m.nhle_vs_expected >= 1.4, f"ratio={m.nhle_vs_expected}")
check("ahl: plus/minus rate captured",
      abs(m.pm_per_gp - 22 / 50) < 0.01, f"pm/gp={m.pm_per_gp}")

# --- 2. find_prospect_standouts kind="AHL" -------------------------------------
plug = make_ahler(age=24)
plug.team_name = "Rival Club"
set_farm(plug, "AHL", 50, 18, -6)

found = asc.find_prospect_standouts([gem, plug], [], kind="AHL")
names = [c["name"] for c in found]
check("ahl: gem is found", gem.full_name in names, f"found={names}")
check("ahl: plug is not found", plug.full_name not in names)
check("ahl: result labeled AHL",
      all(c["kind"] == "AHL" for c in found),
      f"kinds={[c['kind'] for c in found]}")
if found:
    top = found[0]
    check("ahl: signals explain, risks disclosed",
          len(top["signals"]) >= 2 and len(top["risks"]) >= 1,
          f"signals={top['signals']} risks={top['risks']}")
    check("ahl: no 'old for the level' risk in a men's league",
          not any("Old for the level" in r for r in top["risks"]),
          f"risks={top['risks']}")
    check("ahl: translation risk names the AHL",
          any("AHL" in r for r in top["risks"]),
          f"risks={top['risks']}")

# --- 3. junior risk contrast ----------------------------------------------------
old_kid = make_ahler(age=20)
old_kid.team_name = "Rival Club"
set_farm(old_kid, "OHL", 50, 90, 10)
_, _, jr_risks = asc._prospect_value_signals(old_kid)
check("ahl: 'old for the level' still fires for juniors",
      any("Old for the level" in r for r in jr_risks),
      f"risks={jr_risks}")

# --- 4. scout_prospect_tips kind="AHL" ------------------------------------------
class FakeScout:
    def __init__(self, jpa):
        self.full_name = "Eagle Eye"
        self.id = "scout-1"
        self.judging_player_ability = jpa
        self.tip_record = {}
        self.tip_history = []


_orig = asc._scout_jpa
asc._scout_jpa = lambda s: getattr(s, "judging_player_ability", 10)
try:
    rng = random.Random(11)
    tips = asc.scout_prospect_tips(FakeScout(19), [gem, plug],
                                   user_team=None, limit=2, rng=rng,
                                   kind="AHL")
    real = [t for t in tips if t.get("correct")]
    check("ahl: elite scout names the real AHL standout",
          any(t["player"] is gem for t in real),
          f"tips={[t['name'] for t in tips]}")
    check("ahl: tips labeled AHL",
          all(t.get("kind") == "AHL" for t in tips),
          f"kinds={[t.get('kind') for t in tips]}")
    if tips:
        check("ahl: tip shape matches pro tips",
              all(k in tips[0] for k in ("player", "name", "team", "scout",
                                        "scout_jpa", "correct", "reason",
                                        "risks", "confidence")))
    # Bad scout ghosts: AHL-flavored reasons, never junior-flavored.
    ghosts = []
    for seed in range(30):
        r = random.Random(1000 + seed)
        ts = asc.scout_prospect_tips(FakeScout(2), [plug], user_team=None,
                                     limit=1, rng=r, kind="AHL")
        ghosts += [t for t in ts if not t.get("correct")]
    check("ahl: bad-scout ghosts use AHL reasons",
          bool(ghosts) and all("juniors" not in g["reason"].lower()
                               for g in ghosts),
          f"ghosts={len(ghosts)}")
finally:
    asc._scout_jpa = _orig

# --- 5. ledger: farm snapshot + farm grading -----------------------------------
team = Team("Ledger Club", "Eastern", "Atlantic", "Metro")
asc.ensure_analytics_fields(team)
scout = FakeScout(18)
scout.id = "scout-ledger"
team.staff = [scout]

key = asc.record_tip_call(scout, team, "buy", gem, "2026-11-01",
                          reason="AHL gem")
entry = team.tip_ledger.get(key, {})
check("ahl: ledger snapshots the farm season",
      entry.get("pre_farm_gp") == 50 and entry.get("farm_league") == "AHL",
      f"entry={entry}")

# Grade a hit: farm production rises.
team.ahl_roster = [gem]
set_farm(gem, "AHL", 62, 80, 26)  # 1.29 ppg now vs 1.10 then
res = asc.grade_tip_ledger([team], "2027-06-01")
check("ahl: rising farm production grades a hit",
      res["hits"] == 1 and res["misses"] == 0, f"res={res}")
check("ahl: scout track record credited",
      scout.tip_record.get("hits", 0) >= 1,
      f"record={scout.tip_record}")

# Grade a miss: farm production collapses.
gem2 = make_ahler(age=23)
gem2.draft_round = 4
set_farm(gem2, "AHL", 50, 58, 12)
key2 = asc.record_tip_call(scout, team, "buy", gem2, "2026-11-01",
                           reason="AHL gem 2")
check("ahl: second tip filed", key2 in team.tip_ledger)
team.ahl_roster = [gem2]
set_farm(gem2, "AHL", 64, 20, -8)  # 0.31 ppg now vs 1.16 then
res2 = asc.grade_tip_ledger([team], "2027-06-01")
check("ahl: collapsing farm production grades a miss",
      res2["misses"] == 1 and res2["hits"] == 0, f"res={res2}")

# --- 6. trade valuation ----------------------------------------------------------
import trade_engine as te

t1 = Team("Buyer Club", "Eastern", "Atlantic", "Metro")
t1.analytics_philosophy = 80
asc.ensure_analytics_fields(t1)
pid = getattr(gem, "id", id(gem))
base_val = te.player_trade_value(gem)
t1.scout_buy_tips[pid] = {"jpa": 18, "correct": True, "scout": "Eagle Eye",
                          "scout_id": "scout-1"}
adj_val = te.scout_adjusted_value(gem, t1)
check("ahl: filed AHL tip raises the price",
      adj_val > base_val, f"base={base_val} adj={adj_val}")

# --- 7. speed --------------------------------------------------------------------
pool = []
for i in range(600):
    p = make_ahler(age=20 + (i % 6))
    p.team_name = f"Club {i % 30}"
    set_farm(p, "AHL", 50, 10 + (i % 45), (i % 21) - 10)
    pool.append(p)
t0 = time.perf_counter()
_out = asc.find_prospect_standouts(pool, [], limit=25, kind="AHL")
dt = time.perf_counter() - t0
check("ahl: 600-player scan stays fast",
      dt < 2.0, f"{dt:.2f}s")

print()
print(f"{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
