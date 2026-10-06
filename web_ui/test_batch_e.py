"""Batch E: watch depth + multiplayer web layer (no live game)."""
import os
import sys
sys.path.insert(0, os.environ.get("WT", "/tmp/wt-batch-e"))

from web_ui import bridge
from web_ui.screens import multiplayer as mp_mod
from web_ui.screens import watch as watch_mod

app = bridge.create_app(None)
client = app.test_client()

PASS = []


def check(name, cond, detail=""):
    assert cond, f"FAIL: {name} {detail}"
    PASS.append(name)
    print(f"  ok: {name}")


# --- MP state probes (no game) ---
d = client.get("/api/mp/state").get_json()
check("mp/state none", d["ok"] and d["role"] == "none", str(d))
d = client.get("/api/mp/game").get_json()
check("mp/game none", d["ok"] and d["role"] == "none"
      and d["events"] == [] and d["connected"] is False, str(d))
d = client.get("/api/mp/humans").get_json()
check("mp/humans empty", d["ok"] and d["humans"] == [], str(d))
r = client.post("/api/mp/chat", json={"text": "hi"})
check("mp/chat 400 offline", r.status_code == 400, r.status_code)
r = client.post("/api/mp/trade/respond",
                json={"offer_id": "x", "decision": "accept"})
check("mp/trade/respond 400 offline", r.status_code == 400, r.status_code)
r = client.post("/api/mp/action",
                json={"action": "bogus_action", "params": {}})
check("mp/action unsupported", r.status_code == 400, r.status_code)
r = client.get("/api/mp/snapshot")
check("mp/snapshot 404", r.status_code == 404, r.status_code)
r = client.get("/api/mp/sync")
check("mp/sync 404", r.status_code == 404, r.status_code)
d = client.get("/api/mp/result?nonce=zzz").get_json()
check("mp/result pending", d["pending"] is True, str(d))
d = client.get("/api/mp/draft_players", json={"ids": ["1"]}).get_json() \
    if False else client.post("/api/mp/draft_players",
                              json={"ids": ["1"]}).get_json()
check("mp/draft_players empty", d["ok"] and d["players"] == [], str(d))

# --- web_client_event routing ---
class FakeApp:
    _mp_client_ready = True


_fa = FakeApp()
mp_mod.web_client_event(_fa, "chat", {"from": "A", "text": "hello"})
mp_mod.web_client_event(_fa, "day_advanced", {"game_date": "Oct 7"})
mp_mod.web_client_event(_fa, "state_sync",
                        {"save_bytes": b"BYTES", "label": "L",
                         "game_date": "Oct 7"})
check("ready reset on day_advanced", _fa._mp_client_ready is False)
evs = mp_mod.drain_web_inbox()
kinds = [e["kind"] for e in evs]
check("inbox kinds", kinds == ["chat", "day_advanced", "state_sync"], str(kinds))
check("state_sync stashed", mp_mod._mp_client_last_sync[0] == b"BYTES")
check("inbox drained", mp_mod.drain_web_inbox() == [])
mp_mod.consume_last_sync()
check("sync consumed", mp_mod._mp_client_last_sync is None)

# disconnected routing
mp_mod.web_client_event(FakeApp(), "disconnected", {"reason": "gone"})
check("disconnected flagged",
      mp_mod._mp_client_disconnected == "gone")
evs = mp_mod.drain_web_inbox()
check("disconnected event", evs and evs[0]["kind"] == "disconnected")
mp_mod._mp_client_disconnected = None

# _jsonable
class P:
    full_name = "Sid"
j = mp_mod._jsonable({"p": P(), "t": (1, 2), "n": 5})
check("jsonable", j == {"p": "Sid", "t": [1, 2], "n": 5}, str(j))

# pump with no app: no crash
bridge._pump_mp_web(None)
check("pump no-app safe", True)

# _mp_web_store
class A:
    pass


a = A()
bridge._mp_web_store(a, "n1", True, "msg")
check("mp_web_store", a._web_mp_result["ok"] is True
      and a._web_mp_result["nonce"] == "n1")
bridge._mp_web_store(a, "n2", False, "blocked!",
                     blocked=True, blockers=[{"id": "x", "title": "T",
                                              "detail": "D"}])
check("mp_web_store blocked",
      a._web_mp_result["blocked"] is True
      and a._web_mp_result["blockers"][0]["title"] == "T")

# --- watch: past games / replay endpoints (no game) ---
d = client.get("/api/watch/past_games").get_json()
check("past_games empty", d["games"] == [], str(d))
r = client.get("/api/watch/boxscore_history?idx=0")
check("boxscore_history 404", r.status_code == 404, r.status_code)
r = client.get("/api/watch/replay_events?idx=0")
check("replay_events 404", r.status_code == 404, r.status_code)
r = client.get("/replay")
check("replay page 200", r.status_code == 200, r.status_code)

# --- watch helpers ---
gs = {"1": {"g": 1, "a": 0, "shots_on_goal": 3, "hits": 2,
            "blocked_shots": 1, "faceoffs_won": 4, "faceoffs_lost": 6,
            "takeaways": 1, "giveaways": 0},
      "2": {"saves": 20, "shots_against": 22, "goals_against": 2}}
meta = {"1": {"team": 0, "goalie": False}, "2": {"team": 0, "goalie": True}}
ts = watch_mod._team_stats_from_gs(gs, meta)
check("team_stats agg", ts[0]["goals"] == 1 and ts[0]["shots"] == 3
      and ts[0]["saves"] == 20 and ts[0]["blocks"] == 1
      and ts[0]["fo_won"] == 4, str(ts))
sc = watch_mod._scoring_from_events(
    [{"type": "goal", "scoring_team": "Boston Bruins", "shooter": "A",
      "assists": ["B"], "period": 1, "clock": 600, "elapsed": 600,
      "empty_net": False}],
    "Boston Bruins")
check("scoring summary", len(sc) == 1 and sc[0]["team"] == 0
      and sc[0]["scorer"] == "A" and sc[0]["assists"] == ["B"], str(sc))
check("normalize gs", watch_mod._normalize_gs({1: {"g": 1}}) == {"1": {"g": 1}})

# lines grades payload with a fake team (no lines -> [])
check("lines no-snapshot", watch_mod._lines_grades_payload(
    None, 0, "X", {}, {}) == [])

print(f"\nALL {len(PASS)} CHECKS PASSED")
