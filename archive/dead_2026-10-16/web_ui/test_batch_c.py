"""Smoke test for Batch C: offer sheets, buyouts, waivers, staff moves,
jersey numbers. Mock-based (like web_ui/test_scouting_draft.py).

Run: python3 web_ui/test_batch_c.py
"""
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/hockey-manager")

# windows.py needs customtkinter (only on the game machine); the buyout
# path imports buyout_schedule from it, so stub the real math here.
import types as _types

_windows_stub = _types.ModuleType("windows")


def _stub_buyout_schedule(player):
    salary = player.contract.salary
    years = player.contract.years_remaining
    if years <= 0 or salary <= 0:
        return 0, 0, 0, []
    fraction = 1 / 3 if player.age < 26 else 2 / 3
    total_cost = salary * years * fraction
    buyout_years = 2 * years
    annual = total_cost / buyout_years
    rows = []
    for i in range(1, buyout_years + 1):
        savings = salary - annual if i <= years else -annual
        rows.append((i, annual, savings))
    return total_cost, annual, buyout_years, rows


_windows_stub.buyout_schedule = _stub_buyout_schedule
sys.modules["windows"] = _windows_stub

import web_ui.bridge as bridge
from game_classes import PlayerPosition, StaffRole, Staff

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok: {name}")


class Contract:
    def __init__(self, salary, years_remaining, nmc=False, ntc=False):
        self.salary = salary
        self.years_remaining = years_remaining
        self.no_movement_clause = nmc
        self.no_trade_clause = ntc
        self.term = years_remaining
        self.entry_level = False


class Player:
    def __init__(self, pid, name, pos, age, ovr, contract, team_name="",
                 jersey=0, games=0, sign_age=20, pro_seasons=2):
        self.id = pid
        self.full_name = name
        self.first_name, self.last_name = name.split(" ", 1)
        self.primary_position = pos
        self.age = age
        self._ovr = ovr
        self.contract = contract
        self.salary = contract.salary
        self.team_name = team_name
        self.jersey_number = jersey
        self.on_waivers = False
        self.waiver_days = 0
        self.arbitration_filed = False
        self.offer_sheet_pending = False
        self.nhl_games_played = games
        self.first_contract_age = sign_age
        self.pro_seasons_accrued = pro_seasons
        self.career_games = games
        self.is_injured = False
        self.morale = 7
        self.captaincy = ""
        self.value = ovr * 100000

    def overall_rating(self):
        return self._ovr


class Team:
    def __init__(self, name):
        self.team_name = name
        self.league_name = "National Hockey League"
        self.roster = []
        self.ahl_roster = []
        self.staff = []
        self.draft_picks = {}
        self.buyout_cap_hits = {}
        self.salary_cap = 104_000_000
        self.retired_numbers = []


class Pick:
    def __init__(self, year, rnd, team_name):
        self.round = rnd
        self.original_team = team_name
        self.current_team = team_name
        self.year = year


class Staffer:
    def __init__(self, sid, name, role, salary=500000, years=3):
        self.id = sid
        self.full_name = name
        self.first_name, self.last_name = name.split(" ", 1)
        self.role = role
        self.salary = salary
        self.contract_years = years
        self.morale = 70
        self.gm_trust = 70
        self.age = 50
        self.experience = 10
        self.nationality = "Canada"
        self.years_with_team = 3


ut = Team("My Team")
rival = Team("Rival Club")

# rival unsigned RFA: expired contract, age 23 -> RFA, not UFA-eligible
rfa = Player("rfa1", "Rookie Star", PlayerPosition.CENTER, 23, 80,
             Contract(3_000_000, 0), team_name="Rival Club", games=150,
             sign_age=20, pro_seasons=4)
rival.roster.append(rfa)

# my roster players
vet = Player("vet1", "Veteran Joe", PlayerPosition.RIGHT_WING, 30, 78,
             Contract(6_000_000, 3), team_name="My Team", jersey=9,
             games=400, sign_age=20, pro_seasons=8)
nmc_guy = Player("nmc1", "Loyal Dave", PlayerPosition.LEFT_DEFENSE, 32, 75,
                 Contract(5_000_000, 2), team_name="My Team", jersey=44,
                 games=500, sign_age=20, pro_seasons=9)
nmc_guy.contract.no_movement_clause = True
kid = Player("kid1", "Young Kid", PlayerPosition.GOALIE, 21, 70,
             Contract(900_000, 2), team_name="My Team", jersey=35,
             games=10, sign_age=20, pro_seasons=1)
ut.roster.extend([vet, nmc_guy, kid])
ut.ahl_roster.append(Player("ahl1", "AHL Guy", PlayerPosition.CENTER, 25, 68,
                            Contract(800_000, 1), team_name="My Team", jersey=17))

# my own draft picks for compensation: 2027 1st + 2nd + 3rd
for rnd in (1, 2, 3):
    ut.draft_picks.setdefault(2027, []).append(Pick(2027, rnd, "My Team"))

# staff
coach = Staffer("st1", "Coach Carl", StaffRole.HEAD_COACH)
asst = Staffer("st2", "Assistant Amy", StaffRole.ASSISTANT_COACH)
ut.staff.extend([coach, asst])

league = SimpleNamespace(teams=[ut, rival], season_year=2026,
                         user_team=ut, current_date=date(2026, 10, 15),
                         rivalries=[])
news_log = []
mock_app = SimpleNamespace(
    game_manager=SimpleNamespace(user_team=ut, league=league),
    user_team=ut, league=league,
    current_date=date(2026, 10, 15),
    add_news=lambda s: news_log.append(s),
    waiver_list=[],
    _rng=random.Random(42),
)
bridge._web_app_ref = mock_app
from web_ui.bridge import create_app

client = create_app().test_client()

print("== offer sheets ==")
r = client.get("/offer_sheets")
check("GET /offer_sheets 200", r.status_code == 200, r.status_code)

r = client.get("/api/offer_sheets/targets")
d = r.get_json()
check("targets 200", r.status_code == 200, r.status_code)
check("rfa1 in targets", any(t["id"] == "rfa1" for t in d["targets"]),
      [t["id"] for t in d["targets"]])
check("window open in Oct", d["window"]["ok"] is True, d["window"])

r = client.get("/api/offer_sheets/preview",
               query_string={"player_id": "rfa1", "aav": 8_000_000, "years": 4})
d = r.get_json()
check("preview 200/ok", r.status_code == 200 and d["ok"], d)
check("compensation label", bool(d["compensation"]["label"]), d["compensation"])
check("comp picks furnished", all(l["ok"] for l in d["compensation"]["lines"]),
      d["compensation"])
check("checks ok", all(c["ok"] for c in d["checks"]), d["checks"])
check("preview valid", d["valid"] is True)

r = client.post("/api/offer_sheets/present",
                json={"player_id": "rfa1", "aav": 8_000_000, "years": 4})
d = r.get_json()
check("present queued 200", r.status_code == 200 and d["ok"], d)
cmd = bridge.COMMAND_QUEUE.get_nowait()
check("command op", cmd["op"] == "present_offer_sheet", cmd)
bridge._execute_command(mock_app, cmd)
res = getattr(mock_app, "_web_offer_sheet_result", None)
check("result stashed", res is not None and res["marker"] == "present_offer_sheet", res)
check("news posted", len(news_log) > 0, news_log)
r = client.get("/api/offer_sheets/result")
check("result poll 200", r.status_code == 200 and r.get_json()["result"] is not None,
      r.get_json())
print("   outcome:", res["ok"], "-", res["summary"][:80])

print("== buyouts ==")
r = client.get("/api/finances/buyouts")
d = r.get_json()
check("buyouts 200", r.status_code == 200, d)
check("vet1 candidate", any(c["id"] == "vet1" for c in d["candidates"]),
      [c["id"] for c in d["candidates"]])
c = next(x for x in d["candidates"] if x["id"] == "vet1")
check("buyout math (2/3 x 3y)", c["buyout_cost"] == 12_000_000 and
      c["annual_dead"] == 2_000_000 and c["dead_years"] == 6, c)
check("schedule rows", len(c["schedule"]) == 6 and
      c["schedule"][0]["savings"] == 4_000_000 and
      c["schedule"][5]["savings"] == -2_000_000, c["schedule"])

# window closed in Oct -> 422
r = client.post("/api/finances/buyouts/execute", json={"player_id": "vet1"})
check("buyout rejected outside window (422)", r.status_code == 422,
      (r.status_code, r.get_json()))
# jump into the window
mock_app.current_date = date(2027, 6, 20)
r = client.post("/api/finances/buyouts/execute", json={"player_id": "vet1"})
d = r.get_json()
check("buyout queued 200", r.status_code == 200 and d["ok"], (r.status_code, d))
cmd = bridge.COMMAND_QUEUE.get_nowait()
bridge._execute_command(mock_app, cmd)
check("vet1 off roster", all(p.id != "vet1" for p in ut.roster))
check("vet1 free agent", vet.team_name == "Free Agent", vet.team_name)
check("dead cap keyed by year", ut.buyout_cap_hits.get(2026) == 2_000_000,
      ut.buyout_cap_hits)
mock_app.current_date = date(2026, 10, 15)

print("== waivers ==")
r = client.get("/api/waivers/eligible")
d = r.get_json()
check("eligible 200", r.status_code == 200, d)
check("kid1 in eligible", any(p["id"] == "kid1" for p in d["players"]), d)
check("vet1 not eligible (gone)", not any(p["id"] == "vet1" for p in d["players"]))

r = client.post("/api/waivers/place", json={"player_id": "nmc1"})
check("NMC blocked (422)", r.status_code == 422, (r.status_code, r.get_json()))

r = client.post("/api/waivers/place", json={"player_id": "kid1"})
d = r.get_json()
check("waive queued 200", r.status_code == 200 and d["ok"], (r.status_code, d))
cmd = bridge.COMMAND_QUEUE.get_nowait()
bridge._execute_command(mock_app, cmd)
check("kid1 on wire", kid.on_waivers and kid.waiver_days == 2 and
      kid in mock_app.waiver_list, (kid.on_waivers, kid.waiver_days))

print("== staff ==")
r = client.post("/api/staff/reassign", json={"staff_id": "st2", "role": "GOALIE_COACH"})
check("reassign 200", r.status_code == 200 and r.get_json()["ok"], r.get_json())
cmd = bridge.COMMAND_QUEUE.get_nowait()
bridge._execute_command(mock_app, cmd)
check("role changed", asst.role == StaffRole.GOALIE_COACH, asst.role)

r = client.post("/api/staff/reassign",
                json={"staff_id": "st2", "role": "HEAD_COACH"})
check("unique-role conflict 422", r.status_code == 422, (r.status_code, r.get_json()))

r = client.post("/api/staff/release", json={"staff_id": "st2"})
check("release queued 200", r.status_code == 200 and r.get_json()["ok"], r.get_json())
cmd = bridge.COMMAND_QUEUE.get_nowait()
bridge._execute_command(mock_app, cmd)
check("asst released", all(s.id != "st2" for s in ut.staff), [s.id for s in ut.staff])
sev = getattr(ut, "staff_severance", [])
check("severance booked (desktop mechanic)", len(sev) == 1 and sev[0]["amount"] > 0, sev)
check("trust dent on remaining staff", coach.gm_trust < 70, coach.gm_trust)

print("== jersey numbers ==")
r = client.get("/api/jersey_numbers")
d = r.get_json()
check("jersey list 200", r.status_code == 200, d)
check("kid1 listed", any(p["id"] == "kid1" for p in d["players"]), d)

r = client.post("/api/jersey_numbers/set", json={"player_id": "nmc1", "number": 99})
check("99 retired league-wide 422", r.status_code == 422, r.get_json())
r = client.post("/api/jersey_numbers/set", json={"player_id": "nmc1", "number": 1})
check("goalie number 1 blocked for skater 422", r.status_code == 422, r.get_json())
r = client.post("/api/jersey_numbers/set", json={"player_id": "nmc1", "number": 35})
check("duplicate (kid1's 35) 422", r.status_code == 422, r.get_json())
r = client.post("/api/jersey_numbers/set", json={"player_id": "nmc1", "number": 50})
check("valid change 200", r.status_code == 200 and r.get_json()["ok"], r.get_json())
cmd = bridge.COMMAND_QUEUE.get_nowait()
check("jersey command op", cmd["op"] == "set_jersey_number", cmd)
bridge._execute_command(mock_app, cmd)
check("nmc1 now #50", nmc_guy.jersey_number == 50, nmc_guy.jersey_number)

# goalie CAN take number 1
r = client.post("/api/jersey_numbers/set", json={"player_id": "kid1", "number": 1})
check("goalie may wear 1 (200)", r.status_code == 200 and r.get_json()["ok"], r.get_json())

# player profile header jersey
r = client.get("/api/player/nmc1")
d = r.get_json()
check("profile 200", r.status_code == 200, d)
check("jersey on profile", d["header"]["jersey"] == 50, d["header"])
check("jersey editable", d["header"]["jersey_editable"] is True, d["header"])

r = client.get("/offer_sheets")  # page route regression
check("offer page 200", r.status_code == 200)

print(f"\nALL {len(PASS)} CHECKS PASSED")
