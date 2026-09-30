"""QA: dressing-room dynamics (module 03).

Hierarchy, social groups, trade/press cascades, team talks, and the
sim momentum hooks. Deterministic: seeded RNG, fake players.
"""
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, ".")

import dressing_room as dr


def make_player(name, nat="Canada", tenure="4+ years", letter="",
                leadership=60, morale=70, pid=None):
    return SimpleNamespace(
        id=pid if pid is not None else name,
        full_name=name, name=name,
        nationality=nat, team_tenure=tenure,
        captaincy=letter, leadership=leadership, morale=morale,
        stats=SimpleNamespace(games_played=20),
    )


def make_team(players, name="Test Club"):
    return SimpleNamespace(team_name=name, roster=list(players),
                           staff=[], streak=0)


passed, failed = [], []


def check(label, cond):
    (passed if cond else failed).append(label)
    if not cond:
        print(f"  FAIL: {label}")


# 1-2: backfill + influence -------------------------------------------
t = make_team([])
d = dr.ensure_dressing_room_fields(t)
check("backfill creates dict", isinstance(d, dict))
check("backfill keys", all(k in d for k in ("mood_log", "pregame",
                                            "intermission", "arrivals")))

cap = make_player("Cap", letter="C", leadership=80)
alt = make_player("Alt", letter="A", leadership=60)
reg = make_player("Reg", leadership=60)
check("captain outranks alternate",
      dr.influence_of(cap) > dr.influence_of(alt))
check("alternate outranks regular",
      dr.influence_of(alt) > dr.influence_of(reg))
hi_lead = make_player("Hi", leadership=95)
lo_lead = make_player("Lo", leadership=10)
check("leadership raises influence",
      dr.influence_of(hi_lead) > dr.influence_of(lo_lead))
check("influence clamped", 5 <= dr.influence_of(reg) <= 99)

# 3-4: hierarchy -------------------------------------------------------
team = make_team([reg, cap, alt])
h = dr.hierarchy(team)
check("hierarchy sorted desc",
      [r["name"] for r in h] == ["Cap", "Alt", "Reg"])
check("tiers labeled",
      [r["tier"] for r in h] == ["Captain", "Alternate", "Regular"])
check("captain_of finds C", dr.captain_of(team) is cap)
no_c = make_team([reg, alt])
check("de facto voice without C",
      dr.captain_of(no_c) is alt)

# 5-6: cliques ----------------------------------------------------------
core = [make_player(f"Core{i}", tenure="4+ years") for i in range(4)]
new = [make_player(f"New{i}", tenure="This season") for i in range(3)]
lone = make_player("Lone", nat="Sweden", tenure="2 years")
team2 = make_team(core + new + [lone])
cliques = dr.form_cliques(team2)
check("two cliques formed", len(cliques) == 2)
check("clique bond in range", all(0 < c["bond"] <= 0.95 for c in cliques))
check("clique mood is mean",
      cliques[0]["mood"] == 70)
fl = dr.floaters(team2)
check("lone player floats", [f["name"] for f in fl] == ["Lone"])
check("clique_of finds member", dr.clique_of(team2, core[0]) is not None)
check("clique_of misses floater", dr.clique_of(team2, lone) is None)
check("room_mood mean", dr.room_mood(team2) == 70)

# 7-9: trade cascades ----------------------------------------------------
team3 = make_team([
    make_player("Skip", letter="C", leadership=85, morale=70),
    make_player("Mate1", tenure="4+ years", morale=70),
    make_player("Mate2", tenure="4+ years", morale=70),
    make_player("Other", tenure="This season", nat="Sweden", morale=70),
])
dealt = make_player("Dealt", tenure="4+ years", morale=70)
team3.roster.append(dealt)
lines = dr.cascade_on_trade(team3, traded=dealt, date_str="2026-10-01")
mate1 = next(p for p in team3.roster if p.name == "Mate1")
other = next(p for p in team3.roster if p.name == "Other")
check("clique-mates drop more",
      mate1.morale < other.morale < 70)
check("captain steadies (halved hit)", mate1.morale >= 66)
check("trade logged", len(lines) >= 1 and len(team3.dressing_room["mood_log"]) >= 1)

# captain traded -> vacuum
team4 = make_team([make_player("OldC", letter="C", morale=70),
                   make_player("P2", morale=70)])
oldc = team4.roster[0]
lines4 = dr.cascade_on_trade(team4, traded=oldc)
check("captain vacuum logged",
      any("new voice" in ln for ln in lines4))

# arrival integration
team5 = make_team([make_player(f"Vet{i}", tenure="4+ years") for i in range(4)])
arr = make_player("NewGuy", nat="Sweden", tenure="This season")
arr.stats.games_played = 0
dr.cascade_on_trade(team5, arriving=arr, date_str="2026-10-01")
check("outsider morale hit", arr.morale < 70)
check("outsider integration low", dr.integration_of(team5, arr) < 100)
arr.stats.games_played = 10
check("integration grows with games",
      dr.integration_of(team5, arr) == 100)

# 10-12: press cascades ---------------------------------------------------
team6 = make_team([
    make_player("Star", tenure="4+ years", morale=70),
    make_player("Pal", tenure="4+ years", morale=70),
    make_player("Vet", tenure="4+ years", morale=70),
    make_player("Rook", tenure="This season", nat="Sweden", morale=70),
])
star = team6.roster[0]
dr.cascade_on_press(team6, {"player_name": "Star"}, "critical")
pal = team6.roster[1]
check("critical hits target hardest", star.morale == 64 and pal.morale == 67)
dr.cascade_on_press(team6, {"player_name": "Star"}, "supportive")
check("supportive lifts", star.morale > 64)
before = [p.morale for p in team6.roster]
dr.cascade_on_press(team6, {}, "confident")
check("confident lifts room",
      all(a >= b for a, b in zip([p.morale for p in team6.roster], before)))
dr.cascade_on_press(team6, {}, "dismissive")
check("dismissive dips room",
      all(p.morale < 72 for p in team6.roster))
check("unknown choice safe",
      dr.cascade_on_press(team6, {}, "rambling") == [])

# morale clamping
low = make_player("Low", morale=2, tenure="4+ years")
team7 = make_team([low, make_player("Gone", tenure="4+ years", morale=70)])
gone = team7.roster[1]
dr.cascade_on_trade(team7, traded=gone)
check("morale never below 1", low.morale >= 1)

# 13-15: talks -------------------------------------------------------------
random.seed(7)
team8 = make_team([make_player(f"P{i}", tenure="4+ years") for i in range(5)])
team8.roster[0].captaincy = "C"
ctx_trail = {"situation": "pregame", "score_state": "trailing",
             "rival": False, "streak": -3}
out = dr.give_talk(team8, "fired-up", ctx_trail, speaker="coach",
                   rng=random.Random(7))
check("talk returns record",
      all(k in out for k in ("tone", "outcome", "boost", "note")))
check("talk queued", team8.dressing_room["pregame"] is not None)
check("outcome tier valid",
      out["outcome"] in ("landed", "steady", "flat", "backfired"))
check("boost in range", -1 <= out["boost"] <= 2)

out_bad = dr.give_talk(team8, "bogus", ctx_trail, rng=random.Random(7))
check("bad tone falls back to calm", out_bad["tone"] == "calm")

# tone fit: fired-up should do better trailing than leading (same seed)
r1, r2 = random.Random(42), random.Random(42)
a = dr.give_talk(team8, "fired-up",
                 {"situation": "pregame", "score_state": "trailing",
                  "rival": False, "streak": 0}, rng=r1)
b = dr.give_talk(team8, "fired-up",
                 {"situation": "pregame", "score_state": "leading",
                  "rival": False, "streak": 0}, rng=r2)
check("fired-up fits trailing better than leading",
      a["boost"] >= b["boost"])

cap_out = dr.give_talk(team8, "calm", ctx_trail, speaker="captain",
                       rng=random.Random(7))
check("captain speaker named", cap_out["speaker"] == "captain")

italk = dr.give_talk(team8, "cautious",
                     {"situation": "intermission", "score_state": "leading",
                      "rival": False, "streak": 0}, rng=random.Random(3))
check("intermission queued separately",
      team8.dressing_room["intermission"] is not None)

# 16-17: consume ------------------------------------------------------------
team9 = make_team([make_player("P1")])
dr.give_talk(team9, "calm",
             {"situation": "pregame", "score_state": "tied",
              "rival": False, "streak": 0}, rng=random.Random(1))
queued = team9.dressing_room["pregame"]["boost"]
got = dr.consume_pregame_boost(team9)
check("consume returns queued boost", got == queued)
check("consume clears", team9.dressing_room["pregame"] is None)
auto = dr.consume_pregame_boost(team9)
check("empty consume auto-talks (int)", isinstance(auto, int))
ib = dr.consume_intermission_boost(team9, score_diff=-2)
check("intermission consume int", isinstance(ib, int))

# parity: auto_talk uses the same record shape
at = dr.auto_talk(team9, {"situation": "pregame", "score_state": "trailing",
                         "rival": False, "streak": 0}, rng=random.Random(5))
check("auto_talk same shape as give_talk",
      set(at.keys()) == set(out.keys()) and at["tone"] == "fired-up")

# 18-19: sim momentum hooks (deterministic boost injection) ------------------
from simulation import GameMomentum
order = list(GameMomentum)
home = make_team([make_player("H1")], name="Home")
away = make_team([make_player("A1")], name="Away")

home.dressing_room = None  # force backfill path
dr.ensure_dressing_room_fields(home)
dr.ensure_dressing_room_fields(away)
home.dressing_room["pregame"] = {"tone": "fired-up", "outcome": "landed",
                                 "boost": 2, "note": "x", "speaker": "coach",
                                 "speaker_name": "c", "context": {}}
sim = SimpleNamespace(home_team=home, away_team=away,
                      momentum=GameMomentum.NEUTRAL, momentum_history=[],
                      _impact_stories_told=0)
dr.apply_pregame_talks(sim)
check("pregame talk nudges momentum home",
      order.index(sim.momentum) < order.index(GameMomentum.NEUTRAL))
check("pregame consumed", home.dressing_room["pregame"] is None)

away.dressing_room["intermission"] = {"tone": "fired-up", "outcome": "landed",
                                      "boost": 2, "note": "x",
                                      "speaker": "coach", "speaker_name": "c",
                                      "context": {}}
home.dressing_room["intermission"] = {"tone": "calm", "outcome": "flat",
                                      "boost": 0, "note": "x",
                                      "speaker": "coach", "speaker_name": "c",
                                      "context": {}}
sim2 = SimpleNamespace(home_team=home, away_team=away,
                       home_score=3, away_score=0,
                       momentum=GameMomentum.NEUTRAL, momentum_history=[],
                       _impact_stories_told=0)
dr.apply_intermission_talk(sim2)
check("intermission talk nudges momentum away",
      order.index(sim2.momentum) > order.index(GameMomentum.NEUTRAL))

# backfired talk can push the wrong way but never crash
dr.give_talk(home, "fired-up",
             {"situation": "pregame", "score_state": "leading",
              "rival": False, "streak": 5}, rng=random.Random(0))
sim3 = SimpleNamespace(home_team=home, away_team=away,
                       momentum=GameMomentum.NEUTRAL, momentum_history=[],
                       _impact_stories_told=0)
dr.apply_pregame_talks(sim3)
check("negative boost safe", True)

# 20-27: hardening -------------------------------------------------------
# 20: departure cascade identifies the clique AFTER roster removal
clique_players = [make_player(f"Swede{i}", nat="Sweden", tenure="4+ years")
                  for i in range(4)]
others = [make_player(f"Other{i}", nat="Canada", tenure="4+ years")
          for i in range(4)]
departed = clique_players[0]
team20 = make_team(clique_players + others, name="Club20")
team20.roster.remove(departed)  # trade_engine moves bodies before the hook
lines20 = dr.cascade_on_trade(team20, traded=departed, date_str="2026-09-28")
check("departure cascade names the lost clique after roster removal",
      any("sweden" in ln.lower() for ln in lines20))
clique_mates = [p for p in clique_players[1:]]
non_clique = [p for p in others]
check("clique mates hit harder than the room",
      max(p.morale for p in clique_mates) < min(p.morale for p in non_clique))

# 21: press cascade reads a MediaEvent OBJECT (details dict, 'player')
tgt21 = make_player("Target One")
team21 = make_team([tgt21, make_player("Mate")], name="Club21")
ev_obj = SimpleNamespace(details={"player": "Target One", "type": "signing"})
before = tgt21.morale
dr.cascade_on_press(team21, ev_obj, "critical")
check("press cascade hits target from MediaEvent object",
      tgt21.morale < before)

# 22: press cascade reads trade details lists ('traded_players')
tgt22 = make_player("Dealt Star")
team22 = make_team([tgt22, make_player("Mate2")], name="Club22")
ev_trade = SimpleNamespace(
    details={"traded_players": ["Dealt Star"], "type": "trade"})
before22 = tgt22.morale
dr.cascade_on_press(team22, ev_trade, "supportive")
check("press cascade hits target from trade details list",
      tgt22.morale > before22)

# 23: plain-dict 'player_name' key still works (no regression)
tgt23 = make_player("Old Key")
team23 = make_team([tgt23], name="Club23")
before23 = tgt23.morale
dr.cascade_on_press(team23, {"player_name": "Old Key"}, "critical")
check("press cascade keeps dict player_name key", tgt23.morale < before23)

# 24-26: AdvancedGameSim consumes dressing-room talks (both rooms)
import main as _main
AGS = _main.AdvancedGameSim
h24 = make_team([make_player("UH1")], name="UserClub")
a24 = make_team([make_player("AH1")], name="AICLub")
dr.ensure_dressing_room_fields(h24)
dr.ensure_dressing_room_fields(a24)
h24.dressing_room["pregame"] = {"tone": "fired-up", "outcome": "landed",
                                "boost": 2, "note": "x", "speaker": "coach",
                                "speaker_name": "c", "context": {}}
sim24 = AGS.__new__(AGS)
sim24.home_team, sim24.away_team = h24, a24
sim24.dressing_boost = {h24.team_name: 1.0, a24.team_name: 1.0}
sim24._apply_dressing_room_pregame()
check("AdvancedGameSim consumes user pregame talk",
      abs(sim24.dressing_boost[h24.team_name] - 1.02) < 1e-9
      and h24.dressing_room["pregame"] is None)
check("AdvancedGameSim auto-talks the AI room (parity)",
      a24.dressing_room["pregame"] is None
      and any("gave a" in str(ln) and "talk" in str(ln)
              for ln in a24.dressing_room.get("mood_log", [])))

# 26: intermission hook moves the third-period needle
h24.dressing_room["intermission"] = {
    "tone": "calm", "outcome": "backfired", "boost": -1, "note": "x",
    "speaker": "coach", "speaker_name": "c", "context": {}}
sim24.score = {h24.team_name: 0, a24.team_name: 2}
sim24._apply_dressing_room_intermission()
check("AdvancedGameSim intermission talk applies",
      abs(sim24.dressing_boost[h24.team_name] - 1.01) < 1e-9
      and h24.dressing_room["intermission"] is None)

# 27: dressing channel stays capped
for _ in range(10):
    h24.dressing_room["pregame"] = {"tone": "fired-up", "outcome": "landed",
                                    "boost": 2, "note": "x", "speaker": "coach",
                                    "speaker_name": "c", "context": {}}
    sim24._apply_dressing_room_pregame()
check("dressing boost capped at 1.04",
      sim24.dressing_boost[h24.team_name] <= 1.04)


def _last_auto_choice(team):
    log = dr.ensure_dressing_room_fields(team)["mood_log"]
    for ln in reversed(log):
        if ln.startswith("(Automated press answer:"):
            return ln.split(": ", 1)[1].rstrip(".)")
    return None


# 28-30: AI press parity -- auto_press_response ---------------------------
random.seed(7)
t28 = make_team([make_player(f"P{i}", morale=70) for i in range(6)])
ev28 = {"players_involved": ["P0"], "trade": True}
dr.auto_press_response(t28, ev28)
choice28 = _last_auto_choice(t28)
check("auto press logs a valid answer",
      choice28 in ("critical", "supportive", "confident", "dismissive",
                   "hostile", "controversial", "professional",
                   "thoughtful", "diplomatic"))
# Same mechanic as the user's answer: replay the logged choice through
# cascade_on_press on a fresh room and compare morale vectors exactly.
t28b = make_team([make_player(f"P{i}", morale=70) for i in range(6)])
dr.cascade_on_press(t28b, ev28, choice28)
check("AI press == user press mechanic",
      [p.morale for p in t28b.roster] == [p.morale for p in t28.roster])

# 31: mood shapes the automated answer
random.seed(1234)
happy = make_team([make_player(f"H{i}", morale=95) for i in range(6)])
sad = make_team([make_player(f"S{i}", morale=15) for i in range(6)])
happy_choices, sad_choices = set(), set()
for _ in range(30):
    for p in happy.roster:
        p.morale = 95
    dr.auto_press_response(happy, {"players_involved": []})
    happy_choices.add(_last_auto_choice(happy))
    for p in sad.roster:
        p.morale = 15
    dr.auto_press_response(sad, {"players_involved": []})
    sad_choices.add(_last_auto_choice(sad))
check("happy room answers confident/supportive/professional",
      happy_choices <= {"confident", "supportive", "professional"}
      and len(happy_choices) > 1)
check("unhappy room answers diplomatic/supportive/dismissive/controversial",
      sad_choices <= {"diplomatic", "supportive", "dismissive", "controversial"}
      and len(sad_choices) > 1)

# 32-33: trade hook fires for AI sides only --------------------------------
import trade_engine as te
u32 = make_team([make_player("UT1", morale=70), make_player("UT2", morale=70)],
                name="User Club")
u32.is_user_team = True
a32 = make_team([make_player("AI1", morale=70), make_player("AI2", morale=70)],
                name="AI Club")
pA, pB = u32.roster[0], a32.roster[0]
te._post_trade_effects(u32, a32, [pA], [pB], "2026-10-01", None)
check("AI side gets automated press after trade",
      _last_auto_choice(a32) is not None)
check("user side gets no automated press (user answers)",
      _last_auto_choice(u32) is None)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
