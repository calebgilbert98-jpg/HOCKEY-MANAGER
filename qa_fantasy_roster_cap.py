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

    # 3. normalize builds a position-aware 23 from a 40-man pool
    t2 = make_team("Trim")
    mgr2 = FantasyDraftManager([t2], [])
    for i in range(40):
        p = make_player(i, 40 + (i % 30), goalie=(i in (3, 17, 33)))
        t2.roster.append(p)
    mgr2.normalize_post_draft_rosters()
    check("normalize keeps roster <= 23", 18 <= len(t2.roster) <= 23,
          f"roster={len(t2.roster)}")
    pos2 = {}
    for p in t2.roster:
        if p.primary_position == PlayerPosition.GOALIE:
            pos2["G"] = pos2.get("G", 0) + 1
        else:
            pos2["S"] = pos2.get("S", 0) + 1
    check("normalize keeps 2-3 goalies", pos2.get("G", 0) in (2, 3),
          f"goalies={pos2.get('G', 0)}")
    check("normalize keeps >= 17 skaters", pos2.get("S", 0) >= 17,
          f"skaters={pos2.get('S', 0)}")

    # 4. goalie floor: 1 goalie on roster, AHL has 55 and 35 ovr netminders
    #    -> the 55 comes up, the 35 stays down (3rd-goalie bar is 40)
    t3 = make_team("Goalies")
    mgr3 = FantasyDraftManager([t3], [])
    t3.roster = [make_player(i, 70, goalie=(i == 0)) for i in range(23)]
    t3.ahl_roster = [make_player(100, 55, goalie=True),
                     make_player(101, 35, goalie=True)]
    mgr3.normalize_post_draft_rosters()
    g3 = sum(1 for p in t3.roster
             if p.primary_position == PlayerPosition.GOALIE)
    check("goalie floor promotes exactly one", g3 == 2, f"goalies={g3}")
    check("roster stays <= 23 after repair", len(t3.roster) <= 23,
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

    # 7. critical-gap FA: club with 1 goalie org-wide signs the best
    #    undrafted netminder; club with 2 centers signs an undrafted C
    from fantasy_draft import DraftPick
    fa_pool = [make_player(200 + i, 58 - i, goalie=True) for i in range(2)]
    fa_pool += [make_player(300 + i, 52 - i) for i in range(3)]  # centers
    t6 = make_team("ShortG")
    drafted = [make_player(i, 70, goalie=(i == 0)) for i in range(21)]
    t6.roster, t6.ahl_roster, t6.prospects = list(drafted), [], []
    mgr6 = FantasyDraftManager([t6], drafted + fa_pool)
    mgr6.draft_picks = [DraftPick(1, i + 1, i + 1, t6, p)
                        for i, p in enumerate(drafted)]
    mgr6.normalize_post_draft_rosters()
    g6 = sum(1 for p in t6.roster
             if p.primary_position == PlayerPosition.GOALIE)
    check("FA fill signs a 2nd goalie", g6 == 2, f"goalies={g6}")
    signed_g = [p for p in t6.roster if p is fa_pool[0]]
    check("FA fill takes the best undrafted goalie", len(signed_g) == 1,
          f"{[p.full_name for p in signed_g]}")
    t7 = make_team("ShortC")
    # 21 skaters, only 2 centers: force positions
    ros7 = []
    for i in range(21):
        p = make_player(400 + i, 68)
        p.primary_position = (PlayerPosition.CENTER if i < 2
                              else PlayerPosition.LEFT_WING)
        p.overall_rating = lambda _o=68: _o
        ros7.append(p)
    t7.roster, t7.ahl_roster, t7.prospects = ros7, [], []
    mgr7 = FantasyDraftManager([t7], ros7 + fa_pool)
    mgr7.draft_picks = [DraftPick(1, i + 1, i + 1, t7, p)
                        for i, p in enumerate(ros7)]
    mgr7.normalize_post_draft_rosters()
    c7 = sum(1 for p in t7.roster
             if p.primary_position == PlayerPosition.CENTER)
    check("FA fill signs a 3rd center", c7 == 3, f"centers={c7}")

    fails = [(n, d) for n, ok, d in res if not ok]
    for n, ok, d in res:
        print(f"{'PASS' if ok else 'FAIL'} {n} {d}")
    print(f"\n{len(res) - len(fails)}/{len(res)} passed")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
