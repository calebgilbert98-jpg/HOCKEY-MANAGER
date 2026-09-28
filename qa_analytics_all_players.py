"""QA: advanced analytics matter for prospects, rookies, and all players.

Covers:
  1. prospect_advanced(): NHLe translation of the farm season, production
     vs age+overall expectation, plus/minus rate; zeros with no farm season;
     goalie farm seasons don't crash it.
  2. find_prospect_standouts(): the late-round kid out-producing his
     pedigree is found; the mediocre kid is not; min_gp filters short
     farm seasons.
  3. scout_prospect_tips(): a good scout names the real standout
     (correct=True); tip shape matches the pro tips so the trade engine
     prices it.
  4. Trade valuation: a filed prospect tip raises scout_adjusted_value
     above the raw player_trade_value -- analytics move prospect prices.
  5. Rookie flash: a 21-and-under skater with 8-19 GP and elite process
     gets a capped, risk-disclosed signal in find_buy_low instead of
     being invisible behind the veteran sample gates.
  6. AI offers: the analytics multiplier pays up for snake-bitten
     drivers and discounts passengers -- scaled by the club's
     analytics_philosophy, bounded, 1.0 with no sample.
  7. skater_advanced reads the canonical blocked_shots field (not a
     phantom "blocks" attribute) into Game Score.

Run: python3 qa_analytics_all_players.py
"""
import random
import sys

sys.path.insert(0, ".")

from game_classes import (Player, PlayerPosition, PlayerStats, Team,
                          to_100_scale)
import advanced_metrics as am
import analytics_scouting as asc

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'ok' if cond else 'FAIL'}: {name}" +
          (f" -- {detail}" if detail and not cond else ""))


def make_skater(age=24, pos=PlayerPosition.CENTER, **attrs):
    p = Player(first_name="Test", last_name=f"Ana{random.randint(0, 999999)}",
               age=age, primary_position=pos)
    for k, v in attrs.items():
        setattr(p, k, v)
    return p


def set_nhl_line(p, gp, goals, assists, shots):
    p.games_played = gp
    p.goals = goals
    p.assists = assists
    p.shots = shots


def set_farm_season(p, league, gp, pts, pm):
    ppg = pts / gp if gp else 0.0
    p.farm_season = {"league": league, "gp": gp, "g": pts // 2,
                     "a": pts - pts // 2, "pts": pts,
                     "ppg": round(ppg, 3), "plus_minus": pm}


# --- 1. prospect_advanced ---------------------------------------------------
elite_kid = make_skater(age=19)
for a in ("skating", "shooting", "passing", "defensive_awareness"):
    setattr(elite_kid, a, 62)
# A 72-ovr 19yo is *expected* to score ~1.44 ppg in the OHL (the sim's own
# model), so "elite" has to clear that bar by a lot: 130 pts is a monster.
set_farm_season(elite_kid, "OHL", 60, 130, 25)
m = am.prospect_advanced(elite_kid)
check("prospect: elite farm season translates to NHLe",
      abs(m.nhle_ppg - 0.65) < 0.01, f"nhle_ppg={m.nhle_ppg}")
check("prospect: elite kid beats age+overall expectation",
      m.nhle_vs_expected >= 1.4, f"ratio={m.nhle_vs_expected}")
check("prospect: plus/minus rate captured",
      abs(m.pm_per_gp - 25 / 60) < 0.01, f"pm/gp={m.pm_per_gp}")

plug_kid = make_skater(age=19)
set_farm_season(plug_kid, "OHL", 60, 20, -10)
m2 = am.prospect_advanced(plug_kid)
check("prospect: poor season underperforms expectation",
      0 < m2.nhle_vs_expected < 1.0, f"ratio={m2.nhle_vs_expected}")

no_season = make_skater(age=18)
m3 = am.prospect_advanced(no_season)
check("prospect: no farm season -> zeros",
      m3.gp == 0 and m3.nhle_ppg == 0.0 and m3.nhle_vs_expected == 0.0)

goalie_kid = make_skater(age=19, pos=PlayerPosition.GOALIE)
goalie_kid.farm_season = {"league": "OHL", "gp": 40, "w": 22, "l": 18,
                          "sv_pct": 0.910, "gaa": 2.80}
m4 = am.prospect_advanced(goalie_kid)
check("prospect: goalie farm season doesn't crash",
      m4.gp == 40 and m4.nhle_ppg == 0.0)

# --- 2. find_prospect_standouts ----------------------------------------------
steal = make_skater(age=19)
steal.draft_round = 6
steal.team_name = "Rival Club"
for a in ("skating", "shooting", "passing", "defensive_awareness"):
    setattr(steal, a, 60)
set_farm_season(steal, "WHL", 55, 95, 30)
steal.farm_result = "breakout"

mid = make_skater(age=19)
mid.draft_round = 2
mid.team_name = "Rival Club"
set_farm_season(mid, "WHL", 55, 35, 2)

shorty = make_skater(age=18)
shorty.draft_round = 7
shorty.team_name = "Rival Club"
set_farm_season(shorty, "USHL", 12, 20, 8)

found = asc.find_prospect_standouts([steal, mid, shorty], [])
names = [c["name"] for c in found]
check("standouts: late-round producer is found",
      steal.full_name in names, f"found={names}")
check("standouts: mediocre producer is not found",
      mid.full_name not in names)
check("standouts: short farm season filtered by min_gp",
      shorty.full_name not in names)
if found:
    top = found[0]
    check("standouts: result shape matches buy-low dicts",
          all(k in top for k in ("player", "name", "team", "value_score",
                                 "signals", "risks", "age", "gp")))
    check("standouts: signals explain the read, risks disclosed",
          len(top["signals"]) >= 2 and len(top["risks"]) >= 1,
          f"signals={top['signals']} risks={top['risks']}")

# --- 3. scout_prospect_tips ----------------------------------------------------
class FakeScout:
    def __init__(self, jpa):
        self.full_name = "Eagle Eye"
        self.id = "scout-1"
        # analytics_scouting._scout_jpa reads attributes; give it a 1-20 eye
        self.judging_player_ability = jpa
        self.tip_record = {}
        self.tip_history = []


def _jpa_monkey():
    # _scout_jpa(scout) maps the scout's attrs to 1-20; bypass with a stub
    orig = asc._scout_jpa
    asc._scout_jpa = lambda s: getattr(s, "judging_player_ability", 10)
    return orig


_orig_jpa = _jpa_monkey()
try:
    rng = random.Random(7)
    tips = asc.scout_prospect_tips(FakeScout(19), [steal, mid, shorty],
                                   user_team=None, limit=2, rng=rng)
    real = [t for t in tips if t.get("correct")]
    check("scout tips: elite scout names the real standout",
          any(t["player"] is steal for t in real),
          f"tips={[t['name'] for t in tips]}")
    if tips:
        t0 = tips[0]
        check("scout tips: shape matches pro tips",
              all(k in t0 for k in ("player", "name", "team", "scout",
                                    "scout_jpa", "correct", "reason",
                                    "risks", "confidence")))
finally:
    asc._scout_jpa = _orig_jpa

# --- 4. trade valuation: prospect tips move prices -----------------------------
import trade_engine as te

t1 = Team("Test Club", "Eastern", "Atlantic", "Metro")
t1.analytics_philosophy = 80
asc.ensure_analytics_fields(t1)
pid = getattr(steal, "id", id(steal))
base_val = te.player_trade_value(steal)
t1.scout_buy_tips[pid] = {"jpa": 18, "correct": True, "scout": "Eagle Eye",
                          "scout_id": "scout-1"}
adj_val = te.scout_adjusted_value(steal, t1)
check("trade value: filed prospect tip raises the price",
      adj_val > base_val, f"base={base_val} adj={adj_val}")
t2 = Team("Old School", "Eastern", "Atlantic", "Metro")
t2.analytics_philosophy = 5
asc.ensure_analytics_fields(t2)
t2.scout_buy_tips[pid] = {"jpa": 18, "correct": True, "scout": "Eagle Eye",
                          "scout_id": "scout-1"}
adj_old = te.scout_adjusted_value(steal, t2)
check("trade value: old-school room moves less on the same tip",
      base_val < adj_old < adj_val,
      f"base={base_val} old={adj_old} prog={adj_val}")

# --- 5. rookie flash -------------------------------------------------------------
rookie = make_skater(age=20)
for a in ("passing", "puck_handling", "skating", "defensive_awareness",
          "shooting", "strength", "playmaking"):
    setattr(rookie, a, 92)
set_nhl_line(rookie, 10, 2, 3, 30)   # 10 GP: below the veteran 15-GP gate
rookie.team_name = "Some Club"
rm = am.skater_advanced(rookie)
check("rookie: elite process in small sample (fixture sane)",
      rm.xgf_pct >= 56.0, f"xgf={rm.xgf_pct}")
bl = asc.find_buy_low([rookie], [], min_gp=15)
rentry = next((c for c in bl if c["player"] is rookie), None)
check("rookie: 10-GP rookie with elite process gets a tip",
      rentry is not None)
if rentry is not None:
    check("rookie: tip is capped and risk-disclosed",
          rentry["value_score"] <= 10.0 and any(
              "Small sample" in r for r in rentry["risks"]),
          f"score={rentry['value_score']} risks={rentry['risks']}")
    check("rookie: signal names the flash",
          any("Rookie flash" in s for s in rentry["signals"]))

vet_ghost = make_skater(age=28)
set_nhl_line(vet_ghost, 10, 2, 3, 30)
for a in ("passing", "puck_handling", "skating", "defensive_awareness",
          "shooting", "strength", "playmaking"):
    setattr(vet_ghost, a, 92)
bl2 = asc.find_buy_low([vet_ghost], [], min_gp=15)
check("rookie: veteran with 10 GP stays invisible (no small-sample lane)",
      not any(c["player"] is vet_ghost for c in bl2))

# --- 6. AI offer multiplier ------------------------------------------------------
from ai_team_management import AITeamManager

mgr = AITeamManager.__new__(AITeamManager)

snake = make_skater(age=26)
for a in ("passing", "puck_handling", "skating", "defensive_awareness",
          "shooting", "strength", "playmaking"):
    setattr(snake, a, 90)
set_nhl_line(snake, 40, 1, 6, 60)    # 1 goal on 60 shots: snake-bitten
sm = am.skater_advanced(snake)
check("AI mult: fixture is snake-bitten (low PDO, high xGF%)",
      sm.pdo < 0.995 and sm.xgf_pct >= 52.0, f"pdo={sm.pdo} xgf={sm.xgf_pct}")

prog = Team("Progressive", "Eastern", "Atlantic", "Metro")
prog.analytics_philosophy = 90
old = Team("OldSchool", "Eastern", "Atlantic", "Metro")
old.analytics_philosophy = 5
mult_prog = mgr._analytics_offer_multiplier(snake, prog)
mult_old = mgr._analytics_offer_multiplier(snake, old)
check("AI mult: progressive room pays up for snake-bitten process",
      mult_prog > 1.0, f"mult={mult_prog}")
check("AI mult: old-school room barely moves",
      1.0 <= mult_old < mult_prog, f"old={mult_old} prog={mult_prog}")

passenger = make_skater(age=29)
for a in ("passing", "puck_handling", "skating", "defensive_awareness",
          "shooting", "strength"):
    setattr(passenger, a, 42)
setattr(passenger, "playmaking", 42)
set_nhl_line(passenger, 40, 15, 10, 60)  # 25% shooting: riding luck
pm = am.skater_advanced(passenger)
check("AI mult: fixture is a passenger (high PDO, weak process)",
      pm.pdo > 1.015 and pm.xgf_pct <= 48.0, f"pdo={pm.pdo} xgf={pm.xgf_pct}")
mult_pass = mgr._analytics_offer_multiplier(passenger, prog)
check("AI mult: progressive room discounts the passenger",
      mult_pass < 1.0, f"mult={mult_pass}")

no_sample = make_skater(age=24)
check("AI mult: no sample -> 1.0",
      mgr._analytics_offer_multiplier(no_sample, prog) == 1.0)

# Goalie lane: positive GSAx, mediocre SV%.
netminder = make_skater(age=28, pos=PlayerPosition.GOALIE)
for a in ("positioning", "reflexes", "rebound_control", "consistency"):
    setattr(netminder, a, 50)
netminder.games_played = 25
netminder.shots_against = 900
netminder.saves = 812          # .902 SV%
netminder.goals_against = 88
gm = am.goalie_advanced(netminder)
check("AI mult: goalie fixture has positive GSAx, sub-.905 SV%",
      gm.gsax > 5.0 and gm.sv_pct < 0.905, f"gsax={gm.gsax} sv={gm.sv_pct}")
check("AI mult: progressive room pays up for goalie process",
      mgr._analytics_offer_multiplier(netminder, prog) > 1.0)

# --- 7. blocked_shots read ---------------------------------------------------------
shot_blocker = make_skater(age=27, pos=PlayerPosition.DEFENSE)
set_nhl_line(shot_blocker, 40, 0, 0, 0)
st = PlayerStats()
st.games_played = 40
st.blocked_shots = 50
shot_blocker.stats = st
bm = am.skater_advanced(shot_blocker)
check("blocks: canonical blocked_shots field is read",
      bm.blocks == 50, f"blocks={bm.blocks}")
check("blocks: Game Score credits the blocks (50 * 0.05)",
      abs(bm.game_score - 2.5) < 0.01, f"gs={bm.game_score}")

# Mixed-store shape (the real detailed-sim path): scoring on direct
# attributes, the defensive trail ONLY on player.stats. The metrics
# must see both.
mixed = make_skater(age=27, pos=PlayerPosition.DEFENSE)
mixed.games_played = 40
mixed.goals = 5
mixed.assists = 10
mixed.shots = 80
mst = PlayerStats()
mst.hits = 97
mst.blocked_shots = 162
mixed.stats = mst
mm = am.skater_advanced(mixed)
check("blocks: mixed store -- scoring from direct, trail from .stats",
      mm.blocks == 162 and mm.hits == 97 and abs(mm.sh_pct - 6.25) < 0.01,
      f"blocks={mm.blocks} hits={mm.hits} sh%={mm.sh_pct}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
