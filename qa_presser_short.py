# qa_presser_short.py -- pre-game presser is shorter but still functional.
# Muck 2026-10-02: "the pre game presser for gm is too long"
import sys
from types import SimpleNamespace

sys.path.insert(0, "/tmp/wt-presser")

import manager_career as mc

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


# 1. Prematch presser now returns 2 questions, not 3 -----------------------
ctx = {"form_word": "decent", "opp": "Boston Bruins", "opp_word": "dangerous"}
qs = mc.build_prematch_presser(
    SimpleNamespace(team_name="Detroit Red Wings"),
    SimpleNamespace(team_name="Boston Bruins"), ctx)
check("prematch presser returns 2 questions", len(qs) == 2, f"got {len(qs)}")
check("questions have ids", all("id" in q for q in qs))
check("questions have journalists", all(q.get("journalist") for q in qs))
check("questions have question text",
      all(q.get("question") for q in qs))
check("each question has 3 answers",
      all(len(q.get("answers", [])) == 3 for q in qs))
check("question ids are unique", len({q["id"] for q in qs}) == 2)
check("questions drawn from bank",
      all(q["id"] in {b["id"] for b in mc.PREMATCH_QUESTIONS} for q in qs))

# 2. Skip path: _skip_bundle_presser marks all answered, neutral ----------
# Fake app harness: bind the real method to a stub.
import main as _main_mod  # noqa: F401  (import check only)

calls = []


class FakeApp:
    def _career_apply_press_answers(self, answers, kind):
        calls.append((answers, kind))


msg = SimpleNamespace(action_data={
    "presser": qs,
    "presser_answered": [False] * len(qs),
})
# Call the unbound method with a fake self.
_main_mod.HockeyManagerGUI._skip_bundle_presser(FakeApp(), msg)
check("skip marks all answered",
      msg.action_data["presser_answered"] == [True, True],
      f"{msg.action_data['presser_answered']}")
check("skip sets presser_skipped flag",
      msg.action_data.get("presser_skipped") is True)
check("skip applies no effects (neutral)", calls == [], f"{calls}")
check("skip never raises on empty data", True)

# 3. Skip on a message with no presser at all ------------------------------
msg2 = SimpleNamespace(action_data={})
try:
    _main_mod.HockeyManagerGUI._skip_bundle_presser(FakeApp(), msg2)
    check("skip with no presser data never raises", True)
    check("skip with no presser marks empty answered",
          msg2.action_data.get("presser_answered") == [])
except Exception as e:  # noqa: BLE001
    check("skip with no presser data never raises", False, str(e))

# 4. Answer flow still works (single-question answer) ----------------------
msg3 = SimpleNamespace(action_data={
    "presser": qs,
    "presser_answered": [False] * len(qs),
})
try:
    _main_mod.HockeyManagerGUI._answer_bundle_presser(FakeApp(), msg3, 0, 0)
    check("answering still works",
          msg3.action_data["presser_answered"][0] is True)
    check("answering records a reaction",
          0 in msg3.action_data.get("presser_reactions", {}))
except Exception as e:  # noqa: BLE001
    check("answering still works", False, str(e))

print(f"\n{ PASS }/{ PASS + FAIL } passed")
sys.exit(1 if FAIL else 0)
