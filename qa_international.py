"""QA: international windows (international.py + wiring).

Uses lightweight fakes for players/teams/league so the suite runs in
~1s without the app's heavy player generator.
"""
import random
import sys

sys.path.insert(0, ".")

import international as itl

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


class FakePos:
    def __init__(self, name):
        self.name = name


class FakePlayer:
    _n = 0

    def __init__(self, nation, overall, goalie=False, age=25):
        FakePlayer._n += 1
        self.first_name = "Test"
        self.last_name = f"Player{FakePlayer._n}"
        self.nationality = nation
        self.primary_position = FakePos("GOALIE" if goalie else "CENTER")
        self._ov = overall
        self.age = age
        self.is_injured = False
        self.injury_proneness = 10
        self.reputation = 0
        self.archetype = "Playmaker"

    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def overall_rating(self):
        return self._ov


class FakeTeam:
    def __init__(self, name, league_name="National Hockey League"):
        self.team_name = name
        self.league_name = league_name
        self.roster = []
        self.prospects = []


class FakeLeague:
    def __init__(self, teams):
        self.teams = teams
        self.intl_held = {"olympics": [], "worlds": []}
        self.intl_history = []
        self.playoff_bracket = None


class FakeApp:
    def __init__(self, league, user_team):
        self.league = league
        self.user_team = user_team


def make_league(n_teams=4, nations=None, seed=7):
    rng = random.Random(seed)
    nations = nations or itl.CANDIDATE_NATIONS[:8]
    teams = [FakeTeam(f"Team{i}") for i in range(n_teams)]
    for t in teams:
        for nat in nations:
            for _ in range(4):
                t.roster.append(
                    FakePlayer(nat, rng.randint(72, 92),
                               age=rng.randint(19, 36)))
            t.roster.append(FakePlayer(nat, rng.randint(74, 90),
                                       goalie=True))
    lg = FakeLeague(teams)
    return lg, teams


# -- 1: olympic years ----------------------------------------------------------
check("2026 olympic", itl.is_olympic_year(2026))
check("2030 olympic", itl.is_olympic_year(2030))
check("2027 not", not itl.is_olympic_year(2027))
check("2028 not", not itl.is_olympic_year(2028))

# -- 2: nation mapping -----------------------------------------------------------
p = FakePlayer("x", 80)
for raw, want in [("Canada", "Canada"), ("Canadian", "Canada"),
                  ("USA", "USA"), ("Russia", "Russia"),
                  ("Sweden", "Sweden"), ("Finland", "Finland"),
                  ("Finnish", "Finland"),
                  ("Czech Republic", "Czechia"),
                  ("Switzerland", "Switzerland"), ("Swiss", "Switzerland"),
                  ("Germany", "Germany"), ("Slovakia", "Slovakia"),
                  ("Latvia", "Latvia"), ("Mars", "")]:
    p.nationality = raw
    check(f"nation {raw}", itl._nation_of(p) == want, itl._nation_of(p))

# -- 3: olympics run ---------------------------------------------------------------
lg, teams = make_league()
app = FakeApp(lg, teams[0])
res = itl.hold_olympics(app, 2026, random.Random(11))
check("olympics result", res is not None)
if res is None:
    print(f"\n{PASS} passed, {FAIL} failed")
    sys.exit(1)
check("distinct medals",
      len({res["gold"], res["silver"], res["bronze"]}) == 3,
      str({k: res[k] for k in ("gold", "silver", "bronze")}))
check("held recorded", 2026 in lg.intl_held["olympics"])
check("history recorded",
      any(h["year"] == 2026 and h["event"] == "olympics"
          for h in lg.intl_history))
check("no double-hold", lg.intl_held["olympics"].count(2026) == 1)

# -- 4: bonds between NHL teammates + chemistry hook -------------------------------
pair = None
for t in teams:
    ros = list(t.roster)
    for i in range(len(ros)):
        for j in range(i + 1, len(ros)):
            if itl.intl_bond(ros[i], ros[j]) > 0:
                pair = (ros[i], ros[j])
                break
        if pair:
            break
    if pair:
        break
check("bonded NHL teammates found", pair is not None)
check("bond event tagged",
      pair is not None and "2026" in itl.intl_bond_event(*pair),
      itl.intl_bond_event(*pair) if pair else "")
if pair:
    from player_archetypes import line_chemistry_report
    total, drivers = line_chemistry_report(list(pair))
    check("chemistry driver mentions bond",
          any("international bond" in d[0] for d in drivers),
          str([d[0] for d in drivers]))
    check("bond adds positive value",
          any("international bond" in d[0] and d[1] > 0 for d in drivers))

# -- 5: injuries happen (seeded, high rate) -------------------------------------------
lg2, teams2 = make_league(seed=9)
app2 = FakeApp(lg2, teams2[0])
res2 = itl._hold(app2, 2026, "olympics", "Olympic hockey", worlds=False,
                 injury_pct=0.9, max_injury_games=8,
                 rng=random.Random(5))
check("injuries at 90% rate", len(res2["hurt_lines"]) > 0)
victim = None
for t in teams2:
    for pl in t.roster:
        if pl.is_injured and getattr(pl, "last_injury", ""):
            victim = pl
            break
    if victim:
        break
check("injury fields set",
      victim is not None and 1 <= victim.games_remaining_injured <= 8)

# -- 6: reputation bumps for medalists -------------------------------------------------
found = any((pl.reputation or 0) >= 8 for t in teams for pl in t.roster)
check("medal reputation bumped", found)

# -- 7: worlds exclude playoff teams ----------------------------------------------------
lg3, teams3 = make_league(seed=13)


class FakeBracket:
    def __init__(self, east, west):
        self.eastern_teams = east
        self.western_teams = west


lg3.playoff_bracket = FakeBracket(teams3[:2], teams3[2:])
pool = itl._eligible_players(lg3, worlds=True)
pool_teams = {t.team_name for _p, t in pool}
playoff_names = {t.team_name for t in teams3}
check("worlds exclude playoff teams", not (pool_teams & playoff_names))
check("worlds include nobody (all in playoffs)", len(pool) == 0)

lg3b, teams3b = make_league(n_teams=8, seed=14)
lg3b.playoff_bracket = FakeBracket([teams3b[0]], [teams3b[1]])
poolb = itl._eligible_players(lg3b, worlds=True)
poolb_teams = {t.team_name for _p, t in poolb}
check("worlds include non-playoff",
      poolb_teams == {f"Team{i}" for i in range(2, 8)}, str(poolb_teams))
# Prospects are eligible at the worlds (crossover territory).
teams3b[2].prospects.append(FakePlayer("Canada", 68, age=19))
poolc = itl._eligible_players(lg3b, worlds=True)
check("worlds include prospects",
      any(pl.age == 19 for pl, _t in poolc))
app3 = FakeApp(lg3b, teams3b[2])
res3 = itl.hold_worlds(app3, 2027, random.Random(3))
check("worlds result", res3 is not None)
check("worlds held recorded", 2027 in lg3b.intl_held["worlds"])

# -- 8: card text ----------------------------------------------------------------------------
txt = itl.result_card_text(res)
check("card has medals",
      "GOLD" in txt and "SILVER" in txt and "BRONZE" in txt)
check("card mentions MVP", "MVP" in txt, txt[:160])
check("card lists user players", "Your players" in txt, txt[:400])

# -- 9: crossover picks a U23 ------------------------------------------------------------------
yp = FakePlayer("Canada", 84, age=20)
yt = FakeTeam("TeamX")
yp.reputation = 5
rosters = {"Canada": {"nation": "Canada", "roster": [(yp, yt)],
                      "strength": 90.0, "_medal": "gold"}}
bracket = {"gold": "Canada", "silver": "USA", "bronze": "Sweden",
           "games": []}
scores = [(yp, yt, 25.0)]
cons = itl._apply_consequences(rosters, bracket, scores, "Test 2026",
                               random.Random(1), 0.0, 3, "")
check("crossover line names him",
      yp.full_name() in cons["crossover_line"],
      cons["crossover_line"][:120])
check("crossover rep bump", (yp.reputation or 0) >= 10,
      str(yp.reputation))

# -- 10: winners are plausible (strength matters, not deterministic) -----------------------------
rosters10 = {}
for i, nat in enumerate(itl.CANDIDATE_NATIONS[:8]):
    ros = []
    for k in range(18):
        ros.append((FakePlayer(nat, 88 if nat == "Canada" else 80), None))
    rosters10[nat] = {"nation": nat, "roster": ros,
                      "strength": 88.0 if nat == "Canada" else 80.0}
wins = {}
for s in range(60):
    br = itl._resolve_bracket(
        {n: dict(r) for n, r in rosters10.items()}, random.Random(s))
    wins[br["gold"]] = wins.get(br["gold"], 0) + 1
check("stacked Canada wins most", wins.get("Canada", 0) >= 30,
      str(wins))
check("not always Canada", wins.get("Canada", 0) < 60, str(wins))

# -- 11: too few nations -> None --------------------------------------------------------------------
lg5, teams5 = make_league(nations=["Canada"])
app5 = FakeApp(lg5, teams5[0])
check("single nation -> None",
      itl.hold_olympics(app5, 2026, random.Random(1)) is None)

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
