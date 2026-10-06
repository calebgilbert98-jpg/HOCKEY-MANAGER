"""Smoke test for Batch B team-management gap fixes.

Exercises the new APIs + bridge ops on mock teams: captaincy-crisis
detection/resolution, advise-coach, rivalries, coach carousel (fire/hire),
scout assignment cancel, scouting staff list, player database filters,
staff detail tabs, extension negotiation, org chart, staff report,
hiring negotiation chain, and development analytics/recommendations.

Portable: resolves the game root from this file's location (no
worktree-specific paths).
"""
import os
import sys
from datetime import date
from types import SimpleNamespace

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# dressing_room.py defines DressingRoomView(customtkinter.CTkFrame) at
# module level; stub customtkinter so it imports headless.
import types as _types

_ctk_stub = _types.ModuleType("customtkinter")


class _DummyFrame:
    def __init__(self, *a, **k):
        pass


_ctk_stub.CTkFrame = _DummyFrame
sys.modules["customtkinter"] = _ctk_stub

import web_ui.bridge as bridge
from game_classes import PlayerPosition, StaffRole

_POS_BY_ABBR = {
    "C": PlayerPosition.CENTER, "LW": PlayerPosition.LEFT_WING,
    "RW": PlayerPosition.RIGHT_WING, "LD": PlayerPosition.LEFT_DEFENSE,
    "RD": PlayerPosition.RIGHT_DEFENSE, "D": PlayerPosition.DEFENSE,
    "G": PlayerPosition.GOALIE,
}


class Player:
    def __init__(self, pid, name, pos, age, ovr):
        self.id = pid
        self.full_name = name
        self.first_name, self.last_name = name.split(" ", 1)
        self.primary_position = _POS_BY_ABBR.get(pos, PlayerPosition.CENTER)
        self.age = age
        self._ovr = ovr
        self.morale = 70
        self.happiness = 70
        self.captaincy = ""
        self.stats = SimpleNamespace(games_played=120)
        self.is_injured = False
        self.potential = 60
        # dev attributes (native 100-scale)
        for a in ("skating", "shooting", "passing", "checking",
                  "determination", "conditioning", "hockey_iq", "vision",
                  "faceoffs", "positioning", "defense", "goaltending",
                  "reflexes", "rebound_control", "mental_toughness",
                  "consistency"):
            setattr(self, a, 62)
        self.skating = 80

    def overall_rating(self):
        return self._ovr


_ROLE_BY_LABEL = {
    "Head Coach": StaffRole.HEAD_COACH,
    "Amateur Scout": StaffRole.AMATEUR_SCOUT,
    "Assistant Coach": StaffRole.ASSISTANT_COACH,
    "General Manager": StaffRole.GENERAL_MANAGER,
}


class Staffer:
    def __init__(self, sid, name, role_value, salary=200000, years=2,
                 assignment="nhl"):
        self.id = sid
        self.full_name = name
        # Real StaffRole enum: hashable, so staff_market_ask / is_scout /
        # is_unique_role all run their production code paths.
        self.role = _ROLE_BY_LABEL.get(role_value, StaffRole.ASSISTANT_COACH)
        self.assignment = assignment
        self.gm_trust = 70
        self.salary = salary
        self.contract_years = years
        self.overall_rating = 65
        self.morale = 70
        self.age = 52
        self.nationality = "Canada"
        self.experience = 12
        self.reputation = 10
        self.adaptability = 60
        self.man_management = 60
        self.controversy = 20
        self.coaching_forwards = 70
        self.tactical_knowledge = 65

    def negotiate_contract(self, salary, years):
        return 1 <= years <= 5 and salary >= int(self.salary * 0.8)


class Team:
    def __init__(self, name):
        self.team_name = name
        self.roster = []
        self.ahl_roster = []
        self.prospects = []
        self.staff = []
        self.head_coach = None
        self.dressing_room = None
        self.line_control = "coach"
        self.staff_budget = 10_000_000
        self.prestige = 55

    def staff_budget_remaining(self):
        return self.staff_budget - sum(
            int(getattr(s, "salary", 0) or 0) for s in self.staff)


ut = Team("My Team")
rival = Team("Rival Club")
for i in range(14):
    p = Player(f"p{i}", f"Player {i:02d}", "C", 24, 78)
    ut.roster.append(p)
ut.roster[0].full_name = "Captain Clutch"
ut.roster[0].first_name, ut.roster[0].last_name = "Captain", "Clutch"
ut.roster[0].captaincy = "C"
g = Player("g0", "Goalie Guy", "G", 30, 82)
ut.roster.append(g)

coach = Staffer("st1", "Coach Carl", "Head Coach")
coach.assignment = "nhl"
ut.staff.append(coach)
ut.head_coach = coach
scout = Staffer("st2", "Scout Sue", "Amateur Scout", salary=90000)
scout.judging_player_ability = 75
scout.judging_player_potential = 70
ut.staff.append(scout)
# AHL front office: without it, ensure_dressing_room_fields() backfills one
# (production behavior) and staff counts drift mid-test.
ahl_coach = Staffer("st3", "Farm Boss", "Head Coach", salary=120000,
                    assignment="ahl")
ut.staff.append(ahl_coach)
ahl_gm = Staffer("st4", "Farm GM", "General Manager", salary=180000,
                 assignment="ahl")
ut.staff.append(ahl_gm)


class FakeGM:
    def __init__(self):
        self.user_team = ut
        self.league = league
        self.scout_region_assignments = {}

    def sign_free_agent_staff(self, staff, salary, years, assignment="nhl"):
        staff.salary = salary
        staff.contract_years = years
        if staff in league.free_agent_staff:
            league.free_agent_staff.remove(staff)
        ut.staff.append(staff)
        return True


league = SimpleNamespace(
    teams=[ut, rival], season_year=2026, rivalries=[],
    free_agent_staff=[Staffer("st9", "Free Agent Fred", "Assistant Coach",
                              salary=150000)],
    free_agents=[], draft_prospects=[],
    user_team=ut, current_date=date(2026, 10, 15),
)
mock_app = SimpleNamespace(
    game_manager=FakeGM(), user_team=ut, league=league,
    current_date=date(2026, 10, 15),
    scouting_assignments={},
)
bridge._web_app_ref = mock_app
from web_ui.bridge import create_app

app = create_app()
client = app.test_client()
q = bridge.COMMAND_QUEUE

failures = []

if __name__ == "__main__":


    def check(name, cond, detail=""):
        print(("PASS " if cond else "FAIL ") + name
              + (f" -- {detail}" if detail and not cond else ""))
        if not cond:
            failures.append(name)


    def drain():
        while not q.empty():
            bridge._execute_command(mock_app, q.get_nowait())


    # ---- crisis API ----
    r = client.get("/api/morale/crisis")
    d = r.get_json()
    check("GET /api/morale/crisis 200", r.status_code == 200)
    check("crisis null when calm", d.get("crisis") is None)
    check("receipts list", isinstance(d.get("receipts"), list))

    # Simulate an active crisis (as the weekly tick would record it)
    import dressing_room as _dr

    dr = _dr.ensure_dressing_room_fields(ut)
    dr["captaincy_crisis"] = True
    dr["captaincy_crisis_detail"] = {
        "captain_name": "Captain Clutch",
        "challenger_names": ["Player 01"],
        "severity": 2,
    }
    r = client.get("/api/morale/crisis")
    d = r.get_json()
    check("crisis banner state", d.get("crisis") is not None
          and d["crisis"]["captain_name"] == "Captain Clutch")
    check("successor candidates", len(d["crisis"]["successors"]) >= 1)

    # resolve validation
    r = client.post("/api/morale/crisis/resolve", json={"choice": "bogus"})
    check("bad crisis choice rejected", r.status_code == 400)
    r = client.post("/api/morale/crisis/resolve",
                    json={"choice": "reassign"})
    check("reassign without successor rejected", r.status_code == 400)
    # keep path (real resolve_captaincy_crisis)
    r = client.post("/api/morale/crisis/resolve", json={"choice": "keep"})
    check("crisis resolve queued", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("crisis result stashed", res is not None and res.get("kind") == "crisis"
          and res.get("ok") is True, str(res)[:120])
    check("crisis lines", len(res.get("lines") or []) >= 1)
    # authority receipt written
    recs = [x for x in dr.get("practice_receipts", [])
            if x.get("kind") == "authority"]
    check("authority receipt written", len(recs) >= 1)
    r = client.get("/api/morale/crisis")
    check("receipt surfaces in API",
          any("Captaincy crisis" in x.get("title", "")
              for x in r.get_json().get("receipts", [])))

    # ---- advise coach ----
    r = client.get("/api/morale/advice-types")
    d = r.get_json()
    check("advice types 7", len(d.get("types", [])) == 7, len(d.get("types", [])))
    r = client.post("/api/morale/action",
                    json={"action": "advise_coach",
                          "detail": {"advice": "ease_up"}})
    check("advise_coach accepted", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("advice result stashed", res is not None
          and res.get("kind") == "advise_coach" and res.get("ok") is True,
          str(res)[:150])
    check("advice has text", bool(res.get("text")))
    r = client.get("/api/morale/advice-result")
    check("advice-result poll", r.get_json().get("result", {}).get("kind")
          == "advise_coach")

    # feature player path
    r = client.post("/api/morale/action",
                    json={"action": "advise_coach",
                          "detail": {"advice": "feature_player",
                                     "player_id": "p1"}})
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("feature player advice", res is not None and res.get("ok") is True)

    # ---- rivalries ----
    r = client.get("/api/morale/rivalries")
    d = r.get_json()
    check("GET /api/morale/rivalries 200", r.status_code == 200)
    check("rival team picker", "Rival Club" in d.get("teams", []))
    r = client.post("/api/morale/rivalries/declare",
                    json={"kind": "team", "target": "Rival Club"})
    check("declare queued", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("rivalry declared", res is not None and res.get("ok") is True,
          str(res)[:150])
    check("league has rivalry", len(league.rivalries) >= 1)
    r = client.get("/api/morale/rivalries")
    d = r.get_json()
    check("declared rival listed", any(
        x.get("label") == "Rival Club" for x in d.get("declared", [])))
    r = client.post("/api/morale/rivalries/renounce",
                    json={"kind": "team", "target": "Rival Club"})
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("rivalry renounced", res is not None and res.get("ok") is True,
          str(res)[:150])

    # ---- coach carousel ----
    r = client.get("/api/morale/coach/candidates")
    d = r.get_json()
    check("coach candidates 200", r.status_code == 200)
    check("current coach", (d.get("current") or {}).get("name") == "Coach Carl")
    r = client.post("/api/morale/coach/fire", json={"reason": "fired"})
    check("fire queued", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("coach fired", res is not None and res.get("ok") is True,
          str(res)[:150])
    check("coach off staff", not any(
        getattr(s, "id", "") == "st1" for s in ut.staff))
    check("carousel remembers", len(_dr.COACH_CAROUSEL) >= 1)
    # hire back from carousel
    r = client.get("/api/morale/coach/candidates")
    cands = r.get_json().get("candidates", [])
    check("carousel candidates", len(cands) >= 1)
    r = client.post("/api/morale/coach/hire", json={"candidate_idx": 0})
    drain()
    res = getattr(mock_app, "_web_morale_result", None)
    check("coach hired", res is not None and res.get("ok") is True,
          str(res)[:150])
    check("coach back on staff", any(
        getattr(s, "id", "") == "st1" for s in ut.staff))

    # ---- scouting: cancel ----
    mock_app.scouting_assignments = {ut.roster[3]: scout}
    r = client.post("/api/scouting/assignment/cancel",
                    json={"player_id": "p3"})
    check("cancel queued", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_scout_result", None)
    check("assignment cancelled", res is not None and res.get("ok") is True,
          str(res)[:150])
    check("assignment gone", len(mock_app.scouting_assignments) == 0)
    r = client.post("/api/scouting/assignment/cancel",
                    json={"player_id": "nope"})
    check("cancel unknown -> 404", r.status_code == 404)

    # ---- scouting staff list ----
    r = client.get("/api/scouting/staff")
    d = r.get_json()
    check("scout staff 200", r.status_code == 200)
    check("scout listed", any(s.get("name") == "Scout Sue"
                              for s in d.get("scouts", [])))
    check("overview numbers", (d.get("overview") or {}).get("staff_count") == 1)

    # ---- player database ----
    r = client.get("/api/scouting/database?position=forwards&ovr_min=70&limit=50")
    d = r.get_json()
    check("database 200", r.status_code == 200)
    check("database total", d.get("total", 0) >= 14, d.get("total"))
    check("database filters", all(p.get("overall", 0) >= 70
                                  for p in d.get("players", [])))
    check("database teams", "My Team" in d.get("teams", []))
    r = client.get("/api/scouting/database?position=goalies")
    d = r.get_json()
    check("goalie filter", d.get("total") == 1, d.get("total"))
    r = client.get("/api/scouting/database?q=clutch")
    d = r.get_json()
    check("name search", d.get("total") == 1)

    # ---- staff detail tabs ----
    r = client.get("/api/staff/st2")
    d = r.get_json()
    check("staff detail 200", r.status_code == 200)
    check("tabs present", isinstance(d.get("tabs"), dict))
    check("attributes tab", len(d["tabs"].get("attributes", [])) >= 1)
    check("standing tab", len(d["tabs"].get("standing", [])) >= 1)
    check("personality tab", "style" in d["tabs"].get("personality", {}))

    # ---- extension negotiation ----
    r = client.get("/api/staff/st2/negotiate-preview")
    d = r.get_json()
    check("negotiate preview 200", r.status_code == 200)
    check("ask window", d.get("ask_min", 0) > 0 and d.get("ask_max", 0)
          >= d.get("ask_min", 0))
    r = client.get("/api/staff/st2/negotiate-preview?offer=95000")
    check("chance estimate", r.get_json().get("chance") is not None)
    r = client.post("/api/staff/st2/negotiate",
                    json={"salary": 95000, "years": 2})
    check("negotiate queued", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_staff_result", None)
    check("negotiation resolved", res is not None
          and res.get("kind") == "staff_negotiate" and res.get("ok") is True,
          str(res)[:150])
    check("terms applied on accept",
          scout.salary == 95000 and scout.contract_years == 2)
    r = client.post("/api/staff/st2/negotiate",
                    json={"salary": 100, "years": 9})
    check("bad offer rejected", r.status_code == 400)

    # ---- org chart + report ----
    r = client.get("/api/staff/org-chart")
    d = r.get_json()
    check("org chart 200", r.status_code == 200)
    check("org levels", len(d.get("tree", [])) >= 2)
    r = client.get("/api/staff/report")
    d = r.get_json()
    check("staff report 200", r.status_code == 200)
    check("report summary", (d.get("summary") or {}).get("total_staff") == 4)
    check("report departments", len(d.get("departments", [])) >= 1)

    # ---- hiring negotiation chain ----
    r = client.get("/api/free_agents/staff/st9/offer-preview?salary=160000")
    d = r.get_json()
    check("hire preview 200", r.status_code == 200)
    check("hire preview chance", d.get("chance") is not None)
    check("hire preview ask", d.get("market_ask", 0) > 0)
    r = client.post("/api/free_agents/staff/hire",
                    json={"staff_id": "st9", "salary": 160000, "years": 3,
                          "assignment": "nhl"})
    check("hire queued", r.get_json().get("ok") is True)
    drain()
    res = getattr(mock_app, "_web_staff_result", None)
    check("hire resolved", res is not None and res.get("kind") == "hire_staff"
          and res.get("ok") is True, str(res)[:150])
    fred = next((s for s in ut.staff if getattr(s, "id", "") == "st9"), None)
    if res.get("accepted"):
        check("hire accepted -> on staff", fred is not None)
        check("hire terms", fred is not None and fred.salary == 160000)
    else:
        check("hire declined -> stays in pool", fred is None
              and any(getattr(s, "id", "") == "st9"
                      for s in league.free_agent_staff))
    r = client.get("/api/staff/hire-result")
    check("hire-result poll", r.get_json().get("result", {}).get("kind")
          == "hire_staff")

    # ---- development analytics ----
    r = client.get("/api/development/analytics")
    d = r.get_json()
    check("dev analytics 200", r.status_code == 200)
    check("overview", (d.get("overview") or {}).get("total_players") == 15)
    check("positions", len(d.get("positions", [])) >= 1)
    check("age bands", len(d.get("age_bands", [])) == 4)
    pls = d.get("players", [])
    check("per-player cards", len(pls) == 15)
    p0 = pls[0]
    check("key attributes 6", len(p0.get("key_attributes", [])) == 6)
    check("grades", all(a.get("grade") for a in p0["key_attributes"]))
    check("recommendations shape",
          all("area" in x and "priority" in x
              for pl in pls for x in pl.get("recommendations", [])))
    print("  sample recs:", pls[0].get("recommendations"))

    print()
    if failures:
        print(f"{len(failures)} FAILURES: {failures}")
        sys.exit(1)
    print("ALL BATCH B CHECKS PASSED")

