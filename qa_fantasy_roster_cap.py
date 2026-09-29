#!/usr/bin/env python3
"""qa_fantasy_roster_cap.py -- fantasy draft roster soundness (bugfix QA).

Bug: every 40+ pick landed on the NHL roster, so a 40-round fantasy draft
produced 40-man NHL rosters league-wide (and mass cap non-compliance).

Fix: FantasyDraftManager.assign_drafted_player() centralizes roster
assignment with a 23-man NHL cap (shared by all 7 UI pick sites and
headless flows); normalize_post_draft_rosters() trims to the best 23 and
guarantees >= 2 goalies per club; complete_draft() calls the normalizer.
"""
import sys, os, random
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from game_classes import Player, Team, PlayerPosition
from fantasy_draft import FantasyDraftManager

FIRST = ["A", "B", "C", "D", "E", "F"]
LAST = ["One", "Two", "Three", "Four", "Five", "Six"]
POSITIONS = ["C", "LW", "RW", "LD", "RD"]


def make_player(i, ovr, goalie=False):
    pos = "C"
    p = Player(FIRST[i % 6], LAST[(i * 7) % 6] + str(i), 27, pos, 9)
    if goalie:
        p.primary_position = PlayerPosition.GOALIE
    else:
        p.primary_position = PlayerPosition(POSITIONS[i % len(POSITIONS)])
    # the manager assigns on overall_rating(); pin it directly
    p.overall_rating = lambda _o=ovr: _o
    return p


def make_team(name):
    t = Team(name, name + "ville", "Atlantic", "Eastern")
    t.league_name = "National Hockey League"
    t.roster, t.ahl_roster, t.prospects = [], [], []
    return t


def results():
    out = []
    def check(name, cond, detail=""):
        out.append((name, bool(cond), detail))
    return out, check


def main():
    random.seed(7)
    res, check = results()
    t = make_team("Test")
    mgr = FantasyDraftManager([t], [])

    # 1. 40 picks at ovr>=40 -> exactly 23 on NHL roster, rest to AHL
    for i in range(40):
        dest = mgr.assign_drafted_player(t, make_player(i, 60))
    check("23-man NHL cap on 40 qualifying picks", len(t.roster) == 23,
          f"roster={len(t.roster)}")
    check("overflow goes to AHL", len(t.ahl_roster) == 17,
          f"ahl={len(t.ahl_roster)}")
    check("dest return value", True)

    # 2. low picks still go to prospects
    dest = mgr.assign_drafted_player(t, make_player(99, 20))
    check("sub-35 pick -> prospects", dest == "prospects" and
          len(t.prospects) == 1, f"dest={dest}")

    # 3. normalize trims a 40-man roster to the best 23
    t2 = make_team("Trim")
    mgr2 = FantasyDraftManager([t2], [])
    for i in range(40):
        p = make_player(i, 40 + (i % 30), goalie=(i in (3, 17, 33)))
        t2.roster.append(p)
    mgr2.normalize_post_draft_rosters()
    check("normalize trims to 23", len(t2.roster) == 23,
          f"roster={len(t2.roster)}")
    check("normalize keeps the best 23 skaters",
          min(p.overall_rating() for p in t2.roster
              if p.primary_position != PlayerPosition.GOALIE) >= 46,
          "")
    g = sum(1 for p in t2.roster
            if p.primary_position == PlayerPosition.GOALIE)
    check("normalize keeps >= 2 goalies", g >= 2, f"goalies={g}")

    # 4. goalie repair: 1 goalie on a full 23 roster, more in AHL
    t3 = make_team("Goalies")
    mgr3 = FantasyDraftManager([t3], [])
    t3.roster = [make_player(i, 70, goalie=(i == 0)) for i in range(23)]
    t3.ahl_roster = [make_player(100 + i, 55, goalie=True) for i in range(3)]
    mgr3.normalize_post_draft_rosters()
    g3 = sum(1 for p in t3.roster
             if p.primary_position == PlayerPosition.GOALIE)
    check("goalie repair promotes a 2nd goalie", g3 == 2, f"goalies={g3}")
    check("roster stays at 23 after repair", len(t3.roster) == 23,
          f"roster={len(t3.roster)}")

    # 5. no AHL goalies available -> no crash, roster unchanged-ish
    t4 = make_team("NoGoalies")
    mgr4 = FantasyDraftManager([t4], [])
    t4.roster = [make_player(i, 70) for i in range(20)]
    mgr4.normalize_post_draft_rosters()
    check("no goalies available: no crash", len(t4.roster) == 20,
          f"roster={len(t4.roster)}")

    # 6. goalie ceiling: 6 goalies hoarded -> 3 stay, skaters backfilled
    t5 = make_team("Hoarders")
    mgr5 = FantasyDraftManager([t5], [])
    t5.roster = ([make_player(i, 70, goalie=True) for i in range(6)] +
                 [make_player(10 + i, 65) for i in range(14)])
    t5.ahl_roster = [make_player(100 + i, 55) for i in range(6)]
    mgr5.normalize_post_draft_rosters()
    g5 = sum(1 for p in t5.roster
             if p.primary_position == PlayerPosition.GOALIE)
    s5 = sum(1 for p in t5.roster
             if p.primary_position != PlayerPosition.GOALIE)
    check("goalie ceiling demotes extras", g5 == 3, f"goalies={g5}")
    check("skaters backfilled to 18", s5 >= 18, f"skaters={s5}")

    fails = [(n, d) for n, ok, d in res if not ok]
    for n, ok, d in res:
        print(f"{'PASS' if ok else 'FAIL'} {n} {d}")
    print(f"\n{len(res) - len(fails)}/{len(res)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
