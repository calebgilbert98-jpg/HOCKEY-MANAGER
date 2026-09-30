"""QA: RFA / offer-sheet / arbitration at the real-life standard.

Run: python3 qa_rfa_arbitration.py
"""
import random
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List

sys.path.insert(0, '.')
import rfa_system as R

PASS = 0
FAIL = 0


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name} {detail}")


# ---------------------------------------------------------------- fixtures

@dataclass
class FakeContract:
    salary: int = 1_000_000
    years_remaining: int = 0


@dataclass
class FakePlayer:
    name: str = "Test Player"
    age: int = 24
    seasons_played: int = 4
    ovr: int = 80
    pos: str = "C"
    salary: int = 1_000_000
    career_games: int = 200
    career_games_goalie: int = 0
    id: str = field(default_factory=lambda: f"p{random.randint(0, 999999)}")

    def __post_init__(self):
        self.full_name = self.name
        self.contract = FakeContract(salary=self.salary)
        self.primary_position = SimpleNamespace(value=self.pos)

    def overall_rating(self):
        return self.ovr


@dataclass
class FakeTeam:
    name: str = "Test Team"
    user: bool = False
    id: str = field(default_factory=lambda: f"t{random.randint(0, 999999)}")

    def __post_init__(self):
        self.team_name = self.name
        self.roster: List[FakePlayer] = []
        self.draft_picks = {}
        self.cap_space = 20_000_000
        self.is_user_team = self.user


def make_league(n_teams=6, seed=7):
    r = random.Random(seed)
    league = SimpleNamespace(
        teams=[], free_agents=[], season_year=2026, rivalries=[])
    for i in range(n_teams):
        t = FakeTeam(name=f"Team {i}", user=(i == 0))
        # own picks, next two drafts
        for yr in (2027, 2028):
            t.draft_picks[yr] = [
                SimpleNamespace(year=yr, round=rnd,
                                original_team=t.team_name,
                                current_team=t.team_name)
                for rnd in range(1, 8)]
        # roster: mix of RFAs, UFAs, signed players
        for j in range(10):
            age = r.choice([22, 23, 24, 25, 26, 28, 31])
            svc = r.randint(2, 9)
            ovr = r.choice([72, 75, 78, 81, 84, 87])
            expired = r.random() < 0.5
            p = FakePlayer(
                name=f"P{i}_{j}", age=age, seasons_played=svc, ovr=ovr,
                salary=r.choice([775_000, 900_000, 2_000_000, 5_000_000]),
                career_games=r.randint(50, 500))
            if not expired:
                p.contract.years_remaining = r.randint(1, 4)
            t.roster.append(p)
        league.teams.append(t)
    return league


# ---------------------------------------------------------------- 1. QO math

check("QO 110% band", R.qualifying_offer_amount(700_000) == 770_000)
check("QO tier1 boundary (775k -> 105%)",
      R.qualifying_offer_amount(775_000) == 814_000)  # 813,750 Johansson
check("QO Hughes ELC (832500 -> 105%)",
      R.qualifying_offer_amount(832_500) == 874_000)  # real: $874,125
check("QO 105% cap at $1M",
      R.qualifying_offer_amount(999_999) == 1_000_000)  # 1,049,999 -> capped
check("QO top band = salary",
      R.qualifying_offer_amount(3_000_000) == 3_000_000)
check("QO top band 120%-of-AAV binds",
      R.qualifying_offer_amount(2_000_000, aav=1_500_000) == 1_800_000)
check("QO pct fn", R.qualifying_offer_pct(500_000) == 1.10
      and R.qualifying_offer_pct(900_000) == 1.05
      and R.qualifying_offer_pct(5_000_000) == 1.00)

# ---------------------------------------------------------------- 2. RFA/UFA

rfa = FakePlayer(age=24, seasons_played=4)
check("young expired -> RFA", R.is_rfa(rfa) and not R.is_ufa(rfa))
old = FakePlayer(age=28, seasons_played=5)
check("28yo expired -> UFA", R.is_ufa(old) and not R.is_rfa(old))
vet = FakePlayer(age=25, seasons_played=7)
check("7 seasons -> UFA", R.is_ufa(vet))
signed = FakePlayer(age=24, seasons_played=4)
signed.contract.years_remaining = 2
check("signed player is neither", not R.is_rfa(signed) and not R.is_ufa(signed))
g6 = FakePlayer(age=26, seasons_played=4, career_games=50)  # Group 6
check("Group 6 (25+/3+/<80GP) -> UFA", R.is_ufa(g6) and not R.is_rfa(g6))
g6b = FakePlayer(age=26, seasons_played=4, career_games=120)
check("25+/3+/120GP stays RFA", R.is_rfa(g6b))
g6g = FakePlayer(age=26, seasons_played=4, pos="G", career_games_goalie=20,
                 career_games=20)
check("Group 6 goalie (<28GP) -> UFA", R.is_ufa(g6g))

# ---------------------------------------------------------------- 3. comp table

cases = [
    (1_000_000, []),
    (1_544_424, []),
    (1_544_425, [3]),
    (2_340_037, [3]),
    (2_340_038, [2]),
    (4_680_076, [2]),
    (4_680_077, [1, 3]),
    (7_020_113, [1, 3]),
    (7_020_114, [1, 2, 3]),
    (9_360_153, [1, 2, 3]),
    (9_360_154, [1, 1, 2, 3]),
    (11_700_192, [1, 1, 2, 3]),
    (11_700_193, [1, 1, 1, 1]),
    (15_000_000, [1, 1, 1, 1]),
]
for aav, picks in cases:
    label, got = R.offer_sheet_compensation(aav)
    check(f"comp ${aav:,}", got == picks, f"got {got}")

# ---------------------------------------------------------------- 4. arb elig

# signing age = age - seasons_played
e1 = FakePlayer(age=24, seasons_played=4)   # signed ~20 -> needs 4 -> ok
check("arb eligible (signed 20, 4yrs)", R.arbitration_eligible(e1))
e2 = FakePlayer(age=23, seasons_played=3)   # signed ~20 -> needs 4 -> no
check("arb ineligible (signed 20, 3yrs)", not R.arbitration_eligible(e2))
e3 = FakePlayer(age=26, seasons_played=3)   # signed ~23 -> needs 2 -> ok
check("arb eligible (signed 23, 3yrs)", R.arbitration_eligible(e3))
e4 = FakePlayer(age=27, seasons_played=5)   # UFA, not RFA -> no
check("UFA not arb eligible", not R.arbitration_eligible(e4))
e5 = FakePlayer(age=24, seasons_played=4)
e5.contract.years_remaining = 1
check("signed player not arb eligible", not R.arbitration_eligible(e5))
e6 = FakePlayer(age=29, seasons_played=1)   # signed ~28 -> needs 1 -> ok RFA? age 29 = UFA
check("29yo is UFA not RFA", R.is_ufa(e6))

# ---------------------------------------------------------------- 5. arbitrator

r = random.Random(11)
p = FakePlayer(age=24, seasons_played=4, salary=2_000_000, ovr=82)
aw = R.arbitrator_award(p, 3_000_000, 2_000_000, [2_400_000, 2_600_000], r)
check("award within filings", 2_000_000 <= aw["award_aav"] <= 3_000_000,
      str(aw["award_aav"]))
check("award >= 85% floor", aw["award_aav"] >= 1_700_000)
check("no walk-away under $4.85M", aw["walk_away_available"] is False)
check("arbitrator from panel", aw["arbitrator"] in R.ARBITRATOR_PANEL)
check("term 1-2", aw["term_years"] in (1, 2))

big = FakePlayer(age=24, seasons_played=5, salary=6_000_000, ovr=88)
aw2 = R.arbitrator_award(big, 8_000_000, 6_000_000, [7_000_000], r)
check("walk-away available player-elected >$4.85M",
      aw2["walk_away_available"] is True)
aw3 = R.arbitrator_award(big, 8_000_000, 6_000_000, [7_000_000], r,
                         filed_by="club")
check("no walk-away club-elected, ever",
      aw3["walk_away_available"] is False)

# 2-year award may not walk a player straight into UFA eligibility
u = FakePlayer(age=25, seasons_played=6, salary=3_000_000, ovr=84)  # UFA in 1
aw4 = R.arbitrator_award(u, 5_000_000, 3_500_000, None, r)
check("no 2yr award into UFA", aw4["term_years"] == 1)

# settlement ~= midpoint with slight player lean
s = R.settle_arbitration(2_250_000, 1_200_000, random.Random(3))
mid = (2_250_000 + 1_200_000) // 2
check("settlement near midpoint", mid <= s["award_aav"] <= mid * 1.05,
      str(s["award_aav"]))

# ---------------------------------------------------------------- 6. calibration

# 40 summers of filings on a synthetic eligible pool
filing_counts = []
for summer in range(40):
    rr = random.Random(1000 + summer)
    n = 0
    for i in range(60):  # 60 eligible unsigned RFAs
        tier = rr.choice(["star"] * 8 + ["top6_top4"] * 20 + ["depth"] * 32)
        base = R.ARBITRATION_FILING_RATES[tier]
        if rr.random() < min(0.95, base * 1.5):
            n += 1
    filing_counts.append(n)
avg_f = sum(filing_counts) / len(filing_counts)
check("filings avg in 13-26 band", 13 <= avg_f <= 26, f"avg={avg_f:.1f}")
check("filings range sane", min(filing_counts) >= 5
      and max(filing_counts) <= 40,
      f"min={min(filing_counts)} max={max(filing_counts)}")

# hearings ~5%
hearings = sum(1 for _ in range(2000)
               if random.Random().random() < R.ARBITRATION_HEARING_RATE)
check("hearing rate ~5%", 60 <= hearings <= 150, f"{hearings}/2000")

# offer sheets ~0.6/yr: 5 targets x 31 clubs x 0.008 x 0.5
sheets = 0
for summer in range(200):
    rr = random.Random(5000 + summer)
    for _t in range(5):
        score = 0.5
        for _c in range(31):
            if rr.random() < R.OFFER_SHEET_BASE_RATE * score:
                sheets += 1
                break
check("offer sheets ~0.6/yr", 60 <= sheets <= 200, f"{sheets}/200 summers")

# ---------------------------------------------------------------- 7. offseason pass

class FakeInbox:
    def __init__(self):
        self.messages = []

    def add_message(self, m):
        self.messages.append(m)


class FakeApp:
    def __init__(self, league):
        self.news = []
        self._league = league

    def add_news(self, s):
        self.news.append(s)

    def send_email_to_user(self, m):
        self.user_team.inbox.add_message(m)


league = make_league()
league.teams[0].inbox = FakeInbox()
app = FakeApp(league)
app.user_team = league.teams[0]
summary = R.process_rfa_offseason(league, app=app, rng=random.Random(42))
check("pass returns summary", summary["rfas"] > 0 and summary["ufas"] > 0,
      str({k: v for k, v in summary.items() if k != "arbitration_awards"}))
check("filings in band", 0 <= summary["arbitration_filings"] <= 40,
      str(summary["arbitration_filings"]))
check("user inbox queued",
      any(getattr(m, "action_type", None) == "rfa_qualifying"
          for m in league.teams[0].inbox.messages))
# no expired contracts left unsigned on AI rosters
leftover = sum(1 for t in league.teams[1:] for p in t.roster
               if R.contract_expired(p))
check("no unsigned expired on AI rosters", leftover == 0, str(leftover))
# every AI roster still has players (no roster collapse)
check("AI rosters intact", all(len(t.roster) >= 8 for t in league.teams[1:]))
# arbitration awards reference the panel
check("awards have arbitrators",
      all("arbitrator" in str(a) or "settles" in str(a) or "settlement" in str(a)
          for a in summary["arbitration_awards"]))

# user qualifying decision: decline -> UFA pool
user_rfa = next(p for p in league.teams[0].roster if R.is_rfa(p))
res = R.apply_qualifying_decision(app, league, league.teams[0],
                                  user_rfa.id, qualify=False)
check("decline -> UFA pool",
      res["ok"] and user_rfa in league.free_agents
      and user_rfa not in league.teams[0].roster)
# qualify -> rights retained + july mechanics ran
user_rfa2 = next(p for p in league.teams[0].roster if R.is_rfa(p))
res2 = R.apply_qualifying_decision(app, league, league.teams[0],
                                   user_rfa2.id, qualify=True,
                                   rng=random.Random(9))
check("qualify retains rights",
      res2["ok"] and res2["qualified"]
      and user_rfa2 in league.teams[0].roster)

# backfill: prospects promote, pool UFAs sign, rosters stay whole
t = FakeTeam(name="Backfill")
t.prospects = [FakePlayer(name="Kid", age=20, seasons_played=1, ovr=76,
                          salary=825_000) for _ in range(3)]
t.prospects[0].contract.years_remaining = 0
lg2 = SimpleNamespace(teams=[t], free_agents=[
    FakePlayer(name="Vet", age=30, seasons_played=8, ovr=74,
               salary=1_000_000)], season_year=2026, rivalries=[])
lg2.teams[0].roster = []
R._ai_backfill_roster(t, lg2, random.Random(5), target=4)
check("backfill promotes prospects", len(t.roster) >= 3, str(len(t.roster)))
check("backfill signs from pool or prospects", len(t.roster) == 4,
      str(len(t.roster)))

# cap guarantees: AI never spends into over-cap; sweep demotes to compliant
rich = FakeTeam(name="Rich")
check("_cap_room returns a number", isinstance(R._cap_room(rich), float))
poor = FakeTeam(name="Poor")
poor.salary_cap = 5_000_000  # tiny cap -> no room
star = FakePlayer(name="Star", age=24, seasons_played=5, ovr=88,
                  salary=9_000_000)
check("AI won't qualify what it can't fit",
      R._ai_qualify_decision(poor, star, 9_900_000) is False)
# sweep: over-cap team gets papered down
sweep_team = FakeTeam(name="Sweep")
sweep_team.salary_cap = 10_000_000
tw = FakePlayer(name="TwoWay", age=22, seasons_played=2, ovr=74,
                salary=5_000_000)
tw.contract.two_way = True
vet = FakePlayer(name="Vet", age=30, seasons_played=8, ovr=80,
                 salary=8_000_000)
sweep_team.roster = [tw, vet]
sweep_team.ahl_roster = []
moves = R._ai_cap_compliance_sweep(sweep_team)
from salary_cap_system import cap_breakdown
bd = cap_breakdown(sweep_team)
check("sweep demotes until compliant", not bd["over_cap"] and moves >= 1,
      f"moves={moves} over={bd['over_cap']}")
check("sweep demotes two-way first",
      any(getattr(p, 'full_name', '') == "TwoWay" for p in sweep_team.ahl_roster))

# cap consciousness: reserve + roster math, core may dip into reserve
tm = FakeTeam(name="CapTeam")
tm.salary_cap = 104_000_000
# payroll 102M -> 2M room; 21-man roster
tm.roster = [FakePlayer(name=f"P{i}", age=28, seasons_played=6, ovr=76,
                        salary=4_800_000) for i in range(21)]
tm.roster[0].contract.salary = 6_200_000  # 21*4.8=100.8 +1.4 = 102.2M
room = R._cap_room(tm)
reserve = R._reserve_amount(tm)
check("reserve is ~1.5% of cap", 1_500_000 <= reserve <= 1_650_000,
      f"{reserve:,.0f}")
b_disc = R._spending_budget(tm)  # 1.8M room - 1.56M reserve < 775k
b_core = R._spending_budget(tm, core=True)
check("discretionary budget keeps reserve", b_disc < 775_000,
      f"{b_disc:,.0f}")
check("core budget may dip into reserve", b_core >= 775_000,
      f"{b_core:,.0f}")
fringe = FakePlayer(name="Fringe", age=26, seasons_played=4, ovr=73,
                    salary=900_000)
check("AI won't qualify fringe into the reserve",
      R._ai_qualify_decision(tm, fringe, 990_000) is False)
star_young = FakePlayer(name="StarY", age=22, seasons_played=3, ovr=86,
                        salary=900_000)
check("AI qualifies the young star anyway",
      R._ai_qualify_decision(tm, star_young, 990_000) is True)
# roster math: 18 skaters + 3M room can't add a 2M discretionary deal
tm2 = FakeTeam(name="Thin")
tm2.salary_cap = 104_000_000
tm2.roster = [FakePlayer(name=f"Q{i}", age=28, seasons_played=6, ovr=76,
                         salary=5_611_111) for i in range(18)]  # ~101M
b2 = R._spending_budget(tm2)  # 3M - 2*775k - 1.56M < 0
check("roster math blocks thin-roster splurge", b2 < 2_000_000,
      f"{b2:,.0f}")
# aggressor can't poach outside its plan
check("aggressor score zero outside plan",
      R.ai_offer_sheet_target_score(tm, star_young, 8_000_000) == 0.0)

# ---------------------------------------------------------------------------
# Player-decision model (player_decision.py): the player's side of the market
# ---------------------------------------------------------------------------
import player_decision as PD


def dplayer(name="Dec", age=27, ovr=80, ambition=None, loyalty=50,
            happiness=70, controversy=10, pos="C", city_bp="Unknown"):
    p = FakePlayer(name=name, age=age, seasons_played=6, ovr=ovr,
                   salary=1_000_000)
    p.primary_position = pos  # plain string for the role projector
    p.loyalty = loyalty
    p.ambition = ambition or "stability"
    p.happiness = happiness
    p.controversy = controversy
    p.birthplace = city_bp
    p.nationality = "Canada"
    p.relationships = {}
    p.family_ids = []
    p.teamwork = 50
    p.leadership = 50
    p.morale = 70
    p.games_played = 300
    p.points = 150
    p.reputation = 40
    p.last_team_name = ""
    p.team_name = "Free Agent"
    return p


def dteam(name, city, avgs, user=False):
    t = FakeTeam(name=name, user=user)
    t.city = city
    r = random.Random(abs(hash(name)) % (2 ** 31))
    t.roster = []
    for i, a in enumerate(avgs):
        pl = FakePlayer(name=f"{name} P{i}", age=28, seasons_played=6,
                        ovr=a, salary=3_000_000)
        pl.primary_position = "C"
        t.roster.append(pl)
    return t


dleague = SimpleNamespace(teams=[], free_agents=[], season_year=2026,
                          rivalries=[])
contender = dteam("Contenders", "Denver", [85] * 20)
rebuilder = dteam("Rebuilders", "Anaheim", [70] * 20)
dleague.teams = [contender, rebuilder]

# seeding
sp = FakePlayer(name="Seed")
for attr in ("loyalty", "ambition"):
    if hasattr(sp, attr):
        delattr(sp, attr)
PD.ensure_decision_fields(sp)
check("loyalty seeded 1..99", 1 <= sp.loyalty <= 99, f"{sp.loyalty}")
check("ambition seeded valid", sp.ambition in PD.AMBITIONS, sp.ambition)

# cup-chaser (35yo star): contender at 0.8x market beats rebuilder at 1.3x
chaser = dplayer("Chaser", age=35, ovr=88, ambition="cup", loyalty=50)
mk = (88 - 60) * 250_000  # 7.0M market
a_con, _ = PD.contract_appeal(chaser, contender, int(mk * 0.8), 2,
                              league=dleague)
a_reb, _ = PD.contract_appeal(chaser, rebuilder, int(mk * 1.3), 4,
                              league=dleague)
check("cup-chaser picks contender over money", a_con > a_reb,
      f"{a_con:.2f} vs {a_reb:.2f}")

# mercenary: takes the bigger bag
merc = dplayer("Merc", age=28, ovr=88, ambition="money", loyalty=20)
a_con2, _ = PD.contract_appeal(merc, contender, int(mk * 0.8), 2,
                               league=dleague)
a_reb2, _ = PD.contract_appeal(merc, rebuilder, int(mk * 1.3), 4,
                               league=dleague)
check("mercenary takes the money", a_reb2 > a_con2,
      f"{a_reb2:.2f} vs {a_con2:.2f}")

# kid wants ice: top-six on rebuilder beats press box on contender
stacked = dteam("Stacked", "Boston", [86] * 12)
thin = dteam("Thin", "Buffalo", [68] * 12)
dleague.teams = [stacked, thin]
kid = dplayer("Kid", age=20, ovr=76, ambition="ice_time", loyalty=40)
a_st, r_st = PD.contract_appeal(kid, stacked, 2_000_000, 3, league=dleague)
a_th, r_th = PD.contract_appeal(kid, thin, 1_800_000, 3, league=dleague)
check("kid picks ice time over contender", a_th > a_st,
      f"{a_th:.2f} vs {a_st:.2f}")
check("role reason surfaces", any("line" in x or "role" in x for x in r_th),
      str(r_th))
dleague.teams = [contender, rebuilder]

# hometown pull
homeboy = dplayer("Homeboy", age=27, ovr=80, ambition="home",
                  city_bp="Denver, CO")
a_home, r_home = PD.contract_appeal(homeboy, contender, 5_000_000, 4,
                                    league=dleague)
a_away, _ = PD.contract_appeal(homeboy, rebuilder, 5_000_000, 4,
                               league=dleague)
check("hometown pull is real", a_home > a_away + 0.05,
      f"{a_home:.2f} vs {a_away:.2f}")
check("hometown reason surfaces", any("hometown" in x for x in r_home),
      str(r_home))

# people: friend on team A, rival on team B, brother on team A
pal = dplayer("Pal", age=27, ovr=80, ambition="stability")
friend = contender.roster[0]
foe = rebuilder.roster[0]
bro = contender.roster[1]
pal.relationships = {friend.id: 85, foe.id: -85}
pal.family_ids = [bro.id]
a_pal_c, r_pal = PD.contract_appeal(pal, contender, 5_000_000, 4,
                                    league=dleague)
a_pal_r, _ = PD.contract_appeal(pal, rebuilder, 5_000_000, 4,
                                league=dleague)
check("friends/family beat rivals", a_pal_c > a_pal_r + 0.05,
      f"{a_pal_c:.2f} vs {a_pal_r:.2f}")
check("people reasons surface",
      any("friend" in x or "family" in x for x in r_pal), str(r_pal))

# bad blood: monkeypatched hot rivalry; fan favourite vs villain
class HotLedger:
    def memory_weight(self, a, b):
        return 90.0

PD._ledger = lambda app: HotLedger()
star = dplayer("Star", age=28, ovr=90, ambition="stability", loyalty=85,
               happiness=80)
star.games_played = 500
star.points = 500  # PPG fan favourite
star.last_team_name = "Rebuilders"
cost, why = PD._rival_move_cost(star, rebuilder, contender, None)
check("fan favourite pays bad-blood cost", cost > 0.12, f"{cost:.2f}")
check("bad-blood reason names the turn",
      why is not None and "villain" in why, str(why))
goon = dplayer("Goon", age=28, ovr=90, ambition="money", loyalty=20,
               controversy=95)
goon.games_played = 500
goon.points = 200
goon.last_team_name = "Rebuilders"
cost_v, _ = PD._rival_move_cost(goon, rebuilder, contender, None)
check("villain shrugs at bad blood", cost_v < cost,
      f"{cost_v:.2f} vs {cost:.2f}")

# offer-sheet consent: loyal star refuses the rival; mercenary signs
r0 = random.Random(11)
ok_star, ap_star, _ = PD.player_accepts_offer_sheet(
    star, contender, 9_000_000, 5, rebuilder, league=dleague, app=None,
    rng=r0)
check("loyal star won't sign rival sheet", ap_star < 0.52,
      f"appeal {ap_star:.2f}")
ok_merc, ap_merc, _ = PD.player_accepts_offer_sheet(
    merc, contender, 12_500_000, 5, rebuilder, league=dleague, app=None,
    rng=random.Random(11))
check("mercenary signs the big-money sheet", ap_merc >= 0.52,
      f"appeal {ap_merc:.2f}")

# wants_out routing
out = dplayer("Out", age=26, ovr=84, loyalty=40, happiness=25)
check("miserable + disloyal wants out", PD.wants_out(out) is True)
calm = dplayer("Calm", age=26, ovr=84, loyalty=70, happiness=70)
check("happy player stays put", PD.wants_out(calm) is False)

# previous_team resolution
star.last_team_name = "Rebuilders"
check("previous_team resolves", PD.previous_team(star, dleague) is rebuilder)
star.last_team_name = ""
check("previous_team None when unknown",
      PD.previous_team(star, dleague) is None)

# staying beats leaving for the loyal (same money)
loyal = dplayer("Loyal", age=29, ovr=84, ambition="stability", loyalty=90,
                happiness=80)
loyal.team_name = "Contenders"
a_stay, _ = PD.contract_appeal(loyal, contender, 6_000_000, 5,
                              current_team=contender, league=dleague)
a_go, _ = PD.contract_appeal(loyal, rebuilder, 6_000_000, 5,
                             current_team=contender, league=dleague)
check("loyal player prefers staying", a_stay > a_go + 0.05,
      f"{a_stay:.2f} vs {a_go:.2f}")

# ---------------------------------------------------------------- offer-sheet compensation walks forward
from datetime import date as _date

_off = FakeTeam(name="Offer")
_orig = FakeTeam(name="Original")
# Own 1sts 2027..2033, but the 2027 and 2028 1sts were already traded.
for _yr in range(2027, 2034):
    _gone = _yr in (2027, 2028)
    _off.draft_picks[_yr] = [
        SimpleNamespace(year=_yr, round=rnd,
                        original_team=_off.team_name,
                        current_team=("Elsewhere" if _gone and rnd == 1
                                      else _off.team_name))
        for rnd in range(1, 8)]
_rfa = FakePlayer(name="Star RFA", age=24, seasons_played=5, ovr=90,
                  salary=1_000_000)
_rfa.contract.years_remaining = 0
_orig.roster.append(_rfa)
_lg3 = SimpleNamespace(teams=[_off, _orig], free_agents=[],
                       season_year=2026, rivalries=[])
_res = R.execute_offer_sheet(_lg3, _off, _orig, _rfa, aav=12_000_000,
                             years=7, as_of=_date(2027, 7, 15),
                             rng=random.Random(3))
check("offer sheet: four-1sts comp walks past traded near picks",
      _res.get("ok") is True, str(_res.get("reason")))
_got = sorted(p.year for p in _res.get("picks", []))
check("offer sheet: compensation is the next four OWN 1sts",
      _got == [2029, 2030, 2031, 2032], str(_got))
check("offer sheet: player moved to the offering club",
      _rfa in _off.roster and _rfa not in _orig.roster)

# No own 1sts anywhere -> the sheet can't be signed.
_off2 = FakeTeam(name="Broke")
for _yr in range(2027, 2034):
    _off2.draft_picks[_yr] = [
        SimpleNamespace(year=_yr, round=rnd, original_team=_off2.team_name,
                        current_team="Elsewhere") for rnd in range(1, 8)]
_rfa2 = FakePlayer(name="Star RFA 2", age=24, seasons_played=5, ovr=90,
                   salary=1_000_000)
_rfa2.contract.years_remaining = 0
_orig2 = FakeTeam(name="Original 2")
_orig2.roster.append(_rfa2)
_lg4 = SimpleNamespace(teams=[_off2, _orig2], free_agents=[],
                       season_year=2026, rivalries=[])
_res2 = R.execute_offer_sheet(_lg4, _off2, _orig2, _rfa2, aav=12_000_000,
                              years=7, as_of=_date(2027, 7, 15),
                              rng=random.Random(4))
check("offer sheet: blocked with no own 1sts available",
      _res2.get("ok") is False
      and _res2.get("reason") == "missing_own_picks",
      str(_res2.get("reason")))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
