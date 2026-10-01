# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: line-chemistry storytelling surface (Job 1).

Verifies the once-dead storytelling channel now arrives on both paths:
  GameSim path : pending_headlines -> make_headline("line_chemistry") renders
                 narrative text ONLY; the raw "efficiency" payload value is
                 dropped before it can reach a renderer.
  Viewer path  : PBPVisualSim._consume_inner renders "line_chemistry" events
                 as feed lines; unknown kinds with narrative text hit the
                 generic fallback instead of vanishing; kinds without text
                 stay silent (old behavior preserved).
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


import line_chemistry as lc
import headlines

print("== headline builder ==")
msg = headlines.make_headline(
    "line_chemistry", date(2026, 9, 30),
    hook="electric",
    text="This unit is electric because archetypes complement each other; "
         "the setup man has someone to feed.",
    situation="ev",
    efficiency=1.123,  # the cheat-sheet leak: must never be rendered
)
check("builder returns a message", msg is not None)
body = (msg.subject or "") + "\n" + (msg.content or "")
check("narrative story rendered", "archetypes complement each other" in body)
check("efficiency value dropped", "1.123" not in body)
check("efficiency key dropped", "efficiency" not in body.lower())
check("no decimal numbers leak", re.search(r"\d+\.\d+", body) is None)
check("situation labeled", "even strength" in body)

msg2 = headlines.make_headline(
    "line_chemistry", date(2026, 9, 30),
    hook="disjointed", text="", situation="pp", efficiency=0.9)
check("empty story -> None (no blank headlines)", msg2 is None)

check("unknown kinds still return None",
      headlines.make_headline("nope_not_real", date(2026, 9, 30)) is None)

print("== exactly-once emission (engine side, unchanged) ==")


class P:
    _pid = 0

    def __init__(self, ovr=75, role="Grinder", comps=None, name="P"):
        P._pid += 1
        self.player_id = P._pid
        self.full_name = f"{name} {P._pid}"
        self.first_name = name
        self.last_name = str(P._pid)
        self.position = "C"
        self._ovr = ovr
        self._role = role
        self._comps = dict(comps or {})

    def overall_rating(self):
        return self._ovr

    def get_role(self):
        role = self._role

        class R:
            value = role
        return R()


def _fake_raw(player, key):
    if isinstance(player, P):
        return float(player._comps.get(key, player._ovr))
    return 70.0


lc._raw_composite = _fake_raw


GRINDER = {"finishing": 60, "chance_creation": 55, "defensive_play": 82,
           "physicality": 88, "discipline": 80}


class SimStub:
    def __init__(self):
        self.pending_headlines = []


s = SimStub()
# Three identical grinders: poor fit -> efficiency notably below 1.0 ->
# the engine deems the unit notable and emits one story.
unit = [P(ovr=60, role="Grinder", comps=GRINDER, name="Grinder")
        for _ in range(3)]
e1 = lc.unit_efficiency(unit, situation="ev", sim=s)
e2 = lc.unit_efficiency(unit, situation="ev", sim=s)
stories = [h for h in s.pending_headlines if h.get("kind") == "line_chemistry"]
check("notable unit emits a story", len(stories) == 1)
check("second call does not re-emit (exactly once per unit per game)",
      len([h for h in s.pending_headlines
           if h.get("kind") == "line_chemistry"]) == 1)
for st in stories:
    m = headlines.make_headline("line_chemistry", date(2026, 9, 30),
                                **{k: v for k, v in st.items() if k != "kind"})
    check("emitted payload renders", m is not None)
    if m is not None:
        b2 = (m.subject or "") + (m.content or "")
        check("emitted payload has no numeric leak",
              "efficiency" not in b2.lower()
              and re.search(r"\d+\.\d+", b2) is None)
        check("raw efficiency value not in text",
              str(st.get("efficiency", "")) not in b2
              or len(str(st.get("efficiency", ""))) < 4)

print("== viewer dispatch (unbound _consume_inner on a stub) ==")
from pbp_visual_sim import PBPVisualSim

fed = []


def make_stub():
    return types.SimpleNamespace(
        _feed=lambda msg, tag=None, ev=None: fed.append((msg, tag)),
        _instant=False,
    )


fed.clear()
PBPVisualSim._consume_inner(
    make_stub(), {"type": "line_chemistry",
                  "text": "This unit is electric because things click."})
check("line_chemistry renders a feed line",
      len(fed) == 1 and "electric" in fed[0][0])

fed.clear()
PBPVisualSim._consume_inner(
    make_stub(), {"type": "some_future_kind",
                  "text": "A future narrative moment."})
check("unknown kind with text hits generic fallback",
      len(fed) == 1 and "future narrative" in fed[0][0])

fed.clear()
PBPVisualSim._consume_inner(
    make_stub(), {"type": "delayed_extra_attacker", "team": "X"})
check("kind without text stays silent (old behavior)",
      len(fed) == 0)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
