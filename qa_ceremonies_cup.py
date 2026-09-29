"""QA: 2026-27 jersey retirement ceremonies + Stanley Cup awarding recap.
Run: python3 qa_ceremonies_cup.py
"""
import sys
from datetime import date
from types import SimpleNamespace

sys.path.insert(0, ".")

import immortality as im

passed, failed = [], []


def check(label, cond, detail=""):
    (passed if cond else failed).append(label)
    extra = f" -- {detail}" if detail and not cond else ""
    print(f"  {'PASS' if cond else 'FAIL'} {label}{extra}")


def make_team(name):
    return SimpleNamespace(team_name=name, league_name="National Hockey League",
                           roster=[], ahl_roster=[], retired_numbers=[],
                           head_coach=None)


def make_player(fn, ln, pos="CENTER", number=0, captaincy=None, age=25,
                games=200, pts=150, accolades=(), pgoals=0, passt=0, pgp=0):
    return SimpleNamespace(
        first_name=fn, last_name=ln,
        primary_position=SimpleNamespace(name=pos, value="G" if pos == "GOALIE" else "S"),
        jersey_number=number, preferred_number=0, second_number=0,
        jersey_number_since=None, captaincy=captaincy, age=age,
        career_games=games, career_points=pts,
        career_accolades=list(accolades),
        playoff_stats=SimpleNamespace(goals=pgoals, assists=passt,
                                      games_played=pgp))


league = SimpleNamespace(teams=[], season_year=2026)
bos = make_team("Boston Bruins")
ana = make_team("Anaheim Ducks")
lak = make_team("Los Angeles Kings")
league.teams = [bos, ana, lak]

# --- 1. ceremonies fire on their real dates, with a 60-day catch-up window --
# (date jumps / bulk sims must not silently drop a ceremony)
due = im.ceremonies_due(league, date(2026, 12, 1))
check("Bergeron ceremony due Dec 1 2026",
      len(due) == 1 and due[0][1]["player"] == "Patrice Bergeron"
      and due[0][1]["number"] == 37 and due[0][0] is bos)
due = im.ceremonies_due(league, date(2026, 12, 2))
check("Bergeron still due Dec 2 via catch-up",
      len(due) == 1 and due[0][1]["player"] == "Patrice Bergeron",
      str([d[1]["player"] for d in due]))
due = im.ceremonies_due(league, date(2027, 1, 30))
check("Getzlaf ceremony due Jan 30 2027",
      any(d[1]["player"] == "Ryan Getzlaf" and d[0] is ana for d in due),
      str([d[1]["player"] for d in due]))
due = im.ceremonies_due(league, date(2027, 2, 24))
check("Kopitar ceremony due Feb 24 2027",
      any(d[1]["player"] == "Anze Kopitar" and d[0] is lak for d in due),
      str([d[1]["player"] for d in due]))
check("Bergeron expired by Feb 24 (85 days > 60-day window)",
      not any(d[1]["player"] == "Patrice Bergeron" for d in due))

# --- 2b. first-season-relative scheduling -----------------------------------
sched = im.ceremony_schedule_for(2028)
check("schedule anchors to inaugural season",
      [c["date"] for c in sched] == ["2028-12-01", "2029-01-30", "2029-02-24"],
      str([c["date"] for c in sched]))
league_rel = SimpleNamespace(teams=[make_team("Boston Bruins")],
                             ceremony_schedule=sched, season_year=2028)
check("relative date fires in that season's first year",
      len(im.ceremonies_due(league_rel, date(2028, 12, 1))) == 1)
check("absolute 2026 date does NOT fire for a 2028 league",
      im.ceremonies_due(league_rel, date(2026, 12, 1)) == [])

# --- 2c. old-save backfill: past-dated ceremonies retire quietly -------------
old_league = SimpleNamespace(teams=[make_team("Boston Bruins"),
                                    make_team("Anaheim Ducks"),
                                    make_team("Los Angeles Kings")],
                             season_year=2029)  # no ceremony_schedule: old save
notes = im.retire_overdue_ceremonies(old_league, date(2029, 6, 1))
check("all three overdue numbers retired",
      all(im.is_number_retired(t, n)
          for t, n in zip(old_league.teams, (37, 15, 11))),
      str(notes))
check("backfill notes name the legends",
      all(nm in " ".join(notes)
          for nm in ("Bergeron", "Getzlaf", "Kopitar")))
notes2 = im.retire_overdue_ceremonies(old_league, date(2029, 6, 2))
check("backfill is idempotent", notes2 == [])
fresh_old = SimpleNamespace(teams=[make_team("Boston Bruins")],
                            season_year=2026)
check("future ceremonies not backfilled early",
      im.retire_overdue_ceremonies(fresh_old, date(2026, 11, 1)) == []
      and not im.is_number_retired(fresh_old.teams[0], 37))
# --- 2. staging retires the number with the REAL name -------------------------
team, cer = im.ceremonies_due(league, date(2026, 12, 1))[0]
# a generated Bruin currently wears 37
wearer = make_player("Gen", "Eric", number=37)
wearer.preferred_number, wearer.second_number = 11, 22
bos.roster.append(wearer)
story = im.stage_ceremony(team, cer)
check("37 retired in Boston", im.is_number_retired(bos, 37))
check("story uses the real name",
      "Patrice Bergeron" in story and "37" in story)
check("incumbent moved off 37", wearer.jersey_number != 37,
      f"wearing {wearer.jersey_number}")
check("incumbent got his favorite", wearer.jersey_number == 11,
      f"wearing {wearer.jersey_number}")
check("ceremony is idempotent",
      im.ceremonies_due(league, date(2026, 12, 1)) == [])

# --- 3. Cup recap -------------------------------------------------------------
champ = make_team("Boston Bruins")
opp = make_team("Edmonton Oilers")
capt = make_player("Cap", "Tain", number=10, captaincy="C", age=32,
                   games=900, pts=800, pgoals=10, passt=14, pgp=24)
smythe = make_player("Smy", "The", number=91, age=27, games=500, pts=600,
                     pgoals=14, passt=18, pgp=24)
vet = make_player("Old", "Timer", number=4, age=38, games=1300, pts=700,
                  pgoals=4, passt=9, pgp=24)
hero = make_player("He", "Ro", number=20, age=25, games=300, pts=350,
                   pgoals=11, passt=12, pgp=24)
champ.roster = [capt, smythe, vet, hero]
champ.head_coach = SimpleNamespace(first_name="Bench", last_name="Boss")
series = SimpleNamespace(team1=champ, team2=opp, team1_wins=4, team2_wins=2,
                         winner=champ)
bracket = SimpleNamespace(
    stanley_cup_champion=champ,
    playoff_series={"stanley_cup_final": [series]},
    conn_smythe_winner=smythe, conn_smythe_name="Smy The")
league2 = SimpleNamespace(season_year=2026)

story = im.build_cup_recap(champ, bracket, league2)
check("recap names the champions", "Boston Bruins" in story)
check("recap has the series score", "4-2" in story and "Edmonton Oilers" in story)
check("recap names the Conn Smythe", "Smy The" in story and "Conn Smythe" in story)
check("recap has Smythe's line", "14G-18A" in story)
check("captain lifts first", "Cap Tain" in story and "first skate" in story)
check("veteran lifts second", "Old Timer" in story)
check("first-Cup veteran story", "finally a champion" in story)
check("hero line present", "He Ro (11G-12A, 24 GP)" in story)
check("coach interview present", "Bench Boss" in story and '"' in story)
print()
print("---- sample recap ----")
print(story)
print("----------------------")

# --- 4. second carrier who already won: no false first-Cup claim --------------
vet2 = make_player("Ring", "Bearer", number=8, age=36, games=1200, pts=650,
                   accolades=({"award": "stanley_cup", "year": "2022-23"},),
                   pgoals=2, passt=5, pgp=24)
champ2 = make_team("Boston Bruins")
champ2.roster = [capt, vet2]
champ2.head_coach = champ.head_coach
story2 = im.build_cup_recap(champ2, bracket, league2)
check("repeat winner not called first-timer",
      "finally a champion" not in story2 and "Ring Bearer" in story2)

# --- 5. send-once logic -------------------------------------------------------
class FakeApp:
    def __init__(self):
        self.league = SimpleNamespace(
            season_year=2026, cup_recap_sent=None,
            playoff_bracket=bracket)
        self.news_log = []
        self.current_date = date(2027, 6, 15)

import main as _main_mod  # noqa: E402  (import for the method only)
app = FakeApp()
# call the unbound method logic directly via a bound shim
sent = _main_mod.HockeyManagerGUI._maybe_send_cup_recap(app)
check("recap sent once", sent and len(app.news_log) == 1)
check("flag stamped", app.league.cup_recap_sent == "2026:Boston Bruins")
sent2 = _main_mod.HockeyManagerGUI._maybe_send_cup_recap(app)
check("no double-send", not sent2 and len(app.news_log) == 1)

print()
print(f"{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
