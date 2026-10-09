# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: post-fantasy-draft captaincy deferral.

Chris's directive: after a fantasy draft, NO captains until they are set
at the start of preseason.

Covers the real code paths on real Player/Team/League objects:
 1. FantasyDraftView.complete_draft() strips every letter league-wide,
    stamps the deferral flag, and does NOT arm the mandatory picker.
 2. While the deferral window is open, the Continue blocker stays
    suppressed for the human club (GameManager._captaincy_blocker_suppressed).
 3. At the first preseason game day the phase check clears the flag; the
    human club's picker arms via the REAL
    GameManager._opening_night_captaincy_check (never auto-repaired) and
    AI clubs auto-repair to exactly 1 C + 2 As.
 4. The deferral flag survives save/load; old saves without the key
    default to False.
 5. Legal-letter invariant: no club ever wears two Cs through the flow.
"""
import gzip
import os
import pickle
import sys
import tempfile
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name} {detail}")


from game_classes import League, Team, Player
from main import GameManager
import fantasy_draft as fd_mod
from fantasy_draft import FantasyDraftView
from save_load_system import GameSaveManager

FIRST = ["Alex", "Brad", "Cole", "Drew", "Ellis", "Finn", "Gabe", "Hugo",
         "Ivan", "Jake", "Kyle", "Liam"]
LAST = ["Smith", "Jones", "Brown", "Taylor", "Wilson", "Clark", "Lewis",
        "Walker", "Hall", "Young", "King", "Wright"]


def make_player(i, letter):
    p = Player(FIRST[i % 12], LAST[(i * 7) % 12] + str(i), 24, "C", 9,
               captaincy=letter)
    p.leadership = 70 + (i * 13) % 25
    p.captain_tenure_years = 2
    p.alternate_tenure_years = 1
    return p


def make_team(name, letters):
    t = Team(name, name + "ville", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.roster = [make_player(i, letters[i]) for i in range(12)]
    t.ahl_roster = []
    return t


def letters_of(team):
    return [getattr(p, "captaincy", "") or "" for p in team.roster]


def count_letters(team):
    ls = letters_of(team)
    return ls.count("C"), ls.count("A")


# Two clubs wearing full letters, as a draft would scramble them.
user_team = make_team("Users", ["C", "A", "A", "", "", "", "", "", "", "", "", ""])
ai_team = make_team("AIs", ["C", "C", "A", "", "", "", "", "", "", "", "", ""])

league = League("NHL")
league.season_year = 2028
league.teams = [user_team, ai_team]

gm = GameManager.__new__(GameManager)
gm.league = league
gm.user_team = user_team
gm.pending_fantasy_draft = True
gm.app = None                      # headless: picker arms instead of opening
gm._captaincy_choice_pending = False
gm._captaincy_checked_phase = None


class FakeDashboard:
    def refresh_continue_button(self):
        pass


class FakeApp:
    dashboard = FakeDashboard()


# --- 1. complete_draft(): strip letters, stamp flag, do NOT arm picker ---
_orig_showinfo = fd_mod.messagebox.showinfo
fd_mod.messagebox.showinfo = lambda *a, **k: None
try:
    view = FantasyDraftView.__new__(FantasyDraftView)
    view.game_manager = gm
    view.app = FakeApp()
    view.close_view = lambda: None   # tk teardown; not under test
    FantasyDraftView.complete_draft(view)
finally:
    fd_mod.messagebox.showinfo = _orig_showinfo

check("draft cleared pending flag", gm.pending_fantasy_draft is False)
for t in league.teams:
    c, a = count_letters(t)
    check(f"{t.team_name} letter-less after draft", c == 0 and a == 0,
          f"C={c} A={a}")
    check(f"{t.team_name} tenure reset",
          all(getattr(p, "captain_tenure_years", -1) == 0
              and getattr(p, "alternate_tenure_years", -1) == 0
              for p in t.roster))
check("deferral flag stamped",
      getattr(gm, "_fantasy_draft_captaincy_deferred", False) is True)
check("picker NOT armed at draft completion",
      getattr(gm, "_captaincy_choice_pending", True) is False)

# --- 2. Continue blocker suppressed during the deferral window ---
check("blocker suppressed while deferred",
      gm._captaincy_blocker_suppressed() is True)
gm2 = GameManager.__new__(GameManager)
gm2.pending_fantasy_draft = True
check("blocker suppressed while draft in progress",
      gm2._captaincy_blocker_suppressed() is True)

# --- 3. First preseason game day: flag clears, picker arms / AI repairs ---
# This mirrors the phase-check block in HockeyManagerGUI (main.py): clear
# the deferral, then run _opening_night_captaincy_check per club.
gm._fantasy_draft_captaincy_deferred = False   # phase check clears it
gm._opening_night_captaincy_check(user_team, user_team)
gm._opening_night_captaincy_check(ai_team, user_team)

check("deferral over: blocker no longer suppressed",
      gm._captaincy_blocker_suppressed() is False)
check("user picker armed at preseason (never auto-repaired)",
      getattr(gm, "_captaincy_choice_pending", False) is True)
uc, ua = count_letters(user_team)
check("user team still letter-less (awaiting human choice)",
      uc == 0 and ua == 0, f"C={uc} A={ua}")
ac, aa = count_letters(ai_team)
check("AI club auto-repaired to 1C+2A", ac == 1 and aa == 2,
      f"C={ac} A={aa}")

# --- 5. No-two-C invariant across the whole flow ---
for t in league.teams:
    c, _ = count_letters(t)
    check(f"{t.team_name} never wears two Cs", c <= 1, f"C={c}")

# --- 4. Save/load round-trip of the flag ---
gm._fantasy_draft_captaincy_deferred = True
saver = GameSaveManager(gm)
tmp = tempfile.mkdtemp()
path = os.path.join(tmp, "deferral_test.save")
check("save succeeds", saver.save_game(path) is True, path)

gm_fresh = SimpleNamespace(league=None, league_history=None,
                           narrative_ledger=None)
loader = GameSaveManager(gm_fresh)
check("load succeeds", loader.load_game(path) is True, path)
check("deferral flag survives save/load",
      getattr(gm_fresh, "_fantasy_draft_captaincy_deferred", None) is True)

# Old save without the key -> restore loop skips it -> default False.
with gzip.open(path, "rb") as f:
    old_data = pickle.load(f)
old_data.pop("_fantasy_draft_captaincy_deferred", None)
old_path = os.path.join(tmp, "deferral_old.save")
with gzip.open(old_path, "wb") as f:
    pickle.dump(old_data, f, protocol=pickle.HIGHEST_PROTOCOL)
gm_old = SimpleNamespace(league=None, league_history=None,
                         narrative_ledger=None)
check("old save loads", GameSaveManager(gm_old).load_game(old_path) is True)
check("old save defaults flag to missing/False",
      getattr(gm_old, "_fantasy_draft_captaincy_deferred", False) is False)

print(f"\nPASS: {PASS}  FAIL: {FAIL}")
sys.exit(1 if FAIL else 0)
