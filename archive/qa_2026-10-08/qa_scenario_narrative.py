# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: scenario-combos narrative surfacing (Job 2).

Verifies the narrative layer (apply_scenario(detail=True) stories +
decisiveness bands) is wired into the ecosystem WITHOUT touching sim math:
  - note_scenario_moment only inks decisive attacking wins, at most 2
    headlines per game, and emits a pbp event for the live visualizer.
  - The "scenario_moment" headline builder renders narrative text only --
    no edges, no amplifiers, no numbers.
  - apply_scenario(detail=True) returns the same probability as
    detail=False (math untouched).
"""
import os
import re
import sys
import types
from datetime import date

WT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WT)

PASS, FAIL = 0, 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  ok: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name}")


import scenario_composites as sc
import scenario_narrative as sn
import headlines

print("== math untouched ==")
p_plain = sc.apply_scenario(0.30, [], [], "breakaway", sim=None)
p_detail, info = sc.apply_scenario(0.30, [], [], "breakaway", sim=None,
                                   detail=True)
check("detail=True returns same probability", p_plain == p_detail)
check("info carries story + decisiveness",
      isinstance(info, dict) and info.get("story") and info.get("decisiveness"))

print("== note_scenario_moment gating ==")


class Tm:
    def __init__(self, n):
        self.team_name = n


class SimStub:
    def __init__(self):
        self.pending_headlines = []
        self.pbp = []

    def _emit_pbp(self, event_type, **payload):
        self.pbp.append({"type": event_type, **payload})


def decisive_info(edge=14.0):
    return {"scenario": "breakaway", "edge": edge, "amplifier": 1.04,
            "decisiveness": "decisive" if abs(edge) >= 12 else "lean",
            "story": "in alone -- daylight between him and the goalie",
            "tags": ("breakaway",), "context": ("EV", "PK"),
            "event": "breakaway conversion"}


s = SimStub()
ok = sn.note_scenario_moment(s, "breakaway", Tm("Toronto Maple Leafs"),
                             Tm("Boston Bruins"), decisive_info(14.0))
check("decisive attacking win earns ink", ok is True)
check("one headline payload queued",
      sum(1 for h in s.pending_headlines
          if h.get("kind") == "scenario_moment") == 1)
check("pbp event emitted",
      any(e.get("type") == "scenario_moment" for e in s.pbp))

s2 = SimStub()
check("lean band earns nothing",
      sn.note_scenario_moment(s2, "breakaway", Tm("A"), Tm("B"),
                              decisive_info(7.0)) is False
      and s2.pending_headlines == [] and s2.pbp == [])

s3 = SimStub()
check("decisive DEFENSIVE win earns nothing (stories are attacker-framed)",
      sn.note_scenario_moment(s3, "breakaway", Tm("A"), Tm("B"),
                              decisive_info(-15.0)) is False
      and s3.pending_headlines == [])

s4 = SimStub()
check("non-dict info is a safe no-op",
      sn.note_scenario_moment(s4, "breakaway", Tm("A"), Tm("B"), None)
      is False)

print("== headline budget: at most 2 per game ==")
s5 = SimStub()
for _ in range(5):
    sn.note_scenario_moment(s5, "breakaway", Tm("Toronto Maple Leafs"),
                            Tm("Boston Bruins"), decisive_info(16.0))
n_head = sum(1 for h in s5.pending_headlines
             if h.get("kind") == "scenario_moment")
check("5 decisive moments -> 2 headline payloads", n_head == 2)
check("all 5 still hit the pbp feed",
      sum(1 for e in s5.pbp if e.get("type") == "scenario_moment") == 5)
check("moments logged on sim", len(getattr(s5, "_scenario_moments", [])) == 5)

print("== headline rendering: narrative only ==")
spec = next(h for h in s5.pending_headlines
            if h.get("kind") == "scenario_moment")
msg = headlines.make_headline(
    "scenario_moment", date(2026, 9, 30),
    **{k: v for k, v in spec.items() if k != "kind"})
check("builder returns a message", msg is not None)
body = (msg.subject or "") + "\n" + (msg.content or "")
check("story rendered", "daylight between him and the goalie" in body)
check("no decimal numbers", re.search(r"\d+\.\d+", body) is None)
check("no engine vocabulary",
      "decisiveness" not in body.lower() and "amplifier" not in body.lower()
      and "edge" not in body.lower().replace("knowledge", ""))
check("teams named", "Toronto Maple Leafs" in body and "Boston Bruins" in body)
check("involved teams set for inbox routing",
      spec.get("involved") == ("Toronto Maple Leafs", "Boston Bruins"))

print("== viewer dispatch ==")
from pbp_visual_sim import PBPVisualSim

fed = []
stub = types.SimpleNamespace(
    _feed=lambda msg, tag=None, ev=None: fed.append((msg, tag)),
    _instant=False)
PBPVisualSim._consume_inner(
    stub, {"type": "scenario_moment",
           "text": "Toronto Maple Leafs -- in alone -- daylight."})
check("scenario_moment renders a feed line",
      len(fed) == 1 and "daylight" in fed[0][0])

print("== production wiring present ==")
gs_src = open(os.path.join(WT, "simulation.py")).read()
check("rush site uses detail=True + note",
      '_asc_rush(' in gs_src and 'detail=True' in gs_src
      and 'note_scenario_moment' in gs_src)
check("breakaway site wired", '_nsn2(self, "breakaway"' in gs_src)
check("netfront/one-timer site wired", '_nsn3(self, _scn,' in gs_src)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
