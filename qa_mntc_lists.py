"""QA: dynamic M-NTC team lists (hometown, taxes, situation, opportunity).

Run:  python3 qa_mntc_lists.py   (no display needed)

Covers:
 1. Determinism: same (player, destination, season) -> same answer.
 2. Taxes: high-tax destinations blocked more than no-tax ones.
 3. Hometown: a Toronto-born player blocks Toronto less than average.
 4. Situation: a 36-year-old blocks a rebuilder more than a 22-year-old.
 5. Opportunity: a young goalie blocks a 3-goalie club more than a
    1-goalie club; a young skater blocks a stacked depth chart.
 6. Approved lists invert: desirable teams land on them more often.
 7. mntc_list_teams: exactly n teams, excludes his own club,
    deterministic, ordered by block probability.
 8. will_waive_ntc: no-tax destinations get more waivers; reasons cite
    taxes/home.
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import trade_engine as te
from game_classes import Player, PlayerPosition, Team

passed = []


def check(name, cond, extra=""):
    assert cond, f"FAILED: {name} {extra}"
    passed.append(name)
    print(f"  ok: {name}")


TEAM_ROWS = [
    ("Carolina Hurricanes", "Raleigh"), ("Columbus Blue Jackets", "Columbus"),
    ("New Jersey Devils", "Newark"), ("New York Islanders", "New York"),
    ("New York Rangers", "New York"), ("Philadelphia Flyers", "Philadelphia"),
    ("Pittsburgh Penguins", "Pittsburgh"), ("Washington Capitals", "Washington"),
    ("Boston Bruins", "Boston"), ("Buffalo Sabres", "Buffalo"),
    ("Detroit Red Wings", "Detroit"), ("Florida Panthers", "Sunrise"),
    ("Montr\u00e9al Canadiens", "Montreal"), ("Ottawa Senators", "Ottawa"),
    ("Tampa Bay Lightning", "Tampa Bay"), ("Toronto Maple Leafs", "Toronto"),
    ("Chicago Blackhawks", "Chicago"), ("Colorado Avalanche", "Denver"),
    ("Dallas Stars", "Dallas"), ("Minnesota Wild", "St. Paul"),
    ("Nashville Predators", "Nashville"), ("St. Louis Blues", "St. Louis"),
    ("Utah Hockey Club", "Salt Lake City"), ("Winnipeg Jets", "Winnipeg"),
    ("Anaheim Ducks", "Anaheim"), ("Calgary Flames", "Calgary"),
    ("Edmonton Oilers", "Edmonton"), ("Los Angeles Kings", "Los Angeles"),
    ("San Jose Sharks", "San Jose"), ("Seattle Kraken", "Seattle"),
    ("Vancouver Canucks", "Vancouver"), ("Vegas Golden Knights", "Las Vegas"),
]


def make_league(pcts=None):
    teams = [Team(n, c, "D", "E") for n, c in TEAM_ROWS]
    standings = {}
    for i, t in enumerate(teams):
        pct = 0.5 if pcts is None else pcts.get(t.team_name, 0.5)
        w = int(pct * 40)
        standings[t.team_name] = {"W": w, "L": 40 - w, "OTL": 0}
    return SimpleNamespace(teams=teams, standings=standings,
                           season_year=2026)


def by_name(league, name):
    return next(t for t in league.teams if t.team_name == name)


def mkplayer(age, pos=PlayerPosition.CENTER, birthplace="Unknown",
             nat="Canada", pid=None, list_size=10):
    p = Player("Test", f"P{pid or age}", age, pos)
    p.birthplace = birthplace
    p.nationality = nat
    p.contract.no_trade_clause = True
    p.contract.modified_ntc_teams = list_size
    if pid is not None:
        p.id = f"qa-{pid}"
    return p


# --- 1. determinism -------------------------------------------------------
print("1. determinism (season-fixed, no re-roll)")
lg = make_league()
p = mkplayer(28, birthplace="Chicago, IL", pid=1)
dest = by_name(lg, "San Jose Sharks")
r1 = te._mntc_blocks(p, dest, lg)
r2 = te._mntc_blocks(p, dest, lg)
check("same answer twice", r1 == r2, f"{r1} vs {r2}")
blocked, _why = r1
if blocked:
    check("blocked team learned onto no_trade_list",
          "San Jose Sharks" in p.contract.no_trade_list,
          str(p.contract.no_trade_list))
else:
    check("unblocked team stays off no_trade_list",
          "San Jose Sharks" not in p.contract.no_trade_list)

# --- 2. taxes: smallest factor, salary-scaled --------------------------------
print("2. taxes scale least, and matter for non-stars")
hi = by_name(lg, "San Jose Sharks")     # CA: high
lo = by_name(lg, "Tampa Bay Lightning")  # FL: none


def role_player(pid):
    q = mkplayer(28, birthplace="Denver, CO", pid=pid)
    q.contract.salary = 1_500_000  # full tax salience
    return q


def star_player(pid):
    q = mkplayer(28, birthplace="Denver, CO", pid=pid)
    q.contract.salary = 11_000_000  # major dollars: barely notices
    return q


rp, sp = role_player(100), star_player(101)
rp_lo, _ = te._tax_factor(rp, lo)
rp_hi, _ = te._tax_factor(rp, hi)
sp_lo, _ = te._tax_factor(sp, lo)
sp_hi, _ = te._tax_factor(sp, hi)
check("role player: no-tax below 1, high-tax above 1",
      rp_lo < 1.0 < rp_hi, f"lo={rp_lo:.3f} hi={rp_hi:.3f}")
check("star: tax mults closer to 1 than role player's",
      abs(sp_lo - 1.0) < abs(rp_lo - 1.0)
      and abs(sp_hi - 1.0) < abs(rp_hi - 1.0),
      f"star lo={sp_lo:.3f} hi={sp_hi:.3f}")
# Taxes move the needle less than any other factor, by far.
home_mult, _ = te._hometown_factor(rp, by_name(lg, "Colorado Avalanche"))
bad_lg = make_league({"San Jose Sharks": 0.35})
sib_mult, _ = te._situation_factor(
    mkplayer(36, birthplace="Denver, CO", pid=102),
    by_name(bad_lg, "San Jose Sharks"), bad_lg)
tax_dev = max(abs(rp_lo - 1.0), abs(rp_hi - 1.0))
check("tax is the smallest factor by far",
      tax_dev < abs(home_mult - 1.0) and tax_dev < abs(sib_mult - 1.0),
      f"tax={tax_dev:.3f} home={abs(home_mult-1.0):.3f} "
      f"situation={abs(sib_mult-1.0):.3f}")
# Direction still holds on the full probability for role players.
probs_hi = [te._mntc_block_probability(role_player(200 + i), hi, lg)[0]
            for i in range(60)]
probs_lo = [te._mntc_block_probability(role_player(300 + i), lo, lg)[0]
            for i in range(60)]
check("role players still block high-tax more",
      sum(probs_hi) / len(probs_hi) > sum(probs_lo) / len(probs_lo),
      f"hi={sum(probs_hi)/len(probs_hi):.3f} "
      f"lo={sum(probs_lo)/len(probs_lo):.3f}")

# --- 3. hometown ------------------------------------------------------------
print("3. hometown pull")
tor = by_name(lg, "Toronto Maple Leafs")
probs_home, probs_away = [], []
for i in range(60):
    q = mkplayer(29, birthplace="Toronto, ON", pid=300 + i)
    ph, _, _ = te._mntc_block_probability(q, tor, lg)
    probs_home.append(ph)
    others = [t for t in lg.teams
              if t.team_name not in ("Toronto Maple Leafs",)]
    pa = sum(te._mntc_block_probability(q, t, lg)[0]
             for t in others[:10]) / 10
    probs_away.append(pa)
check("Toronto-born blocks Toronto less",
      sum(probs_home) / len(probs_home) <
      sum(probs_away) / len(probs_away),
      f"home={sum(probs_home)/len(probs_home):.3f} "
      f"away={sum(probs_away)/len(probs_away):.3f}")

# --- 4. situation: veterans vs youngsters ------------------------------------
print("4. team situation is age-aware")
bad = make_league({"Edmonton Oilers": 0.35})
oil = by_name(bad, "Edmonton Oilers")
vet_blocks = kid_blocks = 0
for i in range(120):
    v = mkplayer(36, birthplace="Duluth, MN", pid=500 + i)
    k = mkplayer(22, birthplace="Duluth, MN", pid=700 + i)
    if te._mntc_blocks(v, oil, bad)[0]:
        vet_blocks += 1
    if te._mntc_blocks(k, oil, bad)[0]:
        kid_blocks += 1
check("veteran blocks the rebuilder more",
      vet_blocks > kid_blocks,
      f"vet={vet_blocks}/120 kid={kid_blocks}/120")

# --- 5. opportunity ------------------------------------------------------------
print("5. circumstantial opportunity (depth charts)")
lg5 = make_league()
deep_g = by_name(lg5, "Boston Bruins")
thin_g = by_name(lg5, "Utah Hockey Club")
for _ in range(3):
    deep_g.roster.append(Player("G", "Deep", 30, PlayerPosition.GOALIE))
thin_g.roster.append(Player("G", "Thin", 31, PlayerPosition.GOALIE))
deep_blocks = thin_blocks = 0
for i in range(100):
    g = mkplayer(22, pos=PlayerPosition.GOALIE, birthplace="Oslo",
                 nat="Norway", pid=900 + i)
    if te._mntc_blocks(g, deep_g, lg5)[0]:
        deep_blocks += 1
    if te._mntc_blocks(g, thin_g, lg5)[0]:
        thin_blocks += 1
check("young goalie blocks the 3-goalie club more",
      deep_blocks > thin_blocks,
      f"deep={deep_blocks}/100 thin={thin_blocks}/100")

stacked = by_name(lg5, "Colorado Avalanche")
thin = by_name(lg5, "Chicago Blackhawks")
for _ in range(8):
    stacked.roster.append(Player("F", "Stack", 27, PlayerPosition.CENTER))
thin.roster.append(Player("F", "Thin", 29, PlayerPosition.CENTER))
s_blocks = t_blocks = 0
for i in range(100):
    w = mkplayer(21, pos=PlayerPosition.LEFT_WING,
                 birthplace="Malm\u00f6", nat="Sweden", pid=1100 + i)
    if te._mntc_blocks(w, stacked, lg5)[0]:
        s_blocks += 1
    if te._mntc_blocks(w, thin, lg5)[0]:
        t_blocks += 1
check("young skater blocks the stacked chart more",
      s_blocks > t_blocks, f"stacked={s_blocks}/100 thin={t_blocks}/100")

# --- 6. approved lists invert -----------------------------------------------------
print("6. approved lists invert desirability")
lg6 = make_league({"Tampa Bay Lightning": 0.68, "San Jose Sharks": 0.35})
good = by_name(lg6, "Tampa Bay Lightning")
bad6 = by_name(lg6, "San Jose Sharks")
on_good = on_bad = 0
for i in range(120):
    q = mkplayer(30, birthplace="Tampa, FL", pid=1300 + i, list_size=10)
    q.contract.modified_ntc_approved = True
    if not te._mntc_blocks(q, good, lg6)[0]:
        on_good += 1
    if not te._mntc_blocks(q, bad6, lg6)[0]:
        on_bad += 1
check("desirable team lands on approved list more",
      on_good > on_bad, f"good={on_good}/120 bad={on_bad}/120")

# --- 7. mntc_list_teams --------------------------------------------------------------
print("7. materialized list")
lg7 = make_league()
me = by_name(lg7, "Toronto Maple Leafs")
star = mkplayer(34, birthplace="Toronto, ON", pid=1500, list_size=12)
lst1 = te.mntc_list_teams(star, lg7, exclude=me)
lst2 = te.mntc_list_teams(star, lg7, exclude="Toronto Maple Leafs")
check("exactly n teams", len(lst1) == 12, str(len(lst1)))
check("own club excluded", "Toronto Maple Leafs" not in lst1)
check("deterministic", lst1 == lst2)
probs = [te._mntc_block_probability(star, by_name(lg7, t), lg7)[0]
         for t in lst1]
check("ordered by block probability",
      all(probs[i] >= probs[i + 1] for i in range(len(probs) - 1)))
print(f"     sample list: {', '.join(lst1[:5])} ...")

# --- 8. will_waive_ntc nudges -----------------------------------------------------------
print("8. waiver inclination follows taxes/home")
import random as _r
lg8 = make_league()
home_team = by_name(lg8, "Edmonton Oilers")
no_tax = by_name(lg8, "Dallas Stars")
hi_tax = by_name(lg8, "Vancouver Canucks")
waive_notax = waive_hitax = 0
TRIALS = 300
for i in range(TRIALS):
    a = mkplayer(29, birthplace="Dallas, TX", nat="USA", pid=1700 + i)
    b = mkplayer(29, birthplace="Dallas, TX", nat="USA", pid=1900 + i)
    a.contract.no_trade_clause = True
    b.contract.no_trade_clause = True
    rng = _r.Random(42 + i)
    if te.will_waive_ntc(a, home_team, no_tax, lg8, rng=rng)[0]:
        waive_notax += 1
    rng = _r.Random(42 + i)
    if te.will_waive_ntc(b, home_team, hi_tax, lg8, rng=rng)[0]:
        waive_hitax += 1
check("no-tax + home destination waived more",
      waive_notax > waive_hitax,
      f"notax={waive_notax}/{TRIALS} hitax={waive_hitax}/{TRIALS}")
c = mkplayer(29, birthplace="Dallas, TX", nat="USA", pid=2100)
c.contract.no_trade_list.append("Dallas Stars")  # explicitly listed: now
# the waiver negotiation (and its tax/home scoring) actually runs
ok, why = te.will_waive_ntc(c, home_team, no_tax, lg8,
                            rng=_r.Random(7))
check("reason cites the pull",
      "income tax" in why or "home" in why, why)

print(f"\nALL {len(passed)} M-NTC LIST QA CHECKS PASSED")
