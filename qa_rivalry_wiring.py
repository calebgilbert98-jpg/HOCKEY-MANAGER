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
pc.base_controversy = 60  # personality to take the snub personally
rs.record_award_race(lg2.rivalries, pc, pd, "Hart Trophy")
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

print(f"\n{ PASS } passed, { FAIL } failed")
for f in FAILURES:
    print("FAIL:", f)
sys.exit(1 if FAIL else 0)
