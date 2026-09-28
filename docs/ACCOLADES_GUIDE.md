# Player Accolades (Trophy Case) — Handoff Guide

**For:** calebgilbert98 · **Date:** 2026-09-28 · **Status:** built, QA green, committed unpushed

## What it is

A permanent, de-duplicated trophy case on every player. Muck's spec, verbatim:

    Hart Trophy Winner: 2021, 2025
    Rocket Richard Winner: 2021
    Stanley Cup Winner: 2021-22, 2022-23, 2023-24

One line per award, years comma-separated, never a duplicate entry.

## Design

**Storage** — `Player.career_accolades: list` (game_classes.py), plain dicts
`{"award": key, "year": label}`. Save/load round-trips via the existing
generic `__dict__` walk — zero new serialization code. Old saves: read via
`getattr(player, 'career_accolades', [])`.

**Module** — `accolades.py` (new, standalone — nothing of yours touched):
- `bank_accolade(player, award_key, year_label)` — idempotent on
  (award, year); re-running a rollover can never duplicate.
- `group_accolades(player)` — `[(label, [years...]), ...]` in display
  order (Cup first, then Hart → Jennings), years ascending.
- `lady_byng` normalized to `byng` at bank time.

**Year conventions** (his format): individual awards use the ceremony year
("2025" for the 2024-25 season); the Cup uses the season label ("2024-25").

**Banking points** (main.py, additive only — your award/reputation logic untouched):
1. `_update_player_reputations` — season awards (Hart, Art Ross, Rocket,
   Vezina, Norris, Selke, Byng, Calder) banked onto each winner in the same
   loop that feeds reputation. Same `_reputation_updated_for_season` guard,
   plus idempotent banking as a backstop.
2. `_update_offseason_reputations` — Stanley Cup banked onto every
   champion-roster player next to `rs.award_championship(p)`.

**Key gap this exposed:** before this change, season awards were calculated
but never persisted to any player — they only lived in the season recap.
The trophy case starts filling from this season forward; past seasons in old
saves have no banked awards (honest, not backfilled).

**UI** — `PlayerProfileView._create_accolades`: "🏆 Accolades" panel in the
Overview tab's left (career) column, directly under Career Progression and
above Signature Games. Empty state: "No awards yet."

## Deliberately out of scope

- **Jennings / Jack Adams** — team/coach-level awards, not player trophy-case
  entries. Keys exist in `ACCOLADE_LABELS` if you want them later.
- **Conn Smythe** — no winner is ever decided anywhere in the codebase
  (the slot exists but is always None). When a playoff-MVP selection exists,
  one `bank_accolade(p, "conn_smythe", year)` call wires it in.
- Don't bank from anywhere but the two hooks above — one banking point per
  award type, or the idempotency guarantee can't do its job.

## QA

- `qa_accolades.py` — 17/17: idempotent banking, exact display format,
  Cup-first ordering, key normalization, junk/old-save safety, save/load
  round-trip.
- Regressions: `qa_player_cards` 11/11, `qa_career_moments` 18/18;
  headless profile render verified (exact "Hart Trophy Winner: 2021, 2025"
  line present alongside Signature Games).
