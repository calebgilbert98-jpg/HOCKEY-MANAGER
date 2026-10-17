"""Batch A smoke test: inbox action types ported from v0.18.4.

Covers the new /api/command ops (state mutation via _execute_command),
the message detail API, the lottery reveal API, and a full fantasy
draft run (begin -> human pick -> AI chain -> completion) on mocks.
"""
import random
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, "/home/hatch/workspace/hockey-manager")

import web_ui.bridge as bridge
from game_classes import PlayerPosition

TODAY = date(2026, 10, 5)
calls = []


class MockInbox:
    def __init__(self):
        self.messages = []
        self.unread_count = 0

    def mark_message_read(self, mid):
        for m in self.messages:
            if str(m.id) == str(mid):
                m.is_read = True

    def add_message(self, m):
        self.messages.append(m)

    def delete_message(self, mid):
        self.messages = [m for m in self.messages if str(m.id) != str(mid)]


class MockMsg:
    def __init__(self, mid, sender, sender_type, subject, action_type,
                 action_data, content="body text"):
        self.id = mid
        self.sender = sender
        self.sender_type = sender_type
        self.subject = subject
        self.content = content
        self.category = "General"
        self.date_sent = TODAY
        self.is_read = False
        self.is_urgent = False
        self.is_important = False
        self.is_saved = False
        self.priority = 1
        self.requires_response = True
        self.action_type = action_type
        self.action_data = action_data
        self.action_done = False

    def is_overdue(self):
        return False

    def get_age_days(self):
        return 0


def make_team(name):
    return SimpleNamespace(
        team_name=name, league_name="National Hockey League",
        roster=[], ahl_roster=[], prospects=[], inbox=MockInbox())


user_team = make_team("My Team")
rival = make_team("Rivals")

GAME_DAY_DATA = {
    "bundle_id": "gd-2026-10-05", "game_date": "2026-10-05",
    "home": "My Team", "away": "Rivals",
    "presser": [{"question": "How do you feel?", "journalist": "Beat Writer",
                 "answers": [{"label": "Confident", "reaction": "Nods."},
                             {"label": "Cautious", "reaction": "Hmm."}]}],
    "presser_answered": [False], "presser_reactions": {},
    "talk_options": [{"label": "Win it for the fans", "text": "Do it!",
                      "fit": "good"}],
    "talk_chosen": None, "talk_boost": 1.0,
    "instruction_options": [{"id": "play_harder", "label": "Play harder",
                             "text": "Hit everything."}],
    "instruction_chosen": None,
}

msgs = [
    MockMsg("m1", "League", "League", "FANTASY DRAFT — sign up",
            None, {}),
    MockMsg("m2", "Media", "Media", "DRAFT LOTTERY results",
            None, {}),
    MockMsg("m3", "Media", "Media", "GAME DAY: Rivals @ My Team",
            "game_day", dict(GAME_DAY_DATA)),
    MockMsg("m4", "Media", "Media", "Post-game", "postmatch_presser",
            {"questions": [{"question": "Thoughts?", "journalist": "J",
                            "answers": [{"label": "Proud", "reaction": "OK"}]}],
             "answered": [False], "reactions": {}}),
    MockMsg("m5", "AGM", "Staff", "Qualifying offers", "rfa_qualifying",
            {"cards": [{"player_id": "p1", "name": "Kid Star",
                        "qo_amount": 1000000, "prior_salary": 900000}],
             "decided": {}}),
    MockMsg("m6", "AGM", "Staff", "Buyouts", "buyout_window",
            {"cards": [{"player_id": "p2", "name": "Old Vet", "age": 36,
                        "overall": 74, "cap_hit": 5000000, "years_left": 2,
                        "buyout_cost": 3333333, "annual_dead": 833333,
                        "dead_years": 4, "savings_y1": 4166667}],
             "decided": {}}),
    MockMsg("m7", "AGM", "Staff", "Staff renewals", "staff_renewal",
            {"offers": [{"staff_id": "s1", "name": "Coach Al", "role": "coach",
                         "age": 55, "reputation": 80, "years_with_team": 4,
                         "salary": 2000000}],
             "decided": {}}),
    MockMsg("m8", "League", "League", "Fine issued", "media_fine_response",
            {"fine_name": "GM", "fine_team": "My Team",
             "fine_amount": 25000, "fine_reason": "Comments",
             "fine_date": "2026-10-05"}),
    MockMsg("m9", "Rival GM", "GM", "Offer sheet", "offer_sheet_match",
            {"player_id": "p3", "aav": 4000000, "years": 3,
             "compensation": "1st + 3rd"}),
    MockMsg("m10", "Rival GM", "GM", "Trade alt", "offer_sheet_trade_alt",
            {"player_id": "p3", "aav": 4000000, "years": 3,
             "compensation": "1st + 3rd", "package_player_ids": ["x1"],
             "package_value": 3500000}),
    MockMsg("m11", "League", "League", "Arbitration", "arbitration_walkaway",
            {"player_id": "p4", "award_aav": 3000000, "term_years": 2}),
]
for m in msgs:
    user_team.inbox.add_message(m)

def _mock_presser(msg, q, a):
    calls.append(("presser", msg.id, q, a))
    msg.action_data["presser_answered"][q] = True


def _mock_talk(msg, o):
    calls.append(("talk", msg.id, o))
    msg.action_data["talk_chosen"] = o
    msg.action_data["talk_boost"] = 1.05
    msg.action_data["talk_reaction"] = "Fired up!"


def _mock_instr(msg, oid):
    calls.append(("instr", msg.id, oid))
    msg.action_data["instruction_chosen"] = oid


def _mock_post(msg, q, a):
    calls.append(("post", msg.id, q, a))
    msg.action_data["answered"][q] = True


mock_app = SimpleNamespace(
    game_manager=SimpleNamespace(
        user_team=user_team,
        league=SimpleNamespace(
            teams=[user_team, rival], schedule=[
                {"date": TODAY, "home_team": user_team,
                 "away_team": rival, "preseason": False}],
            media_fines=[],
            lottery_results={},
        ),
        current_date=TODAY,
        pending_fantasy_draft=True,
    ),
    user_team=user_team,
    _answer_bundle_presser=_mock_presser,
    _skip_bundle_presser=lambda msg: calls.append(("presser_skip", msg.id)),
    _answer_bundle_team_talk=_mock_talk,
    _answer_bundle_instruction=_mock_instr,
    _answer_postmatch_presser=_mock_post,
    apply_rfa_qualifying_decision=lambda msg, pid, q: calls.append(("rfa", msg.id, pid, q)),
    apply_buyout_decision=lambda msg, pid, b: calls.append(("buyout", msg.id, pid, b)),
    apply_staff_renewal_decision=lambda msg, sid, y: calls.append(("staff", msg.id, sid, y)),
    apply_offer_sheet_match_decision=lambda msg, mt: calls.append(("os_match", msg.id, mt)),
    apply_offer_sheet_trade_alt_decision=lambda msg, ac: calls.append(("os_trade", msg.id, ac)),
    apply_arbitration_walkaway_decision=lambda msg, w: calls.append(("arb", msg.id, w)),
    update_all_views=lambda: calls.append(("update_views",)),
)

bridge._web_app_ref = mock_app
from web_ui.bridge import create_app
flask_app = create_app()
client = flask_app.test_client()


def drain_one():
    cmd = bridge.COMMAND_QUEUE.get_nowait()
    bridge._execute_command(mock_app, cmd)
    return cmd


def post_op(op, **kw):
    r = client.post("/api/command", json=dict(op=op, **kw))
    assert r.status_code == 200, (op, r.status_code)
    assert r.get_json()["ok"] is True
    return drain_one()


# ---- list + detail APIs -------------------------------------------------
data = client.get("/api/inbox").get_json()
by_id = {m["id"]: m for m in data}
assert by_id["m3"]["action_type"] == "game_day"
assert by_id["m3"]["action_data"]["away"] == "Rivals"
assert by_id["m3"]["action_done"] is False
assert by_id["m1"]["special_action"] == "fantasy_draft", by_id["m1"]
assert by_id["m2"]["special_action"] == "", by_id["m2"]  # no pending yet
print("list API: action_data/action_done/special_action OK")

mock_app.game_manager._pending_lottery_reveal = {
    "year": 2026,
    "rows": [
        {"pick": 1, "team": "Rivals", "original_team": "Rivals",
         "odds_pct": 18.5, "movement": 2},
        {"pick": 2, "team": "My Team", "original_team": "My Team",
         "odds_pct": 13.5, "movement": -1},
    ],
}
data = client.get("/api/inbox").get_json()
by_id = {m["id"]: m for m in data}
assert by_id["m2"]["special_action"] == "lottery_reveal", by_id["m2"]
d = client.get("/api/inbox/message/m3").get_json()
assert d["today"] == "2026-10-05", d["today"]
assert d["is_preseason"] is False
assert d["user_team_name"] == "My Team"
print("detail API + lottery special detection OK")

# ---- lottery API ---------------------------------------------------------
lot = client.get("/api/lottery").get_json()
assert lot["active"] is True and lot["year"] == 2026
assert [r["pick"] for r in lot["reveal_order"]] == [2, 1], lot["reveal_order"]
assert "wins the lottery" in lot["reveal_order"][1]["reaction"]
print("lottery API OK:", lot["reveal_order"][1]["reaction"])

# ---- game-day ops ---------------------------------------------------------
post_op("inbox_presser_answer", message_id="m3", q=0, a=1)
assert ("presser", "m3", 0, 1) in calls, calls
post_op("inbox_team_talk", message_id="m3", option=0)
assert ("talk", "m3", 0) in calls
post_op("inbox_instruction", message_id="m3", option_id="play_harder")
assert ("instr", "m3", "play_harder") in calls
post_op("inbox_gameday_watch", message_id="m3")
res = mock_app._game_day_resolution
assert res["watch"] is True and res["talk_boost"] == 1.05
assert res["instruction"] == "play_harder", res
assert bridge._watch_mode == "watch"
m3 = next(m for m in user_team.inbox.messages if m.id == "m3")
assert m3.action_done is True
print("game_day ops OK (presser/talk/instruction/watch)")

post_op("inbox_postmatch_answer", message_id="m4", q=0, a=0)
assert ("post", "m4", 0, 0) in calls
print("postmatch_presser op OK")

# ---- front-office ops ------------------------------------------------------
post_op("inbox_rfa_qualify", message_id="m5", player_id="p1", qualify=True)
assert ("rfa", "m5", "p1", True) in calls
post_op("inbox_buyout_decide", message_id="m6", player_id="p2", buyout=False)
assert ("buyout", "m6", "p2", False) in calls
post_op("inbox_staff_renew", message_id="m7", staff_id="s1", years=2)
assert ("staff", "m7", "s1", 2) in calls
post_op("inbox_staff_renew", message_id="m7", staff_id="s1", years="walk")
assert ("staff", "m7", "s1", None) in calls
post_op("inbox_offer_sheet_match", message_id="m9", match=True)
assert ("os_match", "m9", True) in calls
post_op("inbox_offer_sheet_trade", message_id="m10", accept=False)
assert ("os_trade", "m10", False) in calls
post_op("inbox_arbitration", message_id="m11", walk_away=True)
assert ("arb", "m11", True) in calls
print("rfa/buyout/staff/offer-sheet/arbitration ops OK")

# ---- fine response (real media_engine logic) --------------------------------
post_op("inbox_fine_respond", message_id="m8", choice="accept")
m8 = next(m for m in user_team.inbox.messages if m.id == "m8")
assert m8.action_done is True, "fine not marked done"
assert "outcome" in (m8.action_data or {}), m8.action_data
print("fine response OK:", (m8.action_data or {}).get("outcome", "")[:60])

# ---- lottery clear -----------------------------------------------------------
post_op("inbox_lottery_clear")
assert getattr(mock_app.game_manager, "_pending_lottery_reveal", None) is None
print("lottery clear OK")

# ---- fantasy draft end-to-end -------------------------------------------------
POS = [PlayerPosition.CENTER, PlayerPosition.LEFT_WING,
       PlayerPosition.RIGHT_WING, PlayerPosition.LEFT_DEFENSE,
       PlayerPosition.GOALIE, PlayerPosition.CENTER]


class MockPlayer:
    _n = 0

    def __init__(self, name, ovr, pos):
        MockPlayer._n += 1
        self.id = f"fp{MockPlayer._n}"
        self.full_name = name
        self.age = 27
        self._ovr = ovr
        self.primary_position = pos
        self.contract = None
        self.team_name = ""
        self.captaincy = ""
        self.captain_tenure_years = 0
        self.alternate_tenure_years = 0
        self.former_team = ""

    def overall_rating(self):
        return float(self._ovr)


pool = [MockPlayer(f"Player {i}", 90 - i * 5, POS[i % len(POS)])
        for i in range(6)]
user_team.roster = list(pool[:3])
rival.roster = list(pool[3:])
user_team.ahl_roster = []
rival.ahl_roster = []

random.seed(1234)
r = client.post("/api/fantasy_draft/begin")
assert r.status_code == 200 and r.get_json()["ok"] is True
drain_one()
mgr, err = bridge._fantasy_draft_manager(mock_app)
assert mgr is not None, err
assert mgr.draft_started is True
assert user_team.roster == [] and rival.roster == [], "rosters not cleared"
# shrink to a 2-round draft for the test (4 picks, 6 players in pool)
mgr.draft_picks = mgr.draft_picks[:4]
mgr.config.rounds = 2
st = client.get("/api/fantasy_draft").get_json()
assert st["active"] is True and st["started"] is True
assert st["available_count"] == 6, st["available_count"]
assert len(st["draft_order"]) == 2
print("fantasy draft begin OK; order:", st["draft_order"])

# fast-forward AI picks until it's the user's turn (mirrors client polling)
bridge._fantasy_draft_run_ai(mgr)
for _round in range(4):  # at most a few human picks needed
    st = client.get("/api/fantasy_draft").get_json()
    if st.get("complete") or st.get("completed"):
        break
    cur = st["current"]
    assert cur["is_user_pick"] is True, cur
    top = st["available"][0]
    assert top["overall"] >= st["available"][1]["overall"], "not sorted by ovr"
    r = client.post("/api/fantasy_draft/pick", json={"player_id": top["id"]})
    assert r.status_code == 200 and r.get_json()["ok"] is True
    drain_one()  # human pick + AI chain run on the main thread
st = client.get("/api/fantasy_draft").get_json()
assert st.get("complete") or st.get("completed"), st
assert mock_app.game_manager.pending_fantasy_draft is False
assert len(user_team.roster) > 0 and len(rival.roster) > 0
subjects = [m.subject for m in user_team.inbox.messages]
assert any("Fantasy Draft Complete" in s for s in subjects), subjects
mgr2, _ = bridge._fantasy_draft_manager(mock_app)
assert mgr2 is None, "league-owned session not released"
print("fantasy draft pick/AI-chain/completion OK;",
      len(user_team.roster), "vs", len(rival.roster), "on NHL rosters")

print("\nALL BATCH A CHECKS PASSED")
