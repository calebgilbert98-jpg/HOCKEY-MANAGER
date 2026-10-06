"""Test batch2 watch modes + stats tabs (mock mode, no live game)."""
import sys
sys.path.insert(0, "/tmp/wt2")  # worktree root
from types import SimpleNamespace

from web_ui import bridge
from web_ui.screens import watch as watch_mod
from web_ui.screens import stats as stats_mod

app = bridge.create_app(None)
client = app.test_client()

PASS = []
def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok: {name}")

# --- routes exist ---
for route in ["/watch", "/stats", "/api/stats", "/api/stats/ahl",
              "/api/stats/records", "/api/stats/analytics",
              "/api/watch/events", "/api/watch/boxscore", "/api/watch/status"]:
    r = client.get(route)
    check(f"GET {route}", r.status_code == 200, f"got {r.status_code}")

# --- graceful empty JSON with no live game ---
d = client.get("/api/stats/ahl").get_json()
check("ahl empty", d["skaters"] == [] and d["standings"] == [])
d = client.get("/api/stats/records").get_json()
check("records empty", d["empty"] is True)
d = client.get("/api/stats/analytics").get_json()
check("analytics empty", d["empty"] is True and "reason" in d)
d = client.get("/api/watch/boxscore").get_json()
check("boxscore no-live", d["skaters"] == [] and d["goalies"] == [])
d = client.get("/api/watch/events").get_json()
check("events no-live", d["events"] == [] and d["live"] is False)

# --- _ev_json conversion ---
p = SimpleNamespace(full_name="Test Player", name="TP")
ev = {"type": "shot", "shooter": p, "shooter_pos": (120.5, 30.0),
      "assists": [SimpleNamespace(full_name="A One")], "clock": 512.0}
j = watch_mod._ev_json(ev)
check("ev_json player->name", j["shooter"] == "Test Player", str(j["shooter"]))
check("ev_json tuple->list", j["shooter_pos"] == [120.5, 30.0])
check("ev_json assists", j["assists"] == ["A One"])
import json
json.dumps(j)
check("ev_json serializable", True)

# --- zone mapping sanity ---
z = stats_mod._zone_from_coords
check("zone crease", z(185, 42.5) == "crease", z(185, 42.5))
check("zone low_slot", z(160, 42.5) == "low_slot", z(160, 42.5))
check("zone point", z(110, 42.5) == "point", z(110, 42.5))
import analytics as _an
for _x, _y, _ar in [(185, 42.5, True), (160, 42.5, True), (110, 42.5, True),
                    (195, 70, True), (15, 42.5, False), (130, 25, True), (70, 20, True)]:
    _z = z(_x, _y, _ar)
    check(f"zone valid ({_x},{_y})", _z in _an.LOCATION_XG, _z)

# --- archive analytics ---
g = {"game_id": "g1", "date": "2026-10-01", "home": "Boston Bruins",
     "away": "Toronto Maple Leafs",
     "shots": [
         {"x": 185, "y": 42.5, "side": "right", "result": "goal", "period": 1,
          "shooter_id": 1, "shooter_name": "S1"},
         {"x": 160, "y": 40, "side": "right", "result": "save", "period": 1,
          "shooter_id": 2, "shooter_name": "S2"},
         {"x": 110, "y": 42.5, "side": "right", "result": "save", "period": 2,
          "shooter_id": 3, "shooter_name": "S3"},
     ]}
d = stats_mod._analytics_from_archive(g)
check("archive not empty", d["empty"] is False)
check("archive shots", d["shots"] == 3, d["shots"])
check("archive goals", d["goals"] == 1)
check("archive xg>0", d["total_xg"] > 0.3, d["total_xg"])
check("archive zones", "low_slot" in d["zone_counts"] and "point" in d["zone_counts"],
      str(d["zone_counts"]))
check("archive report", "expected goals" in d["report"])

# --- live-sim analytics ---
sim = SimpleNamespace(
    shot_log=[
        {"team": "Boston Bruins", "location": "LOW_SLOT", "xg": 0.22, "outcome": "goal"},
        {"team": "Boston Bruins", "location": "POINT", "xg": 0.05, "outcome": "save"},
        {"team": "Toronto Maple Leafs", "location": "HIGH_SLOT", "xg": 0.12, "outcome": "save"},
    ],
    momentum_history=[{"momentum": "favoring_home", "time": 100, "period": 1},
                      {"momentum": "neutral", "time": 200, "period": 1}],
    expected_goals={"Boston Bruins": 0.27, "Toronto Maple Leafs": 0.12},
    home_score=1, away_score=0,
)
d = stats_mod._analytics_from_sim(sim, "Boston Bruins", "Toronto Maple Leafs")
check("sim not empty", d["empty"] is False and d["source"] == "live")
teams = {t["name"]: t for t in d["teams"]}
check("sim xg home", abs(teams["Boston Bruins"]["xg"] - 0.27) < 1e-6, teams["Boston Bruins"]["xg"])
check("sim shots", teams["Boston Bruins"]["shots"] == 2)
check("sim goals", teams["Boston Bruins"]["goals"] == 1)
check("sim momentum", len(d["momentum"]) == 2)
check("sim report", "Expected goals" in d["report"], d["report"][:60])

# --- boxscore payload from fake sim ---
meta_pid = 7
watch_mod._watch["id_meta"] = {str(meta_pid): {"team": 0, "name": "Box Tester",
                                               "goalie": False, "jersey": "91"}}
watch_mod._watch["sim"] = SimpleNamespace(
    game_stats={meta_pid: {"g": 2, "a": 1, "shots_on_goal": 5, "hits": 3}},
    home_score=3, away_score=2, period=2,
)
watch_mod._watch["home"] = "Boston Bruins"
watch_mod._watch["away"] = "Toronto Maple Leafs"
watch_mod._watch["home_abbr"] = "BOS"
watch_mod._watch["away_abbr"] = "TOR"
p = watch_mod._boxscore_payload()
check("box payload", p is not None and len(p["skaters"]) == 1)
check("box pts", p["skaters"][0]["pts"] == 3 and p["skaters"][0]["name"] == "Box Tester")
check("box score", p["score"] == {"home": 3, "away": 2})
watch_mod._watch["sim"] = None
watch_mod._watch["id_meta"] = {}

# --- records payload with fake history ---
fr = SimpleNamespace(
    career_records={"Boston Bruins": {"goals": {"value": 50, "player": "Rec Holder",
                                                "player_id": "p1", "season": ""}}},
    season_records={}, goalie_career_records={}, goalie_season_records={},
    team_season_records={"Boston Bruins": {"wins": {"value": 55, "player": "—",
                                                   "player_id": None, "season": "2025-26"}}},
)
hist = SimpleNamespace(franchise_records=fr,
                       champions_list=lambda: [{"year": 2025, "champion": "Boston Bruins",
                                                "runner_up": "Toronto Maple Leafs",
                                                "series_score": "4-2", "conn_smythe": "Star Player"}])
live = SimpleNamespace(league_history=hist, game_manager=SimpleNamespace(league_history=hist))
d = stats_mod._records_payload(live)
check("records teams", len(d["teams"]) == 1 and d["teams"][0]["team"] == "Boston Bruins")
check("records groups", len(d["teams"][0]["groups"]) == 2)
check("records champions", d["champions"][0]["champion"] == "Boston Bruins")

# --- AHL payload with fake league ---
ledger = SimpleNamespace(games_played=10, goals=6, assists=8, penalty_minutes=4,
                         saves=0, shots_against=0, goals_against_avg=0, wins=0, shutouts=0)
gledger = SimpleNamespace(games_played=8, goals=0, assists=0, penalty_minutes=0,
                          saves=240, shots_against=260, goals_against_avg=2.5,
                          wins=5, shutouts=1)
pos = SimpleNamespace(name="CENTER")
pl = SimpleNamespace(id=11, full_name="Farm Star", primary_position=pos)
gl = SimpleNamespace(id=22, full_name="Farm Goalie",
                     primary_position=SimpleNamespace(name="GOALIE"))
t1 = SimpleNamespace(team_name="Providence Bruins",
                     ahl_roster=[pl, gl])
league = SimpleNamespace(teams=[t1])
import ahl_system, ahl_league
_orig_ts, _orig_tg = ahl_system.top_skaters, ahl_system.top_goalies
_orig_st, _orig_tl = ahl_league.get_ahl_standings, ahl_league.ahl_team_list
ahl_system.top_skaters = lambda league, limit=25: [(pl, "Providence Bruins", ledger)]
ahl_system.top_goalies = lambda league, limit=15, min_gp=5: [(gl, "Providence Bruins", gledger)]
ahl_league.get_ahl_standings = lambda league: [(0, {"gp": 10, "w": 6, "l": 3, "otl": 1,
                                                    "pts": 13, "gf": 35, "ga": 28})]
ahl_league.ahl_team_list = lambda league: [SimpleNamespace(team_name="Providence Bruins")]
try:
    live2 = SimpleNamespace(game_manager=SimpleNamespace(league=league))
    d = stats_mod._ahl_payload(live2)
finally:
    ahl_system.top_skaters, ahl_system.top_goalies = _orig_ts, _orig_tg
    ahl_league.get_ahl_standings, ahl_league.ahl_team_list = _orig_st, _orig_tl
check("ahl skaters", len(d["skaters"]) == 1 and d["skaters"][0]["pts"] == 14)
check("ahl goalies", len(d["goalies"]) == 1 and abs(d["goalies"][0]["sv_pct"] - 0.923) < 1e-3)
check("ahl standings", len(d["standings"]) == 1 and d["standings"][0]["pts"] == 13)

print(f"\nALL {len(PASS)} CHECKS PASSED")
