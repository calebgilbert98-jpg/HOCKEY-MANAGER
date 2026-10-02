# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: draft agency -- user picks are never auto-drafted; Sim Pick = head scout.

Covers (Muck 2026-10-02):
1. conduct_entry_draft NEVER auto-drafts user picks by default
   (allow_user_autodraft=False) -- parks a session instead.
2. allow_user_autodraft=True restores the old headless behavior (bulk sims).
3. park_draft_for_user builds a live session journal.
4. user_pick_slots finds user-owned overalls.
5. head_scout_pick: scout quality influences the pick; never raises;
   returns rationale.
6. team_delegates_to_scout: explicit flag + elite-scout default.
7. get_head_scout finds HEAD_SCOUT staff.
"""
import os
import random
import sys
import types
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, FAILURES = 0, 0, []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")


import draft_night as dn
from game_classes import DraftPick, League, Staff, StaffRole, Team


class FakePick(DraftPick):
    def __init__(self, rnd, team_name):
        super().__init__(year=2029, round=rnd, original_team=team_name,
                         current_team=team_name)
        self.overall_pick = None


def make_team(name, idx=0):
    t = Team(name, f"City{idx}", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    return t


def make_scout(jpa, jpp):
    s = Staff(first_name="Test", last_name="Scout",
              role=StaffRole.HEAD_SCOUT)
    s.judging_player_ability = jpa
    s.judging_player_potential = jpp
    return s


def make_prospect(pid, ranking, grade="B", pos="C"):
    p = SimpleNamespace(
        id=pid, full_name=f"Prospect {pid}",
        draft_ranking=ranking, potential_grade=grade,
        primary_position=SimpleNamespace(value=pos),
        skating=70, shooting=70, hockey_iq=70,
        draft_reentry_from="",
    )
    return p


def make_league(n_teams=4, year=2029, user_club="UserClub"):
    lg = League("NHL")
    lg.season_year = year
    lg.draft_prospects_year = year
    lg.teams = [make_team(f"Club{i}", i) for i in range(n_teams)]
    if user_club:
        lg.teams[0].team_name = user_club
    for t in lg.teams:
        t._picks = []
    for rnd in range(1, 8):
        for t in lg.teams:
            t._picks.append(FakePick(rnd, t.team_name))

    def _get_picks_for_year(self, yr):
        return [p for p in self._picks if p.year == yr]
    for t in lg.teams:
        t.get_picks_for_year = types.MethodType(_get_picks_for_year, t)
    lg.standings = {t.team_name: {"Points": 100 - i * 10}
                    for i, t in enumerate(lg.teams)}
    lg.draft_prospects = [make_prospect(f"p{i}", 90 - i) for i in range(40)]
    lg.draft_conducted_years = []
    lg.draft_held_years = []
    lg.lottery_results = {}
    return lg


# --- 1. get_head_scout -------------------------------------------------
t0 = make_team("Testers")
check("no scout -> None", dn.get_head_scout(t0) is None)
t0.staff = [make_scout(70, 70)]
check("head scout found", dn.get_head_scout(t0) is not None)
check("head scout JPA", dn.get_head_scout(t0).judging_player_ability == 70)

# --- 2. team_delegates_to_scout ----------------------------------------
t1 = make_team("Delegators")
t1.staff = []
check("no scout -> no delegate", dn.team_delegates_to_scout(t1) is False)
t1.staff = [make_scout(85, 85)]
check("elite scout -> delegates", dn.team_delegates_to_scout(t1) is True)
t1.staff = [make_scout(60, 60)]
check("average scout -> no delegate", dn.team_delegates_to_scout(t1) is False)
t1.draft_scout_delegate = True
check("explicit flag -> delegates", dn.team_delegates_to_scout(t1) is True)

# --- 3. head_scout_pick --------------------------------------------------
prospects = [make_prospect(f"sp{i}", 95 - i * 2,
                           grade="A" if i < 3 else "B") for i in range(12)]
rng = random.Random(42)
t2 = make_team("ScoutTeam")
t2.staff = [make_scout(90, 90)]
sel, rationale = dn.head_scout_pick(t2, prospects, None, [], 1, None, rng,
                                    overall=1)
check("scout pick returns player", sel is not None)
check("scout pick rationale non-empty", isinstance(rationale, str)
      and len(rationale) > 10, rationale[:60])
check("rationale mentions scout take", "take:" in rationale.lower(),
      rationale[:60])

t3 = make_team("BadScoutTeam")
t3.staff = [make_scout(20, 20)]
sel3, rat3 = dn.head_scout_pick(t3, prospects, None, [], 1, None,
                               random.Random(42), overall=1)
check("bad scout still picks", sel3 is not None)
check("bad scout never raises", isinstance(rat3, str))

t4 = make_team("NoScoutTeam")
t4.staff = []
sel4, rat4 = dn.head_scout_pick(t4, prospects, None, [], 1, None,
                               random.Random(42), overall=1)
check("no scout still picks", sel4 is not None)

sel5, rat5 = dn.head_scout_pick(t2, [], None, [], 1, None,
                               random.Random(42), overall=1)
check("empty pool -> None", sel5 is None)

# --- 4. user_pick_slots ---------------------------------------------------
lg = make_league(user_club="UserClub")
slots = dn.user_pick_slots(lg, "UserClub", 2029)
check("user has 7 picks", len(slots) == 7, f"got {len(slots)}")
check("slots sorted", slots == sorted(slots))
check("no user -> []", dn.user_pick_slots(lg, "", 2029) == [])
check("garbage -> []", dn.user_pick_slots(None, "X", 2029) == [])

# --- 5. conduct_entry_draft NEVER auto-drafts user picks ------------------
lg2 = make_league(user_club="UserClub")
app = SimpleNamespace(user_team=lg2.teams[0])
app.add_news = lambda s: None

picks = dn.conduct_entry_draft(lg2, 2029, app=app)
check("default: no picks made", picks == [], f"got {len(picks)}")
sess = getattr(lg2, 'entry_draft_session', None)
check("default: session parked", sess is not None)
if sess is not None:
    check("session is EntryDraftSession",
          isinstance(sess, dn.EntryDraftSession))
    check("session live for 2029", sess.is_live_for(2029))
check("user got no prospects",
      len(getattr(lg2.teams[0], 'prospects', []) or []) == 0)

# Explicit opt-in: old headless behavior (bulk sims).
lg3 = make_league(user_club="UserClub")
app3 = SimpleNamespace(user_team=lg3.teams[0])
app3.add_news = lambda s: None
for t in lg3.teams:
    t.prospects = []
    t.add_player = lambda p, where='prospects', _t=t: _t.prospects.append(p)
lg3.stamp_draft_rights = lambda p, tn, yr: None
picks3 = dn.conduct_entry_draft(lg3, 2029, app=app3,
                               allow_user_autodraft=True)
check("opt-in: picks made", len(picks3) > 0, f"got {len(picks3)}")
_user_picks3 = [p for p in picks3 if p[0] == "UserClub"]
check("opt-in: user picks drafted", len(_user_picks3) == 7,
      f"got {len(_user_picks3)}")

# No user team: headless runs normally.
lg4 = make_league()
for t in lg4.teams:
    t.prospects = []
    t.add_player = lambda p, where='prospects', _t=t: _t.prospects.append(p)
lg4.stamp_draft_rights = lambda p, tn, yr: None
picks4 = dn.conduct_entry_draft(lg4, 2029, app=None)
check("no user: headless runs", len(picks4) > 0)

# --- 6. park + second call defers -----------------------------------------
lg5 = make_league(user_club="UserClub")
app5 = SimpleNamespace(user_team=lg5.teams[0])
app5.add_news = lambda s: None
ok = dn.park_draft_for_user(lg5, 2029, app=app5)
check("park returns True", ok is True)
_ps = getattr(lg5, 'entry_draft_session', None)
check("parked session live",
      _ps is not None and _ps.is_live_for(2029))
picks5 = dn.conduct_entry_draft(lg5, 2029, app=app5)
check("second call defers", picks5 == [])

print(f"\nPASS {PASS}  FAIL {FAIL}")
for f in FAILURES:
    print("FAIL:", f)
sys.exit(1 if FAIL else 0)
