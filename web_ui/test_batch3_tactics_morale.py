"""Smoke test for deep tactics + morale pages (batch3).

Exercises the new APIs on mock teams: 7-module payload, identity presets,
intel cards, coach payload, social groups, cascades, and the team-talk
preview/deliver flow. Also exercises the new bridge command ops directly.

Mocks follow the web_ui/test_batch_c.py pattern (lightweight classes).
"""
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, "/tmp/wt3")

# dressing_room.py defines DressingRoomView(__import__("customtkinter").CTkFrame)
# at module level; stub customtkinter so the module imports in headless test.
import types as _types
_ctk_stub = _types.ModuleType("customtkinter")


class _DummyFrame:
    def __init__(self, *a, **k):
        pass


_ctk_stub.CTkFrame = _DummyFrame
sys.modules["customtkinter"] = _ctk_stub

import web_ui.bridge as bridge


class Player:
    def __init__(self, pid, name, pos, age, ovr, nat="Canada"):
        self.id = pid
        self.full_name = name
        self.first_name, self.last_name = name.split(" ", 1)
        self.primary_position = pos
        self.age = age
        self._ovr = ovr
        self.nationality = nat
        self.hometown = "Toronto, Canada"
        self.morale = 65  # 1-100 scale for dressing_room
        self.happiness = 70
        self.captaincy = ""
        self.team_tenure = "3 years"
        self.draft_year = 2020
        self.draft_overall = 45
        self.is_injured = False
        self.stats = SimpleNamespace(games_played=120)
        # tendencies for player_system_fit
        self.skating = 70
        self.aggressiveness = 60
        self.stamina = 70
        self.checking = 60
        self.work_rate = 65
        self.anticipation = 65
        self.positioning = 65
        self.decisions = 65
        self.discipline = 60
        self.passing = 65
        self.puckhandling = 65
        self.shoot_pass_tendency = 50
        self.hitting_tendency = 50
        self.flair = 50

    def overall_rating(self):
        return self._ovr


class Team:
    def __init__(self, name):
        self.team_name = name
        self.roster = []
        self.staff = []
        self.dressing_room = None
        self.tactics = None
        self.tactics_familiarity = 85
        self.tactics_control = "coach"
        self.line_control = "coach"


class Staffer:
    def __init__(self, sid, name, role_value):
        self.id = sid
        self.full_name = name
        self.role = SimpleNamespace(value=role_value)
        self.gm_trust = 70
        self.influence = 72
        self.adaptability = 60
        self.tactics_prefs = None


ut = Team("My Team")
rival = Team("Rival Club")

nats = ["Canada", "Sweden", "USA", "Finland", "Canada", "Sweden"]
positions = ["C", "LW", "RW", "LD", "RD"]
for i in range(18):
    p = Player(f"p{i}", f"Player {i:02d}", positions[i % 5],
               22 + (i % 14), 70 + (i % 20), nats[i % len(nats)])
    p.morale = 55 + (i * 2) % 35
    ut.roster.append(p)
for i in range(2):
    g = Player(f"g{i}", f"Goalie {i}", "G", 28, 82)
    ut.roster.append(g)
ut.roster[0].full_name = "Captain Clutch"
ut.roster[0].first_name, ut.roster[0].last_name = "Captain", "Clutch"
ut.roster[0].captaincy = "C"

coach = Staffer("st1", "Coach Carl", "Head Coach")
ut.staff.append(coach)

# Rival with tactical intel on us (for opponent intel cards)
rival.tactical_intel = {"My Team": [
    {"systems": {"forecheck": "forecheck_122", "neutral_zone": "nz_trap_131",
                 "dzone": "dz_box", "ozone": "oz_cycle",
                 "breakout": "bo_controlled", "pp": "umbrella",
                 "pk": "passive_box"},
     "g": 4, "ga": 1, "sog": 32, "pp_pct": 0.33},
    {"systems": {"forecheck": "forecheck_122", "neutral_zone": "nz_trap_131",
                 "dzone": "dz_box", "ozone": "oz_cycle",
                 "breakout": "bo_controlled", "pp": "umbrella",
                 "pk": "passive_box"},
     "g": 5, "ga": 2, "sog": 35, "pp_pct": 0.40},
]}

league = SimpleNamespace(teams=[ut, rival], season_year=2026,
                         user_team=ut, current_date=date(2026, 10, 15),
                         rivalries=[])
mock_app = SimpleNamespace(
    game_manager=SimpleNamespace(user_team=ut, league=league),
    user_team=ut, league=league,
    current_date=date(2026, 10, 15),
)
bridge._web_app_ref = mock_app
from web_ui.bridge import create_app

app = create_app()
client = app.test_client()

failures = []


def check(name, cond, detail=""):
    print(("PASS " if cond else "FAIL ") + name + (f" — {detail}" if detail and not cond else ""))
    if not cond:
        failures.append(name)


# ---- tactics API ----
r = client.get("/api/tactics")
check("GET /api/tactics 200", r.status_code == 200, r.status_code)
d = r.get_json()
check("7 modules", len(d.get("modules", [])) == 7, len(d.get("modules", [])))
nz = [m for m in d["modules"] if m["key"] == "neutral_zone"][0]
check("neutral_zone picker has 3 systems", len(nz["systems"]) == 3)
dz = [m for m in d["modules"] if m["key"] == "dzone"][0]
check("dzone picker has 3 systems", len(dz["systems"]) == 3)
bo = [m for m in d["modules"] if m["key"] == "breakout"][0]
check("breakout picker has 3 systems", len(bo["systems"]) == 3)
check("module has blurb+tradeoffs", bool(nz["blurb"]) and bool(nz["tradeoffs"]))
check("3 identity presets", len(d["identity"]["presets"]) == 3)
check("familiarity present", d.get("familiarity") is not None)
check("control present", d.get("control") in ("coach", "gm"))
check("coach payload 7 rows", d.get("coach") is not None and len(d["coach"]["rows"]) == 7)
check("engine multipliers", isinstance(d.get("engine"), dict) and "attack" in d["engine"],
      str(d.get("engine"))[:100])
check("intel is list", isinstance(d.get("intel"), list))
check("legacy groups kept", len(d.get("groups", [])) == 6)
print("  intel cards:", [(c["kind"], c["title"][:55]) for c in d["intel"]])
print("  identity_lines:", d.get("identity_lines", [])[:2])

# ---- tactics writes (via bridge command execution, as the Tk thread would) ----
q = bridge.COMMAND_QUEUE
while not q.empty():
    q.get_nowait()

r = client.post("/api/tactics/system", json={"category": "neutral_zone", "system": "nz_trap_131"})
check("POST /api/tactics/system ok", r.get_json().get("ok") is True)
bridge._execute_command(mock_app, q.get_nowait())
import tactics as _tx
check("neutral_zone installed", _tx.team_tactics(ut)["neutral_zone"] == "nz_trap_131")
check("familiarity dipped on change", float(getattr(ut, "tactics_familiarity", 100)) < 100,
      str(getattr(ut, "tactics_familiarity", None)))

r = client.post("/api/tactics/system", json={"category": "nope", "system": "x"})
check("bad category rejected", r.status_code == 400)

r = client.post("/api/tactics/preset", json={"preset": "chaos_pressure"})
check("POST /api/tactics/preset ok", r.get_json().get("ok") is True)
bridge._execute_command(mock_app, q.get_nowait())
check("preset applied", _tx.matching_identity(ut) == "chaos_pressure")

r = client.post("/api/tactics/control", json={"who": "gm"})
check("POST /api/tactics/control ok", r.get_json().get("ok") is True)
bridge._execute_command(mock_app, q.get_nowait())
check("control=gm", _tx.get_tactics_control(ut) == "gm")

r = client.post("/api/tactics/coach", json={"mode": "takeover"})
check("POST /api/tactics/coach takeover ok", r.get_json().get("ok") is True)
bridge._execute_command(mock_app, q.get_nowait())
check("takeover hands whiteboard to coach", _tx.get_tactics_control(ut) == "coach")

r = client.post("/api/tactics/coach", json={"mode": "enforce"})
bridge._execute_command(mock_app, q.get_nowait())
check("enforce takes whiteboard", _tx.get_tactics_control(ut) == "gm")

r = client.post("/api/tactics/coach", json={"mode": "bogus"})
check("bad coach mode rejected", r.status_code == 400)

# ---- morale API ----
r = client.get("/api/morale")
check("GET /api/morale 200", r.status_code == 200, r.status_code)
m = r.get_json()
check("social payload", "social" in m and isinstance(m["social"]["cliques"], list))
nc = len(m["social"]["cliques"])
print(f"  cliques: {nc}, floaters: {len(m['social']['floaters'])}")
check("cliques formed", nc > 0)
if nc:
    c0 = m["social"]["cliques"][0]
    check("clique has name/members/bond", bool(c0["name"]) and len(c0["members"]) >= 3
          and c0["bond"] > 0, str(c0)[:120])
    print(f"  e.g. {c0['name']} ({c0['kind']}): {', '.join(x['name'] for x in c0['members'][:4])}…")
check("atmosphere label", m["social"]["atmosphere"] is not None and
      "label" in m["social"]["atmosphere"],
      str(m["social"]["atmosphere"]))
check("cascades payload", "cascades" in m and isinstance(m["cascades"]["log"], list))
check("talk payload 3 tones", "talk" in m and len(m["talk"]["tones"]) == 3)
print("  tones:", [t["key"] for t in m["talk"]["tones"]])

# ---- team talk preview ----
r = client.post("/api/morale/talk/preview", json={
    "tone": "fired-up", "situation": "pregame", "score_state": "trailing",
    "speaker": "coach", "rival": True, "streak": 0})
p = r.get_json()
check("talk preview ok", p.get("ok") is True)
check("fired-up/trailing fit high", p.get("fit", 0) >= 80, str(p.get("fit")))
print(f"  preview: fit={p.get('fit')} likely={p.get('likely')} speaker={p.get('speaker_name')}")

r = client.post("/api/morale/talk/preview", json={
    "tone": "fired-up", "situation": "pregame", "score_state": "leading",
    "speaker": "coach"})
p2 = r.get_json()
check("fired-up/leading fit penalized", p2.get("fit", 100) <= 30, str(p2.get("fit")))

r = client.post("/api/morale/talk/preview", json={"tone": "bogus"})
check("bad tone rejected", r.status_code == 400)

# ---- team talk deliver ----
while not q.empty():
    q.get_nowait()
r = client.post("/api/morale/talk", json={
    "tone": "calm", "situation": "pregame", "score_state": "tied",
    "speaker": "captain", "rival": False, "streak": -3})
check("POST /api/morale/talk ok", r.get_json().get("ok") is True)
bridge._execute_command(mock_app, q.get_nowait())
import dressing_room as _dr
dr = _dr.ensure_dressing_room_fields(ut)
check("talk recorded", isinstance(dr.get("pregame"), dict) and
      dr["pregame"]["tone"] == "calm" and dr["pregame"]["speaker"] == "captain",
      str(dr.get("pregame"))[:150])

# repeat preview should now warn
r = client.post("/api/morale/talk/preview", json={
    "tone": "calm", "situation": "pregame", "score_state": "tied",
    "speaker": "coach"})
p3 = r.get_json()
check("repeat cooldown flagged", p3.get("repeat") is True)

print()
if failures:
    print(f"{len(failures)} FAILURES: {failures}")
    sys.exit(1)
print("ALL PASS")
