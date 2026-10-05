"""Mock-based smoke test for the scouting + draft web screens."""
import sys
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/hockey-manager")

import web_ui.bridge as bridge

# ---- mocks -----------------------------------------------------------------
class MockPlayer:
    def __init__(self, pid, name, pos="C", age=18, overall=72):
        self.id = pid
        self.full_name = name
        self.position = pos
        self.age = age
        self.overall = overall
        self.salary = 900000
        self.captaincy = ""
        self.injured = False

class MockScout:
    def __init__(self, sid, name, role="Amateur Scout"):
        self.id = sid
        self.full_name = name
        # Real StaffRole enum so scouting.is_scout() validation passes.
        try:
            from game_classes import StaffRole as _SR
            self.role = _SR[role.upper().replace(" ", "_").replace("/", "_")]
        except Exception:
            self.role = SimpleNamespace(value=role)
        self.judging_player_ability = 16
        self.judging_player_potential = 15
        self.experience = 10

class MockReport:
    def __init__(self, player, scout):
        self.player = player
        self.scout = scout
        self.accuracy = "B"
        self.viewings = 17
        self.reliability = 0.8
        self.region_coverage = "Western Canada"
        self.competition_level = "Junior A"
        self.scouted_potential = "Top-6 forward"
        self.projected_draft_position = 12
        self.ceiling_rating = 16
        self.floor_rating = 11
        self.notes = "Good motor."

class MockSession:
    year = 2026
    current_pick = 2
    completed = False
    slots = [
        {"overall": 1, "round": 1, "owner": "Rivals", "pick_id": None},
        {"overall": 2, "round": 1, "owner": "My Team", "pick_id": None},
        {"overall": 3, "round": 1, "owner": "Rivals", "pick_id": None},
        {"overall": 4, "round": 2, "owner": "My Team", "pick_id": None},
    ]
    picks = [{"overall": 1, "team": "Rivals", "player_id": 101}]
    def is_complete(self):
        return False

prospects = [MockPlayer(101, "Drafted Kid"), MockPlayer(102, "Free Agent Jr.")]
player_a = MockPlayer(200, "Scouted Kid", "LW")
scout_a = MockScout("s1", "Scout Sam")
mock_app = SimpleNamespace(
    scouting_assignments={player_a: scout_a},
    user_team=SimpleNamespace(
        team_name="My Team",
        scouting_reports={200: MockReport(player_a, scout_a)},
        staff=[scout_a, MockScout("s2", "Pro Phil", "Professional Scout")],
    ),
    league=SimpleNamespace(
        draft_prospects=prospects,
        teams=[],
        entry_draft_session=MockSession(),
    ),
)

bridge._web_app_ref = mock_app
from web_ui.bridge import create_app
flask_app = create_app()
client = flask_app.test_client()

checks = [
    ("/scouting", 200), ("/api/scouting", 200),
    ("/draft", 200), ("/api/draft", 200),
]
for route, want in checks:
    r = client.get(route)
    assert r.status_code == want, f"{route}: got {r.status_code}"
    print(f"GET {route} -> {r.status_code} OK")

data = client.get("/api/scouting").get_json()
assert data["assignment_count"] == 1, data
assert len(data["reports"]) == 1, data
assert data["reports"][0]["accuracy"] == "B"
assert len(data["scouts"]) == 2, data
assert len(data["prospects"]) == 2, data
print("scouting API payload OK:", data["assignment_count"], "assignment,",
      len(data["reports"]), "report,", len(data["scouts"]), "scouts,",
      len(data["prospects"]), "prospects")

dd = client.get("/api/draft").get_json()
assert dd["active"] is True, dd
assert dd["year"] == 2026
assert dd["current_overall"] == 3
assert len(dd["board"]) == 4
made = [b for b in dd["board"] if b["made"]]
assert len(made) == 1 and made[0]["prospect"]["name"] == "Drafted Kid", dd
mine = [b for b in dd["board"] if b["is_user_pick"]]
assert len(mine) == 2 and all(m["owner"] == "My Team" for m in mine), dd
assert dd["user_picks"] == [2, 4], dd
cur = [b for b in dd["board"] if b["is_current"]]
assert len(cur) == 1 and cur[0]["overall"] == 3, dd
print("draft API payload OK:", dd["made_count"], "made of", dd["total_slots"],
      "| user picks:", dd["user_picks"])

# POST new assignment -> command queued
r = client.post("/api/scouting/assignment", json={"prospect_id": "102", "scout_id": "s1"})
assert r.status_code == 200, r.status_code
j = r.get_json()
assert j["ok"] is True, j
cmd = bridge.COMMAND_QUEUE.get_nowait()
assert cmd["op"] == "add_scouting_assignment" and cmd["prospect_id"] == "102", cmd
print("POST /api/scouting/assignment -> 200, queued:", cmd["op"])

# empty draft state: session None -> {"active": False}, still 200
mock_app.league.entry_draft_session = None
dd2 = client.get("/api/draft").get_json()
assert dd2 == {"active": False}, dd2
print("draft empty state OK (session None)")

# weird-data robustness: junk in assignments
mock_app.scouting_assignments = {None: None, "junk": 123}
r = client.get("/api/scouting")
assert r.status_code == 200
print("scouting API survives junk assignments -> 200")

print("ALL SCOUTING+DRAFT TESTS PASSED")
