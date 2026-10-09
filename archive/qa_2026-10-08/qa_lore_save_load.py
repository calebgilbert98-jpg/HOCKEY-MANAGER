# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: lore survives save/load -- retired players, retired numbers, pending
ceremonies, and the milestone idempotency set must round-trip.

Bug history: immortality.py generated retired_players / retired_numbers /
_pending_ceremony in memory, but save_load_system.py never serialized them:
every load deleted retired players from the universe, re-issued retired
numbers to rookies, dropped queued ceremonies, and re-fired every past
milestone celebration.
"""
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from types import SimpleNamespace

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


def make_gm():
    from game_classes import League, Team
    league = League("NHL")
    league.season_year = 2028
    t = Team("Testers", "Testville", "Atlantic", "Eastern")
    league.teams = [t]
    # Lore state, as immortality.py / milestones.py would leave it.
    league.retired_players = [{
        "name": "Gordie Howe II", "position": "RW", "number": 9,
        "games": 1600, "points": 1500, "cups": 2,
        "awards": ["Hart"], "ballot_years": 2, "inducted": False,
    }]
    league._milestone_celebrated = {(101, "500_goals"), (202, "1000_games")}
    t.retired_numbers = [{"number": 9, "player": "Gordie Howe II",
                          "year": 2028}]
    t._pending_ceremony = {"kind": "jersey_retirement",
                           "info": {"player": "Gordie Howe II",
                                    "number": 9}}
    # Sweep batch 2: every other lore/story/earned-state attribute the
    # serializer was dropping.
    league.steal_retro_posted = {501, 502}
    league._last_cup_champ = "Testers"
    league._last_champ_core = frozenset({"2-1-2", "Overload"})
    league._blueprint_dynasties = {"Testers": 2}
    from media_engine import Narrative, CoachMediaBeef
    _n = Narrative("hot_seat", "Testers", "Seat getting warm",
                   subjects=["Coach K"], heat=70.0)
    league.media_narratives = [_n]
    _b = CoachMediaBeef("Coach K", "Testers|Stirrer Sam", "Stirrer Sam",
                        "Testers")
    _b.level = 2
    league.coach_media_beefs = [_b]
    league.media_fines = [{"date": "2028-03-01", "name": "Player P",
                           "amount": 5000}]
    league.draft_day_deals = ["Testers acquire pick #7 from Rivals"]
    t.dynamics_log = [{"date": "2028-03-01", "type": "win_streak",
                       "text": "Won 5 straight", "morale_delta": 5,
                       "tone": "up"}]
    t.dressing_room = {"mood_log": ["Room is buzzing"],
                       "pregame": {"text": "Let's go"},
                       "intermission": None,
                       "arrivals": {11: {"gp_at_arrival": 40}}}
    t.steal_watch = {701: {"name": "Sleeper S", "round": 5}}
    t.sell_watch = {702: {"name": "Bust B"}}
    t.scout_buy_tips = {703: {"tip": "buy"}}
    t.scout_sell_tips = {704: {"tip": "sell"}}
    t.tip_ledger = {"tip-1": {"player_id": 701, "verdict": None}}
    t.line_control = "gm"
    t.tactic_even_strength = "Aggressive"
    t.tactic_power_play = "Umbrella"
    t.tactic_penalty_kill = "Passive"
    t.tactic_line_matching = "Heavy"
    t.tactic_forecheck = "1-2-2"
    t.tactic_offense = "Overload"
    t.tactics_familiarity = 62.5
    t.tactics_installed_by = "coach-1"
    t.preferred_tactics = {"forecheck": "1-2-2"}
    t._parity_state = {"form": 1.5, "streak": 3, "winless": 0,
                       "coach_key": "ck", "new_coach_games": 5}
    t.analytics_quality = 80
    t.analytics_philosophy = 75.0
    t.philosophy_baseline = 30.0
    t._prev_gm_name = "Old GM"
    t.analytics_games = [{"date": "2028-03-01", "home": "Testers",
                          "score": (4, 2)}]
    t.gm_name = "New GM"
    from game_classes import GMProfile
    t.gm_profile = GMProfile(name="New GM", age=50)
    gm = SimpleNamespace(league=league, league_history=None,
                         narrative_ledger=None)
    return gm


from save_load_system import GameSaveManager as SaveLoadSystem

gm = make_gm()
saver = SaveLoadSystem(gm)

tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "lore_test.save")
check("save succeeds", saver.save_game(path), path)

# Load into a fresh manager and verify the lore came back.
gm2 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
loader = SaveLoadSystem(gm2)
check("load succeeds", loader.load_game(path), path)

lg2 = gm2.league
rp = getattr(lg2, "retired_players", None) or []
check("retired players survive", len(rp) == 1 and rp[0]["name"] == "Gordie Howe II"
      and rp[0]["ballot_years"] == 2, str(rp))

mc = getattr(lg2, "_milestone_celebrated", None)
check("milestone idempotency set survives",
      isinstance(mc, set) and (101, "500_goals") in mc and (202, "1000_games") in mc,
      str(mc))

t2 = (lg2.teams or [None])[0]
rn = getattr(t2, "retired_numbers", None) or []
check("retired numbers survive",
      len(rn) == 1 and rn[0]["number"] == 9
      and rn[0]["player"] == "Gordie Howe II", str(rn))

pc = getattr(t2, "_pending_ceremony", None)
check("pending ceremony survives",
      isinstance(pc, dict) and pc.get("kind") == "jersey_retirement"
      and (pc.get("info") or {}).get("number") == 9, str(pc))

# --- Sweep batch 2 round-trips ---
srp = getattr(lg2, "steal_retro_posted", None)
check("steal-retro idempotency set survives",
      isinstance(srp, set) and srp == {501, 502}, str(srp))
check("defending-champ tracking survives",
      getattr(lg2, "_last_cup_champ", None) == "Testers"
      and getattr(lg2, "_last_champ_core", None) == frozenset({"2-1-2", "Overload"})
      and getattr(lg2, "_blueprint_dynasties", None) == {"Testers": 2},
      str((getattr(lg2, "_last_cup_champ", None),
           getattr(lg2, "_last_champ_core", None),
           getattr(lg2, "_blueprint_dynasties", None))))
from media_engine import Narrative as _Narr, CoachMediaBeef as _Beef
mn = getattr(lg2, "media_narratives", None) or []
check("media narratives survive as Narrative objects",
      len(mn) == 1 and isinstance(mn[0], _Narr)
      and mn[0].kind == "hot_seat" and abs(mn[0].heat - 70.0) < 1e-6,
      str([getattr(n, "__dict__", n) for n in mn]))
cb = getattr(lg2, "coach_media_beefs", None) or []
check("coach-media beefs survive as CoachMediaBeef objects",
      len(cb) == 1 and isinstance(cb[0], _Beef) and cb[0].level == 2
      and cb[0].coach_name == "Coach K",
      str([getattr(b, "__dict__", b) for b in cb]))
mf = getattr(lg2, "media_fines", None) or []
check("media fines survive",
      len(mf) == 1 and mf[0].get("amount") == 5000, str(mf))
ddd = getattr(lg2, "draft_day_deals", None) or []
check("draft-day deals feed survives",
      len(ddd) == 1 and "pick #7" in ddd[0], str(ddd))

dl = getattr(t2, "dynamics_log", None) or []
check("dynamics log survives",
      len(dl) == 1 and dl[0].get("text") == "Won 5 straight"
      and dl[0].get("tone") == "up", str(dl))
dr = getattr(t2, "dressing_room", None) or {}
check("dressing-room state survives",
      (dr.get("mood_log") or [""])[0] == "Room is buzzing"
      and (dr.get("arrivals") or {}).get(11, {}).get("gp_at_arrival") == 40,
      str(dr))
check("scout watches survive",
      (getattr(t2, "steal_watch", None) or {}).get(701, {}).get("round") == 5
      and (getattr(t2, "sell_watch", None) or {}).get(702, {}).get("name") == "Bust B"
      and (getattr(t2, "scout_buy_tips", None) or {}).get(703, {}).get("tip") == "buy"
      and (getattr(t2, "scout_sell_tips", None) or {}).get(704, {}).get("tip") == "sell"
      and (getattr(t2, "tip_ledger", None) or {}).get("tip-1", {}).get("player_id") == 701,
      str((getattr(t2, "steal_watch", None), getattr(t2, "tip_ledger", None))))
check("line control survives",
      getattr(t2, "line_control", None) == "gm", str(getattr(t2, "line_control", None)))
check("tactics bundle survives",
      getattr(t2, "tactic_forecheck", None) == "1-2-2"
      and getattr(t2, "tactic_offense", None) == "Overload"
      and abs(float(getattr(t2, "tactics_familiarity", 0) or 0) - 62.5) < 1e-6
      and getattr(t2, "tactics_installed_by", None) == "coach-1"
      and (getattr(t2, "preferred_tactics", None) or {}).get("forecheck") == "1-2-2",
      str((getattr(t2, "tactic_forecheck", None),
           getattr(t2, "tactics_familiarity", None))))
ps = getattr(t2, "_parity_state", None) or {}
check("parity state survives",
      ps.get("streak") == 3 and ps.get("new_coach_games") == 5, str(ps))
check("analytics identity survives",
      getattr(t2, "analytics_quality", None) == 80
      and abs(float(getattr(t2, "analytics_philosophy", 0) or 0) - 75.0) < 1e-6
      and getattr(t2, "_prev_gm_name", None) == "Old GM",
      str((getattr(t2, "analytics_quality", None),
           getattr(t2, "analytics_philosophy", None))))
ag = getattr(t2, "analytics_games", None) or []
check("analytics snapshots survive",
      len(ag) == 1 and ag[0].get("home") == "Testers", str(ag))
check("gm name + profile survive",
      getattr(t2, "gm_name", None) == "New GM"
      and getattr(getattr(t2, "gm_profile", None), "name", None) == "New GM"
      and getattr(getattr(t2, "gm_profile", None), "age", None) == 50,
      str((getattr(t2, "gm_name", None),
           getattr(getattr(t2, "gm_profile", None), "__dict__", None))))

# Old-save tolerance: keys absent -> graceful defaults, no crash.
gm3 = make_gm()
s3 = SaveLoadSystem(gm3)
data = s3._serialize_league()
tdata = data["teams"][0]
for k in ("retired_players", "_milestone_celebrated", "steal_retro_posted",
            "_last_cup_champ", "_last_champ_core", "_blueprint_dynasties",
            "media_narratives", "coach_media_beefs", "media_fines",
            "draft_day_deals"):
    data.pop(k, None)
for k in ("retired_numbers", "_pending_ceremony", "dynamics_log",
            "dressing_room", "scout_watches", "line_control", "tactics",
            "_parity_state", "analytics_identity", "analytics_games",
            "gm_name", "gm_profile"):
    tdata.pop(k, None)
gm4 = SimpleNamespace(league=None, league_history=None,
                      narrative_ledger=None)
s4 = SaveLoadSystem(gm4)
try:
    from game_classes import League as _L
    gm4.league = _L("NHL")
    gm4.league.teams = []
    s4._restore_league(data)
    lg4 = gm4.league
    check("old save: retired_players defaults to empty",
          getattr(lg4, "retired_players", None) == [], str(getattr(lg4, "retired_players", None)))
    check("old save: milestone set defaults to empty",
          getattr(lg4, "_milestone_celebrated", None) == set())
    t4 = (lg4.teams or [None])[0]
    check("old save: retired_numbers defaults to empty",
          getattr(t4, "retired_numbers", None) == [])
    check("old save: pending ceremony defaults to None",
          getattr(t4, "_pending_ceremony", "X") is None)
    check("old save: steal-retro set defaults to empty",
          getattr(lg4, "steal_retro_posted", None) == set())
    check("old save: dynasty tracking defaults to fresh",
          getattr(lg4, "_last_cup_champ", "X") is None
          and getattr(lg4, "_last_champ_core", None) == frozenset()
          and getattr(lg4, "_blueprint_dynasties", None) == {})
    check("old save: media state defaults to empty",
          getattr(lg4, "media_narratives", None) == []
          and getattr(lg4, "coach_media_beefs", None) == []
          and getattr(lg4, "media_fines", None) == []
          and getattr(lg4, "draft_day_deals", None) == [])
    check("old save: dynamics log + dressing room default to empty",
          getattr(t4, "dynamics_log", None) == []
          and getattr(t4, "dressing_room", None) == {})
    check("old save: scout watches default to empty",
          all(getattr(t4, w, None) == {}
              for w in ("steal_watch", "sell_watch", "scout_buy_tips",
                        "scout_sell_tips", "tip_ledger")))
    check("old save: line control defaults to coach",
          getattr(t4, "line_control", None) == "coach")
    check("old save: tactics default to fresh-club values",
          getattr(t4, "tactic_forecheck", None) == "2-1-2"
          and float(getattr(t4, "tactics_familiarity", 0) or 0) == 85.0
          and getattr(t4, "preferred_tactics", None) == {})
    check("old save: parity + analytics default",
          getattr(t4, "_parity_state", None) == {}
          and getattr(t4, "analytics_quality", None) == 35
          and getattr(t4, "analytics_games", None) == []
          and getattr(t4, "_prev_gm_name", None) == "")
    check("old save: gm name + profile default",
          getattr(t4, "gm_name", None) == "General Manager"
          and getattr(getattr(t4, "gm_profile", None), "name", None) is not None)
except Exception as e:  # noqa: BLE001
    check("old save restores without new keys", False, str(e))

print(f"\n{'='*60}\nQA lore_save_load: {PASS} passed, {FAIL} failed")
for f in FAILURES:
    print(f"  FAIL: {f}")
sys.exit(1 if FAIL else 0)
