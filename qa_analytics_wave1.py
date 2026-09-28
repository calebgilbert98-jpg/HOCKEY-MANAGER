"""QA for the analytics wave-1 stack (information asymmetry).

Covers: ledger filing + grading, scout records, department lens
(noise/CI/lag/stability), philosophy-weighted trade AI, sell/steal
watches with news + counterparty, AI staff review, GM-change regress,
hire/fire quality refresh, old-save migration.
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import analytics_scouting as an
import reputation_system as rs

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def mkpos(name):
    return SimpleNamespace(name=name)


def mkskater(name, team, gp, g, a, age=26, pid=None):
    p = SimpleNamespace(
        full_name=name, team_name=team, games_played=gp, goals=g,
        assists=a, shots=220, hits=50, blocked_shots=40,
        takeaways=30, giveaways=20, pim=25, plus_minus=5,
        faceoff_wins=100, faceoff_attempts=200,
        primary_position=mkpos("C"), age=age,
        contract=SimpleNamespace(salary=4000000, years_remaining=2),
    )
    for attr, val in [("shooting", 84), ("passing", 84),
                      ("puckhandling", 83), ("skating", 85),
                      ("off_awareness", 84), ("def_awareness", 80),
                      ("strength", 78), ("checking", 70),
                      ("fighting", 50), ("faceoffs", 75),
                      ("shot_blocking", 65), ("durability", 80)]:
        setattr(p, attr, val)
    p.overall_rating = lambda: 84
    p.id = pid if pid is not None else name
    return p


def mkscout(name, jpa, sid=None, role=None):
    s = SimpleNamespace(full_name=name, judging_player_ability=jpa,
                        id=sid or name)
    an.ensure_analytics_fields(s)
    if role is not None:
        s.role = role
    return s


def mkteam(name, gm="GM"):
    t = SimpleNamespace(team_name=name, roster=[], staff=[],
                        tip_ledger={}, sell_watch={}, steal_watch={},
                        scout_buy_tips={}, scout_sell_tips={},
                        analytics_quality=35, analytics_philosophy=30.0,
                        philosophy_baseline=30.0, _prev_gm_name=gm,
                        _analytics_snapshot={},
                        gm_name=gm, fan_happiness=60, dynamics_log=[])
    return t


# ---------------------------------------------------------------- 1. filing
team = mkteam("Sharks")
scout = mkscout("Ace", 18)
player = mkskater("Breakout Kid", "Sharks", 40, 20, 25)
key = an.record_tip_call(scout, team, "buy", player, "2026-10-01",
                         reason="ixG 14.2 vs 6 goals")
check("record_tip_call returns key", key is not None)
check("ledger entry filed", len(team.tip_ledger) == 1)
check("reason stored", team.tip_ledger[key]["reason"].startswith("ixG"))
check("scout call credited", scout.tip_record["calls"] == 1)
# Duplicate filing is deduped.
key2 = an.record_tip_call(scout, team, "buy", player, "2026-10-01",
                          reason="ixG 14.2 vs 6 goals")
check("duplicate call deduped", key2 == key and scout.tip_record["calls"] == 1)

# ---------------------------------------------------------------- 2. grading
# Breakout happened: pre pace 1.125 P/GP -> now 2.0 P/GP (+78%) => hit.
team.roster.append(player)
team.staff.append(scout)
player.goals, player.assists, player.games_played = 60, 60, 60  # 2.0 P/GP
events = an.grade_tip_ledger([team], "2026-12-15")
check("graded one tip", events == {"hits": 1, "misses": 0})
check("ledger entry removed after grading", len(team.tip_ledger) == 0)
check("scout hit credited", scout.tip_record["hits"] == 1)
check("record line shows hit",
      "100%" in an.scout_record_line(scout))
check("history recorded", len(scout.tip_history) == 1
      and scout.tip_history[0]["result"] == "hit")

# Miss case: a sell tip on a player who keeps producing.
team2 = mkteam("Ducks")
scout2 = mkscout("Washed", 3)
star = mkskater("Steady Star", "Ducks", 60, 35, 45)  # 1.33 P/GP
team2.roster.append(star)
team2.staff.append(scout2)
an.record_tip_call(scout2, team2, "sell", star, "2026-10-01",
                   reason="PDO 1.060")
star.goals, star.assists, star.games_played = 70, 90, 80  # even better
ev2 = an.grade_tip_ledger([team2], "2026-12-15")
check("wrong sell tip graded as miss", ev2 == {"hits": 0, "misses": 1})
check("miss record line", "0%" in an.scout_record_line(scout2))

# ---------------------------------------------------------------- 3. lens
import advanced_metrics as am

lens_team = mkteam("Lens")
lens_team.analytics_quality = 20  # weak department
p = mkskater("Lens Guy", "Lens", 50, 22, 30)
lens_team.roster.append(p)
d1 = am.display_skater_metrics(p, lens_team, "2026-11-01")
d2 = am.display_skater_metrics(p, lens_team, "2026-11-01")
check("lens has tier + lag", d1.tier and d1.lag_days == 14)
check("lens stable within window", d1.values == d2.values)
check("modeled field has CI", d1.ci.get("ixg", 0) > 0)
check("observed fields exact (no CI)", "hits" not in d1.ci)
true_ixg = am.skater_advanced(p).ixg
check("noise visible at low quality",
      abs(d1.values["ixg"] - true_ixg) > 1e-9 or d1.ci["ixg"] > 0)
# After the lag window, the snapshot rebuilds (new seed).
d3 = am.display_skater_metrics(p, lens_team, "2026-11-20")
check("snapshot refreshes after lag", d3.as_of == "2026-11-20")
# Elite department: zero noise.
lens_team.analytics_quality = 100
d4 = am.display_skater_metrics(p, lens_team, "2026-11-20")
check("perfect department: no noise",
      abs(d4.values["ixg"] - true_ixg) < 1e-9 and d4.ci.get("ixg", 0) == 0)
# Ground truth untouched by the lens.
check("ground truth unchanged", am.skater_advanced(p).ixg == true_ixg)

# ---------------------------------------------------------------- 4. trade AI
import trade_engine as te

hi = mkteam("Nerds")
hi.analytics_philosophy = 80.0
lo = mkteam("Grits")
lo.analytics_philosophy = 10.0
target = mkskater("Target", "Nerds", 50, 15, 20)
base = te.player_trade_value(target)
s1 = mkscout("S1", 20)
hi.scout_buy_tips[target.id] = {"jpa": 20, "correct": True,
                                "scout": "S1", "scout_id": "S1"}
lo.scout_buy_tips[target.id] = {"jpa": 20, "correct": True,
                                "scout": "S1", "scout_id": "S1"}
v_hi = te.scout_adjusted_value(target, hi)
v_lo = te.scout_adjusted_value(target, lo)
check("analytics-heavy club prices tip higher", v_hi > v_lo > base)
lo.scout_buy_tips = {}
v_plain = te.scout_adjusted_value(target, lo)
check("no tip: base value", v_plain == base)
hi.scout_sell_tips = {}
lo.scout_sell_tips[target.id] = {"jpa": 20, "correct": True,
                                 "scout": "S1", "scout_id": "S1"}
v_sell = te.scout_adjusted_value(target, lo)
check("sell tip discounts (scaled by philosophy)", v_sell < base)

# ---------------------------------------------------------------- 5. watches
buyer = mkteam("Buyer")
seller = mkteam("Seller")
seller_team_obj = seller
gem = mkskater("Gem", "Buyer", 30, 12, 10)
tip = {"jpa": 18, "correct": True, "scout_id": "sc1",
       "signals": ["ixG 14.2 vs 6 goals"], "value_score": 3.5,
       "selling_team": "Seller"}
rs.watch_steal_candidate(gem, buyer, tip)
check("steal watch opened", len(buyer.steal_watch) == 1)
# Scout object to grade.
sc1 = mkscout("Scout One", 18, sid="sc1")
buyer.staff.append(sc1)
# Breakout: pre 0.73 P/GP -> post 1.73 P/GP over 15 GP.
buyer.roster.append(gem)
gem.goals, gem.assists, gem.games_played = 25, 23, 45
league_ns = SimpleNamespace(teams=[buyer, seller], rivalries=[])
evs = rs.check_steal_watch(buyer, league_ns)
check("steal watch validates breakout", len(evs) == 1
      and evs[0]["kind"] == "steal_validated")
check("steal watch cleared", len(buyer.steal_watch) == 0)
check("news produced", bool(evs[0].get("news")))
check("scout credited via scout_id", sc1.tip_record["hits"] == 1)
_respect = [r for r in (getattr(league_ns, "rivalries", []) or [])
            if r.get("kind") == "gm_respect"]
check("counterparty respect recorded in league store", len(_respect) > 0)

# Sell watch: regression validates.
old = mkteam("Old")
new = mkteam("New")
decliner = mkskater("Decliner", "New", 30, 15, 20)
new.roster.append(decliner)
sc2 = mkscout("Sell Scout", 17, sid="sc2")
old.staff.append(sc2)
rs.watch_sell_candidate(decliner, old, new,
                        {"jpa": 17, "scout_id": "sc2",
                         "signals": ["PDO 1.055 vs career 1.000"]})
check("sell watch opened", len(old.sell_watch) == 1)
decliner.goals, decliner.assists, decliner.games_played = 22, 18, 50  # collapse
sev = rs.check_sell_watch(old, [old, new],
                          SimpleNamespace(teams=[old, new]))
check("sell watch validates collapse", len(sev) == 1
      and sev[0]["kind"] == "sell_validated")
check("sell scout credited", sc2.tip_record["hits"] == 1)
check("sell news produced", bool(sev[0].get("news")))

# Failure breeds doubt: steal watch that fizzles.
buyer2 = mkteam("Buyer2")
dud = mkskater("Dud", "Buyer2", 30, 12, 10)
buyer2.roster.append(dud)
rs.watch_steal_candidate(dud, buyer2, {"jpa": 5, "scout_id": "sx",
                                       "signals": ["ghost"], "selling_team": "X"})
dud.goals, dud.assists, dud.games_played = 15, 15, 80  # 50 flat games
fev = rs.check_steal_watch(buyer2)
check("failed steal creates doubt event", len(fev) == 1
      and fev[0]["kind"] == "steal_failed")

# ---------------------------------------------------------------- 6. arms race
from game_classes import StaffRole

league = SimpleNamespace(
    teams=[], free_agent_staff=[],
    current_season=1)
random.seed(7)
t1 = mkteam("A")
t2 = mkteam("B")
bad = mkscout("Bad Eye", 4, sid="bad")
bad.role = StaffRole.HEAD_SCOUT
bad.tip_record = {"calls": 10, "hits": 2}
good = mkscout("Good Eye", 19, sid="good")
good.role = StaffRole.HEAD_SCOUT
good.tip_record = {"calls": 10, "hits": 9}
t1.staff.append(bad)
t2.staff.append(good)
fa = mkscout("Free Agent Eye", 17, sid="fa")
fa.role = StaffRole.PROFESSIONAL_SCOUT
league.free_agent_staff.append(fa)
league.teams = [t1, t2]
an.ai_scout_staff_review(league, "2027-01-01")
check("sub-40% scout fired", bad not in t1.staff)
check("fired scout lands in pool", bad in league.free_agent_staff)
check("replacement hired", any(getattr(s, "id", "") == "fa"
                               for s in t1.staff))
check("good scout kept", good in t2.staff)

# ---------------------------------------------------------------- 7. regress
t3 = mkteam("C", gm="Old GM")
t3.analytics_philosophy = 75.0
t3.philosophy_baseline = 30.0
t3.gm_name = "New GM"
an.tick_analytics_philosophy(SimpleNamespace(teams=[t3]))
check("GM change regresses philosophy",
      t3.analytics_philosophy < 75.0
      and t3._prev_gm_name == "New GM")

# ---------------------------------------------------------------- 8. quality
t4 = mkteam("D")
d = SimpleNamespace(role=StaffRole.ANALYTICS_DIRECTOR,
                    judging_player_ability=80, tactical_knowledge=80,
                    adaptability=80)
t4.staff.append(d)
an.refresh_analytics_quality(t4)
check("director sets quality", t4.analytics_quality == 80)
check("snapshot invalidated", t4._analytics_snapshot == {})
try:
    from game_classes import Staff as _S
    _sd = _S(first_name="A", last_name="B",
             role=StaffRole.ANALYTICS_DIRECTOR)
    _sd.judging_player_ability = 85
    _sd.tactical_knowledge = 82
    _sd.adaptability = 78
    check("rating matches department quality",
          int(_sd.overall_rating) == an.analytics_director_quality(_sd))
except Exception:
    check("rating matches department quality", False)

# ---------------------------------------------------------------- 9. migration
legacy_team = SimpleNamespace(team_name="Legacy", roster=[])
an.ensure_analytics_fields(legacy_team)
check("legacy team backfilled",
      hasattr(legacy_team, "tip_ledger")
      and hasattr(legacy_team, "analytics_philosophy"))
legacy_staff = SimpleNamespace(full_name="Old Scout", role="Head Scout")
an.ensure_analytics_fields(legacy_staff)
check("legacy staff backfilled",
      legacy_staff.tip_record == {"calls": 0, "hits": 0}
      and legacy_staff.tip_history == [])

# ---------------------------------------------------------------- 10. scale
# audit: staff JPA is native 1-100; the tip math runs on the 1-20 eye
# scale. _scout_jpa normalizes once -- every consumer gets the tuned
# scale. A JPA-80 scout is good (16), not maxed; a JPA-5 scout is
# guesswork (1), not average.
check("jpa 100 -> 20", an._scout_jpa(mkscout("a", 100)) == 20)
check("jpa 80 -> 16", an._scout_jpa(mkscout("a", 80)) == 16)
check("jpa 50 -> 10", an._scout_jpa(mkscout("a", 50)) == 10)
check("jpa 5 -> 1", an._scout_jpa(mkscout("a", 5)) == 1)
check("elite detects most",
      an._detect_chance(18, 15.0) >= 0.85
      and an._false_positive_chance(18) == 0.05)
check("poor scout guesses",
      an._detect_chance(3, 15.0) <= 0.20
      and an._false_positive_chance(3) == 0.45)
_fresh = [an._make_scout(random, StaffRole.PROFESSIONAL_SCOUT)
          for _ in range(20)]
check("fresh scouts on 1-100 scale",
      all(25 <= int(getattr(s, "judging_player_ability", 0) or 0) <= 85
          for s in _fresh if s is not None))
_fdir = an._make_director(random)
check("fresh director on 1-100 scale",
      _fdir is not None
      and 55 <= int(getattr(_fdir, "judging_player_ability", 0)) <= 95)

# ---------------------------------------------------------------- 11. watch
# lifecycle: sim dates thread through, acted-on reads grade once.
t5 = mkteam("E")
p5 = mkskater("Watch Me", "E", 40, 12, 18, pid="p5")
t5.roster.append(p5)
sc5 = mkscout("Eye", 85, sid="sc5")
sc5.role = StaffRole.PROFESSIONAL_SCOUT
t5.staff.append(sc5)
an.record_tip_call(sc5, t5, "buy", p5, "2026-11-01", reason="r")
rs.watch_steal_candidate(p5, t5, {"scout": "Eye", "scout_id": "sc5"},
                         "2026-12-01")
check("watch stores sim date",
      t5.steal_watch["p5"]["date"] == "2026-12-01")
an.mark_tip_acted_on(t5, "buy", "p5", "2026-12-01")
_key = [k for k in t5.tip_ledger][0]
check("ledger marked acted-on", t5.tip_ledger[_key].get("acted_on"))
# Age the entry past the grade window: ledger must retire it, never
# grade it -- the watch owns the grade.
t5.tip_ledger[_key]["date"] = "2026-01-01"
_h0 = dict(sc5.tip_record)
an.grade_tip_ledger([t5], "2026-12-01")
check("acted-on read not double-graded",
      dict(sc5.tip_record) == _h0 and _key not in t5.tip_ledger)
# Non-acted-on reads still grade through the ledger.
sc6 = mkscout("Eye2", 85, sid="sc6")
sc6.role = StaffRole.PROFESSIONAL_SCOUT
t5.staff.append(sc6)
an.record_tip_call(sc6, t5, "buy", p5, "2026-01-01", reason="r")
p5.games_played = 90
p5.goals = 45
p5.assists = 45
an.grade_tip_ledger([t5], "2026-12-01")
check("unacted read grades via ledger", sc6.tip_record["calls"] >= 1)

# ---------------------------------------------------------------- 12. lens
# for anyone: an opponent viewed through the user's department gets a
# lens (values + CI), not an empty dict.
import advanced_metrics as am
tu, to = mkteam("User"), mkteam("Opp")
tu.analytics_quality = 80
po = mkskater("Opponent Star", "Opp", 40, 20, 25, pid="po")
to.roster.append(po)
lens = am.display_skater_metrics(po, tu, "2026-11-15")
check("opponent lens has values", bool(lens.values))
check("opponent lens has CI",
      "cf_pct" in lens.ci and lens.ci["cf_pct"] > 0)
check("cf_pct CI in points, not x100",
      lens.ci["cf_pct"] < 30)
check("lens tier honest",
      lens.tier == "Elite analytics department"
      and lens.lag_days == 1)
lens2 = am.display_skater_metrics(po, tu, "2026-11-15")
check("lens stable in window", lens2.values == lens.values)

# ---------------------------------------------------------------- 13. save
# migration: a save pickled BEFORE the analytics fields existed must
# load and backfill without crashing (real pickle round-trip).
import pickle
try:
    from game_classes import Staff as _S2
    _legacy = _S2(first_name="Old", last_name="Timer",
                  role=StaffRole.PROFESSIONAL_SCOUT)
    for _f in ("tip_record", "tip_history", "scout_buy_tips",
               "scout_sell_tips", "analytics_quality",
               "analytics_philosophy", "tip_ledger"):
        try:
            delattr(_legacy, _f)
        except AttributeError:
            pass
    _blob = pickle.dumps(_legacy)
    _loaded = pickle.loads(_blob)
    an.ensure_analytics_fields(_loaded)
    check("pickled old save backfills",
          _loaded.tip_record == {"calls": 0, "hits": 0}
          and _loaded.tip_history == [])
    check("pickled new save keeps record",
          (lambda _s: (setattr(_s, "tip_record",
                               {"calls": 5, "hits": 4}) or
                       pickle.loads(pickle.dumps(_s)).tip_record)
                      == {"calls": 5, "hits": 4})(_S2(
                          first_name="N", last_name="E",
                          role=StaffRole.PROFESSIONAL_SCOUT)))
except Exception:
    check("pickled old save backfills", False)
    check("pickled new save keeps record", False)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
