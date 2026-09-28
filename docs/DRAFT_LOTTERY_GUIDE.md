# Draft Lottery Guide (televised reveal)

Spectacle wave item 5. One new module + hooks; additive except for one
placeholder it replaces (see below).

## What it does

On **May 8** each year (lottery day), the game now runs the real NHL draft
lottery and presents it as a televised reveal:

- **Real odds** (2022+ NHL rules): the bottom 11 teams by regular-season
  points are eligible; two weighted draws decide **#1 and #2 overall**
  (the first-draw winner is excluded from the second). Picks 3-16 fall by
  reverse standings. A traded pick keeps its ORIGINAL team's lottery slot.
- **The lottery actually moves the draft.** The old
  `simulate_draft_lottery` sorted a local list and changed nothing --
  `get_draft_order` sorted round 1 purely by standings. Now
  `get_draft_order(year)` reorders round 1 by the stored lottery rows.
  (This replaces the old explicitly-"simplified" placeholder with real
  odds; the replacement is the approved televised-lottery item.)
- **Inbox card** (`🎰 DRAFT LOTTERY {year}: results are in`, headlines.py
  `lottery_results` kind): full 1-16 list with movement arrows, plus a
  **WATCH THE REVEAL** special-action button (inbox_window.py, same pattern
  as the fantasy-draft button).
- **The reveal window** (`LotteryRevealWindow`): broadcast-style countdown,
  picks 16 -> 3, then the #2/#1 drama with a longer pause. Each pick shows
  odds, movement (+3 ▲ / -2 ▼), and a reaction line ("LEAPS 5 spots -- the
  room erupts!"). Skip button, finale board, and an **OPEN DRAFT CENTRAL**
  button that routes straight into draft planning.
- **Reactions with light teeth**: the user's team winning #1 (+2 morale),
  jumping 4+ (+1), or sliding 3- (-1) posts to the dynamics feed via
  `record_team_event` (same channel as the GM-reputation fallout).
- **Ledger memory**: a `draft_lottery` event (weight 40, idempotent) so the
  league remembers who won.

## Files

- `draft_lottery.py` -- NEW: odds table, `eligible_teams`, `run_lottery`
  (idempotent, persists `league.lottery_results[year]`), `reaction_line`,
  `apply_user_reactions`, `lottery_reveal_text`, `LotteryRevealWindow`.
- `game_classes.py` -- `League.lottery_results` / `lottery_held_years`
  fields; `simulate_draft_lottery` delegates to `run_lottery` (no-op when
  run); `get_draft_order` applies the round-1 lottery reorder.
- `main.py` -- lottery-day hook (May 8, once/year via `lottery_held_years`);
  `_hold_draft_lottery` (runs lottery, stashes `_pending_lottery_reveal`
  on game_manager, delivers inbox card, reactions, ledger).
- `headlines.py` -- `lottery_results` builder.
- `inbox_window.py` -- `_handle_lottery_reveal_button` /
  `_watch_lottery_reveal` (shows only, never hides -- the fantasy-draft
  handler owns the hide path).
- `save_load_system.py` -- persists `lottery_results` (int keys survive)
  and `lottery_held_years`.
- `qa_draft_lottery.py` -- 28/28 (odds, eligibility, shape, idempotency,
  win-rate stats, draft-order application, traded-pick slot, delegate,
  reveal text, dynamics reactions, save/load keys).

## Flow notes

- `_hold_entry_draft` (June) still calls `simulate_draft_lottery(year)`,
  which is now a no-op when May 8 already ran -- saves that skip/sim past
  May 8 still get a real-odds lottery on draft day.
- `get_draft_order` only reorders round 1 when lottery rows exist for that
  year; rounds 2-7 and pre-lottery years are untouched.
- Lottery day sits between the season and the draft; playoff teams are
  unaffected (they were never lottery-eligible).

## What NOT to touch

- Odds are the real NHL table -- don't "tune" them for drama; the draws
  already produce jumps.
- Never add a third draw or extend eligibility past 11 without Muck's
  approval (league-rules boundary, like the scoring band).
- The reveal window must stay openable from the inbox card alone -- no
  auto-opening popups on lottery day (inbox-first rule).
