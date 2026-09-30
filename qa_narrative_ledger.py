# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: narrative ledger — Wave 3 rivalries + narrative foundation.

Covers: record/query indexes, callback cooldowns, pruning/archive caps,
season rollover, save round-trip, four-viewpoint interpretation,
playoff-series memory derivation, grudge headline, and the
record_game_incident bridge. Headless.
"""
import sys
import time
from types import SimpleNamespace

sys.path.insert(0, ".")

import narrative_ledger as nl
from narrative_ledger import NarrativeLedger, interpret, incident_short

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

print("== ledger basics ==")
led = NarrativeLedger()
led.set_clock(2026, 10)
e1 = led.record("incident", teams=["Boston Bruins", "Toronto Maple Leafs"],
               facts={"incident_kind": "controversial_hit",
                      "perpetrator": "M. Knies", "victim": "D. Pastrnak",
                      "perpetrator_team": "Toronto Maple Leafs"},
               weight=55, text="Knies levels Pastrnak late")
check("record returns event with id", e1["id"] == 1)
check("between finds it",
      len(led.between("Toronto Maple Leafs", "Boston Bruins")) == 1)
check("pair order independent",
      len(led.between("Boston Bruins", "Toronto Maple Leafs")) == 1)
check("unrelated pair empty",
      len(led.between("Boston Bruins", "Edmonton Oilers")) == 0)
check("latest_incident", led.latest_incident("Boston Bruins",
      "Toronto Maple Leafs")["id"] == 1)
check("kind filter", len(led.between("Boston Bruins", "Toronto Maple Leafs",
      kinds=["playoff_series"])) == 0)
led.record("incident", teams=["Boston Bruins", "Toronto Maple Leafs"],
           players=["M. Knies"], weight=30, text="minor scrum")
check("for_player", len(led.for_player("M. Knies")) == 1)
check("min_weight filter",
      len(led.between("Boston Bruins", "Toronto Maple Leafs",
                      min_weight=50)) == 1)

print("== callback cooldowns ==")
led.set_clock(2026, 20)
cand = led.callback_candidate("Boston Bruins", "Toronto Maple Leafs")
check("candidate found (newest incident)", cand is not None and cand["id"] == 2,
      str(cand["id"] if cand else None))
_cid = cand["id"]
led.mark_referenced(_cid)
check("cooldown blocks repeat",
      led.callback_candidate("Boston Bruins", "Toronto Maple Leafs") is None)
led.set_clock(2026, 20 + nl.CALLBACK_COOLDOWN_DAYS)
cand = led.callback_candidate("Boston Bruins", "Toronto Maple Leafs")
check("cooldown expiry re-arms", cand is not None)
check("second reference is not 'first meeting'",
      cand["ref_count"] == 1)
led.set_clock(2026, 20 + nl.MEMORY_WINDOW_DAYS + 1)
check("memory window expiry",
      led.callback_candidate("Boston Bruins", "Toronto Maple Leafs") is None)
# trivia never earns a callback
led2 = NarrativeLedger(); led2.set_clock(2026, 5)
led2.record("incident", teams=["A", "B"], weight=10, text="chirping")
check("low weight never a candidate",
      led2.callback_candidate("A", "B") is None)

print("== interpretation: one event, four viewpoints ==")
ev = led._by_id[1]
check("room (perpetrator team)",
      interpret(ev, "room", "Toronto Maple Leafs") is not None and
      "loved it" in interpret(ev, "room", "Toronto Maple Leafs"))
check("room (victim team)",
      "hasn't forgotten" in (interpret(ev, "room", "Boston Bruins") or ""))
check("fans hero/villain",
      "hero" in (interpret(ev, "fans", "Toronto Maple Leafs") or "") and
      "villain" in (interpret(ev, "fans", "Boston Bruins") or ""))
check("media speaks", interpret(ev, "media") is not None)
check("league silent when small", interpret(ev, "league") is None)
big = dict(ev, weight=80)
check("league speaks when large", interpret(big, "league") is not None)
check("incident_short", incident_short(ev["facts"]) == "the hit (M. Knies on D. Pastrnak)",
      incident_short(ev["facts"]))

print("== playoff-series memory ==")
def fake_series(winner_is_t1, results, round_name="Second Round",
                wpos=1, lpos=8):
    t1 = SimpleNamespace(team_name="Colorado Avalanche",
                         standings_position=wpos if winner_is_t1 else lpos)
    t2 = SimpleNamespace(team_name="Dallas Stars",
                         standings_position=lpos if winner_is_t1 else wpos)
    games = []
    for i, (t1w, ot, steal) in enumerate(results, 1):
        games.append({"game": i, "t1_score": 3 if t1w else 2,
                      "t2_score": 2 if t1w else 3, "team1_won": t1w,
                      "ot": ot, "goalie_steal": steal})
    return SimpleNamespace(
        team1=t1, team2=t2, winner=t1 if winner_is_t1 else t2,
        team1_wins=sum(1 for t1w, _, _ in results if t1w),
        team2_wins=sum(1 for t1w, _, _ in results if not t1w),
        games_played=len(results), is_complete=True,
        game_results=games, round_name=round_name)

led3 = NarrativeLedger(); led3.set_clock(2027, 200)
# 7-game comeback: winner loses first 3, wins 4 straight; game 7 OT; steal
s = fake_series(True, [(False, False, None), (False, False, None),
                       (False, True, None), (True, False, None),
                       (True, False, "J. Oettinger (38 saves)"),
                       (True, False, None), (True, True, None)])
ev3 = nl.record_playoff_series_memory(led3, s)
check("series recorded", ev3 is not None)
f = ev3["facts"]
check("seven games", f["seven_games"] is True)
check("comeback 1-3", f["comeback"] == "came back from 1-3 down", str(f["comeback"]))
check("ot games counted", f["ot_games"] == 2)
check("beats mention OT + steal + clincher",
      any("OT" in b for b in f["beats"]) and
      any("goalie steal" in b for b in f["beats"]) and
      any("closed it out" in b for b in f["beats"]), str(f["beats"]))
check("no upset (1 beats 8)", f["upset"] is False)
# upset + sweep
s2 = fake_series(False, [(False, False, None)] * 4, wpos=8, lpos=1)
ev4 = nl.record_playoff_series_memory(led3, s2)
check("sweep detected", ev4["facts"]["sweep"] is True)
check("upset detected", ev4["facts"]["upset"] is True)
# blown lead: loser up 2-0 then loses 4-2
s3 = fake_series(True, [(False, False, None), (False, False, None),
                       (True, False, None), (True, False, None),
                       (True, False, None), (True, False, None)])
ev5 = nl.record_playoff_series_memory(led3, s3)
check("blown lead", ev5["facts"]["blown_lead"] == "Dallas Stars blew a 2-0 series lead",
      str(ev5["facts"]["blown_lead"]))
check("series_history", len(led3.series_history("Colorado Avalanche",
      "Dallas Stars")) == 3)
check("media memory line",
      "Remember" in (interpret(ev3, "media") or ""))
check("fans winner/loser lines",
      "want it again" in (interpret(ev3, "fans", "Colorado Avalanche") or "") and
      "haven't forgiven" in (interpret(ev3, "fans", "Dallas Stars") or ""))
check("rivalry_summary",
      led3.rivalry_summary("Colorado Avalanche", "Dallas Stars")
      ["playoff_series"] == 3)

print("== perf: 4000-event index ==")
led4 = NarrativeLedger()
t0 = time.time()
for i in range(4200):
    led4.record("incident", teams=[f"Team{i % 32}", f"Team{(i + 7) % 32}"],
                weight=(i % 100), text=f"ev {i}")
t_write = time.time() - t0
check("cap enforced", len(led4) == nl.MAX_EVENTS, str(len(led4)))
check("overflow archived", len(led4.archive) > 0)
t0 = time.time()
for _ in range(2000):
    led4.between("Team3", "Team10")
    led4.callback_candidate("Team3", "Team10")
t_q = (time.time() - t0) / 4000
check(f"write 4200 in {t_write:.2f}s", t_write < 5.0)
check(f"query ~{t_q * 1e6:.1f}us/op (sub-ms)", t_q < 0.001, f"{t_q}")

print("== season rollover ==")
led5 = NarrativeLedger()
led5.set_clock(2024, 100)
led5.record("incident", teams=["X", "Y"], weight=20, text="forgettable")
led5.record("incident", teams=["X", "Y"], weight=80, text="unforgettable")
led5.set_clock(2028, 10)
led5.advance_season(2028)
evs = led5.between("X", "Y")
check("old low-weight archived", len(evs) == 1 and evs[0]["weight"] == 80,
      str([e["weight"] for e in evs]))
check("archive kept count", len(led5.archive) > 0)

print("== save round-trip ==")
d = led3.to_dict()
led6 = NarrativeLedger.from_dict(d)
check("round-trip preserves queries",
      len(led6.series_history("Colorado Avalanche", "Dallas Stars")) == 3 and
      led6._seq == led3._seq)
check("bad input -> empty ledger",
      len(NarrativeLedger.from_dict(None)) == 0 and
      len(NarrativeLedger.from_dict({"events": [{"no": "id"}]})) == 0)

print("== grudge headline ==")
from datetime import date
import headlines
msg = headlines.make_headline(
    "grudge_callback", date(2027, 1, 15), home="Boston Bruins",
    away="Toronto Maple Leafs", short="the hit (M. Knies on D. Pastrnak)",
    room_line="The room hasn't forgotten.",
    fans_line="The fans still boo.",
    media_line="Rivalry fuel.", league_line="",
    first_meeting=True, involved=("Boston Bruins", "Toronto Maple Leafs"))
check("headline built", msg is not None)
check("four viewpoints in body",
      msg is not None and "ROOM" in msg.content and "FANS" in msg.content
      and "MEDIA" in msg.content and "LEAGUE" not in msg.content)
check("unknown kind still None",
      headlines.make_headline("nope", date(2027, 1, 15)) is None)

print("== record_game_incident bridge ==")
import reputation_system as rs
led7 = NarrativeLedger(); led7.set_clock(2026, 50)
nl.set_active_ledger(led7)
ta = SimpleNamespace(team_name="Edmonton Oilers")
tb = SimpleNamespace(team_name="Calgary Flames")
rivalries = []
res = rs.record_game_incident(rivalries, ta, tb, "controversial_hit",
                             "big hit by EDM")
check("incident recorded", res.get("recorded") is True)
check("ledger bridged",
      len(led7.between("Edmonton Oilers", "Calgary Flames")) == 1)
check("ledger weight from INCIDENT_WEIGHTS",
      led7.between("Edmonton Oilers", "Calgary Flames")[0]["weight"] ==
      rs.INCIDENT_WEIGHTS["controversial_hit"])
nl.set_active_ledger(None)
res2 = rs.record_game_incident(rivalries, ta, tb, "brawl", "scrap")
check("no ledger, no crash", res2.get("recorded") is True)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)