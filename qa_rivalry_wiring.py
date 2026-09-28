"""QA: rivalry lifecycle wiring.

Verifies the rivalry lifecycle functions are actually CALLED from the
production paths they were designed for (they previously had zero
production callers):

  1. seed_regional_rivalries -- new-league generation only
     (existing saves keep their lived-in state; idempotent)
  2. decay_rivalries + review_rivalries -- League.end_of_season
     (decay every offseason; full review every 3rd season)
  3. on_player_transfer -- trade_engine._post_trade_effects
     (the authoritative post-trade integration point)
  4. record_playoff_series -- PlayoffBracket.advance_to_next_round
     (once per completed series, upset via standings_position)
  5. record_major_injury -- GameSim._apply_hit_injury
     (top severity tier only; season_ending at 20+ games)
  6. record_firing -- dressing_room.fire_coach(league=...)
  7. record_award_race -- photo-finish award races in _calculate_season_awards

Headless: lightweight fakes + tiny real objects, no UI, no telemetry.
"""
import ast
import os
import random
import sys
from datetime import date
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


import reputation_system as rs
from reputation_system import (
    add_rivalry, decay_rivalries, on_player_transfer, record_award_race,
    record_major_injury, review_rivalries, rivalry_between,
    seed_regional_rivalries,
)
from game_classes import League, Team


def _mkteam(name, city="City"):
    return Team(name, city, "Atlantic", "Eastern")


def _mkplayer(pid, name, overall=80):
    return SimpleNamespace(id=pid, full_name=name, overall=overall,
                           primary_position=SimpleNamespace(name="CENTER"))


# ---------------------------------------------------------------- seeding
def _extract_method(path, name):
    """Pull a method's real source out of a module we can't import (main)."""
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    src = ast.get_source_segment(open(path).read(), item)
                    # de-indent one level (method -> function)
                    lines = src.splitlines()
                    ded = "\n".join(
                        l[4:] if l.startswith("    ") else l for l in lines)
                    ns = {}
                    exec(compile(ded, path, "exec"), ns)
                    return ns[name]
    raise AssertionError(f"{name} not found in {path}")


_seed_fn = _extract_method("main.py", "_seed_regional_rivalries")

fake_app = SimpleNamespace(league=SimpleNamespace(rivalries=[],
    teams=[SimpleNamespace(team_name="Calgary Flames"),
           SimpleNamespace(team_name="Edmonton Oilers"),
           SimpleNamespace(team_name="Toronto Maple Leafs"),
           SimpleNamespace(team_name="Ottawa Senators")]))
_seed_fn(fake_app)
rivs = fake_app.league.rivalries
check("seed: new league gets regional rivalries", len(rivs) == 2,
      f"got {len(rivs)}")
boa = rivalry_between(rivs, fake_app.league.teams[0], fake_app.league.teams[1])
check("seed: Battle of Alberta at 55 / grudge 75 / regional",
      boa is not None and boa["intensity"] == 55
      and boa["grudge"] == 75 and boa["origin"] == "regional",
      str(boa))
n_before = len(rivs)
_seed_fn(fake_app)  # idempotent: merge-by-max, no duplicates
check("seed: idempotent on re-run", len(rivs) == n_before,
      f"{n_before} -> {len(rivs)}")

# Existing save: non-empty ledger is untouched.
lived = [{"a": "x", "a_name": "X", "b": "y", "b_name": "Y", "kind": "team_team",
          "intensity": 70, "origin": "playoff_series", "story": "lived",
          "grudge": 60, "career_cost": 40}]
fake_old = SimpleNamespace(league=SimpleNamespace(rivalries=lived,
    teams=[SimpleNamespace(team_name="Calgary Flames"),
           SimpleNamespace(team_name="Edmonton Oilers")]))
_seed_fn(fake_old)
check("seed: existing save keeps lived-in state",
      len(lived) == 1 and lived[0]["story"] == "lived", str(lived))

# Both new-game tails call the seeder.
_main_src = open("main.py").read()
check("seed: regional seeder defined",
      "def _seed_regional_rivalries(self):" in _main_src)
check("seed: generate_database + setup_new_game tails call seeder",
      _main_src.count("self._seed_regional_rivalries()") == 2,
      f"found {_main_src.count('self._seed_regional_rivalries()')}")

# ------------------------------------------------- end_of_season lifecycle
lg = League("TEST")
lg.add_team(_mkteam("Calgary Flames", "Calgary"))
lg.add_team(_mkteam("Edmonton Oilers", "Edmonton"))
lg.season_year = 2027  # -> 2028 after rollover; 2028 % 3 == 0 => review
pa, pb = _mkplayer(1, "Victim One"), _mkplayer(2, "Hitter Two")
rs.record_major_injury(lg.rivalries, pa, pb, season_ending=True)
r0 = rivalry_between(lg.rivalries, pa, pb)
i0 = r0["intensity"]
lg.end_of_season()
r1 = rivalry_between(lg.rivalries, pa, pb)
check("end_of_season: review ran on 3rd season (solidified)",
      r1 is not None and r1.get("solidified") is True
      and r1["intensity"] >= 65,
      f"intensity {i0} -> {r1['intensity'] if r1 else None}")
check("end_of_season: season_year advanced", lg.season_year == 2028)

# Non-review season: decay only, no solidification.
lg2 = League("TEST2")
lg2.add_team(_mkteam("Team A", "A"))
lg2.add_team(_mkteam("Team B", "B"))
lg2.season_year = 2026  # -> 2027; 2027 % 3 != 0 => decay only
pc, pd = _mkplayer(3, "Mild One"), _mkplayer(4, "Mild Two")
# A mid-size beef (award races now spark at 10 and can die in one quiet
# offseason -- by design -- so the decay probe uses a meatier one).
rs.record_major_injury(lg2.rivalries, pc, pd, season_ending=False)
r2 = rivalry_between(lg2.rivalries, pc, pd)
i2 = r2["intensity"]
lg2.end_of_season()
r2b = rivalry_between(lg2.rivalries, pc, pd)
check("end_of_season: decay runs every offseason",
      r2b is not None and r2b["intensity"] < i2,
      f"{i2} -> {r2b['intensity'] if r2b else None}")
check("end_of_season: no review off-cycle",
      r2b is not None and not r2b.get("solidified"))

# ------------------------------------------------------- trade transfer
import trade_engine as te
from game_classes import DraftPick  # noqa: F401  (ensures import path)

ta = _mkteam("Trade A", "A"); tb = _mkteam("Trade B", "B")
pleague = SimpleNamespace(teams=[ta, tb], rivalries=[])
moved = _mkplayer(10, "Traded Star", overall=90)
# Personal beef: follows the man.
rs.record_major_injury(pleague.rivalries, moved, _mkplayer(11, "Old Foe"),
                       season_ending=True)
# Ambient beef: left behind.
moved.base_controversy = 60  # personality to take the snub personally
rs.record_award_race(pleague.rivalries, moved, _mkplayer(12, "Rival Scorer"),
                     "Art Ross Trophy")
te._post_trade_effects(ta, tb, [moved], [], "2026-10-01", pleague)
personal = [r for r in pleague.rivalries
            if r["origin"] == "major_injury"]
ambient = [r for r in pleague.rivalries
           if r["origin"] == "award_race"]
check("trade: personal beef follows the traded player",
      len(personal) == 1, f"{len(personal)} personal records")
check("trade: ambient beef left behind",
      len(ambient) == 0, f"{len(ambient)} ambient records remain")
# league=None must not crash the trade path.
try:
    te._post_trade_effects(ta, tb, [_mkplayer(13, "Loner")], [],
                           "2026-10-01", None)
    check("trade: league=None is safe", True)
except Exception as e:
    check("trade: league=None is safe", False, str(e))

# ------------------------------------------------------- playoff series
from playoff_system import PlayoffBracket, PlayoffSeries

bleague = SimpleNamespace(rivalries=[])
t1 = _mkteam("Seed Two", "S2"); t1.standings_position = 2
t2 = _mkteam("Seed Five", "S5"); t2.standings_position = 5
br = PlayoffBracket(bleague)
s = PlayoffSeries("Wild Card", t1, t2)
for _ in range(4):
    s.add_game_result(False)  # team2 (the 5-seed) sweeps: UPSET
br.playoff_series["wild_card"] = [s]
try:
    br.advance_to_next_round("wild_card")
except Exception:
    pass  # bracket scaffolding may complain; the hook runs first
rec = [r for r in bleague.rivalries if r["origin"] == "playoff_series"]
check("playoff: completed series records heat",
      len(rec) == 1, f"{len(rec)} records")
if rec:
    check("playoff: sweep upset = 30 heat, upset in story",
          rec[0]["intensity"] == 30 and "upset" in rec[0]["story"].lower(),
          f"intensity={rec[0]['intensity']}")
# Idempotent: advancing again must not double-record.
n_rec = len(bleague.rivalries)
try:
    br.advance_to_next_round("wild_card")
except Exception:
    pass
check("playoff: no double-record on re-advance",
      len(bleague.rivalries) == n_rec)

# ------------------------------------------------------- major injury
import simulation as sim_mod

fake_sim = SimpleNamespace(rivalries=[],
                           _log_event=lambda *a, **k: None)
victim = _mkplayer(20, "Hit Victim", overall=88)
hitter = _mkplayer(21, "Big Hitter", overall=82)
with mock.patch("random.randint", return_value=9):
    sim_mod.GameSim._apply_hit_injury(
        fake_sim, victim, hitter, "Hitters", "Victims",
        sim_mod.HitType.CHARGING, 2)
check("injury: victim sidelined", bool(getattr(victim, "is_injured", False)))
mi = [r for r in fake_sim.rivalries if r["origin"] == "major_injury"]
check("injury: top-tier hit records personal beef",
      len(mi) == 1, f"{len(mi)} records")
if mi:
    check("injury: player-player, intensity 50",
          mi[0]["kind"] == "player_player" and mi[0]["intensity"] == 50,
          f"{mi[0]['kind']}@{mi[0]['intensity']}")
# Minor knock: no personal record.
fake_sim2 = SimpleNamespace(rivalries=[],
                            _log_event=lambda *a, **k: None)
v2 = _mkplayer(22, "Bruised Guy")
with mock.patch("random.randint", return_value=2):
    sim_mod.GameSim._apply_hit_injury(
        fake_sim2, v2, hitter, "Hitters", "Victims",
        sim_mod.HitType.BOARDING, 1)
check("injury: minor hit stays ambient (no personal record)",
      not [r for r in fake_sim2.rivalries if r["origin"] == "major_injury"])

# ------------------------------------------------------- coach firing
import dressing_room as dr

fteam = _mkteam("Fire Club", "FC")
fteam.gm_name = "Test GM"
fcoach = SimpleNamespace(full_name="Fired Coach", name="Fired Coach",
                         controversy=30)
fteam.head_coach = fcoach
fteam.staff = [fcoach]
fleague = SimpleNamespace(rivalries=[])
dr.fire_coach(fteam, reason="fired", date_str="2026-11-01", league=fleague)
fr = [r for r in fleague.rivalries if r["origin"] == "firing"]
check("firing: coach-GM grudge recorded",
      len(fr) == 1, f"{len(fr)} records")
if fr:
    check("firing: kind gm_coach, follows the coach",
          fr[0]["kind"] == "gm_coach" and "Fired Coach" in fr[0]["story"],
          fr[0]["story"][:60])
check("firing: chair actually emptied",
      getattr(fteam, "head_coach", "x") is None)
# league=None: old behavior, no crash, no record.
fteam2 = _mkteam("Fire Club 2", "FC")
fteam2.head_coach = SimpleNamespace(full_name="C2", name="C2", controversy=10)
fteam2.staff = [fteam2.head_coach]
try:
    dr.fire_coach(fteam2, reason="fired")
    check("firing: league=None is safe", True)
except Exception as e:
    check("firing: league=None is safe", False, str(e))

# ------------------------------------------------------- award races
import awards_race as ar

# Photo finish: 3 points apart on ~120 -> personal (for the right personality).
a1 = _mkplayer(30, "Hart Winner"); a1.goals = 50; a1.assists = 70
a1.base_controversy = 65  # the type to bristle at a snub
a2 = _mkplayer(31, "Hart Runner"); a2.goals = 48; a2.assists = 69
for p in (a1, a2):
    p.games_played = 82
    p.pim = 20
    p.team_name = "Hart Club"
players = [a1, a2]
race = ar.art_ross_race(players)
check("awards: race returns top two", len(race) >= 2)
s1 = float(race[0]["score"]); s2 = float(race[1]["score"])
photo = s1 > 0 and (s1 - s2) / s1 < 0.05
check("awards: 3-pt gap on 120 reads as photo finish", photo,
      f"{s1} vs {s2}")
if photo:
    record_award_race(pleague.rivalries, race[0]["player"],
                      race[1]["player"], "Art Ross Trophy")
    aw = [r for r in pleague.rivalries if r["origin"] == "award_race"
          and "Art Ross" in r["story"]]
    check("awards: photo finish recorded as personal beef", len(aw) == 1)
# Runaway: 40-point gap -> nobody's enemy.
b1 = _mkplayer(32, "Runaway"); b1.goals = 60; b1.assists = 90; b1.pim = 10
b1.games_played = 82; b1.team_name = "R Club"
b2 = _mkplayer(33, "Distant"); b2.goals = 30; b2.assists = 80; b2.pim = 10
b2.games_played = 82; b2.team_name = "R Club"
race2 = ar.art_ross_race([b1, b2])
t1s = float(race2[0]["score"]); t2s = float(race2[1]["score"])
check("awards: runaway is NOT a photo finish",
      not (t1s > 0 and (t1s - t2s) / t1s < 0.05), f"{t1s} vs {t2s}")
# Personality gate: same photo finish between two even-keeled pros ->
# a good race, not a grudge.
c1 = _mkplayer(34, "Calm One"); c1.base_controversy = 12
c2 = _mkplayer(35, "Calm Two"); c2.base_controversy = 8
rs.record_award_race(pleague.rivalries, c1, c2, "Hart Trophy")
_calm = [r for r in pleague.rivalries if r["origin"] == "award_race"
         and "Hart Trophy" in r["story"]
         and "Calm One" in r["story"]]
check("awards: saints in a photo finish -> no record", len(_calm) == 0,
      f"{len(_calm)} records")
# All eight player awards pass an award name at the call site.
_expected_awards = ["Hart Trophy", "Art Ross Trophy", "Rocket Richard Trophy",
                    "Vezina Trophy", "Norris Trophy", "Selke Trophy",
                    "Lady Byng Trophy", "Calder Trophy"]
_missing = [a for a in _expected_awards if f', "{a}")' not in _main_src]
check("awards: 8 player races wired with names", not _missing,
      f"missing: _missing")

# ------------------------------------------------------- FA signing transfers
# Every live signing path funnels through on_player_transfer so a signed
# man's personal beefs follow him and ambient noise cools -- the ledger
# never holds a stale "he plays for X" grudge after he signs elsewhere.
def _method_src(path, name):
    """Source text of a method we can't import (main)."""
    tree = ast.parse(open(path).read())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == name:
                    return ast.get_source_segment(open(path).read(), item) or ""
    return ""


_fin_src = _method_src("main.py", "_finalize_contract_signing")
check("signing: user path (_finalize_contract_signing) calls on_player_transfer",
      "on_player_transfer" in (_fin_src or ""), "wired" if _fin_src else "method not found")
_mp_src = _method_src("main.py", "_mp_sign_free_agent")
check("signing: MP path (_mp_sign_free_agent) calls on_player_transfer",
      "on_player_transfer" in (_mp_src or ""), "wired" if _mp_src else "method not found")
_rfa_src = open("rfa_system.py").read()
check("signing: RFA offer sheet (execute_offer_sheet) calls on_player_transfer",
      "on_player_transfer" in _rfa_src)

# Behavioral: FA signing with from_team=None (no old club).
fa_man = _mkplayer(40, "Signed Star", overall=88)
fa_man.base_controversy = 62
rivs_fa = []
rs.record_major_injury(rivs_fa, fa_man, _mkplayer(41, "Old Foe"),
                       season_ending=True)          # personal: follows
rs.record_award_race(rivs_fa, fa_man, _mkplayer(42, "Rival Scorer"),
                     "Hart Trophy")                 # ambient: left behind
res_fa = rs.on_player_transfer(rivs_fa, fa_man, from_team=None,
                               to_team=_mkteam("New Club", "N"))
_carried = [r["origin"] for r in res_fa["carried"]]
_left = [r["origin"] for r in res_fa["left_behind"]]
check("signing: personal beef follows the FA to his new club",
      _carried == ["major_injury"], f"carried={_carried}")
check("signing: ambient beef does not follow the FA",
      "award_race" in _left, f"left={_left}")

# ------------------------------------------------- AI FA executor + claims
import ai_team_management as aim
from game_classes import PlayerPosition


class _FakeTeam:
    def __init__(self, name, roster):
        self.team_name = name
        self.roster = list(roster)

    def add_player(self, player, roster_type="roster"):
        self.roster.append(player)
        player.team_name = self.team_name


def _mkfa(pid, name, pos, ovr=80, salary=0, euro=False):
    p = SimpleNamespace(
        id=pid, full_name=name, primary_position=pos, age=27,
        salary=salary, contract_years=0,
        contract=SimpleNamespace(salary=salary, years_remaining=0,
                                 no_trade_clause=False),
        is_euro_import=euro, team_name="", ovr=ovr,
        overall_rating=lambda _o=ovr: _o)
    return p


def _ask(ovr):
    """The player's true ask: the same machinery the user faces
    (ovr x $100k at the $104M cap, floored at $750k)."""
    return max(int((ovr * 100_000 / 104_000_000) * 104_000_000), 750_000)


def _mkstrategy(needs, budget=95_000_000, risk=0.0,
               priority=None):
    return aim.TeamStrategy(
        priority=priority or aim.ManagementPriority.CONTEND,
        trade_preference=aim.TradePreference.MODERATE,
        budget_limit=budget, min_roster_age=20, max_roster_age=36,
        position_needs=list(needs), salary_cap_tolerance=0.9,
        prefer_youth=False, prefer_experience=False, risk_tolerance=risk,
        will_trade_picks=True, will_trade_prospects=True,
        rebuilding_timeline=3)


def _mkmgr(league, team, strategy):
    mgr = aim.AITeamManager()
    mgr._league_ref = league
    mgr.team_strategies[team.team_name] = strategy
    return mgr


def _mkdecision(p, salary=None, term=3):
    # Default: a realistic offer -- exactly the player's ask.
    if salary is None:
        salary = _ask(getattr(p, "ovr", 80))
    return SimpleNamespace(
        decision_type="free_agent_offer", target_player=p,
        offer_details={"salary": salary, "term": term,
                       "no_trade_clause": False})


# Success: hole + need + budget -> signed, pool shrinks, hook fires.
fa1 = _mkfa(50, "AI Target", PlayerPosition.CENTER, ovr=82)
fa1.base_controversy = 62
lg_fa = SimpleNamespace(free_agents=[fa1], rivalries=[], season_year=2026)
rs.record_award_race(lg_fa.rivalries, fa1, _mkfa(51, "Foe", PlayerPosition.CENTER),
                     "Hart Trophy")
hole_roster = [_mkfa(60 + i, f"Roster{i}", PlayerPosition.CENTER, salary=3_000_000)
               for i in range(20)]
t1 = _FakeTeam("AI Club", hole_roster)
m1 = _mkmgr(lg_fa, t1, _mkstrategy([PlayerPosition.CENTER]))
ok = m1._execute_free_agent_signing(t1, _mkdecision(fa1), lg_fa)
check("ai fa: hole + need + budget -> signed",
      ok and fa1 not in lg_fa.free_agents and fa1 in t1.roster
      and fa1.team_name == "AI Club" and fa1.salary == _ask(82)
      and fa1.contract_years == 3,
      f"ok={ok} roster={len(t1.roster)}")
check("ai fa: transfer hook fired on signing",
      len([r for r in lg_fa.rivalries if r["origin"] == "award_race"]) == 0,
      f"rivalries={len(lg_fa.rivalries)}")

# Guards: no double-sign, no full roster, no over-budget, no wrong position.
lg2 = SimpleNamespace(free_agents=[], rivalries=[], season_year=2026)
m2 = _mkmgr(lg2, t1, _mkstrategy([PlayerPosition.CENTER]))
check("ai fa: already-signed player is not re-signed",
      not m2._execute_free_agent_signing(t1, _mkdecision(fa1), lg2)
      and len(t1.roster) == 21)
full = _FakeTeam("Full Club",
                 [_mkfa(70 + i, f"F{i}", PlayerPosition.CENTER, salary=3_000_000)
                  for i in range(23)])
lg3 = SimpleNamespace(free_agents=[_mkfa(80, "Extra", PlayerPosition.CENTER)],
                      rivalries=[], season_year=2026)
m3 = _mkmgr(lg3, full, _mkstrategy([PlayerPosition.CENTER]))
check("ai fa: 23-man roster blocks signing",
      not m3._execute_free_agent_signing(full, _mkdecision(lg3.free_agents[0]), lg3)
      and len(lg3.free_agents) == 1)
poor = _FakeTeam("Poor Club", [])
lg4 = SimpleNamespace(free_agents=[_mkfa(81, "Rich", PlayerPosition.CENTER)],
                      rivalries=[], season_year=2026)
m4 = _mkmgr(lg4, poor, _mkstrategy([PlayerPosition.CENTER], budget=1_000_000))
check("ai fa: over-budget offer is not executed",
      not m4._execute_free_agent_signing(poor, _mkdecision(lg4.free_agents[0]), lg4))
check("ai fa: wrong position is not executed",
      not m1._execute_free_agent_signing(
          t1, _mkdecision(_mkfa(82, "Winger", PlayerPosition.LEFT_WING)),
          SimpleNamespace(free_agents=[], rivalries=[], season_year=2026)))

# Throttle: one signing per team per tick, even with three valid targets.
t5 = _FakeTeam("Throttle Club", [])
lg5 = SimpleNamespace(
    free_agents=[_mkfa(90 + i, f"T{i}", PlayerPosition.CENTER) for i in range(3)],
    rivalries=[], season_year=2026)
m5 = _mkmgr(lg5, t5, _mkstrategy([PlayerPosition.CENTER]))
m5._execute_decisions(t5, [_mkdecision(p) for p in list(lg5.free_agents)])
check("ai fa: at most one signing per tick",
      len(t5.roster) == 1 and len(lg5.free_agents) == 2,
      f"roster={len(t5.roster)} pool={len(lg5.free_agents)}")

# Euro guard: imports are league-min gambles, never mid-cap bets.
euro = _mkfa(100, "Euro Star", PlayerPosition.CENTER, ovr=88, euro=True)
lg6 = SimpleNamespace(free_agents=[euro], rivalries=[], season_year=2026)
t6 = _FakeTeam("Euro Club", [])
m6 = _mkmgr(lg6, t6, _mkstrategy([PlayerPosition.CENTER], budget=95_000_000))
decisions = m6._evaluate_free_agency(
    t6, m6.team_strategies["Euro Club"], lg6.free_agents, date(2026, 7, 2))
_euro_offers = [d for d in decisions if d.target_player is euro]
check("ai fa: euro import gets a real market offer (never capped)",
      len(_euro_offers) == 1
      and _euro_offers[0].offer_details["salary"] > 1_000_000,
      f"offer={_euro_offers[0].offer_details['salary'] if _euro_offers else None}")

# -- GM offer boldness: competitive by default, bold only when earned ------
_bteam = _FakeTeam("Bold Club", [])
_bfa = _mkfa(120, "Missing Piece", PlayerPosition.CENTER, ovr=88)
_bfa2 = _mkfa(121, "Good Player", PlayerPosition.CENTER, ovr=82)
_blg = SimpleNamespace(free_agents=[_bfa], rivalries=[], season_year=2026)
_bm = _mkmgr(_blg, _bteam, _mkstrategy([PlayerPosition.CENTER], risk=1.0))
_bstrat = _bm.team_strategies["Bold Club"]
_bold = _bm._offer_boldness(_bteam, _bstrat, _bfa, 88, _ask(88), 50_000_000)
check("ai fa: gambler GM bidding for the missing piece goes bold",
      abs(_bold - 1.18) < 1e-9, f"factor={_bold}")
# Disciplined floor: cautious GM, tight cap, not the missing piece.
_bstrat2 = _mkstrategy([PlayerPosition.CENTER], risk=0.0)
_disc = _bm._offer_boldness(_bteam, _bstrat2, _bfa2, 82, _ask(82), 5_000_000)
check("ai fa: cautious GM against a tight cap stays at the floor",
      abs(_disc - 0.90) < 1e-9, f"factor={_disc}")
# Owner warning leashes even the gambler.
_bm.gm_security["Bold Club"] = SimpleNamespace(
    hot_seat=False, tenured_winner=False, owner_warning=True)
_leashed = _bm._offer_boldness(_bteam, _bstrat, _bfa, 88, _ask(88), 50_000_000)
check("ai fa: owner warning caps the offer at the ask",
      abs(_leashed - 1.0) < 1e-9, f"factor={_leashed}")
# Tenured winner stays conservative.
_bm.gm_security["Bold Club"] = SimpleNamespace(
    hot_seat=False, tenured_winner=True, owner_warning=False)
_cons = _bm._offer_boldness(_bteam, _bstrat, _bfa2, 82, _ask(82), 50_000_000)
check("ai fa: tenured winner doesn't bid against himself",
      abs(_cons - 1.07) < 1e-9, f"factor={_cons}")
# Hot-seat GM wired to panic reaches; the patient one doesn't.
_bm.gm_security["Bold Club"] = SimpleNamespace(
    hot_seat=True, tenured_winner=False, owner_warning=False)
_bm.gm_identities["Bold Club"] = SimpleNamespace(pressure_response=0.8)
_panic = _bm._offer_boldness(_bteam, _bstrat, _bfa2, 82, _ask(82), 50_000_000)
_bm.gm_identities["Bold Club"] = SimpleNamespace(pressure_response=0.2)
_patient = _bm._offer_boldness(_bteam, _bstrat, _bfa2, 82, _ask(82), 50_000_000)
check("ai fa: hot-seat panicker reaches, patient builder doesn't",
      abs(_panic - 1.15) < 1e-9 and abs(_patient - 1.10) < 1e-9,
      f"panic={_panic} patient={_patient}")
# Rebuilder never wins bidding wars.
_bstrat3 = _mkstrategy([PlayerPosition.CENTER], risk=1.0,
                       priority=aim.ManagementPriority.REBUILD)
_reb = _bm._offer_boldness(_bteam, _bstrat3, _bfa, 88, _ask(88), 50_000_000)
check("ai fa: rebuilder never bids bold on veterans",
      abs(_reb - 1.0) < 1e-9, f"factor={_reb}")
# Full path: the bold offer lands in the decision and the reasoning says so.
_bm2 = _mkmgr(_blg, _bteam, _mkstrategy([PlayerPosition.CENTER], risk=1.0))
_bstrat_bm2 = _bm2.team_strategies["Bold Club"]
_expf = _bm2._offer_boldness(_bteam, _bstrat_bm2, _bfa, 88, _ask(88), 95_000_000)
_bdec = _bm2._evaluate_free_agency(
    _bteam, _bstrat_bm2, _blg.free_agents, date(2026, 7, 2))
_bold_offers = [d for d in _bdec if d.target_player is _bfa]
check("ai fa: bold offer executes end-to-end with the story attached",
      len(_bold_offers) == 1
      and _bold_offers[0].offer_details["salary"] == int(_ask(88) * _expf)
      and "bold bid" in _bold_offers[0].reasoning,
      f"offer={_bold_offers[0].offer_details['salary'] if _bold_offers else None}")

# -- handshake realism: the player weighs the offer against his ask ---------
_ask80 = _ask(80)
_hand0 = _mkfa(110, "Proud", PlayerPosition.CENTER, ovr=80)
_hand1 = _mkfa(111, "Prouder", PlayerPosition.CENTER, ovr=80)
_t7 = _FakeTeam("Handshake Club", [])
_lg7 = SimpleNamespace(free_agents=[_hand0, _hand1],
                       rivalries=[], season_year=2026)
_m7 = _mkmgr(_lg7, _t7, _mkstrategy([PlayerPosition.CENTER]))
check("ai fa: insult offer (<70% of ask) walks",
      not _m7._execute_free_agent_signing(
          _t7, _mkdecision(_hand0, salary=1_000_000), _lg7)
      and len(_lg7.free_agents) == 2 and len(_t7.roster) == 0)
check("ai fa: counter-zone offer (85%) meets the ask when affordable",
      _m7._execute_free_agent_signing(
          _t7, _mkdecision(_hand0, salary=int(0.85 * _ask80)), _lg7)
      and _hand0.salary == _ask80 and _hand0 in _t7.roster,
      f"salary={_hand0.salary} ask={_ask80}")
check("ai fa: full offer signs at the offered salary",
      _m7._execute_free_agent_signing(
          _t7, _mkdecision(_hand1, salary=_ask80), _lg7)
      and _hand1.salary == _ask80 and _hand1 in _t7.roster)
# Counter-zone but the ask breaks the budget -> walks.
_t8 = _FakeTeam("Broke Club", [])
_lg8 = SimpleNamespace(
    free_agents=[_mkfa(112, "Pricy", PlayerPosition.CENTER, ovr=80)],
    rivalries=[], season_year=2026)
_m8 = _mkmgr(_lg8, _t8, _mkstrategy([PlayerPosition.CENTER],
                                   budget=7_000_000))
check("ai fa: counter-zone offer walks when the ask breaks the budget",
      not _m8._execute_free_agent_signing(
          _t8, _mkdecision(_lg8.free_agents[0],
                           salary=int(0.85 * _ask80)), _lg8)
      and len(_lg8.free_agents) == 1 and len(_t8.roster) == 0)

# -- market feedback: AI signings move Caleb's market like the user's do --
class _FakeCapSys:
    """Records register_signing; demand_for mirrors the real choke point."""
    def __init__(self, market_setter=True):
        self.registered = []
        self.current_cap = 104_000_000
        self._market_setter = market_setter
    def demand_for(self, base_pct, ovr, pos, age, season):
        return int(base_pct * self.current_cap)
    def register_signing(self, name, aav, ovr, pos, age, season):
        self.registered.append((name, aav, ovr, pos, age, season))
        return self._market_setter

_fcap = _FakeCapSys(market_setter=True)
_mkt_fa = _mkfa(130, "Market Star", PlayerPosition.CENTER, ovr=90)
_mkt_team = _FakeTeam("Market Club", [])
_mkt_lg = SimpleNamespace(free_agents=[_mkt_fa], rivalries=[],
                          season_year=2026, salary_cap_system=_fcap)
_mkt_mgr = _mkmgr(_mkt_lg, _mkt_team, _mkstrategy([PlayerPosition.CENTER]))
_mkt_mgr._cap_system = _fcap
_mkt_ok = _mkt_mgr._execute_free_agent_signing(
    _mkt_team, _mkdecision(_mkt_fa), _mkt_lg)
check("ai fa: signing registers with the market engine",
      _mkt_ok and _fcap.registered == [
          ("Market Star", _ask(90), 90, PlayerPosition.CENTER.value,
           27, 2026)],
      f"registered={_fcap.registered}")
check("ai fa: market-setter queues the signing + market headlines",
      any("have signed Market Star" in s for s in _mkt_mgr._pending_news)
      and any("sets the market" in s for s in _mkt_mgr._pending_news),
      f"pending={_mkt_mgr._pending_news}")
_drained = _mkt_mgr.drain_pending_news()
check("ai fa: drain_pending_news flushes and clears",
      len(_drained) >= 2 and _mkt_mgr.drain_pending_news() == []
      and _mkt_mgr._pending_news == [])
# A non-market-setting signing: registered, no market headline.
_fcap2 = _FakeCapSys(market_setter=False)
_mkt_fa2 = _mkfa(131, "Role Player", PlayerPosition.LEFT_WING, ovr=78)
_mkt_team2 = _FakeTeam("Quiet Club", [])
_mkt_lg2 = SimpleNamespace(free_agents=[_mkt_fa2], rivalries=[],
                           season_year=2026, salary_cap_system=_fcap2)
_mkt_mgr2 = _mkmgr(_mkt_lg2, _mkt_team2,
                   _mkstrategy([PlayerPosition.LEFT_WING]))
_mkt_mgr2._cap_system = _fcap2
_mkt_ok2 = _mkt_mgr2._execute_free_agent_signing(
    _mkt_team2, _mkdecision(_mkt_fa2), _mkt_lg2)
check("ai fa: ordinary signing registers without a market headline",
      _mkt_ok2 and len(_fcap2.registered) == 1
      and any("have signed Role Player" in s
              for s in _mkt_mgr2._pending_news)
      and not any("sets the market" in s
                  for s in _mkt_mgr2._pending_news))

# Waiver claims call the transfer hook on both paths.
_pw_src = _method_src("main.py", "process_waivers")
check("claims: single-player process_waivers calls on_player_transfer",
      "on_player_transfer" in _pw_src)
_mc_src = _method_src("main.py", "_mp_claim_waivers")
check("claims: MP _mp_claim_waivers calls on_player_transfer",
      "on_player_transfer" in _mc_src)

print(f"\n{ PASS } passed, { FAIL } failed")
for f in FAILURES:
    print("FAIL:", f)
sys.exit(1 if FAIL else 0)
