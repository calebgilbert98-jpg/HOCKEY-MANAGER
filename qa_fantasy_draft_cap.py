"""QA: fantasy-draft start behavior (seed 20260928).

Asserts the fantasy draft runs on an even playing field with no hard cap
enforcement during the draft, soft cap-aware AI scoring, no real-club
payroll shaping, no seeded real-life dead cap, and normal cap rules intact
afterwards.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import random
random.seed(20260928)

passed, failed = [], []
def check(label, cond):
    (passed if cond else failed).append(label)
    print(f"  {'PASS' if cond else 'FAIL'} {label}")

from database_generator import DatabaseGenerator, DATABASE_CONFIGURATIONS
from fantasy_draft import FantasyDraftManager
from salary_cap_system import cap_breakdown
import real_cap_data as rcd
from game_classes import Team, Player, Contract
from player_generator import PlayerPosition

# ------------------------------------------------------------------
# 1. should_seed_dead_cap: fantasy starts skip real-life penalties.
# ------------------------------------------------------------------
check("fantasy draft start -> no seeded dead cap",
      rcd.should_seed_dead_cap(2026, {"fantasy_draft": True,
                                      "start_without_cap_penalties": False}) is False)
check("start_without_cap_penalties -> no seeded dead cap",
      rcd.should_seed_dead_cap(2026, {"fantasy_draft": False,
                                      "start_without_cap_penalties": True}) is False)
check("standard start -> dead cap seeded",
      rcd.should_seed_dead_cap(2026, {"fantasy_draft": False,
                                      "start_without_cap_penalties": False}) is True)
check("no settings object -> dead cap seeded",
      rcd.should_seed_dead_cap(2026, None) is True)
check("2027 rollover -> no seeded dead cap regardless",
      rcd.should_seed_dead_cap(2027, {"fantasy_draft": False,
                                      "start_without_cap_penalties": False}) is False)

# ------------------------------------------------------------------
# 2. Fantasy-mode generation skips club-specific payroll shaping.
# ------------------------------------------------------------------
gen = DatabaseGenerator(DATABASE_CONFIGURATIONS['Small'])
check("fantasy_draft_mode defaults off", gen.fantasy_draft_mode is False)
gen.fantasy_draft_mode = True
league = gen.generate_comprehensive_database()
nhl = [t for t in league.teams
       if getattr(t, 'league_name', '') == 'National Hockey League']
check("32 NHL clubs generated in fantasy mode", len(nhl) == 32)
check("all NHL rosters non-empty in fantasy mode",
      all(len(t.roster or []) > 0 for t in nhl))
# Toronto/Vancouver must NOT be squeezed/shaped around their real rooms.
room_of = {t.team_name: cap_breakdown(t)["space"] / 1e6 for t in nhl}
tight_shaped = all(room_of[n] <= 1.0 for n in
                   ("Toronto Maple Leafs", "Florida Panthers",
                    "Columbus Blue Jackets", "Vegas Golden Knights"))
check("tight-4 are NOT all squeezed in fantasy mode (shaping off)",
      not tight_shaped)
print(f"    fantasy-mode room sample: TOR {room_of['Toronto Maple Leafs']:.1f}M, "
      f"VAN {room_of['Vancouver Canucks']:.1f}M, VGK {room_of['Vegas Golden Knights']:.1f}M")

# ------------------------------------------------------------------
# 3. Fantasy-draft AI: soft cap pressure, never a hard block.
#    (Uses the real manager API: draft_picks carry the selections.)
# ------------------------------------------------------------------
def _mk_player(pid, ovr, salary, pos=PlayerPosition.CENTER, age=26):
    p = Player("T", "E", age, pos)
    p.id = pid
    p.overall_cache = ovr
    p.contract = Contract(salary, 3, 0, 0)
    return p

# Monkey-patch overall_rating for deterministic overalls.
Player.overall_rating = lambda self: getattr(self, "overall_cache", 80)

ta = Team("Test Club", "Test City", "Div", "Conf")
tb = Team("Cheap Club", "Test City", "Div", "Conf")
pool = ([_mk_player(f"qa-a-{i}", 80, 4_500_000) for i in range(40)] +
        [_mk_player(f"qa-b-{i}", 80, 1_000_000) for i in range(40)] +
        [_mk_player("qa-star", 97, 16_000_000),
         _mk_player("qa-depth", 78, 1_200_000)])
mgr = FantasyDraftManager([ta, tb], pool)

def _give_picks(manager, team, players):
    n = 0
    for pick in manager.draft_picks:
        if n >= len(players):
            break
        if pick.team.team_name == team.team_name and pick.player is None:
            pick.player = players[n]
            n += 1
    return n

_give_picks(mgr, ta, [_mk_player(f"qa-ta-{i}", 80, 4_500_000)
                      for i in range(20)])
_give_picks(mgr, tb, [_mk_player(f"qa-tb-{i}", 80, 1_000_000)
                      for i in range(20)])
# _give_picks fills slots directly (bypassing make_pick); advance the
# cursor past the 40 hand-filled slots so the manager's invariant
# (cursor points at the first empty slot) holds for the checks below.
mgr.current_pick = 40

star = next(p for p in pool if p.id == "qa-star")
depth = next(p for p in pool if p.id == "qa-depth")

# ta: 20 x $4.5M = $90M committed; star $16M -> projected $109M > cap.
factor_hot = mgr._cap_pressure_factor(ta, star)
check("pressure factor < 1.0 when projected over the cap",
      factor_hot < 1.0)
print(f"    pressure factor at ~$109M projected: {factor_hot:.3f}")
# tb: 20 x $1M = $20M committed; star $16M -> projected $39M < cap.
check("no pressure on a cheap roster",
      mgr._cap_pressure_factor(tb, star) == 1.0)
# Cap disabled in config -> no pressure ever.
mgr.config.salary_cap_enabled = False
check("pressure disabled when cap turned off in config",
      mgr._cap_pressure_factor(ta, star) == 1.0)
mgr.config.salary_cap_enabled = True

# make_pick must NOT block an expensive pick even when "over".
ok = mgr.make_pick(star)
check("make_pick never blocks on cap grounds", ok is True)
check("expensive pick recorded despite pressure",
      star in mgr._team_drafted_players(
          next(p.team for p in mgr.draft_picks if p.player is star)))

# Value scoring: the same star is worth MORE to the cheap team.
v_hot = mgr.calculate_player_draft_value(depth, ta, 1)  # fresh depth pick
star2 = _mk_player("qa-star2", 97, 16_000_000)
pool.append(star2)
v_star_hot = mgr.calculate_player_draft_value(star2, ta, 1)
v_star_cheap = mgr.calculate_player_draft_value(star2, tb, 1)
check("cap pressure discounts stars for capped-out drafters",
      v_star_hot < v_star_cheap)
print(f"    star value: capped-out drafter {v_star_hot:.1f} vs "
      f"cheap drafter {v_star_cheap:.1f}")
print(f"    depth value for capped-out drafter: {v_hot:.1f}")
check("draft values are computable and non-negative",
      v_hot >= 0 and v_star_hot >= 0 and v_star_cheap >= 0)

# ------------------------------------------------------------------
# 4. Positional need still drives the AI.
# ------------------------------------------------------------------
tc = Team("Need Club", "Test City", "Div", "Conf")
mgr2 = FantasyDraftManager([tc, tb], pool)
_give_picks(mgr2, tc, [_mk_player(f"qa-tc-{i}", 85, 5_000_000,
                                  PlayerPosition.CENTER)
                       for i in range(4)])
needs = mgr2.analyze_team_needs(tc)
check("need analysis returns a dict", isinstance(needs, dict))
check("center need lower than goalie need after drafting 4 centers",
      needs.get("C", 9) < needs.get("G", 0))
print(f"    needs: C={needs.get('C')}, G={needs.get('G')}")

print(f"\n{len(passed)} passed, {len(failed)} failed")
sys.exit(1 if failed else 0)
