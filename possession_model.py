"""Possession model: one decision for what happens to the puck after a shot.

Thesis: single-game shot totals must vary like real hockey (team std ~6,
not ~13). The old model retained attacking O-zone possession after ~90% of
saves -- every stop chained into another chance, so a few marathon sieges
decided the shot count. Real hockey breaks possessions constantly: goalies
cover pucks, defenders clear rebounds, pucks go loose.

This module is the single decision both engines share ("one decision, two
fidelities"):
  - GameSim (simulation.py) calls after_shot() on every save/miss/block and
    applies all four outcomes -- its possession chains are where the
    variance lived.
  - AdvancedGameSim (quick_sim.py) resolves each shot independently with no
    rebound chains; that independence IS the low-variance fidelity, so it
    needs no call. Its measured single-game SOG std (~7.5) already sits
    near the real ~6.

Outcomes:
  FREEZE  -- goalie covers / puck out of play: faceoff (existing path).
  DEFENSE -- defending team gains clean possession (clears/breakouts next).
  LOOSE   -- puck loose: both teams battle (existing _resolve_loose_puck_battle).
  RETAIN  -- attacking team keeps O-zone possession (the old default).

Base tables are calibrated so possessions break up like real hockey while
second chances stay alive -- roughly one in three saves still extends the
attack. The per-tick OZ shot rate (simulation.py shot_chance) is tuned
against these tables so the league mean stays ~29 SOG/team/game and scoring
stays in the 2.70-3.60 band: more, shorter possessions, same total volume.

Personality channels (additive, never overridden):
  freeze_mult   -- goalie_personality save_effects: calm technicians cover
                   more pucks; battlers play everything.
  rebound_shift -- goalie_personality.rebound_shift: scramblers kick pucks
                   back into play (freeze -> retain), technicians swallow
                   them (retain -> freeze).
"""

import random

FREEZE = "freeze"
DEFENSE = "defense"
LOOSE = "loose"
RETAIN = "retain"

OUTCOMES = (FREEZE, DEFENSE, LOOSE, RETAIN)

# Base outcome mix per shot result. Rows sum to 1.0.
# save: the old code froze ~9% and retained ~91% -- every stop chained into
#   another chance, which is what blew single-game variance to std ~13.
#   Real hockey: the goalie covers or the defense clears most stops, but
#   net-front second chances are still common -- ~40% of saves extend the
#   attack (expected chain ~1.7 shots, not ~10). Faceoffs run ~25-30/game
#   here vs ~60 in the real NHL, so there is realism headroom on the
#   whistle without distorting game flow.
# miss:  rim-arounds are usually retrieved or go loose; rarely a whistle.
# block: blocks spray pucks loose; the shooter almost never keeps it clean.
_BASE = {
    "save":  {FREEZE: 0.28, DEFENSE: 0.20, LOOSE: 0.12, RETAIN: 0.40},
    "miss":  {FREEZE: 0.04, DEFENSE: 0.24, LOOSE: 0.37, RETAIN: 0.35},
    "block": {FREEZE: 0.00, DEFENSE: 0.28, LOOSE: 0.47, RETAIN: 0.25},
}


def after_shot(result, quality=0.4, freeze_mult=1.0, rebound_shift=0.0,
               rng=None):
    """Decide the puck's fate after a resolved shot.

    result: "save" | "miss" | "block".
    quality: 0..1 shot danger -- dangerous looks get covered more often.
    freeze_mult: goalie-personality multiplier on the freeze channel.
    rebound_shift: goalie-personality delta; positive moves probability
        from freeze to retain (scrambler kicking out rebounds), negative
        the reverse (technician swallowing pucks).
    Returns one of FREEZE / DEFENSE / LOOSE / RETAIN.
    """
    r = rng.random if rng else random.random
    table = _BASE.get(result, _BASE["save"])
    p = dict(table)

    try:
        q = max(0.0, min(1.0, float(quality)))
    except (TypeError, ValueError):
        q = 0.4
    # Dangerous looks get covered: freeze scales ~0.7x-1.3x across quality.
    p[FREEZE] *= 0.7 + 0.6 * q
    try:
        p[FREEZE] *= max(0.2, min(3.0, float(freeze_mult)))
    except (TypeError, ValueError):
        pass
    # Temperament: scramblers feed second chances, technicians end them.
    try:
        s = max(-0.25, min(0.25, float(rebound_shift)))
    except (TypeError, ValueError):
        s = 0.0
    if s:
        move = min(s, p[FREEZE]) if s > 0 else -min(-s, p[RETAIN])
        p[FREEZE] -= move
        p[RETAIN] += move

    total = sum(p.values())
    if total <= 0:
        return RETAIN
    roll = r() * total
    for outcome in OUTCOMES:
        roll -= p[outcome]
        if roll <= 0:
            return outcome
    return RETAIN


def retain_probability(result="save", quality=0.4, freeze_mult=1.0,
                       rebound_shift=0.0):
    """Expected P(RETAIN) -- for tuning/diagnostics without sampling."""
    table = dict(_BASE.get(result, _BASE["save"]))
    try:
        q = max(0.0, min(1.0, float(quality)))
    except (TypeError, ValueError):
        q = 0.4
    table[FREEZE] *= (0.7 + 0.6 * q)
    try:
        table[FREEZE] *= max(0.2, min(3.0, float(freeze_mult)))
    except (TypeError, ValueError):
        pass
    try:
        s = max(-0.25, min(0.25, float(rebound_shift)))
    except (TypeError, ValueError):
        s = 0.0
    if s:
        move = min(s, table[FREEZE]) if s > 0 else -min(-s, table[RETAIN])
        table[FREEZE] -= move
        table[RETAIN] += move
    total = sum(table.values())
    return table[RETAIN] / total if total > 0 else 0.0
