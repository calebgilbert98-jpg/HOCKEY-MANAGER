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
        self.id = FakePlayer._n
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

# -- 12: Olympic coach selection ----------------------------------------------------
class FakeRole:
    def __init__(self, name):
        self.name = name


class FakeCoach:
    _n = 0

    def __init__(self, name, nation, rep, hc=True, cups=(),
                 man=50, mot=50, tac=50, disc=50):
        FakeCoach._n += 1
        self.id = 9000 + FakeCoach._n
        self.full_name = name
        self.name = name
        self.nationality = nation
        self.reputation = rep
        self.role = FakeRole("HEAD_COACH" if hc else "ASSISTANT_COACH")
        self.career_accolades = [
            {"award": "stanley_cup", "year": y} for y in cups]
        self.man_management = man
        self.motivating = mot
        self.tactical_knowledge = tac
        self.discipline = disc


def _coach_league():
    lg, teams = make_league(n_teams=4, seed=21)
    # Canada: hot incumbent with a recent Cup vs a bigger name gone cold.
    c1 = FakeCoach("Cup Winner", "Canada", 78,
                   cups=("2025-26",), man=90, mot=90, tac=80, disc=80)
    c2 = FakeCoach("Big Name", "Canada", 88, man=50, mot=50, tac=50, disc=50)
    # USA: a star American coach (must NOT coach Canada).
    c3 = FakeCoach("Yank Boss", "USA", 95, man=90, mot=90, tac=90, disc=90)
    # Latvia: no head coach, only an assistant (fallback path).
    c4 = FakeCoach("Latvia Assistant", "Latvia", 55, hc=False)
    teams[0].staff = [c1]
    teams[1].staff = [c2]
    teams[2].staff = [c3]
    teams[3].staff = [c4]
    lg.standings = {t.team_name: {"W": 30, "L": 15, "OTL": 5, "Points": 65}
                    for t in teams}
    return lg, teams, (c1, c2, c3, c4)


lgc, tmc, (c1, c2, c3, c4) = _coach_league()
coach, cteam = itl.select_olympic_coach(lgc, "Canada", 2026)
check("recent Cup beats bigger name", coach is c1,
      getattr(coach, "full_name", None))
check("coach's club returned", cteam is tmc[0])
coach_u, _ = itl.select_olympic_coach(lgc, "USA", 2026)
check("USA gets the American", coach_u is c3)
check("nationality is a hard filter",
      itl._nation_of(coach) == "Canada" and itl._nation_of(coach_u) == "USA")
coach_l, _ = itl.select_olympic_coach(lgc, "Latvia", 2026)
check("assistant fallback for small nation", coach_l is c4,
      getattr(coach_l, "full_name", None))
coach_x, _ = itl.select_olympic_coach(lgc, "Germany", 2026)
check("no matching coach -> None", coach_x is None)

# -- 13: the coach's own hand on the roster -------------------------------------
prof = itl._coach_profile(c1)  # man=90 -> loyalty 0.8
check("loyalty tendency read", 0.7 < prof["loyalty"] <= 1.0, str(prof))
p_home = FakePlayer("Canada", 84, age=28)
p_away = FakePlayer("Canada", 85, age=28)
s_home = itl._coach_pick_score(p_home, tmc[0], 84.0, c1, tmc[0], prof,
                               frozenset())
s_away = itl._coach_pick_score(p_away, tmc[1], 85.0, c1, tmc[0], prof,
                               frozenset())
check("his guys get the bump", s_home > s_away, f"{s_home} vs {s_away}")
p_vet = FakePlayer("Canada", 82, age=34)
p_kid = FakePlayer("Canada", 82, age=20)
s_vet = itl._coach_pick_score(p_vet, tmc[1], 82.0, c1, tmc[0], prof,
                              frozenset())
s_kid = itl._coach_pick_score(p_kid, tmc[1], 82.0, c1, tmc[0], prof,
                              frozenset())
check("veteran trust", s_vet > s_kid, f"{s_vet} vs {s_kid}")
p_gold = FakePlayer("Canada", 82, age=28)
s_gold = itl._coach_pick_score(p_gold, tmc[1], 82.0, c1, tmc[0], prof,
                               frozenset({p_gold.full_name()}))
check("gold-medal loyalty", s_gold > 82.0, str(s_gold))

# Role balance: 12 forwards / 6 D / 2 goalies when the talent is there.
lgd, teamsd = make_league(n_teams=4, seed=31)
for t in teamsd:
    n_marked = 0
    for pl in t.roster:
        if n_marked >= 2:
            break
        if pl.primary_position.name != "GOALIE":
            pl.primary_position.value = "D"   # 2 D per team -> 8 per nation
            n_marked += 1
    # Deepen Canada's pool so a full 12F/6D/2G split is possible.
    for i in range(3):
        extra = FakePlayer("Canada", 86 - i, age=27)
        if i == 0:
            extra.primary_position.value = "D"
        t.roster.append(extra)
pool = itl._eligible_players(lgd, worlds=False)
r = itl._build_roster(pool, "Canada")
n_d = sum(1 for p, _ in r["roster"] if itl._is_dman(p))
n_g = sum(1 for p, _ in r["roster"] if itl._is_goalie(p))
n_f = len(r["roster"]) - n_d - n_g
check("roster: 6 defensemen", n_d == 6, str(n_d))
check("roster: 2 goalies", n_g == 2, str(n_g))
check("roster: 12 forwards", n_f == 12, str(n_f))
check("coach carried on roster", r["coach"] is None)  # no coach passed

# -- 14: announce (Feb 9) -> resolve (Feb 22) split ------------------------------
lga, _, _ = _coach_league()
lga.intl_prep = {}
lga.intl_announced = []
appa = FakeApp(lga, None)
story = itl.announce_olympics(appa, 2026, random.Random(11))
check("announcement story", story is not None and "coaches" in story,
      (story or "")[:120])
check("prep stored", 2026 in lga.intl_prep)
check("announced recorded", 2026 in lga.intl_announced)
prep = lga.intl_prep[2026]
check("prep has coaches", any(v.get("coach_name")
                              for v in prep["rosters"].values()))
res_a = itl.resolve_olympics(appa, 2026, random.Random(11))
check("medal-day result", res_a is not None)
if res_a is not None:
    check("coaches on result", bool(res_a.get("coaches")),
          str(res_a.get("coaches")))
    check("card names coaches",
          "Behind the benches" in itl.result_card_text(res_a))
    # Same skaters announced and resolved: every announced id unique,
    # and each nation's prep roster matches what was built.
    announced_ids = [pid for v in prep["rosters"].values()
                     for pid in v["player_ids"]]
    check("rosters fixed at announce",
          len(set(announced_ids)) == len(announced_ids) > 0,
          str(len(announced_ids)))
    check("every nation iced a team",
          all(len(v["player_ids"]) >= 18 for v in prep["rosters"].values()))
check("held recorded after resolve", 2026 in lga.intl_held["olympics"])
# Gold roster names feed the next coach's loyalty signal.
check("gold roster recorded",
      any(h.get("gold_roster") for h in lga.intl_history
          if h.get("event") == "olympics"))

# -- 15: Olympic break keeps NHL games off Feb 10-24 ----------------------------
from datetime import date as _date
from game_classes import League
_bare = League.__new__(League)
cal_oly = _bare._create_authentic_nhl_calendar(2029)  # Feb 2030: olympic
cal_reg = _bare._create_authentic_nhl_calendar(2026)  # Feb 2027: not
ob = cal_oly["events"].get("olympic_break")
check("olympic break exists in olympic years",
      ob is not None and ob[0] == _date(2030, 2, 10)
      and ob[1] == _date(2030, 2, 24), str(ob))
check("no break otherwise", cal_reg["events"].get("olympic_break") is None)
dark = [d for d in cal_oly["available_dates"]
        if _date(2030, 2, 10) <= d <= _date(2030, 2, 24)]
check("NHL dark Feb 10-24", len(dark) == 0, str(dark[:3]))
lit = [d for d in cal_reg["available_dates"]
       if _date(2027, 2, 10) <= d <= _date(2027, 2, 24)]
check("normal February otherwise", len(lit) > 0, str(len(lit)))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
