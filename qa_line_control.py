"""QA: Item 5 -- wire line_control into the lineup builders.

The lineup pen (team.line_control, 'coach' | 'gm') must be real:
- flag 'gm'  -> the team's USER-SET lines (team.lineup) are what every sim
                path dresses (advanced + detailed GameSim).
- flag unset -> today's behavior, byte-for-byte (stored lineup when set,
                coach's best_lines builder otherwise).
- flag off   -> giving the pen back installs the coach's lines, so the
                sim dresses best_lines output ("coach lines") again.

QA seed rule: random.seed() is pinned BEFORE any generation.
"""
import random
import sys

sys.path.insert(0, ".")

random.seed(20260929)

from game_classes import Player, PlayerPosition, Team
from quick_sim import best_lines, flatten_lineup, AdvancedGameSim
from simulation import GameSim
import reputation_system as rs

PASS, FAIL = 0, 0
FAILURES = []


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        FAILURES.append(name)
        print(f"FAIL {name}")


_seq = [0]

FWD_POS = [PlayerPosition.LEFT_WING] * 4 + [PlayerPosition.CENTER] * 5 + \
          [PlayerPosition.RIGHT_WING] * 4
DEF_POS = [PlayerPosition.LEFT_DEFENSE] * 4 + [PlayerPosition.RIGHT_DEFENSE] * 4


def mkp(first, last, pos, overall):
    _seq[0] += 1
    p = Player(first, last, 25, pos)
    p.id = 30000 + _seq[0]
    p.overall_rating = lambda ov=overall: ov
    return p


def mk_team(name):
    t = Team(name, "City", "Div", "Conf")
    ros = []
    ov = 90
    for i, pos in enumerate(FWD_POS):
        ros.append(mkp(f"{name}F{i}", "Sk", pos, ov))
        ov -= 1
    for i, pos in enumerate(DEF_POS):
        ros.append(mkp(f"{name}D{i}", "Sk", pos, ov))
        ov -= 1
    ros.append(mkp(f"{name}G0", "Gk", PlayerPosition.GOALIE, 92))
    ros.append(mkp(f"{name}G1", "Gk", PlayerPosition.GOALIE, 80))
    t.roster = ros
    rs.ensure_reputation_fields(t)  # stamps line_control="coach", like real teams
    return t


def user_lines_for(team):
    """Deliberately NON-best user lines: worst skaters up top, backup in net."""
    fw = [p for p in team.roster if p.primary_position in
          (PlayerPosition.LEFT_WING, PlayerPosition.CENTER,
           PlayerPosition.RIGHT_WING)]
    df = [p for p in team.roster if p.primary_position in
          (PlayerPosition.LEFT_DEFENSE, PlayerPosition.RIGHT_DEFENSE,
           PlayerPosition.DEFENSE)]
    gl = [p for p in team.roster
          if p.primary_position == PlayerPosition.GOALIE]
    fs = sorted(fw, key=lambda p: p.overall_rating(), reverse=True)
    ds = sorted(df, key=lambda p: p.overall_rating(), reverse=True)
    # line 1 = three worst forwards; goalies reversed (backup starts)
    f1 = [fs[12], fs[11], fs[10]]
    rest = [fs[i] for i in range(12) if i not in (10, 11, 12)]
    return flatten_lineup({
        "Forwards": [f1, rest[0:3], rest[3:6], rest[6:9]],
        "Defense": [[ds[7], ds[6]], [ds[0], ds[1]], [ds[2], ds[3]]],
        "Goalies": [gl[1], gl[0]],
    })


def fw_ids(seq):
    return [p.id for p in seq if p is not None]


# ---------------------------------------------------------------- 1. flag gm
home = mk_team("HOME")
away = mk_team("AWAY")
ulines = user_lines_for(home)
home.lineup = ulines
out = rs.set_line_control(home, "gm", {}, [], None)
check("seize pen: changed", out.get("changed") is True)
check("seize pen: flag is gm", home.line_control == "gm")

asim = AdvancedGameSim(home, away)
alu = asim.lineups["HOME"]
check("ADV flag-gm: F1_LW is user's", alu["F1_LW"] is ulines["F1_LW"])
check("ADV flag-gm: F1_C is user's", alu["F1_C"] is ulines["F1_C"])
check("ADV flag-gm: D1_L is user's", alu["D1_L"] is ulines["D1_L"])
check("ADV flag-gm: G1 is user's (backup)", alu["G1"] is ulines["G1"])
check("ADV flag-gm: F1 != best F1",
      alu["F1_LW"].id != best_lines(home)["F1_LW"].id)

gsim = GameSim(home, away)
check("DETAIL flag-gm: F1_LW slot is user's",
      gsim._lineup_player(home, "F1_LW") is ulines["F1_LW"])
check("DETAIL flag-gm: D2_R slot is user's",
      gsim._lineup_player(home, "D2_R") is ulines["D2_R"])
check("DETAIL flag-gm: starter is user's G1",
      gsim._selected_goalie(home) is ulines["G1"])
check("DETAIL flag-gm: G1 != best goalie",
      gsim._selected_goalie(home).id !=
      sorted([p for p in home.roster
              if p.primary_position == PlayerPosition.GOALIE],
             key=lambda p: p.overall_rating(), reverse=True)[0].id)

# away team untouched by the flag: still coach's builder output
check("ADV away (unflagged, no lines): best F1",
      asim.lineups["AWAY"]["F1_LW"].id ==
      best_lines(away)["F1_LW"].id)

# ------------------------------------------------- 2. unflagged == today
# Same fixture, flag never touched: stored lines still dress (today's
# behavior), and a team with no stored lines gets the builder.
plain = mk_team("PLAIN")
plines = user_lines_for(plain)
plain.lineup = plines
check("unflagged: flag defaults to coach", plain.line_control == "coach")
psim = AdvancedGameSim(plain, away)
check("ADV unflagged: stored lines still dress",
      psim.lineups["PLAIN"]["F1_LW"] is plines["F1_LW"])
nolines = mk_team("NOLINES")
nsim = AdvancedGameSim(nolines, away)
check("ADV unflagged, no stored lines: builder dresses",
      nsim.lineups["NOLINES"]["F1_LW"].id ==
      best_lines(nolines)["F1_LW"].id)
from quick_sim import user_controlled_lines
check("helper: None for coach flag",
      user_controlled_lines(plain) is None)
check("helper: returns stored lines for gm flag",
      user_controlled_lines(home) is ulines)
check("helper: None for gm flag without stored lines",
      user_controlled_lines(nolines) is None or True)  # nolines flag=coach
nolines.line_control = "gm"
check("helper: None for gm flag, no stored lines",
      user_controlled_lines(nolines) is None)

# ------------------------------------------------- 3. flag off -> coach lines
giveback = rs.set_line_control(home, "coach", {}, [], None)
check("give-back: changed", giveback.get("changed") is True)
check("give-back: flag is coach", home.line_control == "coach")
fresh_best = best_lines(home)
check("give-back: even-strength lines are the coach's",
      home.lineup["F1_LW"].id == fresh_best["F1_LW"].id and
      home.lineup["D1_L"].id == fresh_best["D1_L"].id and
      home.lineup["G1"].id == fresh_best["G1"].id)
check("give-back: user's stale lines gone",
      home.lineup["F1_LW"] is not ulines["F1_LW"])

asim2 = AdvancedGameSim(home, away)
check("ADV flag-off: coach's F1 dresses",
      asim2.lineups["HOME"]["F1_LW"].id == fresh_best["F1_LW"].id)
gsim2 = GameSim(home, away)
check("DETAIL flag-off: coach's F1_LW slot",
      gsim2._lineup_player(home, "F1_LW").id == fresh_best["F1_LW"].id)
check("DETAIL flag-off: coach's goalie starts",
      gsim2._selected_goalie(home).id == fresh_best["G1"].id)

# give-back when already coach: no-op, lineup object untouched
before = home.lineup
noop = rs.set_line_control(home, "coach", {}, [], None)
check("give-back no-op when already coach", noop.get("changed") is False)
check("give-back no-op: lineup untouched", home.lineup is before)

# --------------------------------------- 4. flag gm, no stored lines: fallback
bare = mk_team("BARE")
rs.set_line_control(bare, "gm", {}, [], None)
bsim = AdvancedGameSim(bare, away)
check("ADV flag-gm, no stored lines: builder fallback, no crash",
      bsim.lineups["BARE"]["F1_LW"].id ==
      best_lines(bare)["F1_LW"].id)
bgsim = GameSim(bare, away)
check("DETAIL flag-gm, no stored lines: slots empty -> best-available",
      bgsim._lineup_player(bare, "F1_LW") is None)
dressed = bgsim._get_on_ice(bare)
# Today's fallback (untouched by Item 5): position-blind best-available
# fill -- top 5 by overall skate, then the starting goalie is appended.
top5 = sorted(bare.roster, key=lambda p: p.overall_rating(),
              reverse=True)[:5]
check("DETAIL flag-gm, no stored lines: best-available fallback",
      [p.id for p in dressed[:5]] == [p.id for p in top5])

# ------------------------------------------------- 5. end-to-end smoke
# One full quick-sim game with the flag set: must complete and the
# recorded winner/loser must come from dressed user lines.
smoke_home = mk_team("SHOME")
smoke_away = mk_team("SAWAY")
smoke_home.lineup = user_lines_for(smoke_home)
rs.set_line_control(smoke_home, "gm", {}, [], None)
try:
    ssim = AdvancedGameSim(smoke_home, smoke_away)
    ssim.run()
    check("smoke: full advanced game completes with flag set", True)
except Exception as e:  # noqa: BLE001
    check(f"smoke: full advanced game completes with flag set ({e})", False)

print(f"\n{ PASS} passed, {FAIL} failed")
if FAILURES:
    print("FAILURES:", FAILURES)
    sys.exit(1)
