# Waiver Priority + Training Camp Guide

Two systems built 2026-09-28 per Muck's direction: (1) realistic
NHL-style waiver claim rules with a proper waiver wire screen, and
(2) an EHM-style training camp with per-player camp ratings and
scrimmages. The wire screen already existed as `WaiversView` -- it was
upgraded, not duplicated.

---

## 1. NHL waiver priority (`waiver_logic.py`, `main.py`, `windows.py`)

### The rule (CBA Article 13 style)

- Claim order = **lowest points percentage first**.
- **Until Nov 1**: order comes from **last season's final standings**.
  **From Nov 1**: order comes from **current standings** (points%).
- A club that **successfully claims a player drops to the bottom** of
  the order (priority spent). Order of multiple claimants is preserved
  at the tail.
- The used-priority list resets whenever the basis flips (season
  rollover, Nov 1).

### Code map

| Piece | Location |
|---|---|
| `snapshot_final_standings(league)` | `waiver_logic.py`; called at the top of `League.end_of_season()` in `game_classes.py`, before `initialize_standings()` wipes the table. Banks `{team_name: {points, games}}` + season label. Old-save safe (plain attrs, read via getattr). |
| `waiver_priority_order(league, on_date)` | `waiver_logic.py`. Returns teams worst-first. Handles the Nov 1 flip and the drop-to-bottom demotion list (`league._waiver_claim_demotion`, `league._waiver_priority_basis_key`). |
| `waiver_priority_rank()` / `waiver_priority_basis_label()` | `waiver_logic.py`. UI helpers. |
| `note_waiver_claim(league, team)` | `waiver_logic.py`. Call after every successful claim. |
| `process_waivers()` | `main.py`. Now iterates `waiver_priority_order()` instead of the old roster-strength sort. Claim transfer extracted into `_execute_waiver_claim(player, team)` (rivalry + dressing-room hooks preserved). |
| User claims | `windows.py` `claim_from_waivers()`. **No longer instant**: submitting sets `player.user_claim_pending = True`; the claim resolves at the next Mon/Thu waiver run **in priority order**. A higher-priority rival that wants him beats you (news posted, flag cleared). If your roster fills or cap evaporates first, the claim lapses with news. |
| Multiplayer `_mp_claim_waivers` | Untouched -- still instant (MP has its own rules). |

### Wire screen (`WaiversView`, `windows.py`)

- New **priority strip** at the top of the Waiver Wire tab:
  `Claim priority (last season's final standings): 1. ..., 2. ... -- your club is #N.`
- New **Days Left** column; the Actions column shows **"Claim Submitted"**
  for pending user claims (clicking again explains it's queued).
- The click-handler column index moved `#8` -> `#9` (new column).

---

## 2. Training camp (`training_camp.py`, `training_camp_ui.py`, `main.py`, `waiver_logic.py`)

### The calendar

- **Sep 12**: camps open. Every NHL club's camp roster = NHL roster +
  AHL roster + invited rights-held prospects (<25). Ratings reset.
- **Sep 15/18/21/24/27/30**: scrimmage days. Intra-squad Red vs White,
  balanced by alternating overall (vets and kids mix, EHM-style).
- **Sep 30**: camp closes. Averages computed, development applied, the
  **camp report goes to the user's inbox** (top 5, bottom 3, prospects
  pushing for a spot, scrimmage scores + 3 stars).

### Ratings model

- Skaters: `4.5 + (ovr-65)*0.09 + noise(0,0.9) + 0.3/-0.2 for win/loss`,
  clamped 3.0-10.0. Age <= 21 gets extra boom/bust variance.
- Goalies: `6.2 - (goals_allowed-3.0)*0.9 + noise`, clamped.
- Persisted per player: `player.camp_ratings` (list), `player.camp_avg`,
  `player.camp_standout`. Per team: `team.camp_roster`,
  `team.camp_scrimmages` (date, red-white score, 3 stars).
- `run_camp_day()` is **idempotent per date** (safe on reloads, heals a
  save loaded mid-camp). Hooked into the daily advance next to the
  waiver clock in `main.py`.

### Camp matters

- **Standout youngsters** (<=22, avg >= 7.5 over 2+ scrimmages): +1 to
  two key attributes (goalies: goaltending), +5 morale, flagged
  `camp_standout`.
- **Poor camps** (avg <= 4.5, 2+ games): -5 morale.
- **AI camp cuts read camp form**: in `waiver_logic.process_ai_waivers`
  with `camp_cuts=True`, waiver candidates sort by `camp_avg`
  ascending -- a bad camp jumps the cut queue, a great camp saves a
  bubble player. Waiver-exempt kids assigned straight down go worst
  camp first too.

### Screen (`training_camp_ui.py`)

`TrainingCampWindow` (Team menu -> **Training Camp**,
`app.open_training_camp_window()`): Camp Ratings tab (Player/Age/Pos/
OVR, per-scrimmage S1..Sn columns, Avg, Note flags: Standout / Poor
camp / Pushing for a spot) and Scrimmages tab (date, Red-White score,
3 stars). Shows the user's club; data persists all season.

---

## QA

- `qa_waiver_priority_camp.py` -- **24/24**: basis flip, points% >
  raw points, drop-to-bottom + tail order + basis reset, snapshot,
  full Sep 12-30 cycle (6 scrimmages, ratings, inbox report, news),
  idempotency, standout bump, morale hit, camp-form cut ordering.
- Headless E2E on the S3 save (`s2_july.hm`): 57 campers, 32/32 AI
  clubs ran camp, both windows render, beaten-claim (BUF #3 beats user
  #6, news posted), won-claim (user #1 wins, drops to #32 after).
- Regressions green: `qa_ai_waivers` 17/17, `qa_offer_sheet` 16/16,
  `qa_rfa_arbitration` 88/88, `qa_waiver_shed` 24/24,
  `qa_trade_values` 59/59.

## What NOT to touch

- The Nov-1 / drop-to-bottom semantics are the NHL rule -- don't
  "simplify" to a plain standings sort.
- `user_claim_pending` is spent exactly once (win, beaten, or lapsed);
  grep before adding new terminal branches to `process_waivers`.
- Camp runs Sep 12-30; the early-Oct AI camp cuts assume ratings exist.
  Don't move one without the other.
