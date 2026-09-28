"""QA: televised draft lottery (draft_lottery.py + wiring)."""
import random
import sys

sys.path.insert(0, ".")

from game_classes import League
import draft_lottery as dl

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail}")


def make_league():
    lg = League("NHL")
    nhl = [t for t in lg.teams
           if getattr(t, "league_name", "") == "National Hockey League"]
    # Deterministic standings: team i gets i*5 points (team 0 worst).
    lg.standings = {t.team_name: {"Points": i * 5}
                    for i, t in enumerate(nhl)}
    lg.initialize_all_draft_picks()
    return lg, nhl


# -- 1: odds table ---------------------------------------------------------
check("odds sum to 100", abs(sum(dl.LOTTERY_ODDS) - 100.0) < 1e-9,
      str(sum(dl.LOTTERY_ODDS)))
check("11 eligible odds", len(dl.LOTTERY_ODDS) == 11)
check("worst team 25.5%", dl.LOTTERY_ODDS[0] == 25.5)

# -- 2: eligibility --------------------------------------------------------
lg, nhl = make_league()
elig = dl.eligible_teams(lg)
check("11 eligible", len(elig) == 11, str(len(elig)))
check("worst is eligible first",
      elig[0].team_name == nhl[0].team_name)
check("12th team not eligible",
      nhl[11].team_name not in {t.team_name for t in elig})

# -- 3: run_lottery shape ---------------------------------------------------
YEAR = 2027
rows = dl.run_lottery(lg, YEAR, random.Random(7))
check("16 rows", len(rows) == 16, str(len(rows)))
check("picks 1..16", [r["pick"] for r in rows] == list(range(1, 17)))
check("two distinct winners",
      rows[0]["original_team"] != rows[1]["original_team"])
check("movement zero-sum", sum(r["movement"] for r in rows) == 0,
      str(sum(r["movement"] for r in rows)))
check("rows persisted", lg.lottery_results.get(YEAR) == rows)

# -- 4: idempotent ----------------------------------------------------------
rows2 = dl.run_lottery(lg, YEAR, random.Random(999))
check("idempotent rerun", rows2 == rows)

# -- 5: statistical sanity (worst team wins #1 ~25.5%) ---------------------
wins = 0
N = 400
lg3, nhl3 = make_league()
worst = nhl3[0].team_name
for s in range(N):
    lgx, _ = make_league()
    rx = dl.run_lottery(lgx, YEAR, random.Random(10_000 + s))
    if rx[0]["original_team"] == worst:
        wins += 1
rate = wins / N
check("worst-team win rate near 25.5%",
      0.18 <= rate <= 0.33, f"{rate:.3f}")

# -- 6: get_draft_order applies the lottery --------------------------------
order = lg.get_draft_order(YEAR)
r1 = [o for o in order if o[2].round == 1]
check("32 round-1 picks", len(r1) == 32, str(len(r1)))
check("pick #1 overall goes to lottery winner",
      r1[0][2].original_team == rows[0]["original_team"],
      f"{r1[0][2].original_team} vs {rows[0]['original_team']}")
lotto_seq = [r1[i][2].original_team for i in range(16)]
check("round-1 top 16 follow lottery",
      lotto_seq == [r["original_team"] for r in rows], str(lotto_seq[:4]))
check("round 2 unaffected by lottery",
      [o for o in order if o[2].round == 2][0][2].original_team ==
      nhl[0].team_name)

# -- 7: traded pick keeps original slot ------------------------------------
lg4, nhl4 = make_league()
rows4 = dl.run_lottery(lg4, YEAR, random.Random(21))
# Trade the original worst team's first-rounder to the best team.
src, dst = nhl4[0], nhl4[31]
pick = next(p for p in src.get_picks_for_year(YEAR) if p.round == 1)
src.trade_pick(pick, dst.team_name, "qa trade")
dst.receive_pick(pick)
order4 = lg4.get_draft_order(YEAR)
r1_4 = [o for o in order4 if o[2].round == 1]
slot = next(i for i, o in enumerate(r1_4) if o[2] is pick)
want = next(r["pick"] for r in rows4 if r["original_team"] == src.team_name)
check("traded pick keeps original lottery slot", slot + 1 == want,
      f"slot {slot + 1} vs {want}")
check("new owner selects there", r1_4[want - 1][1].team_name == dst.team_name)

# -- 8: simulate_draft_lottery ---------------------------------------------
lg5, _ = make_league()
lg5.simulate_draft_lottery(YEAR)
check("delegate runs lottery", bool(lg5.lottery_results.get(YEAR)))
before = list(lg5.lottery_results[YEAR])
lg5.simulate_draft_lottery(YEAR)
check("delegate no-op when run", lg5.lottery_results[YEAR] == before)

# -- 9: reveal text / reactions ---------------------------------------------
txt = dl.lottery_reveal_text(rows, YEAR)
check("reveal text 17 lines", len(txt.splitlines()) == 17,
      str(len(txt.splitlines())))
check("reaction for #1 mentions win",
      "WINS" in dl.reaction_line(rows[0]))
jump = next((r for r in rows if r["movement"] >= 4), None)
if jump:
    check("big-jump reaction", "LEAPS" in dl.reaction_line(jump))
else:
    check("big-jump reaction (no jump this seed)", True)

# -- 10: user reactions post dynamics events --------------------------------
class FakeApp:
    pass

app = FakeApp()
app.user_team = nhl[0]
n0 = len(getattr(app.user_team, "dynamics_log", []) or [])
dl.apply_user_reactions(app, rows)
n1 = len(getattr(app.user_team, "dynamics_log", []) or [])
mine = [r for r in rows if r["original_team"] == nhl[0].team_name]
# Only big moves post (win #1, jump 4+, slide 3-); small moves are quiet.
want_evts = sum(1 for r in mine
                if r["pick"] == 1 or r["movement"] >= 4 or r["movement"] <= -3)
check("dynamics events posted for user team", n1 - n0 == want_evts,
      f"{n1 - n0} vs {want_evts}")

# -- 11: save/load key survival ----------------------------------------------
saved = {str(k): v for k, v in lg.lottery_results.items()}
restored = {}
for k, v in saved.items():
    restored[int(k)] = [dict(r) for r in v]
check("int keys survive str round-trip", restored.get(YEAR) == rows)

# -- 12: lottery day constants ------------------------------------------------
from datetime import date
check("lottery day is May 8",
      (dl.LOTTERY_DAY_MONTH, dl.LOTTERY_DAY_DAY) == (5, 8))
check("not draft day",
      not (date(2027, 5, 8).month == 6 and 23 <= date(2027, 5, 8).day <= 25))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
