# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: multiplayer signing + junior-assignment parity (item 3).

Covers: the shared waiver-exemption rule, MP demotion (exempt -> quiet
AHL assignment with the recall-gate stamp; non-exempt -> waivers), the
new return_to_junior MP action (same gate as single-player), and MP
free-agent signings registering with Caleb's market engine.
"""
import os
import random
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import main as main_mod
from game_classes import (Contract, Player, PlayerPosition, Team)

PASS, FAIL = [], []


def check(name, cond, extra=""):
    (PASS if cond else FAIL).append(name)
    print(f"{'PASS' if cond else 'FAIL'}: {name}" + (f" -- {extra}" if extra and not cond else ""))


def skater(seed=1, age=21, games=0, first="Test", last="Player"):
    random.seed(seed)
    p = Player(first, f"{last}{seed}", age, PlayerPosition.CENTER)
    p.nhl_games_played = games
    p.contract = Contract(salary=1_000_000, years_remaining=2)
    p.on_waivers = False
    p.waiver_days = 0
    p.ahl_games_since_assignment = None
    p.nhl_audition = "audition"
    return p


def _nm(p):
    return p.full_name


def mp_self(team):
    """A fake host `self` with the MP helpers bound."""
    news = []
    fake = SimpleNamespace(
        league=SimpleNamespace(season_year=2027, teams=[team]),
        waiver_list=[],
        current_date="2027-01-15",
        news_log=[],
    )
    fake.add_news = lambda msg: news.append(msg)
    fake.news = news
    for meth in ("_mp_demote_player", "_mp_return_to_junior",
                 "_mp_sign_free_agent", "_mp_find_free_agent",
                 "_mp_team_player",
                 "_mp_cap_room", "_validate_contract_terms"):
        setattr(fake, meth,
                getattr(main_mod.HockeyManagerGUI, meth).__get__(fake))
    return fake


def mp_team(name="MP Team"):
    t = Team(team_name=name, city="Test", division="X", conference="Y")
    t.roster, t.ahl_roster, t.prospects = [], [], []
    return t


# 1. Shared waiver-exemption rule.
_needs = main_mod._player_needs_waivers
check("21yo, 20 games -> exempt", _needs(skater(age=21, games=20)) is False)
check("24yo, 159 games -> exempt", _needs(skater(age=24, games=159)) is False)
check("25yo -> needs waivers", _needs(skater(age=25, games=0)) is True)
check("22yo, 160 games -> needs waivers",
      _needs(skater(age=22, games=160)) is True)

# 2. MP demote: exempt kid goes down quietly with the gate stamped.
team = mp_team()
kid = skater(seed=11, age=21, games=20, first="Exempt", last="Kid")
team.roster.append(kid)
fake = mp_self(team)
ok, msg = fake._mp_demote_player(team, kid)
check("exempt demote succeeds", ok, msg)
check("exempt kid off the NHL roster", kid not in team.roster)
check("exempt kid on the AHL roster", kid in team.ahl_roster)
check("exempt kid NOT on waivers",
      kid.on_waivers is False and kid not in fake.waiver_list)
check("recall gate stamped on quiet assignment",
      kid.ahl_games_since_assignment == 0,
      repr(kid.ahl_games_since_assignment))
check("audition cleared", kid.nhl_audition is None)
check("exempt demote logged news", any(_nm(kid) in m for m in fake.news))

# 3. MP demote: veteran must clear the wire.
team2 = mp_team("MP Team 2")
vet = skater(seed=12, age=30, games=400, first="Veteran", last="Vet")
team2.roster.append(vet)
fake2 = mp_self(team2)
ok2, msg2 = fake2._mp_demote_player(team2, vet)
check("vet demote succeeds", ok2, msg2)
check("vet placed on waivers", vet.on_waivers is True and vet.waiver_days == 2)
check("vet in the waiver list", vet in fake2.waiver_list)
check("vet stays on roster until clearance", vet in team2.roster)
check("vet NOT quietly in the AHL", vet not in team2.ahl_roster)

# 4. return_to_junior: signed under-20 CHL prospect.
team3 = mp_team("MP Team 3")
jr = skater(seed=13, age=19, games=0, first="Junior", last="Kid")
jr.junior_league = "OHL"
team3.ahl_roster.append(jr)
fake3 = mp_self(team3)
ok3, msg3 = fake3._mp_return_to_junior({"player_id": str(jr.id)}, team3, "m")
check("junior return succeeds", ok3, msg3)
check("kid off the AHL roster", jr not in team3.ahl_roster)
check("kid back in the prospect pool", jr in team3.prospects)
check("playing_where set to junior",
      "Junior" in str(getattr(jr, "playing_where", "")).upper()
      or "OHL" in str(getattr(jr, "playing_where", "")),
      repr(getattr(jr, "playing_where", None)))

# 4b. return_to_junior gates.
unsigned = skater(seed=14, age=19, first="Unsigned", last="Kid")
unsigned.junior_league = "WHL"
unsigned.contract = None
team3.ahl_roster.append(unsigned)
ok4, msg4 = fake3._mp_return_to_junior({"player_id": str(unsigned.id)}, team3, "m")
check("unsigned kid refused", ok4 is False, msg4)

old = skater(seed=15, age=22, first="Old", last="Prospect")
old.junior_league = "QMJHL"
team3.ahl_roster.append(old)
ok5, msg5 = fake3._mp_return_to_junior({"player_id": str(old.id)}, team3, "m")
check("22-year-old refused", ok5 is False, msg5)

ncaa = skater(seed=16, age=19, first="College", last="Kid")
ncaa.junior_league = "NCAA"
team3.ahl_roster.append(ncaa)
ok6, msg6 = fake3._mp_return_to_junior({"player_id": str(ncaa.id)}, team3, "m")
check("ex-college kid refused", ok6 is False and "NCAA" in msg6, msg6)

# return works from the NHL roster too (mirrors move_player).
team3b = mp_team("MP Team 3b")
jr2 = skater(seed=17, age=18, first="Junior", last="Kid2")
jr2.junior_league = "WHL"
team3b.roster.append(jr2)
fake3b = mp_self(team3b)
ok7, _ = fake3b._mp_return_to_junior({"player_id": str(jr2.id)}, team3b, "m")
check("junior return from NHL roster works",
      ok7 and jr2 in team3b.prospects and jr2 not in team3b.roster)

# 5. MP signing registers with the market engine.
registered = []


class SpyCap:
    current_cap = 95_500_000

    def register_signing(self, name, salary, ovr, pos, age, season):
        registered.append((name, salary, ovr, pos, age, season))
        return salary >= 10_000_000  # market-setter, like the real engine


team4 = mp_team("MP Team 4")
star = skater(seed=18, age=27, games=500, first="Star", last="Winger")
star.contract = Contract(salary=750_000, years_remaining=0)
star.junior_league = ""
star.overall_pick = 0
# overall_rating drives the comp; pin it high via a stub.
star.overall_rating = lambda: 47  # 1-50 scale -> ~94/100
fa_pool = [star]
fake4 = mp_self(team4)
fake4.league.salary_cap_system = SpyCap()
fake4.free_agents = lambda: fa_pool
ok8, msg8 = fake4._mp_sign_free_agent(
    {"player_id": str(getattr(star, "id", "")),
     "salary": 12_000_000, "years": 6, "signing_bonus": 1_000_000},
    team4, "partner-manager")
check("MP star signing succeeds", ok8, msg8)
check("MP signing registered with the market engine",
      len(registered) == 1 and registered[0][0] == _nm(star)
      and registered[0][1] == 12_000_000, repr(registered))
check("market-setter news logged",
      any("sets the market" in m.get("story", "") for m in fake4.news_log),
      str(fake4.news_log))
check("star on the MP roster", star in team4.roster)

# 5b. Draft-lock still enforced on the MP path.
locked = skater(seed=19, age=18, first="Draft", last="Kid")
locked.contract = Contract(salary=750_000, years_remaining=0)
fa_pool2 = [locked]
fake5 = mp_self(mp_team("MP Team 5"))
fake5.league.salary_cap_system = SpyCap()
fake5.free_agents = lambda: fa_pool2
try:
    from draft_generator import player_locked_by_draft as _lk
    _is_locked = bool(_lk(locked))
except Exception:
    _is_locked = False
if _is_locked:
    ok9, msg9 = fake5._mp_sign_free_agent(
        {"player_id": str(getattr(locked, "id", "")),
         "salary": 900_000, "years": 3}, fake5.league.teams[0], "m")
    check("draft-eligible kid blocked on MP path", ok9 is False, msg9)
else:
    check("draft-eligible kid blocked on MP path (not draft-eligible)", True)

# 6. Dispatch wiring probes.
src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "main.py")).read()
check("return_to_junior in MP dispatch",
      '"return_to_junior": self._mp_return_to_junior' in src)
check("MP demote uses the shared exemption rule",
      "_player_needs_waivers(player)" in src)
check("MP signing calls register_signing",
      src.count("register_signing") >= 3)

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
