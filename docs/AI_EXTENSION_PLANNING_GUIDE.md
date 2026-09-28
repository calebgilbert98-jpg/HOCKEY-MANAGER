# AI Extension Planning Guide

## What it is
`ai_extension_planning.py` — every AI GM now plans extensions the way a user
does: the franchise core's upcoming raises are reserved **first**, and
everything else (depth extensions, UFA shopping) spends from what's left.
If the $15M franchise center is due next summer, the questionable second-pair
guy doesn't get $9M today.

## The forward book
`plan(team, identity, strategy, ask_fn, cap_ceiling, current_charge,
current_date, league_min)` returns an `ExtensionPlan`:

- `pieces` — (player, score), best first. **Not just star power**: a 20-year-old
  B-potential first-rounder at 74 overall scores as a piece (potential grade ×
  youth, draft pedigree, ELC second-contract kicker, homegrown bonus). A loyal
  GM values his drafted kids more; a patient GM bets bigger on development; an
  aggressive GM only respects the finished product.
- `reserved` — the *raises* (projected next AAV minus current salary) for pieces
  with `years_remaining` in (0, 1, 2). Year 2 can't be extended yet (window
  closed) but the money is still earmarked.
- `discretionary` — cap ceiling minus (committed payroll + reserved + roster-fill
  floor). `crunch=True` when even the core doesn't fit.
- `queue` — window-eligible (yr 0/1) candidates, piece-first, each with
  `priority`, `projected`, and `max_offer`. Aggressive GMs pay +3% to lock a
  piece early (the Carlsson lesson); patient GMs won't bid against themselves;
  loyal GMs +5% for homegrown pieces.

## GM ability
`gm_ability01` (experience + tenure + reputation). Good GMs project the ask
within ~2%. Bad GMs misjudge **both ways** — they lowball star asks (cap
surprise coming) and overrate depth (the overpay pipeline). Deterministic, no
RNG.

## Parity: one rulebook
Per Muck's order there is **no parity gap** between AI and user. Both
`_evaluate_contract_extensions` and `_execute_contract_extension` in
`ai_team_management.py` now call
`transaction_windows.check_window("extension", …)` — the exact function
gating the user's path. The old local `years_remaining != 1` copies are gone,
so the AI also gets the June exclusive re-sign window (yr 0 post-decrement).

## Wiring (ai_team_management.py)
- `process_daily_decisions` builds the plan per team each pass into
  `self._ext_plans[team_name]`.
- `_evaluate_contract_extensions`: candidates iterate piece-first; a non-piece
  offer is skipped when it exceeds the remaining discretionary pool (pieces
  draw from reserved, not discretionary).
- `_evaluate_free_agency`: `available_budget` subtracts `plan.reserved`; in a
  crunch the team doesn't shop UFAs at all.

## Scout perception vs the GM's eyes (scout_trust)

The "future" half of `franchise_score` blends two reads of a young player:

- **The franchise scouts' perception** — `potential_grade`, the org belief
  the scouting staff's reports built (shaped over time by
  `scout_reveal_step` with the head scout's JPP).
- **The GM's own eyes** — current overall mapped onto the grade ladder
  (`_gut_grade_index`: 66→F … 74→C … 85→A- … 90+→A+).

`scout_trust(identity)` (0..1, adaptability-led, patience secondary)
weights them: a stubborn old-school GM (trust ≈ 0.15) overrules his scouts
with his gut — he'll buy a kid the scouts are down on and stay cold on a
"B" the scouts love. An adaptable modern GM (trust → 1.0) leans fully on
the reports. Either way the GM's **vision** (loyalty/patience/aggression)
keeps the ultimate say — trust only weights the information, never the
call. Established stars are unaffected (face value dominates their score).

## Trade-screen value tags (EHM-style)

`trade_value_tier(player, identity, strategy)` → `(label, color, score)` —
the same `franchise_score`, so the tag and the money the GM reserves always
agree. `UNTOUCHABLE` (80+, red — true cornerstones only), `CORE` (50+,
gold), `VALUED` (35+, teal), `GETTABLE` (dim). Wired in `windows.py`:
`gm_trade_value_badges(ai_manager, team)` builds the `badge_fn` that
`CTkPlayerList.set_players(..., badge_fn=...)` renders on the partner's
roster — with a legend under the level selector. The user's own list shows
no tags (he knows his own values). Falls back to a neutral read when the
AI manager/identity is unavailable.

## What NOT to touch
- The offer math in `_evaluate_contract_extensions` (ask × boldness, room
  check) and `_execute_contract_extension` terms are caleb's — the planner
  only orders candidates and gates non-core spend.
- `franchise_score` thresholds (`_PIECE_SCORE_THRESHOLD = 50`,
  `_STAR_OVERRIDE_OVR = 86`) are tuning knobs, safe to adjust.

## QA
`qa_ai_extension_planning.py` — 32 checks: piece ID (incl. the low-overall
future piece), GM subjectivity, ability-graded projection, reservation math,
the $15M-man scenario, crunch, personality pricing, rulebook parity, wiring.
`qa_trade_values.py` — 33 checks: tier bands, tag/book agreement, GM
subjectivity (incl. scout_trust boundaries, the scout-overrule case, star
stability, determinism), badge_fn wiring from the real `AITeamManager`,
headless `CTkPlayerList` badge rendering + backward compatibility.
