# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: multiplayer NMC consent is host-authoritative (no client trust).

Run:  xvfb-run -a python3 qa_mp_nmc_consent.py

Covers:
 1. send_to_minors on an NMC player -> host opens a waiver consent flow
    (NTC_WAIVER_REQUEST, context="waivers"); the player is NOT demoted yet.
 2. A forged ntc_consent=true param is IGNORED -- the flow still opens.
 3. Answer "cancel" -> stays on the roster, pending entry cleared.
 4. Answer "ask" + player grants -> demotion executes on the host.
 5. Answer "ask" + player refuses -> stays on the roster.
 6. Non-NMC player -> immediate demotion, no waiver request sent.
 7. Buyout of an NMC player needs NO consent (single-player parity).
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trade_engine as te
import windows as _windows
import main as _main

passed = []


def check(name, cond, extra=""):
    assert cond, f"FAILED: {name} {extra}"
    passed.append(name)
    print(f"  ok: {name}")


class FakeHost:
    def __init__(self):
        self.waiver_requests = []
        self.chats = []

    def send_ntc_waiver_request(self, session_id, waiver_id, player_id,
                                player_name, clause, dest_team, context):
        self.waiver_requests.append({
            "session_id": session_id, "waiver_id": waiver_id,
            "player_id": player_id, "player_name": player_name,
            "clause": clause, "dest_team": dest_team, "context": context})
        return True

    def broadcast_chat(self, text):
        self.chats.append(text)

    def find_peer_by_team(self, team_id):
        return SimpleNamespace(session_id="sess-1", name="Muck")


def make_contract(nmc=False):
    return SimpleNamespace(no_movement_clause=nmc, no_trade_clause=False,
                           modified_ntc_teams=0, salary=5_000_000,
                           years_remaining=2, ntc_waiver_for="")


def make_player(pid, nmc=False):
    return SimpleNamespace(id=pid, full_name=f"Player {pid}",
                           contract=make_contract(nmc),
                           on_waivers=False, waiver_days=0,
                           age=30, nhl_games_played=400,
                           ahl_games_since_assignment=None)


def make_team():
    team = SimpleNamespace(team_name="TOR", roster=[], ahl_roster=[],
                           buyout_cap_hits={})
    team.remove_player = lambda p: team.roster.remove(p) \
        if p in team.roster else None
    # Legal lineup (18+2) so the dress-minimum guard doesn't block the
    # demote under test. SimpleNamespace fillers matching make_player.
    for i in range(18):
        f = SimpleNamespace(id=f"fill-s{i}", full_name=f"Filler S{i}",
                            contract=make_contract(), on_waivers=False,
                            waiver_days=0, age=25, nhl_games_played=300,
                            is_injured=False, position="C",
                            ahl_games_since_assignment=None)
        team.roster.append(f)
    for i in range(2):
        g = SimpleNamespace(id=f"fill-g{i}", full_name=f"Filler G{i}",
                            contract=make_contract(), on_waivers=False,
                            waiver_days=0, age=28, nhl_games_played=200,
                            is_injured=False, position="G",
                            primary_position=SimpleNamespace(value="G"),
                            ahl_games_since_assignment=None)
        team.roster.append(g)
    return team


def make_app(team):
    app = object.__new__(_main.HockeyManagerGUI)
    app._mp_pending_ntc = {}
    app._mp_pending_offers = {}
    app.league = SimpleNamespace(teams=[team], season_year=2026)
    app.mp_host = FakeHost()
    app.waiver_list = []
    app.add_news = lambda msg: None
    app._fa_pool = []
    app.free_agents = lambda: app._fa_pool
    return app


def demote(app, team, pid, extra=None):
    params = {"team_id": "TOR", "player_id": pid}
    if extra:
        params.update(extra)
    return _main.HockeyManagerGUI._mp_send_to_minors(app, params, team,
                                                     "Muck")


def answer(app, waiver_id, choice):
    _main.HockeyManagerGUI._mp_resolve_ntc_answer(
        app, {"waiver_id": waiver_id, "choice": choice,
              "manager": "Muck"})


# --- 1+2. NMC demote -> consent flow; forged consent ignored ------------
print("1-2. NMC demotion opens a host-side consent flow")
team = make_team()
star = make_player("p1", nmc=True)
team.roster.append(star)
app = make_app(team)

ok, detail, bcast = demote(app, team, "p1", {"ntc_consent": True})
check("action accepted-but-deferred", ok and bcast is False, detail)
check("player NOT demoted yet", not star.on_waivers)
check("one waiver request sent", len(app.mp_host.waiver_requests) == 1)
req = app.mp_host.waiver_requests[0]
check("context is waivers", req["context"] == "waivers", req)
check("pending entry recorded",
      len(app._mp_pending_ntc) == 1
      and list(app._mp_pending_ntc.values())[0]["kind"] == "demote")
wid = req["waiver_id"]

# --- 3. cancel -> stays --------------------------------------------------
print("3. cancel keeps him on the roster")
answer(app, wid, "cancel")
check("pending cleared", not app._mp_pending_ntc)
check("still on roster, not on waivers",
      star in team.roster and not star.on_waivers)

# --- 4. ask + granted -> demotion runs -----------------------------------
print("4. ask + granted runs the demotion on the host")
ok, detail, bcast = demote(app, team, "p1")
req = app.mp_host.waiver_requests[-1]
orig_waive = te.will_waive_ntc
te.will_waive_ntc = lambda *a, **k: (True, "chasing a Cup")
try:
    answer(app, req["waiver_id"], "ask")
finally:
    te.will_waive_ntc = orig_waive
check("demotion executed", star.on_waivers and star.waiver_days == 2)
check("pending cleared", not app._mp_pending_ntc)

# --- 5. ask + refused -> stays -------------------------------------------
print("5. ask + refused keeps him on the roster")
star.on_waivers = False
star.waiver_days = 0
ok, detail, bcast = demote(app, team, "p1")
req = app.mp_host.waiver_requests[-1]
te.will_waive_ntc = lambda *a, **k: (False, "loves it here")
try:
    answer(app, req["waiver_id"], "ask")
finally:
    te.will_waive_ntc = orig_waive
check("not demoted", not star.on_waivers)
check("pending cleared", not app._mp_pending_ntc)
check("refusal announced",
      any("refused" in c for c in app.mp_host.chats))

# --- 6. non-NMC -> immediate ----------------------------------------------
print("6. non-NMC player demoted immediately, no request")
team2 = make_team()
plug = make_player("p2", nmc=False)
team2.roster.append(plug)
app2 = make_app(team2)
n_before = len(app2.mp_host.waiver_requests)
ok, detail = demote(app2, team2, "p2")[:2]
check("demoted at once", ok and plug.on_waivers, detail)
check("no waiver request",
      len(app2.mp_host.waiver_requests) == n_before)

# --- 7. buyout of NMC player needs no consent ----------------------------
print("7. buyout ignores NMC (single-player parity)")
team3 = make_team()
vet = make_player("p3", nmc=True)
team3.roster.append(vet)
app3 = make_app(team3)
orig_sched = _windows.buyout_schedule
_windows.buyout_schedule = lambda p: (100.0, 50.0, 2,
                                       [(1, 50.0, 25.0), (2, 50.0, 25.0)])
try:
    ok, detail = _main.HockeyManagerGUI._mp_buyout_player(
        app3, {"team_id": "TOR", "player_id": "p3"}, team3, "Muck")
finally:
    _windows.buyout_schedule = orig_sched
check("buyout completed", ok, detail)
check("no consent flow opened", not app3._mp_pending_ntc
      and not app3.mp_host.waiver_requests)
check("player bought out", vet not in team3.roster
      and vet in app3._fa_pool)
check("dead cap written", app3.league and team3.buyout_cap_hits.get(2026)
      == 50)

print(f"\nALL {len(passed)} NMC-CONSENT QA CHECKS PASSED")
