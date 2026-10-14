"""Fix A acceptance: dress-minimum guard rescoped to the Oct-7 goalie bug.

1. Goalie regression (Oct-7 bug stays fixed): a club with exactly 2
   goalies trading one away for futures is BLOCKED.
2. Rental archetype unblocked: 1 skater for picks with AHL backfill
   available is ALLOWED (the 2,187-blocked-deals defect).
3. No-backfill edge: 1 skater for picks with an empty farm is still
   BLOCKED (conservative: never leave a club that cannot dress).
4. Sanity: a balanced 1-for-1 skater swap at exactly 18 skaters stays
   legal (incoming counts, UI-BUG-04).

Deterministic: no randomness involved in the guard.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from game_classes import Player, PlayerPosition, Contract, Team, DraftPick
import roster_limits as rl


def _mkplayer(ovr, age, pos, salary=1_000_000):
    p = Player("Test", "Player", age, pos)
    p.overall_rating = lambda: ovr  # noqa: E731 -- deterministic test overall
    p.contract = Contract(salary=salary, years_remaining=2)
    return p


def _mkteam(name, n_skaters, n_goalies, n_ahl_skaters):
    t = Team(name, "City", "Div", "Conf")
    t.roster = ([_mkplayer(75, 28, PlayerPosition.CENTER)
                 for _ in range(n_skaters)]
                + [_mkplayer(80, 30, PlayerPosition.GOALIE)
                   for _ in range(n_goalies)])
    t.ahl_roster = [_mkplayer(68, 22, PlayerPosition.CENTER)
                    for _ in range(n_ahl_skaters)]
    t.draft_picks = {}
    return t


def _pick(**kw):
    return DraftPick(year=2030, round=1,
                     original_team="Somewhere", current_team="Somewhere",
                     **kw)


def test_goalie_trade_away_blocked():
    """Oct-7 regression: 2 goalies -> trading one away leaves 1: BLOCKED."""
    t = _mkteam("GTest", n_skaters=20, n_goalies=2, n_ahl_skaters=4)
    goalie = next(p for p in t.roster
                  if p.primary_position == PlayerPosition.GOALIE)
    blocked, reason = rl.trade_breaks_dress_minimum(
        t, [goalie], [_pick()])
    assert blocked, "trading away one of 2 goalies must stay blocked"
    assert "goalie" in reason


def test_goalie_swap_stays_legal():
    """1-for-1 goalie swap at exactly 2 goalies: ALLOWED (incoming counts)."""
    t = _mkteam("GSwap", n_skaters=20, n_goalies=2, n_ahl_skaters=4)
    goalie_out = next(p for p in t.roster
                      if p.primary_position == PlayerPosition.GOALIE)
    goalie_in = _mkplayer(82, 29, PlayerPosition.GOALIE)
    blocked, _ = rl.trade_breaks_dress_minimum(
        t, [goalie_out], [goalie_in])
    assert not blocked, "1-for-1 goalie swap must stay legal"


def test_skater_for_picks_with_backfill_allowed():
    """The rental archetype: 18 skaters -> 17 + AHL backfill: ALLOWED."""
    t = _mkteam("Rent", n_skaters=18, n_goalies=2, n_ahl_skaters=5)
    skater = next(p for p in t.roster
                  if p.primary_position != PlayerPosition.GOALIE)
    blocked, reason = rl.trade_breaks_dress_minimum(
        t, [skater], [_pick()])
    assert not blocked, f"rental-for-picks with farm backfill blocked: {reason}"


def test_skater_for_picks_without_backfill_blocked():
    """18 skaters -> 17 with an empty farm: still BLOCKED."""
    t = _mkteam("NoFarm", n_skaters=18, n_goalies=2, n_ahl_skaters=0)
    skater = next(p for p in t.roster
                  if p.primary_position != PlayerPosition.GOALIE)
    blocked, _ = rl.trade_breaks_dress_minimum(
        t, [skater], [_pick()])
    assert blocked, "no-backfill rental must stay blocked"


def test_balanced_swap_at_minimum_stays_legal():
    """1-for-1 skater swap at exactly 18: ALLOWED (UI-BUG-04)."""
    t = _mkteam("Swap", n_skaters=18, n_goalies=2, n_ahl_skaters=0)
    out = next(p for p in t.roster
               if p.primary_position != PlayerPosition.GOALIE)
    inc = _mkplayer(76, 27, PlayerPosition.LEFT_WING)
    blocked, _ = rl.trade_breaks_dress_minimum(t, [out], [inc])
    assert not blocked, "balanced 1-for-1 swap at the minimum must stay legal"


def test_old_guard_untouched_for_demotions():
    """would_break_dress_minimum keeps its strict semantics for the
    demotion caller (no behavior change outside trades)."""
    t = _mkteam("Dem", n_skaters=18, n_goalies=2, n_ahl_skaters=5)
    skater = next(p for p in t.roster
                  if p.primary_position != PlayerPosition.GOALIE)
    # Old function: 18 -> 17 breaks, even with a full farm.
    assert rl.would_break_dress_minimum(t, [skater]) is True


# ---------------------------------------------------------------------------
# Fix A follow-up: post-trade AI recall (adversarial finding 1)
# ---------------------------------------------------------------------------

import trade_engine as te


def _drain_ai_team():
    """AI team at 16 skaters with a 4-man farm (post-drain state)."""
    t = _mkteam("AI", n_skaters=16, n_goalies=2, n_ahl_skaters=4)
    t.is_user_team = False
    return t


def test_post_trade_recall_restores_ai_lineup():
    """Counted backfill is actually recalled for AI sides."""
    t = _drain_ai_team()
    assert not rl.can_dress_lineup(t)
    te._post_trade_ai_recall(t, None)
    assert rl.can_dress_lineup(t), "AI team must be restored to 18 skaters"
    assert len(t.ahl_roster) == 2, "exactly the 2-man shortfall is recalled"


def test_post_trade_recall_skips_human_team():
    """Human-managed clubs keep human recall decisions."""
    t = _drain_ai_team()
    t.is_user_team = True
    te._post_trade_ai_recall(t, None)
    assert not rl.can_dress_lineup(t), "human team must be left for the user"
    assert len(t.ahl_roster) == 4, "farm untouched for human team"


def test_chained_deals_cannot_recount_backfill():
    """Deal 1 allowed on backfill -> recall moves it -> deal 2 blocked."""
    t = _mkteam("Chain", n_skaters=18, n_goalies=2, n_ahl_skaters=2)
    t.is_user_team = False
    skaters = [p for p in t.roster
               if p.primary_position != PlayerPosition.GOALIE]
    # Deal 1: 18 -> 16, farm covers 2/2 -> allowed.
    blocked1, _ = rl.trade_breaks_dress_minimum(t, skaters[:2], [_pick()])
    assert not blocked1
    # Simulate the completed deal: move the players out, recall the farm.
    for p in skaters[:2]:
        t.roster.remove(p)
    te._post_trade_ai_recall(t, None)
    assert rl.can_dress_lineup(t)
    assert len(t.ahl_roster) == 0
    # Deal 2: another 2 out -> farm is empty -> BLOCKED (no double-count).
    skaters2 = [p for p in t.roster
                if p.primary_position != PlayerPosition.GOALIE]
    blocked2, reason2 = rl.trade_breaks_dress_minimum(
        t, skaters2[:2], [_pick()])
    assert blocked2, f"chained drain must block once backfill is spent: {reason2}"


# ---------------------------------------------------------------------------
# Copilot PR #12 findings
# ---------------------------------------------------------------------------

def test_incoming_ahl_goalie_does_not_satisfy_goalie_block():
    """Finding 1: a farm goalie stays on the farm (_source_roster_type)
    and must NOT satisfy the 2-goalie hard block."""
    t = _mkteam("FarmG", n_skaters=20, n_goalies=2, n_ahl_skaters=0)
    partner = _mkteam("Part", n_skaters=20, n_goalies=2, n_ahl_skaters=0)
    farm_goalie = _mkplayer(75, 24, PlayerPosition.GOALIE)
    partner.ahl_roster.append(farm_goalie)
    # The tier filter drops the farm goalie before the guard ever sees it.
    assert te._nhl_tier_incoming(partner, [farm_goalie]) == []
    goalie_out = next(p for p in t.roster
                      if p.primary_position == PlayerPosition.GOALIE)
    blocked, reason = rl.trade_breaks_dress_minimum(
        t, [goalie_out], te._nhl_tier_incoming(partner, [farm_goalie]))
    assert blocked, "a farm goalie must not satisfy the goalie hard block"
    assert "goalie" in reason


def test_incoming_nhl_goalie_still_counts():
    """Finding 1 companion: genuine NHL-roster incoming is kept (no
    over-blocking of real 1-for-1 goalie swaps)."""
    partner = _mkteam("Part2", n_skaters=20, n_goalies=2, n_ahl_skaters=0)
    nhl_goalie = next(p for p in partner.roster
                      if p.primary_position == PlayerPosition.GOALIE)
    assert te._nhl_tier_incoming(partner, [nhl_goalie]) == [nhl_goalie]
    # And a player on no list at all defaults to NHL-tier (mirrors
    # _source_roster_type).
    floater = _mkplayer(80, 27, PlayerPosition.CENTER)
    assert te._nhl_tier_incoming(partner, [floater]) == [floater]


def test_tier_filter_matches_source_roster_type_equality():
    """Adversarial (a): the tier filter must mirror _source_roster_type's
    Player.id-based equality -- an equal-but-not-identical farm object
    must still be excluded."""
    partner = _mkteam("Part3", n_skaters=20, n_goalies=2, n_ahl_skaters=0)
    farm_goalie = _mkplayer(75, 24, PlayerPosition.GOALIE)
    partner.ahl_roster.append(farm_goalie)
    twin = _mkplayer(75, 24, PlayerPosition.GOALIE)
    twin.id = farm_goalie.id  # equal (==) but not identical (is)
    assert twin == farm_goalie and twin is not farm_goalie
    assert te._nhl_tier_incoming(partner, [twin]) == [], \
        "equal-but-not-identical farm goalie must be excluded"


def test_restore_dressed_lineup_capped_at_23():
    """Finding 2: 23-man roster + injuries -> real recalls are capped at
    the 23-man limit; count-exempt fillers cover the rest (no forced
    paper-down -- possible waiver exposure -- at the next day gate)."""
    t = _mkteam("Cap23", n_skaters=21, n_goalies=2, n_ahl_skaters=4)
    assert rl.active_roster_count(t) == 23
    for p in [p for p in t.roster
              if p.primary_position != PlayerPosition.GOALIE][:6]:
        p.is_injured = True
    assert not rl.can_dress_lineup(t)  # 15 dressable skaters
    done = rl.restore_dressed_lineup(t)
    assert done["recalled"] == 0, "no room under the 23-man max"
    assert done["summoned"] == 3, "fillers cover the 3-man shortfall"
    assert rl.active_roster_count(t) == 23, "23-man max respected"
    assert rl.can_dress_lineup(t)
    assert len(t.ahl_roster) == 4, "farm untouched when there's no room"


def test_restore_dressed_lineup_recalls_when_room():
    """Companion: with room under 23, real farm players are recalled
    before any fillers are summoned."""
    t = _mkteam("Room", n_skaters=16, n_goalies=2, n_ahl_skaters=4)
    t.is_user_team = False
    done = rl.restore_dressed_lineup(t)
    assert done["recalled"] == 2
    assert done["summoned"] == 0
    assert rl.can_dress_lineup(t)
    assert len(t.ahl_roster) == 2
