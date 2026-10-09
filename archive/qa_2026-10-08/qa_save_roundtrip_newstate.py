# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""qa_save_roundtrip_newstate.py -- round-trip audit for persisted state added
by the six-commit stack (Muck 2026-09-30: "make sure saving isnt broken in
the future and corrupting post all our builds").

Covers every new piece of persisted state from:
  1f2f124 foundations, 00d15a0 scenarios, dc5fbb6 chemistry,
  66c6430 morale, a502e17 composite toggle, db798d7 drama.

Audit result:
  - team._lc_auditions (hot-hand/returnee audition ledger, dc5fbb6): was
    NEVER serialized -- every save wiped in-flight auditions so they never
    resolved after a load. FIXED: 'lc_auditions' in _serialize_team /
    _restore_team (save_load_system.py).
  - Staff.morale (66c6430 living system): round-trips via the generic
    __dict__ walk in _serialize_staff/_restore_staff. Verified here.
  - LiveHeat (00d15a0): per-game sim attachment, intentionally transient.
  - team._lc_lineup_notes: per-game storytelling cache, recomputed.
  - ot_drama levers: per-game pure functions, no persisted state.
  - show_composite_ratings (a502e17): session-lived by design (Muck).
  - 1f2f124 foundations: mechanics only, no new persisted state.
  - No new version/scale stamp writes anywhere in the six commits
    (no contradictory-stamp recurrence).
"""
import sys
import os
import pickle
import gzip
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL = 0, 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS: {name}")
    else:
        FAIL += 1
        print(f"  FAIL: {name} {detail}")


from save_load_system import GameSaveManager
from game_classes import Team, Staff, StaffRole
from datetime import date

gm = SimpleNamespace(league=None, user_team=None, current_date=date(2026, 10, 1))
sls = GameSaveManager(gm)


def fresh_team():
    return Team("Test Team", "Test City", "Atlantic", "Eastern")


# 1. audition ledger round-trips ----------------------------------------
t = fresh_team()
t._lc_auditions = {
    101: {"partner_pid": 202, "from_line": 3, "to_line": 2,
          "start_gp": 41, "kind": "heater"},
    303: {"partner_pid": 404, "from_line": 2, "to_line": 3,
          "start_gp": 55, "kind": "returnee", "earned": True},
}
data = sls._serialize_team(t)
check("lc_auditions serialized", "lc_auditions" in data)
check("lc_auditions content intact",
      data["lc_auditions"] == t._lc_auditions,
      f"got {data['lc_auditions']!r}")

t2 = sls._restore_team(data)
check("lc_auditions restored", getattr(t2, "_lc_auditions", None) == t._lc_auditions,
      f"got {getattr(t2, '_lc_auditions', None)!r}")

# 2. double round-trip is stable (no mutation / duplication) ------------
data2 = sls._serialize_team(t2)
t3 = sls._restore_team(data2)
check("ledger stable across two round-trips",
      getattr(t3, "_lc_auditions", None) == t._lc_auditions)

# 3. old save without the key -> empty ledger, no crash ------------------
t4 = fresh_team()
data4 = sls._serialize_team(t4)
del data4["lc_auditions"]  # simulate a pre-fix save
t5 = sls._restore_team(data4)
check("missing key restores to empty ledger",
      getattr(t5, "_lc_auditions", "MISSING") == {},
      f"got {getattr(t5, '_lc_auditions', 'MISSING')!r}")

# 4. ledger values are plain pickle-safe data ---------------------------
blob = pickle.dumps(data["lc_auditions"], protocol=pickle.HIGHEST_PROTOCOL)
check("ledger pickle-safe", pickle.loads(blob) == t._lc_auditions)

# 5. staff morale round-trips (living system, 66c6430) -------------------
s = Staff("Jane", "Doe", StaffRole.HEAD_COACH)
s.morale = 37
sd = sls._serialize_staff(s)
check("morale serialized", sd.get("morale") == 37, f"got {sd.get('morale')!r}")
s2 = sls._restore_staff(sd)
check("morale restored", getattr(s2, "morale", None) == 37,
      f"got {getattr(s2, 'morale', None)!r}")

# 6. version stamps consistent on fresh saves ---------------------------
save_data = sls.create_save_data()
check("fresh save carries version stamp",
      bool(save_data.get("version")))
check("fresh save carries attribute_scale=100",
      save_data.get("attribute_scale") == 100,
      f"got {save_data.get('attribute_scale')!r}")

# 7. fresh saves never self-migrate (no contradictory-stamp recurrence) --
from save_load_system import should_migrate_50_to_100
check("fresh save does not trigger migration",
      should_migrate_50_to_100(save_data) is False)
# ... and stays stable after a pickle round-trip (save -> load -> re-save)
blob2 = gzip.compress(pickle.dumps(save_data, protocol=pickle.HIGHEST_PROTOCOL))
reloaded = pickle.loads(gzip.decompress(blob2))
check("stamps byte-stable across pickle round-trip",
      reloaded.get("version") == save_data.get("version")
      and reloaded.get("attribute_scale") == 100)
check("reloaded save does not trigger migration",
      should_migrate_50_to_100(reloaded) is False)

# 8. full team pickle round-trip (what the real save path does) ---------
t6 = fresh_team()
t6._lc_auditions = {7: {"partner_pid": 8, "from_line": 0, "to_line": 1,
                        "start_gp": 10, "kind": "heater"}}
d6 = sls._serialize_team(t6)
rt = sls._restore_team(pickle.loads(pickle.dumps(d6)))
check("full team pickle round-trip keeps ledger",
      getattr(rt, "_lc_auditions", None) == t6._lc_auditions)

print(f"\n{ PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
