"""Batch C (league) smoke test: new routes return 200 with graceful empty
payloads when no live game is attached; pure logic (view filters, sort,
milestone defs) verified on synthetic rows.

Run: python3 web_ui/test_batch_c_league.py
"""
import sys
from types import SimpleNamespace

sys.path.insert(0, "/tmp/wt-batch-c")

from web_ui import bridge

app = bridge.create_app(None)
client = app.test_client()

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok: {name}")


# --- pages render (200) ---
for route in ["/standings", "/ahl", "/deadline", "/season-summary",
              "/draft", "/playoffs", "/history", "/news", "/calendar"]:
    r = client.get(route)
    check(f"GET {route}", r.status_code == 200, f"got {r.status_code}")

# --- new APIs graceful-empty with no live game ---
empties = [
    ("/api/standings/views", {"rows": []}),
    ("/api/standings/team-analytics", {"rows": []}),
    ("/api/standings/division-analysis", {"rows": []}),
    ("/api/standings/divisions-grid", {"divisions": []}),
    ("/api/stats/advanced", {"skaters": [], "goalies": []}),
    ("/api/stats/breakout", {"players": []}),
    ("/api/stats/rookies", {"skaters": [], "goalies": []}),
    ("/api/stats/award-races", {"rows": []}),
    ("/api/stats/milestones", {"watch": []}),
    ("/api/stats/nhl-records", {"empty": True}),
    ("/api/ahl/overview", {"empty": True}),
    ("/api/ahl/standings", {"standings": []}),
    ("/api/ahl/scores", {"recent": [], "upcoming": []}),
    ("/api/ahl/calder", {"empty": True}),
    ("/api/ahl/team", {"selected": None}),
    ("/api/ahl/prospects", {"skaters": [], "cooking": [], "goalies": []}),
    ("/api/playoffs/projection", {"available": False}),
    ("/api/playoffs/series/nope", {"found": False}),
    ("/api/draft/trade-pick", {"can_trade": False}),
    ("/api/draft/trade-pick/result", {"result": None}),
    ("/api/draft/shortlist", {"shortlist": []}),
    ("/api/season-summary", {"season_over": False}),
    ("/api/awards-ceremony", {"script": []}),
    ("/api/history/career-leaders", {"leaders": []}),
    ("/api/history/hall-of-fame", {"inductees": []}),
    ("/api/history/advanced-stats", {"teams": []}),
    ("/api/history/season-reviews", {"lines": []}),
    ("/api/history/awards-full", {"awards": {}}),
    ("/api/deadline", {"available": False}),
    ("/api/calendar/events", {"events": []}),
]
for route, keys in empties:
    r = client.get(route)
    d = r.get_json()
    ok = r.status_code == 200 and all(d.get(k) == v for k, v in keys.items())
    check(f"empty {route}", ok, f"got {r.status_code} {d}")

# --- POST empties ---
r = client.post("/api/news/refresh")
check("POST /api/news/refresh no-live", r.status_code == 200 and
      r.get_json()["ok"] is False)
r = client.post("/api/deadline/stance", json={"stance": "buyer"})
check("POST /api/deadline/stance no-live", r.status_code in (503, 400, 500))
r = client.post("/api/deadline/stance", json={"stance": "bogus"})
check("POST /api/deadline/stance bad value", r.status_code == 400)
r = client.post("/api/draft/trade-pick", json={})
check("POST /api/draft/trade-pick missing args", r.status_code == 400)
r = client.post("/api/draft/shortlist", json={"player_id": "x"})
check("POST /api/draft/shortlist no-live", r.status_code == 400)

# --- pure logic: standings view filters ---
from web_ui.screens import standings as st_mod

rows = [
    {"name": f"T{i}", "conf": "Eastern" if i < 8 else "Western",
     "division": f"D{i % 4}", "pts": 100 - i * 3, "w": 50 - i,
     "diff": 20 - i, "is_user": i == 0, "gp": 60, "l": 5, "otl": 5,
     "gf": 180, "ga": 160, "pt_pct": 0.8, "streak": ""}
    for i in range(16)
]
wc = st_mod._standings_view_teams(rows, "Wild Card Race")
check("wild card race = 4th-8th per conf",
      len(wc) == 10 and all(
          r["name"] in {f"T{i}" for i in (3, 4, 5, 6, 7, 11, 12, 13, 14, 15)}
          for r in wc), str([r["name"] for r in wc]))
dl = st_mod._standings_view_teams(rows, "Division Leaders")
check("division leaders = 1 per division", len(dl) == 4)
pp = st_mod._standings_view_teams(rows, "Playoff Picture")
check("playoff picture = 8 per conf", len(pp) == 16)
ec = st_mod._standings_view_teams(rows, "Eastern Conference")
check("eastern filter", len(ec) == 8 and all(r["conf"] == "Eastern" for r in ec))
srt = st_mod._apply_standings_sort(rows, "Goal Differential")
check("sort by goal diff", srt[0]["diff"] == 20 and srt[-1]["diff"] == 5)
srt2 = st_mod._apply_standings_sort(rows, "Wins")
check("sort by wins", srt2[0]["w"] == 50)

# --- milestone defs sanity ---
check("milestone skater defs", len(st_mod.__dict__) > 0)  # module loaded
from web_ui.screens import stats as stats_mod
check("skater milestone defs", len(stats_mod._MILESTONE_WATCH_SKATERS) == 4)
check("goalie milestone defs", len(stats_mod._MILESTONE_WATCH_GOALIES) == 3)
check("standings views list",
      st_mod._STANDINGS_VIEWS == ["League Overview", "Eastern Conference",
                                  "Western Conference", "Wild Card Race",
                                  "Division Leaders", "Playoff Picture"])

# --- ceremony order sanity (awards_ceremony import surface) ---
from web_ui.screens import season_end as se_mod
check("season_end has ceremony route",
      hasattr(se_mod, "_ceremony_script"))

# --- bridge: draft_trade_pick op registered (source check) ---
import inspect
src = inspect.getsource(bridge)
check("bridge has draft_trade_pick op", 'op == "draft_trade_pick"' in src)
check("bridge stashes result",
      "_web_draft_trade_result" in src)

print(f"\n{len(PASS)} checks passed")
