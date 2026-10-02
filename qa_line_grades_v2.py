#!/usr/bin/env python3
"""QA for line grades v2 (Muck 2026-10-02): grades must be intuitive.

5.0 = average game, 7.0+ = great, <=3.0 = poor. Shutdown lines that
play well but don't score must NOT get 2.5s anymore.
"""
import sys, os
sys.path.insert(0, '/tmp/wt-grades')
os.chdir('/tmp/wt-grades')

passed, failed = [], []
def check(name, cond, extra=""):
    (passed if cond else failed).append(name)
    print(("PASS " if cond else "FAIL ") + name + (f" [{extra}]" if extra and not cond else ""))

from game_classes import PlayerPosition
from mesh_system import compute_skater_game_grade_v2

class FakePlayer:
    def __init__(self, pos, overall):
        self.primary_position = pos
        self._ovr = overall
        self.full_name = f"Test {pos.value}"
    def overall_rating(self):
        return self._ovr

def gs(**kw):
    base = {'g': 0, 'a': 0, 'shots_on_goal': 0, 'hits': 0, 'takeaways': 0,
            'giveaways': 0, 'faceoffs_won': 0, 'faceoffs_lost': 0}
    base.update(kw)
    return base

# --- the core complaint: shutdown D, great game, no points ---
shut_d = FakePlayer(PlayerPosition.LEFT_DEFENSE, 82)
grade, why = compute_skater_game_grade_v2(
    shut_d, gs(blocked_shots_by=4, hits=3, takeaways=2, plus_minus=2))
check("shutdown D solid game >= 5.5", grade >= 5.5, f"got {grade}")
check("shutdown D not a 2.5", grade > 4.0, f"got {grade}")
check("shutdown D why mentions blocks", "blk" in why, f"why={why!r}")

# --- 3-point star game should be high ---
star_c = FakePlayer(PlayerPosition.CENTER, 92)
grade, why = compute_skater_game_grade_v2(
    star_c, gs(g=2, a=1, shots_on_goal=5, hits=1, plus_minus=2))
check("3-pt star game >= 7.5", grade >= 7.5, f"got {grade}")
check("3-pt star why has points", "2G" in why and "1A" in why, f"why={why!r}")

# --- quiet grinder game: ~5.0, not 2.5 ---
grinder = FakePlayer(PlayerPosition.LEFT_WING, 76)
grade, why = compute_skater_game_grade_v2(grinder, gs(shots_on_goal=1, hits=2))
check("quiet grinder game 4.0-6.0", 4.0 <= grade <= 6.0, f"got {grade}")

# --- scoreless star: dinged but not destroyed ---
grade2, _ = compute_skater_game_grade_v2(star_c, gs(shots_on_goal=2))
check("scoreless star below 5.0", grade2 < 5.0, f"got {grade2}")
check("scoreless star above 3.5", grade2 > 3.5, f"got {grade2}")

# --- stinker: giveaways + minus ---
bad, why3 = compute_skater_game_grade_v2(
    grinder, gs(giveaways=3, plus_minus=-3, shots_on_goal=0))
check("stinker below 4.0", bad < 4.0, f"got {bad}")
check("stinker why notes giveaways", "gv" in why3, f"why={why3!r}")

# --- faceoffs matter for centers ---
grade_fo, why_fo = compute_skater_game_grade_v2(
    star_c, gs(faceoffs_won=12, faceoffs_lost=4))
grade_nofo, _ = compute_skater_game_grade_v2(star_c, gs())
check("faceoff dominance helps", grade_fo > grade_nofo,
      f"{grade_fo} vs {grade_nofo}")
check("FO% in why", "FO" in why_fo, f"why={why_fo!r}")

# --- AdvGS path: 'blocked_shots' key (defensive roll), no 'blocked_shots_by' ---
adv_d = FakePlayer(PlayerPosition.RIGHT_DEFENSE, 80)
grade_adv, _ = compute_skater_game_grade_v2(
    adv_d, {'g': 0, 'a': 0, 'shots_on_goal': 1, 'hits': 2, 'takeaways': 1,
            'giveaways': 0, 'faceoffs_won': 0, 'faceoffs_lost': 0,
            'blocked_shots': 3})
check("AdvGS blocked_shots counts as defense", grade_adv >= 5.5,
      f"got {grade_adv}")

# --- GameSim path: 'blocked_shots' means shooter's shots blocked (ignore) ---
gsim_f = FakePlayer(PlayerPosition.RIGHT_WING, 84)
grade_gsim, _ = compute_skater_game_grade_v2(
    gsim_f, gs(shots_on_goal=4, blocked_shots=3, blocked_shots_by=0))
grade_clean, _ = compute_skater_game_grade_v2(
    gsim_f, gs(shots_on_goal=4, blocked_shots_by=0))
check("GameSim shooter-blocked not counted as defense",
      abs(grade_gsim - grade_clean) < 0.01, f"{grade_gsim} vs {grade_clean}")

# --- goalie ---
goalie = FakePlayer(PlayerPosition.GOALIE, 88)
gg, gwhy = compute_skater_game_grade_v2(
    goalie, {'saves': 31, 'shots_against': 34, 'goals_against': 3})
check("goalie .912 ~ above 5", gg > 5.0, f"got {gg}")
check("goalie why has saves", "31/34" in gwhy, f"why={gwhy!r}")
gg2, _ = compute_skater_game_grade_v2(
    goalie, {'saves': 28, 'shots_against': 28, 'goals_against': 0})
check("shutout goalie high", gg2 >= 8.0, f"got {gg2}")
gg3, _ = compute_skater_game_grade_v2(goalie, {'saves': 0, 'shots_against': 0})
check("goalie no shots -> None grade", gg3 is None, f"got {gg3}")

# --- never raises on garbage ---
for bad_in in [None, {}, "x", {'g': 'abc'}]:
    try:
        r = compute_skater_game_grade_v2(grinder, bad_in)
        ok = isinstance(r, tuple) and len(r) == 2
    except Exception:
        ok = False
    check(f"never raises on {bad_in!r}", ok)
try:
    r = compute_skater_game_grade_v2(None, gs())
    check("never raises on None player", isinstance(r, tuple))
except Exception:
    check("never raises on None player", False)

# --- grade bounds ---
for _ in range(20):
    import random
    p = FakePlayer(random.choice([PlayerPosition.CENTER,
                                  PlayerPosition.LEFT_WING,
                                  PlayerPosition.RIGHT_DEFENSE]),
                   random.randint(60, 95))
    gr, wh = compute_skater_game_grade_v2(p, gs(
        g=random.randint(0, 4), a=random.randint(0, 4),
        shots_on_goal=random.randint(0, 8), hits=random.randint(0, 6),
        takeaways=random.randint(0, 3), giveaways=random.randint(0, 3),
        blocked_shots_by=random.randint(0, 5)))
    if gr is None or not (0.0 <= gr <= 10.0):
        check("grade in [0,10]", False, f"got {gr}")
        break
else:
    check("grade in [0,10] (20 fuzz)", True)

# --- compute_line_ratings integration ---
from game_box_score import compute_line_ratings
class P(FakePlayer):
    _ids = iter(range(1000, 2000))
    def __init__(self, pos, ovr):
        super().__init__(pos, ovr)
        self.id = next(P._ids)
        self.full_name = f"P{self.id}"
ps = [P(PlayerPosition.CENTER, 90), P(PlayerPosition.LEFT_WING, 84),
      P(PlayerPosition.RIGHT_WING, 82)]
by_id = {p.id: p for p in ps}
gstats = {ps[0].id: gs(g=1, a=1, shots_on_goal=4),
          ps[1].id: gs(shots_on_goal=2, hits=3, takeaways=1),
          ps[2].id: gs(a=1, blocked_shots_by=1)}
lines = compute_line_ratings({'Forwards': [[p.id for p in ps]]}, gstats, by_id)
check("line ratings returns 1 line", len(lines) == 1)
L = lines[0]
check("line rating is mean of grades", abs(L['rating'] - sum(
    pl['grade'] for pl in L['players']) / 3) < 0.11, f"{L['rating']}")
check("players carry why strings", all('why' in pl for pl in L['players']))
check("star has points in why", "1G" in L['players'][0]['why'],
      f"{L['players'][0]['why']!r}")
# missing player -> skipped entirely, rating from known players only
lines2 = compute_line_ratings({'Forwards': [[ps[0].id, 99999]]}, gstats, by_id)
check("missing pid skipped", len(lines2[0]['players']) == 1)
check("rating from known players only",
      abs(lines2[0]['rating'] - lines2[0]['players'][0]['grade']) < 0.01)

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
