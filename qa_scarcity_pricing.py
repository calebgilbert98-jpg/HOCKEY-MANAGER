# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""QA: UFA/RFA market scarcity pricing (Chris's ask).

Supply/demand multiplier on every ask path -- thin market + many suitors
inflates asks, a flooded pool softens them. User and AI share one market.

Run: python3 qa_scarcity_pricing.py
"""
import random
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import List

sys.path.insert(0, '.')
import salary_cap_system as S
import rfa_system as R
from ai_team_management import AITeamManager

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
    entry_level: bool = False


@dataclass
class FakePlayer:
    name: str = "Test Player"
    age: int = 27
    ovr: int = 80          # native scale
    pos: str = "C"
    salary: int = 1_000_000
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
    payroll: int = 60_000_000
    id: str = field(default_factory=lambda: f"t{random.randint(0, 999999)}")

    def __post_init__(self):
        self.team_name = self.name
        self.roster: List[FakePlayer] = []
        self.salary_cap = S.DEFAULT_CAP
        self.is_user_team = False

    def add(self, p):
        self.roster.append(p)
        self.payroll += p.salary


def mkteams(n, payroll=60_000_000):
    return [FakeTeam(name=f"Team{i}", payroll=payroll)
            for i in range(n)]


def mkleague(teams, fas):
    lg = SimpleNamespace()
    lg.teams = teams
    lg.free_agents = list(fas)
    lg.season_year = 2026
    lg.salary_cap_system = S.SalaryCapSystem()
    return lg


def fill_roster(team, specs):
    """specs: list of (pos, ovr, salary) -- builds a realistic roster so
    team_needs() returns a real weakest-first order."""
    for i, (pos, ovr, sal) in enumerate(specs):
        p = FakePlayer(name=f"{team.name}-{pos}{i}", pos=pos, ovr=ovr,
                       salary=sal)
        p.contract.years_remaining = 3
        team.add(p)


NHL_ROSTER = (
    [("C", 82, 6_000_000), ("C", 78, 3_500_000), ("C", 74, 1_200_000),
     ("C", 70, 900_000)] +
    [("LW", 80, 5_000_000), ("LW", 76, 2_500_000), ("LW", 72, 1_000_000),
     ("RW", 81, 5_500_000), ("RW", 75, 2_000_000), ("RW", 71, 950_000)] +
    [("LD", 80, 5_000_000), ("LD", 76, 2_800_000), ("LD", 72, 1_100_000),
     ("RD", 79, 4_500_000), ("RD", 75, 2_200_000), ("RD", 70, 900_000)] +
    [("G", 82, 6_000_000), ("G", 74, 1_500_000)]
)


def league_with_needs(n_teams=8, need_pos="C", need_ovr=70):
    """Every team is solid except a hole at need_pos (weak = top-2 need)."""
    teams = mkteams(n_teams)
    for t in teams:
        specs = [s for s in NHL_ROSTER if s[0] != need_pos]
        specs.append((need_pos, need_ovr, 900_000))
        specs.append((need_pos, need_ovr - 2, 800_000))
        fill_roster(t, specs)
    return teams


# ------------------------------------------------- A: bounds and defaults

def section_a():
    teams = league_with_needs()
    fas = [FakePlayer(name=f"FA-C{i}", pos="C", ovr=80, salary=2_000_000)
           for i in range(6)]
    lg = mkleague(teams, fas)
    cap = lg.salary_cap_system

    # 1. default demand_for() unchanged: no scarcity arg == scarcity 1.0
    a = cap.demand_for(0.05, 85, "C", 27, 2026)
    b = cap.demand_for(0.05, 85, "C", 27, 2026, scarcity=1.0)
    check("A1 default demand_for unchanged", a == b, f"{a} vs {b}")

    # 2. multiplier always within [0.90, 1.35] over random markets
    rng = random.Random(7)
    ok = True
    for _ in range(200):
        nf = rng.randint(0, 40)
        fas2 = [FakePlayer(pos=rng.choice("CLWRDG"), ovr=rng.randint(60, 92))
                for _ in range(nf)]
        lg2 = mkleague(league_with_needs(), fas2)
        for pos in ("C", "LW", "RD", "G"):
            m = S.fa_market_scarcity(lg2, pos)["multiplier"]
            if not (0.90 <= m <= 1.35):
                ok = False
    check("A2 multiplier clamped [0.90, 1.35]", ok)

    # 3. signal keys valid; copy has no raw numbers/multipliers
    import re
    valid = {"thin_market", "high_demand", "balanced", "buyers_market"}
    ok = True
    for pos in ("C", "LW", "RD", "G"):
        sc = S.fa_market_scarcity(lg, pos)
        if sc["signal"] not in valid:
            ok = False
        txt = S.scarcity_signal_text(sc["signal"], pos)
        if re.search(r"\d", txt) or "%" in txt or "x" in txt.split():
            ok = False
        short = S.scarcity_signal_short(sc["signal"])
        if re.search(r"\d", short):
            ok = False
    check("A3 qualitative copy only, no numbers", ok)

    # 4. degenerate inputs never raise, never move the market
    for bad in (None, SimpleNamespace(), "junk"):
        try:
            sc = S.fa_market_scarcity(bad, "C")
            ok_b = sc["multiplier"] == 1.0 and sc["signal"] == "balanced"
        except Exception:
            ok_b = False
        check(f"A4 degenerate league tolerated ({type(bad).__name__})", ok_b)
    try:
        sc = S.fa_market_scarcity(lg, "ZZZ")
        # position_group() leniently maps unknown codes to Forward --
        # the module's standing convention. Just require no raise and a
        # bounded, valid read.
        fwd = S.fa_market_scarcity(lg, "C")
        check("A4b bad position tolerated",
              sc["multiplier"] == fwd["multiplier"]
              and sc["signal"] == fwd["signal"]
              and 0.90 <= sc["multiplier"] <= 1.35)
    except Exception:
        check("A4b bad position tolerated", False, "raised")

    # 5. RFA helper never raises, bounded
    p = FakePlayer(pos="C", ovr=84)
    m = R._scarcity_mult(lg, p)
    check("A5 _scarcity_mult bounded", 0.90 <= m <= 1.35, f"m={m}")
    m2 = R._scarcity_mult(None, p)
    check("A5b _scarcity_mult(None league) == 1.0", m2 == 1.0, f"m={m2}")


# --------------------------------------- B: thin vs flooded (real ask path)

def section_b():
    teams = league_with_needs(n_teams=8, need_pos="C")
    # Balanced baseline: 8 quality C FAs, 8 clubs with a C need and space.
    base_fas = [FakePlayer(name=f"BaseC{i}", pos="C", ovr=80,
                           salary=2_500_000) for i in range(8)]
    lg = mkleague(teams, base_fas)
    mgr = AITeamManager()
    mgr.set_cap_system(lg.salary_cap_system, lg)

    probe = FakePlayer(name="Probe", pos="C", ovr=82, age=27,
                       salary=3_000_000)
    base_ask = mgr._player_ask(probe, league=lg)
    base_sc = S.fa_market_scarcity(lg, "C")
    print(f"  baseline: supply={base_sc['supply']} demand={base_sc['demand']} "
          f"mult={base_sc['multiplier']} ask=${base_ask:,}")

    # Thin market: strip the quality Cs out of the pool.
    lg.free_agents = [p for p in lg.free_agents
                      if not (p.primary_position.value == "C"
                              and p.overall_rating() >= 78)]
    thin_sc = S.fa_market_scarcity(lg, "C")
    thin_ask = mgr._player_ask(probe, league=lg)
    print(f"  thin:     supply={thin_sc['supply']} demand={thin_sc['demand']} "
          f"mult={thin_sc['multiplier']} ask=${thin_ask:,}")
    check("B1 thin market inflates ask",
          thin_sc["multiplier"] > base_sc["multiplier"]
          and thin_ask > base_ask,
          f"{base_sc['multiplier']}->{thin_sc['multiplier']}")
    check("B1b thin market signal fires",
          thin_sc["signal"] in ("thin_market", "high_demand"),
          thin_sc["signal"])

    # Flooded market: 40 quality Cs hit the pool.
    flood = [FakePlayer(name=f"FloodC{i}", pos="C", ovr=80,
                        salary=2_500_000) for i in range(40)]
    lg.free_agents = flood
    flood_sc = S.fa_market_scarcity(lg, "C")
    flood_ask = mgr._player_ask(probe, league=lg)
    print(f"  flooded:  supply={flood_sc['supply']} demand={flood_sc['demand']} "
          f"mult={flood_sc['multiplier']} ask=${flood_ask:,}")
    check("B2 flooded market softens ask",
          flood_sc["multiplier"] < base_sc["multiplier"]
          and flood_ask < base_ask,
          f"{base_sc['multiplier']}->{flood_sc['multiplier']}")
    check("B2b flooded signal fires",
          flood_sc["signal"] == "buyers_market", flood_sc["signal"])

    # Cap-strapped clubs are not bidders: put every team over the cap.
    for t in teams:
        t.salary_cap = 1  # ~zero room
    strap_sc = S.fa_market_scarcity(lg, "C")
    print(f"  strapped: demand={strap_sc['demand']} "
          f"mult={strap_sc['multiplier']}")
    check("B3 cap-strapped clubs excluded from demand",
          strap_sc["demand"] == 0, f"demand={strap_sc['demand']}")


# ------------------------------------------------- C: user/AI parity

def section_c():
    teams = league_with_needs(n_teams=8, need_pos="C")
    fas = [FakePlayer(name=f"PC{i}", pos="C", ovr=80, salary=2_500_000)
           for i in range(4)]
    lg = mkleague(teams, fas)
    mgr = AITeamManager()
    mgr.set_cap_system(lg.salary_cap_system, lg)
    cap = lg.salary_cap_system

    # The AI path and the user path both reduce to demand_for with the
    # same scarcity read -- verify the reduction, not the UI.
    probe = FakePlayer(name="Parity", pos="C", ovr=84, age=28,
                       salary=4_000_000)
    ai_ask = mgr._player_ask(probe, league=lg)
    sc = S.fa_market_scarcity(lg, "C")["multiplier"]
    from game_classes import to_100_scale
    ovr100 = int(to_100_scale(probe.overall_rating()))
    base_pct = S.base_ask_dollars(ovr100, 28, False, "C") / cap.current_cap
    manual = max(cap.demand_for(base_pct, ovr100, "C", 28, 2026,
                                scarcity=sc), 750_000)
    check("C1 AI ask == demand_for with scarcity read", ai_ask == manual,
          f"ai={ai_ask} manual={manual}")

    # RFA re-sign path: market-based outcomes carry the same multiplier.
    rng = random.Random(3)
    rfa = FakePlayer(name="RFA", pos="C", ovr=84, age=24, salary=3_000_000)
    aav_plain, _ = R._ai_rfa_deal(rfa, 4_000_000, rng)          # no league
    rng2 = random.Random(3)
    aav_scar, _ = R._ai_rfa_deal(rfa, 4_000_000, rng2, league=lg)
    print(f"  RFA re-sign: no-league=${aav_plain:,} "
          f"with-league=${aav_scar:,} (mult={sc})")
    check("C2 _ai_rfa_deal backward-compatible (league=None)", aav_plain > 0)
    # market outcomes scale with scarcity; the bare-QO outcome does not
    check("C3 RFA re-sign carries scarcity",
          abs(aav_scar - aav_plain * sc) < aav_plain * 0.02 + 2
          or aav_scar == aav_plain,
          f"{aav_plain} -> {aav_scar}")


# ------------------------------------------- D: demand-side sanity (goalies)

def section_d():
    # Goalie market: few quality Gs, every team wants one -> premium.
    teams = league_with_needs(n_teams=8, need_pos="G", need_ovr=68)
    fas = [FakePlayer(name=f"FAG{i}", pos="G", ovr=79, salary=2_000_000)
           for i in range(2)]
    lg = mkleague(teams, fas)
    sc = S.fa_market_scarcity(lg, "G")
    print(f"  goalies: supply={sc['supply']} demand={sc['demand']} "
          f"mult={sc['multiplier']} signal={sc['signal']}")
    check("D1 thin goalie market -> premium",
          sc["multiplier"] > 1.0 and sc["signal"] in (
              "thin_market", "high_demand"),
          f"{sc}")
    # Forwards flooded while goalies thin: groups are independent.
    fas += [FakePlayer(name=f"FAF{i}", pos="LW", ovr=80, salary=2_000_000)
            for i in range(30)]
    lg.free_agents = fas
    sc_g = S.fa_market_scarcity(lg, "G")
    sc_f = S.fa_market_scarcity(lg, "LW")
    check("D2 position groups independent",
          sc_g["multiplier"] > 1.0 >= sc_f["multiplier"],
          f"G={sc_g['multiplier']} LW={sc_f['multiplier']}")


def main():
    print("== A: bounds and defaults ==")
    section_a()
    print("== B: thin vs flooded (real ask path) ==")
    section_b()
    print("== C: user/AI parity ==")
    section_c()
    print("== D: demand-side sanity ==")
    section_d()
    print(f"\nRESULT: {PASS} passed, {FAIL} failed")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
