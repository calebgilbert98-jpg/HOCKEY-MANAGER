# Board Patience Model — Guide

**Commit:** board patience retune (2026-09-28, Muck's direction).
**QA:** `qa_board_patience.py` 43/43. Regression: `qa_lore_save_load` 34/34.

## Design principle

Boards judge **trends, not games**. The old model moved confidence ±4–7 *every
game* — a 5-game skid cost ~25 points, so a 9-7-1 first-year start had the
board "wobbling in the low 40s". That was wrong on three counts: no honeymoon
for a new GM, monthly bands that ignored the expectation tier, and three
channels (games + monthly + press) punishing the same stretch.

## The new model

### 1. Per-game: exception-only (`BoardSystem.record_result`)
Routine games move **nothing**. The board intervenes only when it's dire:
- **8-game losing streak** → −10 (patience-dampened), formal warning, news item.
- **8-game winning streak** → +5, board delighted.
- **Disastrous start** (≤15% points through 8–12 games) → −12, honeymoon void.
  A 0-10 start puts a fire under anyone.
- **12-game skid** → disaster flag: even a year-one GM can be sacked now.
- Playoffs: ±2/−3 (short series, every game matters, modestly).

`board.last_crisis` carries the headline; `main.py` surfaces it as news.

### 2. Monthly reviews: the real channel (`monthly_review`)
Bands are **expectation-aware** (`MONTHLY_BANDS`):

| Expectation | Delighted | Satisfied | Concerned | Alarmed |
|---|---|---|---|---|
| win_cup | ≥.68 (+5) | ≥.58 (+2) | ≥.48 (−4) | else (−8) |
| contend | ≥.62 (+5) | ≥.54 (+2) | ≥.44 (−3) | else (−7) |
| playoffs | ≥.58 (+4) | ≥.50 (+2) | ≥.40 (−3) | else (−6) |
| rebuild | ≥.50 (+4) | ≥.42 (+2) | ≥.32 (−2) | else (−5) |

A rebuild board at .450 is *satisfied* — it judges development, not standings.

### 3. Patience factor (situational modifier)
Seeded by `on_hired()` on day one; divides every negative delta:
- Year 1: **1.4** (honeymoon — bumpy starts expected)
- Year 2: 1.15, Year 3+: 1.0
- Inherited rebuild (<52 strength or rebuild expectation): +0.2
- Young roster (avg age <26): +0.1
- Recent Cups: +0.3 each (max 2, decays yearly)
- Each missed-expectation year erodes −0.15 (floor 0.7); meeting it rebuilds +0.1.

Owners don't rotate GMs every year — but patience is finite.

### 4. Anti-double-jeopardy
- **Monthly negative cap (−12):** crisis + monthly + press in the same month
  can't stack past −12. If the cap absorbs part of a review, the email says so
  honestly ("it won't punish you twice for the same run of results").
- **Comeback boost:** positive movement ×1.5 when confidence < 25 — a win at
  rock bottom is a lifeline.
- Big one-off events (scandal) bypass the cap — they're discrete, not the
  same stretch twice.

### 5. Ask the owner for patience (`request_patience`)
GM-initiated, from the Manager Hub Board tab (or the inbox nudge at <40
confidence). Only when confidence < 55; 120-day cooldown.
- **Owner personalities** (`OwnerProfile`): patient_builder (75% grant),
  demanding (35%), meddler (55%, attaches conditions in the flavor text),
  distant (50%). Seeded per club at hire.
- **Granted:** +3, negatives halved 60 days, roster morale +2 (the room settles).
- **Refused:** −4, negatives ×1.25 for 60 days (spent capital, kept losing),
  refusals stack −15% on future asks.
- Year-one GMs get +10% grant chance (new hire, inherited situation).

### 6. Year-one sack rule
A first-year GM **cannot be sacked** unless it's a genuine disaster: scandal,
disastrous start, or 12-game skid (`_disaster` flag). Otherwise confidence
floors at 1 — the seat is hot, but the project continues.

## Wiring (main.py)
- Career start: `board.on_hired(strength, avg_age, date)` + updated welcome email
  (owner archetype named, monthly-review model explained).
- `_career_after_user_game`: passes `today_iso`; crisis → news item.
- `_career_board_review`: passes date; <40 confidence + off cooldown → inbox
  nudge suggesting the owner meeting.
- Press answers route through `apply_press_board_effect` (monthly cap).
- GM stature drift (±2/mo) untouched.

## Save compatibility
`to_dict`/`from_dict` carry the new fields; `from_dict` migrates old saves
with graceful defaults (season 1, neutral patience, random owner kept as
patient_builder default until re-hired — existing careers keep playing, new
fields just work).

## Tuning knobs (for future balance passes)
`CRISIS_LOSS_STREAK`, `DISASTER_START_GAMES/PCT`, `MONTHLY_BANDS`,
monthly cap (−12), comeback threshold (25) / multiplier (1.5) — all constants
at the top of the board section in `manager_career.py`.
