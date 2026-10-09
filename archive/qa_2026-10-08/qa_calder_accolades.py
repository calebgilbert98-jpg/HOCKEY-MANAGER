"""QA: Calder Cup wins banked as career accolades on players + AHL staff.

Standalone (accolades.py and ahl_league.py are import-clean stdlib-only).
Run: python3 qa_calder_accolades.py
"""
import pickle
import sys

sys.path.insert(0, "/tmp/wt-calder")

import accolades as acc
import ahl_league as ahl


# ---------------------------------------------------------------- mocks
class MockPlayer:
    def __init__(self, name, ovr=72):
        self.name = name
        self._ovr = ovr

    def overall_rating(self):
        return self._ovr


class MockRole:
    def __init__(self, value):
        self.value = value


class MockStaff:
    def __init__(self, name, role_value, assignment):
        self.name = name
        self.role = MockRole(role_value)
        self.assignment = assignment


class MockParent:  # NHL club
    def __init__(self, name):
        self.team_name = name
        self.ahl_roster = []
        self.staff = []


class MockAHL:  # AHL shell
    def __init__(self, name, parent):
        self.team_name = name
        self.league_level = 2
        self.parent_team = parent


class MockLeague:
    def __init__(self, shells):
        self.teams = shells
        self.season_year = 2024
        self.ahl_schedule_label = "2024-25"


def make_champ_setup(n_players=18):
    parent = MockParent("Test NHL Club")
    parent.ahl_roster = [MockPlayer(f"P{i}", 68 + (i % 10)) for i in range(n_players)]
    parent.staff = [
        MockStaff("AHL HC", "Head Coach", "ahl"),
        MockStaff("AHL AC", "Assistant Coach", "ahl"),
        MockStaff("AHL GM", "General Manager", "ahl"),
        MockStaff("NHL HC", "Head Coach", "nhl"),  # must NOT be banked
        MockStaff("AHL Scout", "Amateur Scout", "ahl"),
    ]
    shell = MockAHL("Test Farm Club", parent)
    return shell, parent


PASS = []
FAIL = []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""))


# 1: champion roster players get the accolade
shell, parent = make_champ_setup()
ahl._bank_calder_accolades(shell, "2024-25")
ok = all(
    any(isinstance(e, dict) and e.get("award") == "calder_cup"
        and e.get("year") == "2024-25" for e in (getattr(p, "career_accolades", None) or []))
    for p in parent.ahl_roster
)
check("players_banked", ok and len(parent.ahl_roster) == 18)

# 2: AHL staff banked, NHL-assignment staff NOT banked
staff_acc = {s.name: any(isinstance(e, dict) and e.get("award") == "calder_cup"
                         for e in (getattr(s, "career_accolades", None) or []))
             for s in parent.staff}
check("ahl_staff_banked",
      staff_acc["AHL HC"] and staff_acc["AHL AC"] and staff_acc["AHL GM"]
      and staff_acc["AHL Scout"] and not staff_acc["NHL HC"],
      str(staff_acc))

# 3: display -- label + order (Cup first, Calder Cup second)
p = MockPlayer("Star", 90)
acc.bank_accolade(p, "stanley_cup", "2023-24")
acc.bank_accolade(p, "calder_cup", "2024-25")
acc.bank_accolade(p, "hart", "2025")
grouped = acc.group_accolades(p)
labels = [lbl for lbl, _ in grouped]
check("display_label", ("Calder Cup", ["2024-25"]) in grouped, str(grouped))
check("display_order", labels[:2] == ["Stanley Cup", "Calder Cup"], str(labels))
check("no_clash_with_calder_trophy",
      acc.ACCOLADE_LABELS.get("calder") == "Calder Trophy"
      and acc.ACCOLADE_LABELS.get("calder_cup") == "Calder Cup")

# 4: idempotent -- banking twice never duplicates
before = acc.accolade_count(p)
acc.bank_accolade(p, "calder_cup", "2024-25")
check("idempotent", acc.accolade_count(p) == before)

# 5: persistence -- plain-dict pickle round trip
blob = pickle.dumps(p.career_accolades)
rt = pickle.loads(blob)
check("pickle_roundtrip",
      any(e.get("award") == "calder_cup" and e.get("year") == "2024-25" for e in rt))

# 6: full run_calder_cup path -- champion roster + staff stamped
shells = []
for i in range(16):
    par = MockParent(f"NHL {i}")
    par.ahl_roster = [MockPlayer(f"T{i}P{j}", 70 + (i % 5)) for j in range(20)]
    par.staff = [MockStaff(f"T{i} AHL HC", "Head Coach", "ahl")]
    shells.append(MockAHL(f"Farm {i}", par))
league = MockLeague(shells)
league.ahl_standings = {
    i: {"w": 40 - i, "l": i, "otl": 0, "pts": 80 - 2 * i,
        "gf": 150, "ga": 120, "gp": 48} for i in range(16)
}
info = ahl.run_calder_cup(league)
ok_info = info is not None and isinstance(info.get("champion_idx"), int)
check("full_run_champion", ok_info, str(info))
if ok_info:
    champ_shell = shells[info["champion_idx"]]
    champ_parent = champ_shell.parent_team
    rok = all(any(isinstance(e, dict) and e.get("award") == "calder_cup"
                  and e.get("year") == "2024-25"
                  for e in (getattr(pl, "career_accolades", None) or []))
              for pl in champ_parent.ahl_roster)
    sok = all(any(isinstance(e, dict) and e.get("award") == "calder_cup"
                  for e in (getattr(s, "career_accolades", None) or []))
              for s in champ_parent.staff)
    check("full_run_roster_stamped", rok)
    check("full_run_staff_stamped", sok)
    check("full_run_champions_history",
          isinstance(getattr(league, "ahl_champions", None), list)
          and len(league.ahl_champions) == 1)
    # non-champions untouched
    others = [s for idx, s in enumerate(shells) if idx != info["champion_idx"]]
    untouched = all(not getattr(pl, "career_accolades", None)
                    for s in others for pl in s.parent_team.ahl_roster)
    check("full_run_losers_untouched", untouched)
    # second call is a no-op (once-per-season guard)
    check("full_run_guard", ahl.run_calder_cup(league) is None)

# 7: garbage never raises
for bad in (None, object(), MockAHL("NoParent", None)):
    try:
        ahl._bank_calder_accolades(bad, "")
        ahl._bank_calder_accolades(bad, "2024-25")
    except Exception as e:  # noqa: BLE001
        check(f"garbage_{bad!r}", False, repr(e))
        break
else:
    check("garbage_never_raises", True)
weird_parent = MockParent("Weird")
weird_parent.ahl_roster = None
weird_parent.staff = [None, object(), MockStaff("X", None, None)]
try:
    ahl._bank_calder_accolades(MockAHL("W", weird_parent), "2024-25")
    check("garbage_staff_never_raises", True)
except Exception as e:  # noqa: BLE001
    check("garbage_staff_never_raises", False, repr(e))

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
