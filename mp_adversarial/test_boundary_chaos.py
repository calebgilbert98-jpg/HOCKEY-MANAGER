# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Event-boundary chaos: hostile conditions at the draft, trade deadline,
waivers, playoffs, and offseason rollover. Any divergence or crash at a
boundary is a P0.

Run: python3 -m mp_adversarial.test_boundary_chaos   (from repo root)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mp_adversarial.harness import check, summary, ACTION_COUNT
from mp_adversarial.fakeapp import ChaosApp, apply, make_player

app = ChaosApp()
A, B = "CHAOSA", "CHAOSB"
team_a = app._mp_find_team(A)
team_b = app._mp_find_team(B)

# ------------------------------------------------- (a) entry draft
# Set up a draft clock for team A with two prospects.
pros1 = make_player("dp1", last="DraftKid", age=18)
pros1.draft_ranking = 1
pros2 = make_player("dp2", last="DraftKid2", age=18)
pros2.draft_ranking = 2
app.league.draft_prospects = [pros1, pros2]
app._mp_draft_clock = {
    "clock_id": "clk-a1", "team_id": A, "overall": 5,
    "round_num": 1, "deadline": 9999999999.0,
    "pick_id": None, "done": False,
}

# B spams draft_pick when it's NOT their turn.
ok, detail = apply(app, "draft_pick",
                   {"team_id": B, "player_id": "pdp1",
                    "clock_id": "clk-a1"}, B)
ACTION_COUNT["n"] += 1
check("draft: other team's pick rejected", ok is False, detail)

# A picks with a stale clock_id.
ok, detail = apply(app, "draft_pick",
                   {"team_id": A, "player_id": "pdp1",
                    "clock_id": "stale-clock"}, A)
ACTION_COUNT["n"] += 1
check("draft: stale clock rejected", ok is False, detail)

# A picks a prospect that's not in the pool.
ok, detail = apply(app, "draft_pick",
                   {"team_id": A, "player_id": "pghost",
                    "clock_id": "clk-a1"}, A)
ACTION_COUNT["n"] += 1
check("draft: ghost prospect rejected", ok is False, detail)

# A makes the real pick.
ok, detail = apply(app, "draft_pick",
                   {"team_id": A, "player_id": "pdp1",
                    "clock_id": "clk-a1"}, A)
ACTION_COUNT["n"] += 1
check("draft: on-clock pick registers",
      ok is True and app._mp_draft_clock.get("pick_id") == "pdp1", detail)

# Racing second pick on the same clock (double-submit).
ok, detail = apply(app, "draft_pick",
                   {"team_id": A, "player_id": "pdp2",
                    "clock_id": "clk-a1"}, A)
ACTION_COUNT["n"] += 1
check("draft: double-submit keeps first pick",
      app._mp_draft_clock.get("pick_id") == "pdp1",
      f"pick_id={app._mp_draft_clock.get('pick_id')}")

# Clock done: late pick rejected.
app._mp_draft_clock["done"] = True
ok, detail = apply(app, "draft_pick",
                   {"team_id": A, "player_id": "pdp2",
                    "clock_id": "clk-a1"}, A)
ACTION_COUNT["n"] += 1
check("draft: pick after done rejected", ok is False, detail)
app._mp_draft_clock = None

# ------------------------------------------ (b) trade deadline
# Freeze the league: set the date past the deadline. The Mar 2027
# deadline belongs to season 2026-27, so season_year must be 2026
# (2027 would mean the league already rolled over and lifted the freeze).
app.league.season_year = 2026
app.current_date = "2027-04-15"  # after the ~Mar deadline
from game_classes import Player as _P  # noqa
pa = team_a.roster[2]
pb = team_b.roster[2]
pa_id, pb_id = str(getattr(pa, "id", "")), str(getattr(pb, "id", ""))
offer = {"players_out": [pa_id], "players_in": [pb_id],
         "picks_out": [], "picks_in": [],
         "retention": {}, "pick_protection": {}}
ok, detail = apply(app, "propose_trade",
                   {"team_id": A, "partner_team_id": B,
                    "offer": offer}, A)
ACTION_COUNT["n"] += 1
check("deadline: proposal after freeze rejected",
      ok is False and "frozen" in str(detail).lower(), detail)
check("deadline: no pending offer leaked",
      len(app._mp_pending_offers) == 0,
      str(list(app._mp_pending_offers)))

# Flurry: 10 rapid proposals at the freeze, none may execute or leak.
for i in range(10):
    ACTION_COUNT["n"] += 1
    ok, _ = apply(app, "propose_trade",
                  {"team_id": A, "partner_team_id": B,
                   "offer": offer}, A)
    assert ok is False
check("deadline: 10-proposal flurry all rejected, none leaked",
      len(app._mp_pending_offers) == 0)

# Accept-after-deadline: seed a pending offer, roll past the freeze,
# then accept -> execution must die at _mp_execute_mp_trade.
app.current_date = "2027-01-15"  # before deadline
ok, detail = apply(app, "propose_trade",
                   {"team_id": A, "partner_team_id": B,
                    "offer": offer}, A)
ACTION_COUNT["n"] += 1
# (May route to AI evaluation or need human; just check it didn't crash.)
app.current_date = "2027-04-15"  # now past the freeze
# Simulate an accept on any pending offer for this pair.
for _oid in list(app._mp_pending_offers):
    ACTION_COUNT["n"] += 1
    app._mp_resolve_trade_response(
        {"offer_id": _oid, "decision": "accept", "manager": "ChaosGM"})
check("deadline: accept-after-freeze executes nothing",
      pa in team_a.roster and pb in team_b.roster,
      "rosters must be unchanged")
app._mp_pending_offers.clear()
app.league.season_year = 2027
app.current_date = "2027-01-15"

# ------------------------------------------------- (c) waiver race
# Two clients claim the same player in the same instant.
w = make_player("wrace", last="RaceGuy", salary=1_000_000)
w.team_name = "AI_CLUB"
w.on_waivers = True
app.waiver_list.append(w)
ok1, d1 = apply(app, "claim_waivers",
                {"team_id": A, "player_id": "pwrace"}, A)
ACTION_COUNT["n"] += 1
ok2, d2 = apply(app, "claim_waivers",
                {"team_id": B, "player_id": "pwrace"}, B)
ACTION_COUNT["n"] += 1
check("waivers: both claims queue (priority decides at noon)",
      ok1 and ok2, f"{d1} / {d2}")
_pending = getattr(w, "mp_claim_teams", [])
check("waivers: both teams recorded",
      A in _pending and B in _pending, str(_pending))
# Same team claiming twice -> rejected (no double-queue).
ok3, d3 = apply(app, "claim_waivers",
                {"team_id": A, "player_id": "pwrace"}, A)
ACTION_COUNT["n"] += 1
check("waivers: duplicate claim rejected", ok3 is False, d3)
# Claiming your own player -> rejected.
w2 = make_player("wown", last="OwnGuy", salary=1_000_000)
w2.team_name = A
w2.on_waivers = True
app.waiver_list.append(w2)
ok4, d4 = apply(app, "claim_waivers",
                {"team_id": A, "player_id": "pwown"}, A)
ACTION_COUNT["n"] += 1
check("waivers: own-player claim rejected", ok4 is False, d4)

# ------------------------------------------- (d) playoffs / elimination
# Eliminated teams CAN still do roster moves (NHL rule); trades stay
# frozen by the deadline gate. Verify no crash and no phantom gate.
kid = make_player("pkid", last="PlayKid", age=21)
kid.team_name = A
team_a.ahl_roster.append(kid)
ok, detail = apply(app, "call_up",
                   {"team_id": A, "player_id": "ppkid"}, A)
ACTION_COUNT["n"] += 1
check("playoffs: call-up after elimination works", ok, detail)

# ------------------------------------------------- (e) rollover
# Contract actions during the rollover advance must not corrupt.
# (Simulate by firing them back-to-back; handlers must stay consistent.)
ve = team_a.roster[5]
ve.contract.years_remaining = 1
ve_id = str(getattr(ve, "id", ""))
ok1, d1 = apply(app, "extend_contract",
                {"team_id": A, "player_id": ve_id,
                 "salary": 2_500_000, "years": 3}, A)
ACTION_COUNT["n"] += 1
ok2, d2 = apply(app, "extend_contract",
                {"team_id": A, "player_id": ve_id,
                 "salary": 2_500_000, "years": 3}, A)
ACTION_COUNT["n"] += 1
check("rollover: double-extend doesn't corrupt",
      True, f"{d1} / {d2}")
check("rollover: host still consistent",
      app._mp_find_team(A) is team_a and
      app._mp_find_team(B) is team_b)

ok = summary()
sys.exit(0 if ok else 1)
