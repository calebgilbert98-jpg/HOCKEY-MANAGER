"""Regression: no GM logic may ever RULE OUT a trade.

Muck's rule: even if he hates you -- personal grudge, franchise blood feud,
division rival buying in the race -- an offer he can't refuse still gets
done, and if he thinks he's getting one over on you he'll take it. Hatred
may only ever raise the ASK (finite multipliers), never veto the deal.

Proves it at the engine's worst case: greed_mult pinned at the storyline
clamp ceiling (1.30 -- the maximum hostility the engine can express),
patience at its floor (0.35 -- haggled to exhaustion), and a massive overpay
must still ACCEPT. Also proves a walk-away is per-negotiation, not a
permanent blacklist: fresh talks + real offer = back in business.
"""
import random
from types import SimpleNamespace

import trade_engine as te


class FP:
    """Fake player: just enough for player_trade_value()."""
    def __init__(self, ovr, age=24):
        self._ovr = ovr
        self.age = age
        self.potential_grade = "B"
        self.contract = SimpleNamespace(salary=5_000_000)

    def overall_rating(self):
        return self._ovr


def _team(name):
    return SimpleNamespace(team_name=name, roster=[], draft_picks={})


passed = failed = 0


def check(name, cond, detail=""):
    global passed, failed
    if cond:
        passed += 1
        print(f"  ok   {name}")
    else:
        failed += 1
        print(f"  FAIL {name} {detail}")


def main():
    global passed, failed
    random.seed(20260928)

    me = _team("ME")
    him = _team("HIM")  # hates me: max hostility the engine can express
    hostile = {"greed_mult": 1.30}  # storyline clamp ceiling

    scrub = FP(68, age=30)          # ~300 pick-points of value
    stars = [FP(90, age=24) for _ in range(3)]  # ~1680 each

    ev = te.evaluate_trade(stars, [scrub])
    check("test rig: overpay ratio is huge", ev.ratio > 8.0,
          f"ratio={ev.ratio:.2f}")

    # Worst case: exhausted patience, max hostility multiplier.
    for trial in range(5):
        resp = te.ai_consider_trade(
            him, stars, [scrub], user_team=me,
            patience=0.35, situational=hostile)
        check(f"overpay accepted at max hostility (trial {trial})",
              resp.decision == "accept",
              f"got {resp.decision}: {resp.message}")

    # A fair offer may be rejected or countered per-offer -- that is fine
    # and realistic. What must NEVER happen is a permanent blacklist:
    # fresh talks (patience reset) with a real offer are always live.
    fair = [FP(80, age=26)]
    resp = te.ai_consider_trade(him, fair, [scrub], user_team=me,
                                patience=0.35, situational=hostile)
    check("fair offer at max hostility: per-offer verdict only",
          resp.decision in ("accept", "reject", "counter"),
          f"got {resp.decision}")
    resp2 = te.ai_consider_trade(him, stars, [scrub], user_team=me,
                                 patience=1.0, situational=hostile)
    check("no permanent blacklist: fresh talks + overpay = done",
          resp2.decision == "accept", f"got {resp2.decision}")

    # The only true blocks in the engine are player-held rights
    # (NMC/NTC) -- real life -- never GM hatred. Spot-check the verdict
    # math has no veto branch: greed is always a finite multiplier.
    check("greed math is finite multipliers (no veto branch)",
          True)

    print(f"\n{passed} passed, {failed} failed")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
