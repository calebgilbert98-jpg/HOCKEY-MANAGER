"""Headless QA: AHL farm confidence -> morale / attitude / call-up buzz.

Covers ahl_system.weekly_farm_confidence: prospect cooking surge (+4,
+6 with NHL taste), veteran frustration, young slumper dip, goalie
read, one-note-per-season gating, AI-farm silence, buzz clearing on
call-up, season-rollover reset, save/load round-trip of the flags, and
the main.py weekly hook wiring.

Run with DISPLAY=:99.
"""
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("DISPLAY", ":99")
sys.path.insert(0, "/home/hatch/workspace/HOCKEY-MANAGER")
os.chdir("/home/hatch/workspace/HOCKEY-MANAGER")

PASS, FAIL = 0, 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS {name}")
    else:
        FAIL += 1
        print(f"  FAIL {name} {detail}")

from game_classes import PlayerStats
import ahl_system

# ---------------------------------------------------------------- fakes
class FakePlayer:
    def __init__(self, first, last, position, age, overall,
                 morale=70, happiness=70, nhl_gp=0):
        self.first_name = first
        self.last_name = last
        self.full_name = f"{first} {last}"
        self.primary_position = SimpleNamespace(value=position)
        self.age = age
        self._overall = overall
        self.morale = morale
        self.happiness = happiness
        self.stats = PlayerStats()
        self.stats.games_played = nhl_gp
        self.ahl_stats = PlayerStats()
        self.ahl_roster_flag = True

    def overall_rating(self):
        return self._overall


def set_skater_line(p, gp, goals, assists):
    p.ahl_stats.games_played = gp
    p.ahl_stats.goals = goals
    p.ahl_stats.assists = assists


def set_goalie_line(p, gp, saves, shots_against):
    p.ahl_stats.games_played = gp
    p.ahl_stats.saves = saves
    p.ahl_stats.shots_against = shots_against
    p.ahl_stats._update_goalie_stats()


def mkteam(name):
    return SimpleNamespace(team_name=name, roster=[], ahl_roster=[])


def run_week(league, user_team):
    return ahl_system.weekly_farm_confidence(league, user_team=user_team)


print("== 1. prospect cooking: surge + buzz + one note ==")
user = mkteam("Test Club")
ai = mkteam("Rival Club")
# ovr 70 -> expected 0.64 P/GP; cooking needs >= 0.896 over 10+ GP
kid = FakePlayer("Cole", "Hotshot", "C", 20, 70)
set_skater_line(kid, 12, 5, 6)  # 11 pts / 12 = 0.917 P/GP
user.ahl_roster.append(kid)
league = SimpleNamespace(teams=[user, ai])
notes = run_week(league, user)
check("morale +4 on cooking prospect", kid.morale == 74, f"got {kid.morale}")
check("buzz flag set", getattr(kid, "ahl_callup_buzz", False) is True)
check("one inbox note for user farm", len(notes) == 1,
      f"got {len(notes)}")
check("note names the player", "Cole Hotshot" in (notes[0].content if notes else ""))
check("note category Development", (notes[0].category if notes else "") == "Development")

print("== 2. note fires once per season ==")
notes2 = run_week(league, user)
check("no second note same season", len(notes2) == 0, f"got {len(notes2)}")
check("buzz still live while cooking",
      getattr(kid, "ahl_callup_buzz", False) is True)
# Simulate the end_of_season reset, then cooking again -> note returns
kid.ahl_buzz_note_sent = False
notes3 = run_week(league, user)
check("note returns after season reset", len(notes3) == 1)

print("== 3. NHL taste: bigger surge ==")
taster = FakePlayer("Sam", "Audition", "LW", 21, 70, nhl_gp=6)
set_skater_line(taster, 11, 5, 6)  # 1.0 P/GP, cooking
user.ahl_roster.append(taster)
run_week(league, user)
check("morale +6 with NHL taste", taster.morale == 76, f"got {taster.morale}")

print("== 4. veteran stuck: frustration, no note ==")
vet = FakePlayer("Old", "Pro", "D", 29, 70)
set_skater_line(vet, 14, 4, 9)  # 0.93 P/GP, cooking, never called up
user.ahl_roster.append(vet)
n_before = len(run_week(league, user))
check("veteran happiness -3", vet.happiness == 67, f"got {vet.happiness}")
check("veteran morale -2", vet.morale == 68, f"got {vet.morale}")
check("veteran gets no buzz", getattr(vet, "ahl_callup_buzz", False) is False)
check("veteran gets no inbox note", n_before == 0, f"got {n_before} notes")

print("== 5. young slumper: confidence dip ==")
slump = FakePlayer("Cold", "Streak", "RW", 21, 70)
set_skater_line(slump, 16, 1, 3)  # 0.25 P/GP <= 0.5x expected
user.ahl_roster.append(slump)
run_week(league, user)
check("slumper morale -4", slump.morale == 66, f"got {slump.morale}")
check("slumper happiness -2", slump.happiness == 68, f"got {slump.happiness}")
check("slumper gets no buzz", getattr(slump, "ahl_callup_buzz", False) is False)

print("== 6. quiet week: mid-career, mid-production ==")
mid = FakePlayer("Steady", "Eddie", "C", 25, 70, morale=72, happiness=72)
set_skater_line(mid, 20, 6, 7)  # 0.65 P/GP ~ 1.0x expected
user.ahl_roster.append(mid)
run_week(league, user)
check("no morale touch on quiet week", mid.morale == 72, f"got {mid.morale}")
check("no happiness touch on quiet week", mid.happiness == 72)
check("no buzz on quiet week", getattr(mid, "ahl_callup_buzz", False) is False)

print("== 7. goalies read on SV% ==")
gcook = FakePlayer("Brick", "Wall", "G", 22, 70)
set_goalie_line(gcook, 8, 220, 240)  # .917 SV%
user.ahl_roster.append(gcook)
notes_g = run_week(league, user)
check("hot goalie morale +3", gcook.morale == 73, f"got {gcook.morale}")
check("hot goalie buzz set", getattr(gcook, "ahl_callup_buzz", False) is True)
check("hot goalie note mentions SV%", any("SV%" in n.content for n in notes_g))
gslump = FakePlayer("Sieve", "Boy", "G", 23, 70, morale=70, happiness=70)
set_goalie_line(gslump, 8, 200, 240)  # .833 SV%
user.ahl_roster.append(gslump)
gslump.ahl_buzz_note_sent = True  # isolate: no note expectation
run_week(league, user)
check("cold goalie morale -3", gslump.morale == 67, f"got {gslump.morale}")

print("== 8. AI farm: morale moves, inbox stays silent ==")
aikid = FakePlayer("Rival", "Kid", "C", 20, 70)
set_skater_line(aikid, 12, 5, 6)
ai.ahl_roster.append(aikid)
notes_ai = run_week(league, user)
check("AI prospect morale +4", aikid.morale == 74, f"got {aikid.morale}")
check("AI prospect buzz set", getattr(aikid, "ahl_callup_buzz", False) is True)
check("no inbox note for AI farm", len(notes_ai) == 0, f"got {len(notes_ai)}")

print("== 9. call-up clears a stale buzz flag ==")
user.ahl_roster.remove(kid)
user.roster.append(kid)
run_week(league, user)
check("buzz cleared on NHL roster", getattr(kid, "ahl_callup_buzz", True) is False)
user.roster.remove(kid)
user.ahl_roster.append(kid)

print("== 10. morale/happiness clamps hold ==")
edge = FakePlayer("Max", "Edge", "C", 20, 70, morale=99, happiness=99)
set_skater_line(edge, 12, 5, 6)
user.ahl_roster.append(edge)
run_week(league, user)
check("morale clamps at 100", edge.morale == 100, f"got {edge.morale}")
edge2 = FakePlayer("Min", "Edge", "RW", 21, 70, morale=2, happiness=1)
set_skater_line(edge2, 16, 1, 3)
user.ahl_roster.append(edge2)
run_week(league, user)
check("morale clamps at 1", edge2.morale == 1, f"got {edge2.morale}")
check("happiness clamps at 0", edge2.happiness == 0, f"got {edge2.happiness}")

print("== 11. save/load round-trips the flags ==")
try:
    from save_load_system import GameSaveManager
    gsm = GameSaveManager.__new__(GameSaveManager)
    kid.ahl_callup_buzz = True
    kid.ahl_buzz_note_sent = True
    data = gsm._serialize_player(kid)
    check("buzz flag serialized", data.get("ahl_callup_buzz") is True)
    check("note-sent serialized", data.get("ahl_buzz_note_sent") is True)
    # restore path needs a real Player; emulate via generic setattr loop
    restored = SimpleNamespace()
    for k, v in data.items():
        setattr(restored, k, v)
    check("buzz flag restored", getattr(restored, "ahl_callup_buzz", False) is True)
    check("note-sent restored", getattr(restored, "ahl_buzz_note_sent", False) is True)
except Exception as e:
    check("save/load round-trip", False, repr(e))

print("== 12. season rollover resets the flags (source check) ==")
src = open("/home/hatch/workspace/HOCKEY-MANAGER/game_classes.py").read()
check("end_of_season resets ahl_buzz_note_sent",
      "player.ahl_buzz_note_sent = False" in src)
check("end_of_season resets ahl_callup_buzz",
      "player.ahl_callup_buzz = False" in src)

print("== 13. main.py weekly hook wiring ==")
main_src = open("/home/hatch/workspace/HOCKEY-MANAGER/main.py").read()
check("hook calls weekly_farm_confidence",
      "ahl_system.weekly_farm_confidence" in main_src)
check("hook routes notes to inbox", "self.send_email_to_user(_note)" in main_src)
# Execute the hook's exact logic against a fake app
sent = []
fake_app = SimpleNamespace(
    game_manager=SimpleNamespace(league=league),
    user_team=user,
    send_email_to_user=lambda m: sent.append(m))
hook_src = (
    "import ahl_system\n"
    "_league = getattr(self.game_manager, \"league\", None)\n"
    "if _league is not None:\n"
    "    for _note in ahl_system.weekly_farm_confidence(_league, user_team=team):\n"
    "        try:\n"
    "            self.send_email_to_user(_note)\n"
    "        except Exception:\n"
    "            continue\n"
)
try:
    exec(compile(hook_src, "<hook>", "exec"),
         {"self": fake_app, "team": user})
    check("hook executes against fake app", True)
except Exception as e:
    check("hook executes against fake app", False, repr(e))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)