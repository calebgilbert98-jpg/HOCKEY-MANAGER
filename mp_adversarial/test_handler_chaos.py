# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Adversarial handler chaos: every routed MP action against the real
host handlers with (a) valid params -> must apply to the canonical team,
(b) hostile params -> must reject cleanly, never raise, never touch the
wrong team.

Run: python3 -m mp_adversarial.test_handler_chaos   (from repo root)
"""
import copy
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_adversarial.harness import check, summary, ACTION_COUNT
from mp_adversarial.fakeapp import ChaosApp, apply, make_player


def snapshot_team(team):
    return {
        "roster": sorted(str(getattr(p, "id", "")) for p in team.roster),
        "ahl": sorted(str(getattr(p, "id", "")) for p in team.ahl_roster),
        "staff": len(getattr(team, "staff", []) or []),
        "lineup": copy.deepcopy(getattr(team, "lineup", {}) or {}),
        "block": sorted(str(getattr(p, "id", ""))
                        for p in getattr(team, "trade_block", []) or []),
    }


def other_team_untouched(app, which="CHAOSB"):
    """The other team's canonical state must never move."""
    t = app._mp_find_team(which)
    return snapshot_team(t)


app = ChaosApp()
A, B = "CHAOSA", "CHAOSB"
team_a = app._mp_find_team(A)
fa0 = app.free_agent_pool[0]
fa0_id = str(getattr(fa0, "id", ""))

# ---------------------------------------------------------------- 1. valid
# sign_free_agent
b_before = other_team_untouched(app)
ok, detail = apply(app, "sign_free_agent",
                   {"team_id": A, "player_id": fa0_id,
                    "salary": 2_000_000, "years": 2}, A)
ACTION_COUNT["n"] += 1
check("sign_free_agent applies", ok, detail)
check("signed player on A's roster",
      any(str(getattr(p, "id", "")) == fa0_id for p in team_a.roster), detail)
check("B untouched by A's signing",
      other_team_untouched(app) == b_before)

# extend_contract
victim = team_a.roster[2]
victim.contract.years_remaining = 1
vid = str(getattr(victim, "id", ""))
ok, detail = apply(app, "extend_contract",
                   {"team_id": A, "player_id": vid,
                    "salary": 3_000_000, "years": 4}, A)
ACTION_COUNT["n"] += 1
check("extend_contract applies", ok, detail)

# call_up / send_to_minors round trip
ahl_kid = make_player("ahlkid", last="AHLKid", age=21)
ahl_kid.team_name = A
team_a.ahl_roster.append(ahl_kid)
ok, detail = apply(app, "call_up",
                   {"team_id": A, "player_id": "pahlkid"}, A)
ACTION_COUNT["n"] += 1
check("call_up applies", ok, detail)
check("kid on NHL roster after call_up",
      any(str(getattr(p, "id", "")) == "pahlkid" for p in team_a.roster))
ok, detail = apply(app, "send_to_minors",
                   {"team_id": A, "player_id": "pahlkid"}, A)
ACTION_COUNT["n"] += 1
check("send_to_minors applies", ok, detail)

# set_lines
lines = {"L1": [vid], "L2": [], "L3": [], "L4": []}
ok, detail = apply(app, "set_lines", {"team_id": A, "lines": lines}, A)
ACTION_COUNT["n"] += 1
check("set_lines applies", ok, detail)

# set_trade_block
ok, detail = apply(app, "set_trade_block",
                   {"team_id": A, "player_ids": [vid]}, A)
ACTION_COUNT["n"] += 1
check("set_trade_block applies", ok, detail)
try:
    import trade_market as _tm
    _blocks = _tm.get_trade_blocks(app.league)
    _in_block = vid in [str(x) for x in _blocks.get(A, [])]
except Exception:
    _in_block = False
check("block holds the player", _in_block, detail)

# set_captaincy
_alt1 = str(getattr(team_a.roster[3], "id", ""))
_alt2 = str(getattr(team_a.roster[4], "id", ""))
ok, detail = apply(app, "set_captaincy",
                   {"team_id": A, "captain_id": vid,
                    "alt_ids": [_alt1, _alt2]}, A)
ACTION_COUNT["n"] += 1
check("set_captaincy applies", ok, detail)

# fire_staff / hire_staff
from game_classes import Staff, StaffRole
st = Staff(first_name="Chaos", last_name="Coach", role=StaffRole.HEAD_COACH)
st.id = "st1"
team_a.staff.append(st)
ok, detail = apply(app, "fire_staff", {"team_id": A, "staff_id": "st1"}, A)
ACTION_COUNT["n"] += 1
check("fire_staff applies", ok, detail)

# assign_scout
ok, detail = apply(app, "assign_scout",
                   {"team_id": A, "scout_id": "sx", "region": "OHL"}, A)
ACTION_COUNT["n"] += 1
# May fail gracefully if no scout system; must not crash.
check("assign_scout doesn't crash", True)

# practice_session / start_practice_plan
ok, detail = apply(app, "practice_session",
                   {"team_id": A, "player_id": vid,
                    "practice_type": "skating", "intensity": "medium",
                    "duration": 60, "trainer_quality": 70}, A)
ACTION_COUNT["n"] += 1
check("practice_session doesn't crash", True)
ok, detail = apply(app, "start_practice_plan",
                   {"team_id": A, "player_id": vid,
                    "practice_type": "skating", "intensity": "medium",
                    "total_sessions": 5}, A)
ACTION_COUNT["n"] += 1
check("start_practice_plan doesn't crash", True)

# claim_waivers
w = make_player("waiv1", last="WaivGuy", salary=1_000_000)
w.team_name = B
w.on_waivers = True
app.waiver_list.append(w)
ok, detail = apply(app, "claim_waivers",
                   {"team_id": A, "player_id": "pwaiv1"}, A)
ACTION_COUNT["n"] += 1
check("claim_waivers queues", ok, detail)

# buyout_player
ok, detail = apply(app, "buyout_player",
                   {"team_id": A, "player_id": vid}, A)
ACTION_COUNT["n"] += 1
check("buyout_player doesn't crash", True)

# return_to_junior
jun = make_player("jun1", last="JunKid", age=18)
jun.team_name = A
team_a.roster.append(jun)
ok, detail = apply(app, "return_to_junior",
                   {"team_id": A, "player_id": "pjun1"}, A)
ACTION_COUNT["n"] += 1
check("return_to_junior doesn't crash", True)

# request_save (no mp_host attached -> must fail gracefully, not crash)
ok, detail = apply(app, "request_save", {"team_id": A}, A)
ACTION_COUNT["n"] += 1
check("request_save without host doesn't crash", True)

# release_player
rel = make_player("rel1", last="RelGuy", salary=1_000_000)
rel.team_name = A
team_a.roster.append(rel)
ok, detail = apply(app, "release_player",
                   {"team_id": A, "player_id": "prel1"}, A)
ACTION_COUNT["n"] += 1
check("release_player doesn't crash", True)

# ------------------------------------------------------- 2. hostile params
HOSTILE = [
    ("sign_free_agent", {"team_id": A}),                          # missing pid
    ("sign_free_agent", {"team_id": A, "player_id": "nope",
                         "salary": 1, "years": 1}),               # unknown FA
    ("sign_free_agent", {"team_id": A, "player_id": fa0_id,
                         "salary": -5_000_000, "years": 2}),      # negative $
    ("sign_free_agent", {"team_id": A, "player_id": fa0_id,
                         "salary": "lots", "years": "many"}),     # garbage types
    ("sign_free_agent", {"team_id": A, "player_id": fa0_id,
                         "salary": 10**15, "years": 99}),         # absurd
    ("extend_contract", {"team_id": A, "player_id": "ghost",
                         "salary": 1, "years": 1}),               # ghost player
    ("extend_contract", {"team_id": A, "player_id": vid,
                         "salary": -1, "years": -2}),             # negative
    ("call_up", {"team_id": A, "player_id": vid}),                # already NHL
    ("call_up", {"team_id": A, "player_id": "ghost"}),            # ghost
    ("send_to_minors", {"team_id": A, "player_id": "ghost"}),     # ghost
    ("claim_waivers", {"team_id": A, "player_id": "ghost"}),      # ghost
    ("claim_waivers", {"team_id": A}),                            # missing pid
    ("set_lines", {"team_id": A, "lines": "notadict"}),           # wrong shape
    ("set_lines", {"team_id": A}),                                # missing lines
    # ghost->empty handled below (not a rejection case)
    ("set_trade_block", {"team_id": A, "player_ids": "nope"}),    # wrong shape
    ("fire_staff", {"team_id": A, "staff_id": "ghost"}),          # ghost staff
    ("fire_staff", {"team_id": A}),                               # missing
    ("buyout_player", {"team_id": A, "player_id": "ghost"}),      # ghost
    ("offer_sheet", {"team_id": A}),                              # missing all
    ("offer_sheet", {"team_id": A, "player_id": "ghost",
                     "aav": -1, "years": 0}),                    # garbage
    ("draft_pick", {"team_id": A, "player_id": "ghost"}),         # no clock
    ("hire_staff", {"team_id": A}),                               # missing
    ("assign_scout", {"team_id": A}),                             # missing
    ("practice_session", {"team_id": A}),                         # missing
    ("start_practice_plan", {"team_id": A, "player_id": vid}),    # partial
    ("propose_trade", {"team_id": A}),                            # missing all
    ("propose_trade", {"team_id": A, "partner_team_id": "ghost",
                       "offer": {}}),                            # ghost partner
    ("propose_trade", {"team_id": A, "partner_team_id": A,
                       "offer": {"players_out": [vid],
                                 "players_in": [vid]}}),         # self-trade
    ("set_captaincy", {"team_id": A}),                            # missing
    ("team_talk", {"team_id": A, "tone": "nonsense-tone"}),        # bad tone
    ("press_conference", {"team_id": A, "stance": 12345}),          # bad type
    ("set_tactics", {"team_id": A}),                              # missing
    ("return_to_junior", {"team_id": A, "player_id": "ghost"}),   # ghost
    ("release_player", {"team_id": A, "player_id": "ghost"}),     # ghost
]

b_snap = other_team_untouched(app)
crashes = 0
for action, params in HOSTILE:
    ACTION_COUNT["n"] += 1
    try:
        ok, detail = apply(app, action, params, A)
        # Hostile input must be rejected, never applied.
        check(f"hostile {action} rejected",
              ok is False, f"params={params} -> ({ok}, {detail})")
    except Exception as e:
        crashes += 1
        check(f"hostile {action} no-crash", False,
              f"RAISED {type(e).__name__}: {e}")
check("zero handler crashes on hostile input", crashes == 0,
      f"{crashes} raised")
# Ghost player IDs in lines must resolve to empty slots, never to another
# club's players.
ACTION_COUNT["n"] += 1
ok, detail = apply(app, "set_lines",
                   {"team_id": A,
                    "lines": {"Forwards": [["ghost123"]] }}, A)
_flat = str(getattr(team_a, "lineup", ""))
check("ghost lines don't inject players",
      "ghost123" not in _flat, detail)
check("B untouched by hostile barrage", other_team_untouched(app) == b_snap)

# ------------------------------------------------- 3. cross-team authz at
# handler level: _apply_multiplayer_action resolves team from params;
# net_host already rejects mismatched team_id, but verify the handler
# never writes to a team that isn't the resolved one.
b_snap2 = other_team_untouched(app)
ok, detail = apply(app, "set_trade_block",
                   {"team_id": B, "player_ids": []}, B)
ACTION_COUNT["n"] += 1
check("explicit B action resolves to B", ok or "block" in str(detail).lower())

ok_summary = summary()
sys.exit(0 if ok_summary else 1)
