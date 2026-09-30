# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: board patience model (Muck's retune).

Boards judge trends, not games. Monthly reviews are the channel; per-game
movement only fires on dire/disastrous triggers. Year-one honeymoon,
anti-double-jeopardy monthly cap, owner patience requests, disaster-only
year-1 sackings.
"""
import sys
from unittest import mock

sys.path.insert(0, ".")
import manager_career as mc

PASS = FAIL = 0


def check(name, cond, extra=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name} {extra}")


def fresh_board(exp="playoffs", season=1, conf=60):
    b = mc.BoardSystem()
    b.set_expectation(exp)
    b.season_number = season
    b.confidence = conf
    b.owner = mc.OwnerProfile("patient_builder")
    b._compute_patience_factor()
    return b


# --- 1. no routine per-game movement ---------------------------------------
b = fresh_board()
for i in range(5):
    b.record_result(True, False, True, today_iso="2026-10-10")
for i in range(5):
    b.record_result(False, False, True, today_iso="2026-10-12")
check("mixed 10 games: no routine movement", b.confidence == 60,
      f"got {b.confidence}")
check("no crisis flagged", b.last_crisis == "" and b.warnings_given == 0)

# --- 2. 8-game losing streak: crisis ---------------------------------------
b = fresh_board()
for i in range(8):
    b.record_result(False, False, True, today_iso="2026-11-05")
check("8-loss streak warns", b.warnings_given == 1 and b.last_crisis != "")
# dampened: -10 / 1.4 = -7.14 -> -7
check("8-loss streak delta dampened", b.confidence == 53,
      f"got {b.confidence}")
# streak continues: the 8-streak warning doesn't re-fire; at 0-9 the
# disastrous-start path takes over instead (intended: 0-10 puts a fire
# under anyone).
b.record_result(False, False, True, today_iso="2026-11-07")
check("0-9 triggers disaster path", b._disaster and b.disaster_start_flagged)
b.record_result(False, False, True, today_iso="2026-11-09")
check("disaster doesn't re-fire", b.warnings_given == 2)

# --- 3. disastrous start ----------------------------------------------------
b = fresh_board()
for i in range(9):
    b.record_result(False, False, True, today_iso="2026-10-20")
check("0-9 start flags disaster", b._disaster and b.disaster_start_flagged)
check("year-1 honeymoon voided by disaster", b.season_number == 1 and b._disaster)

# --- 4. 12-game skid burns it down ------------------------------------------
b = fresh_board()
# dodge the 0-9 disaster trigger with an early OT point, then lose out
b.record_result(False, True, True, today_iso="2026-10-02")
for i in range(12):
    b.record_result(False, False, True, today_iso="2026-10-25")
check("12-game skid sets disaster", b._disaster)

# --- 5. 8-game winning streak: small delight --------------------------------
b = fresh_board()
for i in range(8):
    b.record_result(True, False, True, today_iso="2026-11-05")
check("8-win streak +5", b.confidence == 65, f"got {b.confidence}")

# --- 6. monthly bands are expectation-aware ---------------------------------
b = fresh_board("rebuild")
b.monthly_review(0.45, "2026-11-30")
check("rebuild 0.45 satisfied +2", b.confidence == 62, f"got {b.confidence}")
b = fresh_board("win_cup")
b.monthly_review(0.50, "2026-11-30")
# concerned -4, dampened year-1: -4/1.4 = -2.86 -> -3
check("win_cup 0.50 concerned dampened", b.confidence == 57,
      f"got {b.confidence}")
b = fresh_board("playoffs")
b.monthly_review(0.70, "2026-11-30")
check("playoffs 0.70 delighted +4", b.confidence == 64, f"got {b.confidence}")

# --- 7. year-1 honeymoon halves negatives ------------------------------------
b = fresh_board("playoffs", season=1)
b.monthly_review(0.30, "2026-11-30")   # alarmed -6 -> -6/1.4 = -4.28 -> -4
check("year-1 alarmed dampened", b.confidence == 56, f"got {b.confidence}")
b2 = fresh_board("playoffs", season=3)
b2.monthly_review(0.30, "2026-11-30")  # alarmed -6, patience 1.0 -> -6
check("year-3 alarmed full weight", b2.confidence == 54, f"got {b2.confidence}")

# --- 8. anti-double-jeopardy: monthly cap ------------------------------------
b = fresh_board("win_cup", season=3)   # patience 1.0, no honeymoon
for i in range(8):
    b.record_result(False, False, True, today_iso="2026-11-05")
# crisis: -10 dampened by 1.0 -> -10, capped: room -12 -> -10 applied
c_after_crisis = b.confidence
b.monthly_review(0.20, "2026-11-28")   # alarmed -8, cap leaves room -2
check("monthly cap bounds a bad month",
      b.confidence == c_after_crisis - 2, f"crisis={c_after_crisis} final={b.confidence}")
check("cap message is honest", "won't punish you twice" in b.last_review)
check("total monthly movement >= -12", (60 - b.confidence) <= 12)

# --- 9. comeback boost at rock bottom ----------------------------------------
b = fresh_board(season=3, conf=20)
for i in range(8):
    b.record_result(True, False, True, today_iso="2026-12-05")
# 8-win streak +5, boosted 1.5x at conf<25 -> +8 (round 7.5)
check("comeback boost at <25", b.confidence == 28, f"got {b.confidence}")

# --- 10. patience request: granted -------------------------------------------
b = fresh_board(conf=40)
with mock.patch("random.random", return_value=0.0):
    granted, headline, body = b.request_patience("2026-12-01")
check("patience granted", granted and b.confidence == 43,
      f"granted={granted} conf={b.confidence}")
check("patience window set", b.patience_until == "2027-01-30")
# negatives halved inside the window
b.monthly_review(0.30, "2026-12-28")   # alarmed -6 -> /1.4 -> -4 -> /2 -> -2
check("granted patience halves negatives", b.confidence == 41,
      f"got {b.confidence}")

# --- 11. patience request: refused --------------------------------------------
b = fresh_board(conf=40)
b.owner = mc.OwnerProfile("demanding")
with mock.patch("random.random", return_value=0.99):
    granted, headline, body = b.request_patience("2026-12-01")
check("patience refused", not granted and b.confidence == 36,
      f"granted={granted} conf={b.confidence}")
check("refusal counted", b.patience_refusals == 1)
b.monthly_review(0.30, "2026-12-28")
# alarmed -6 -> /1.4 = -4.28 -> -4 -> hangover x1.25 -> -5
check("refusal hangover stings", b.confidence == 31, f"got {b.confidence}")

# --- 12. patience gating -------------------------------------------------------
b = fresh_board(conf=70)
granted, headline, body = b.request_patience("2026-12-01")
check("no ask needed at 70", not granted and headline == "No meeting needed")
b = fresh_board(conf=40)
with mock.patch("random.random", return_value=0.0):
    b.request_patience("2026-12-01")
granted2, h2, _b2 = b.request_patience("2026-12-15")
check("cooldown enforced", not granted2 and h2 == "Too soon")

# --- 13. year-1 sack protection -------------------------------------------------
b = fresh_board(season=1, conf=5)
b.record_result(False, False, True, today_iso="2026-11-05")  # no crisis: streak 1
b.confidence = 0
b._check_sack()
check("year-1 not sacked at 0", not b.sacked and b.confidence == 1)
b = fresh_board(season=1, conf=5)
b.record_big_event("scandal")
b.confidence = 0
b._check_sack()
check("year-1 scandal CAN sack", b.sacked)
b = fresh_board(season=3, conf=5)
b.confidence = 0
b._check_sack()
check("year-3 sacked at 0", b.sacked)

# --- 14. season review: dampened miss, clock rolls ------------------------------
b = fresh_board("playoffs", season=1)
b.recent_cups = 0
headline, body, delta = b.season_review(False, 0, False)
# -20 / 1.4 = -14.28 -> -14
check("year-1 miss dampened", delta == -14, f"got {delta}")
check("season clock rolls", b.season_number == 2)
check("patience erodes on miss", b.patience_factor < 1.4)
check("counters reset", b.season_wins == 0 and b.streak == 0)

# --- 15. playoffs stay modest ----------------------------------------------------
b = fresh_board(season=3)
b.record_result(True, False, True, is_playoff=True, today_iso="2027-04-20")
b.record_result(False, False, True, is_playoff=True, today_iso="2027-04-22")
check("playoff games +/- small", b.confidence == 59, f"got {b.confidence}")

# --- 16. persistence round-trip ---------------------------------------------------
b = fresh_board("contend")
b.on_hired(58, 24.5, "2026-10-01")
b.owner = mc.OwnerProfile("meddler")  # set after hire (hire randomizes)
d = b.to_dict()
b2 = mc.BoardSystem.from_dict(d)
check("owner survives save/load", b2.owner.archetype == "meddler")
check("patience fields survive",
      b2.season_number == 1 and abs(b2.patience_factor - b.patience_factor) < 1e-9)
# old save: no new keys -> graceful defaults
b3 = mc.BoardSystem.from_dict({"confidence": 42, "expectation": "playoffs"})
check("old save migrates cleanly",
      b3.confidence == 42 and b3.season_number == 1
      and b3.owner.archetype == "patient_builder"
      and b3.patience_factor == 1.0)

# --- 17. owner archetypes ----------------------------------------------------------
seen = {mc.OwnerProfile.random().archetype for _ in range(200)}
check("owner mix covers archetypes", len(seen) >= 3, f"got {seen}")
for a, spec in mc.OwnerProfile.ARCHETYPES.items():
    check(f"archetype {a} has lines",
          bool(spec["grant_line"]) and bool(spec["refuse_line"]))

print(f"\nQA board_patience: {PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
