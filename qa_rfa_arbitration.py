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
from game_classes import is_human_managed  # noqa - ensure importable
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

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
