# AHL Farm Confidence — Handoff Guide

## What it is
Farm performance now feeds players' confidence and attitude, but only
where it's situationally relevant. Once a week (Monday, inside
`main._career_weekly_update`), every farm roster in the league is measured
against the **same expected-production curves that generate the AHL stat
lines** — a kid "cooking" is genuinely beating what his attributes
project, never narrative on top of noise.

## The rules (all in `ahl_system.weekly_farm_confidence`)
| Situation | Effect |
|---|---|
| Prospect (≤23), ≥1.4× expected P/GP, 10+ GP | morale +4, `ahl_callup_buzz=True`, **one inbox note per season** (user's farm only) |
| Same, but has NHL GP this season | morale +6 ("give me another shot" energy) |
| Veteran (≥27) producing but never called up | happiness −3, morale −2 (quiet frustration, no inbox noise) |
| Young player ≤0.5× expected, 15+ GP | morale −4, happiness −2 |
| Goalie ≥.915 SV% (5+ GP) | morale +3, buzz + note |
| Goalie ≤.875 SV% | morale −3, happiness −1 |
| Anything else | no touch, buzz flag cleared |

Expected P/GP = `max(0.05, (ovr − 54) × 0.04)`; expected SV% =
`.880 + (ovr − 55) × 0.0012` — identical to `_skater_game`/`_goalie_game`.

## Integration (additive only — nothing of yours was modified)
- The morale moves flow into your existing systems untouched: the
  situational call-up readiness term "Confidence right now" reads
  `morale`, and the weekly happiness/morale chain in `manager_career`
  picks up the happiness moves.
- `prospect_development.callup_readiness` and `_moment_terms`: **not touched**.
- New player attributes (plain bools — save/load round-trips via the
  generic `__dict__` path, `getattr` defaults cover old saves):
  - `ahl_callup_buzz` — live flag, recomputed weekly; cleared for anyone
    on an NHL roster so it can't go stale after a call-up.
  - `ahl_buzz_note_sent` — gates the one-per-season inbox note; reset in
    `League.end_of_season` next to the AHL ledger wipe.
- Hook: 8 lines in `main._career_weekly_update`, wrapped in try/except.

## Perf
~800 farm players × a handful of attribute reads, once a week.
Microseconds; no per-frame or per-day cost. AHL sim itself untouched.

## QA
`qa_ahl_confidence.py` — 39/39 headless (DISPLAY=:99): all six
situations, note-once-per-season gating, AI-farm silence, buzz clearing
on call-up, clamp behavior (morale 1–100, happiness 0–100), flag
round-trip through `GameSaveManager`, rollover reset, and the main.py
hook executed against a fake app. Regressions still green:
bracket 67/67, stats/AHL/Smythe 40/40, playoff-threaded 12/12,
prospect_development 81/81.
