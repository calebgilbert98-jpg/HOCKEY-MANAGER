# RFA / Offer Sheets / Arbitration — Real-Life Standard

`rfa_system.py` — restricted free agency, offer-sheet compensation, and
salary arbitration encoded to the current NHL CBA (2020 MOU terms, verified
2026-09-28 against NHL.com, NHLPA, PuckPedia, Pro Hockey Rumors, Sportsnet).
Full research brief: `~/workspace/rfa_arbitration_brief.md`.

## Real-life rules encoded

**RFA/UFA determination.** Expired contract + (27+ on June 30 **or** 7+
accrued pro seasons) → Group 3 UFA. Otherwise → RFA (Group 2). Group 6
carve-out: 25+, 3+ pro seasons, <80 NHL GP (<28 for goalies) → UFA.
Same 27/7 bar `trade_engine.clause_eligible` already used.

**Qualifying offers** (prior-year base salary → minimum QO):
- < $775,000 → 110%
- $775,000–$999,999 → 105%, capped at $1,000,000
- ≥ $1,000,000 → lesser of prior salary or 120% of AAV

No QO by the deadline → UFA. The 2026 CBA (in-game 2026-27) moves the
tiers to ≤$1.25M → 110%, $1.25–1.75M → 105%, ≥$1.75M → 100% — flip
`QO_TIER*_MAX/PCT` when the sim gets there.

**Offer sheets.** Any club may sign an unsigned RFA (one who hasn't filed
for arbitration and hasn't accepted a QO). Original club has 7 days to
match; matched players can't be traded for a year without consent
(`player.offer_sheet_match_no_trade_until`). Compensation = the signing
club's **own** picks, next draft (2025 bands):

| AAV | Compensation |
|---|---|
| ≤ $1,544,424 | none |
| → $2,340,037 | 3rd |
| → $4,680,076 | 2nd |
| → $7,020,113 | 1st + 3rd |
| → $9,360,153 | 1st + 2nd + 3rd |
| → $11,700,192 | 2×1st + 2nd + 3rd |
| above | 4×1st |

AAV for compensation = total ÷ years (÷5 for deals >5 years). Real
frequency: **12 offer sheets in 20 cap-era years** (~0.6/yr), 4 unmatched.

**Salary arbitration** (CBA Article 12):
- Eligibility: Group 2 RFA + pro experience by age at first SPC signing —
  18–20 → 4 yrs, 21 → 3, 22–23 → 2, 24+ → 1. Must not have signed an
  offer sheet. Club-elected: max 2/team/year, once per player career.
- The arbitrator: assigned from a jointly-appointed neutral panel
  (`ARBITRATOR_PANEL`, fictional names). Weighs comparables (same
  position, age ±2, signed AAVs); UFA comparables barred. Award ≥ 85% of
  prior salary, 1–2 year term. Player-elected → the **team** picks 1 vs 2
  years; a 2-year award may not end as the player hits UFA.
- Walk-away: **only** player-elected awards ≥ **$4.85M** (2025-26), 48h
  window → player becomes UFA. Never from club-elected awards. In practice
  it almost never happens — the AI only walks away when the award is both
  above the threshold and absurd vs market.

## Real-life likelihood calibration (2021–2025)

| Summer | Filed | Hearings |
|---|---|---|
| 2021 | 19 | 0 |
| 2022 | 26 | 1 |
| 2023 | 22–23 | 3 |
| 2024 | 14 | 1 |
| 2025 | 13 | 0 |

Mean ~19 filings/summer (range 13–26); **~95% settle pre-hearing** at
~midpoint of the two filings with a slight player lean
(`settle_arbitration`); ~5% reach a hearing (`ARBITRATION_HEARING_RATE`);
0–2 club-elected per summer. Per-eligible-RFA filing rates are
tier-weighted (`ARBITRATION_FILING_RATES`: star 0.40 / top6 0.24 / depth
0.12) with an ask-gap multiplier, so filings concentrate where real
disputes happen. QA asserts multi-summer bands: filings avg 13–26,
hearings ~5%, offer sheets ~0.6/yr.

## July flow (`process_rfa_offseason`, called from `main._start_offseason`)

1. Classify every expired contract → RFA / UFA counts.
2. AI clubs extend QOs (`_ai_qualify_decision`: young/upside and
   contributors qualified; fringe non-tendered → UFA pool).
3. ~40% of AI RFAs sign pre-July; the rest negotiate into July (the
   offer-sheet/arbitration pool — real shape, filings are July 5).
4. AI UFAs: core re-signed (82+ ovr, or 78+ with 5+ years tenure), rest →
   UFA pool. **Backfill** (`_ai_backfill_roster`): promote signed prospects
   first, then cheap pool UFAs — AI rosters never shrink.
5. Offer sheets: per (unsigned RFA, rival club) roll at
   `OFFER_SHEET_BASE_RATE × desirability`. AI victims match unless the AAV
   is absurd vs market or the cap can't fit it (then they take the real
   picks via `execute_offer_sheet`, which also fires the existing
   `reputation_system.record_offer_sheet` heat).
6. Arbitration: player-elected filings at calibrated rates → 95% settle,
   5% hearing → award applied. Rare club-elected cases (0–2/summer).
6b. Unsigned AI RFAs who filed nothing sign through July.
7. User's RFAs → interactive inbox message (`rfa_qualifying`): per-player
   **Extend QO / Don't qualify**. Answering runs `resolve_user_rfa` for
   that player — the same July mechanics (offer-sheet risk →
   `offer_sheet_match` inbox; arbitration filing → award news; walk-away
   window → `arbitration_walkaway` inbox when the threshold binds).

## Cap compliance — nobody signs what they can't fit

`_cap_room(team)` reads `salary_cap_system.cap_breakdown` — the exact
accounting (roster + buyouts + retained + dead cap) the user's
day-advancement blocker enforces. `Team.cap_space` is a live property
(`salary_cap − payroll`, recomputed on every read), used only as fallback.

- **AI teams never go over the cap.** Every AI spend path is hard-gated:
  no QO above room (non-tender instead), no RFA/UFA signing above room
  (offer capped at room; holdout/release below the $775k minimum), no
  offer sheet the aggressor can't fit, no match the victim can't fit.
- **Compliance sweep** (`_ai_cap_compliance_sweep`): after the July pass,
  any AI team still over (dead-cap subtleties) papers players down —
  two-ways first (fully exempt), then biggest hits — until compliant.
- **The user can offer whatever they want** — including qualifying into
  over-cap (the inbox shows live cap space and warns when the total QO
  bill exceeds it). Accountability is the existing FM-style day blocker:
  an over-cap roster cannot advance the day until salary is shed via
  trade, waivers, or demotion. No unsolvable states: demotion is always
  available as the release valve.

## Inbox actions (all in `inbox_window.py`, handlers in `main.py`)

- `rfa_qualifying` → `apply_rfa_qualifying_decision` →
  `rfa_system.apply_qualifying_decision`
- `offer_sheet_match` → `apply_offer_sheet_match_decision` →
  `rfa_system.apply_offer_sheet_match` (match = sign at terms + 1yr
  no-trade flag; decline = `execute_offer_sheet` transfers the picks)
- `arbitration_walkaway` → `apply_arbitration_walkaway_decision` →
  `rfa_system.apply_walk_away`

Also fixed as a drive-by: `contract_counter` had a renderer but was missing
from the interactive gate, so it rendered as plain text — now gated.

## API (pure functions, GUI-free)

`is_rfa / is_ufa / is_ufa_eligible / is_group6_ufa`,
`qualifying_offer_amount(prior_salary, aav=None)`,
`offer_sheet_compensation(aav) -> (label, [rounds])`,
`arbitration_eligible(player)`, `arbitration_filing_probability`,
`arbitrator_award(..., filed_by="player")`, `settle_arbitration`,
`comparable_salaries`, `execute_offer_sheet`, `resolve_arbitration`,
`process_rfa_offseason`, `apply_qualifying_decision`, `resolve_user_rfa`,
`apply_offer_sheet_match`, `apply_walk_away`.

## Approximations (documented in code)

- First-SPC signing age isn't stamped on players; estimated as
  `age − seasons_played`. Good enough for the eligibility gate.
- The game stores one salary number as the cap hit, so AAV == salary;
  the 120%-of-AAV QO cap only binds if real AAV tracking is ever added
  (`qualifying_offer_amount` takes an `aav` param for that day).
- QO amounts round to the nearest $1k (real: exact dollars).
- December 1 unsigned-RFA rule not modeled; QO accept window (Jul 1–15)
  simplified to the July pass.

## What not to touch

- calebgilbert98's cap engine: cap hits read via the live `Team.cap_space`
  property; nothing in the cap wave was modified.
- The draft-rights lifecycle: rights retention rides on it, doesn't alter it.
- `trade_engine` valuations: `_market_value` reuses the game's own
  estimator (`ContractNegotiationView._estimate_market_value`).

## QA

`qa_rfa_arbitration.py` — 57 checks: QO math incl. real Johansson/Hughes
arithmetic, all 14 compensation boundaries, RFA/UFA/Group 6, arbitration
experience table, arbitrator floor/walk-away/term rules, settlement shape,
multi-summer calibration bands, full offseason pass on a fake league
(AI rosters intact, no unsigned expired left, user inbox queued, backfill).
