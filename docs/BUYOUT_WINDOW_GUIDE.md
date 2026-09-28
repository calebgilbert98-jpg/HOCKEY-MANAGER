# Buyout Window Guide (June 15–30)

## What it is
The real NHL's first buyout window now exists in the game. It runs once
per offseason inside `HockeyManagerGUI._start_offseason`, after the
board review / immortality / copycat beats and before the draft lottery
guarantee — matching the real calendar order (lottery May 8 → buyouts
open Jun 15 → draft Jun 23–25 → free agency Jul 1).

## Why it was built
Previously the offseason jumped straight from the Cup to July 1, so
June 15–30 never existed in game time. The date gate in
`transaction_windows.check_window("buyout", ...)` therefore made
buyouts **impossible for everyone**, and no AI GM ever bought a player
out. The window is now a real beat: the stamped game date moves to
June 15 while the pass runs.

## Module: `buyout_window.py`
- `process_buyout_window(league, app=None, rng=None)` — the entry point.
  Returns `{"ai_buyouts": [...], "user_candidates": n, "window_year": y}`.
- `execute_buyout(league, team, player, season_year=None)` — **the one
  rulebook.** The single data mutation every buyout path uses (AI
  window, user calculator, interactive inbox). Writes
  `team.buyout_cap_hits` keyed by season-start calendar year, removes
  the player from the roster, sets `team_name = "Free Agent"` (the FA
  pool discovers players by that scan), clears player-side retention
  state (the retaining club's dead cap survives, per CBA).
- AI logic per club (NHL only, user club excluded):
  - Candidates: `years_remaining >= 1`, not ELC, no NMC/NTC (real rule:
    no buyout without consent — the AI doesn't ask, it moves on),
    overall < 86 (franchise pieces are never bought out), cap hit >= $2M.
  - Dead-weight test: ($6M+, <82 ovr) / ($4.5M+, <78) / ($3M+, <75), or
    the classic profile (34+, $4M+, <80 ovr, 2+ years left).
  - Team need: only clubs tighter than $8M in cap space consider it.
  - Buyout math must help: year-1 savings >= $500K (via the shared
    `windows.buyout_schedule` — 2/3 of remaining salary over 2× term,
    1/3 if under 26).
  - Trigger probability scales with GM ability (`gm_ability01`):
    `0.35 + 0.5 * ability`, max 2 buyouts per team per summer.
    Real NHL: a handful of buyouts league-wide, not a fire sale.
  - Each buyout is recorded to the narrative ledger (`kind="buyout"`,
    weight 45) and the news wire.

## User experience
The user's candidates arrive as an interactive inbox message
(`action_type="buyout_window"`, `requires_response=True`), mirroring
the RFA qualifying pattern: per-candidate cards sorted with flagged
dead weight first (name, age, overall, cap hit × years left, buyout
cost, annual dead cap × years, year-1 savings), each with **Buy out /
Keep** buttons. Undecided players stay put.
- `HockeyManagerGUI.apply_buyout_decision(message, player_id, buyout)`
  executes through `execute_buyout`. Like the RFA actions, it does NOT
  re-check the calendar gate — the message itself is the June 15–30
  window authorization, so resolving it after July 1 works.
- `BuyoutCalculatorView._confirm_buyout` (windows.py) was refactored to
  call `execute_buyout` — same math, same season-year keying as before.
  The calculator's window gate is unchanged (it still only *opens*
  during June 15–30 of game time).

## What NOT to touch
- `buyout_schedule(player)` in windows.py — the cap math both paths
  share. If the CBA math changes, change it there once.
- The multiplayer `_mp_buyout_player` (main.py) still carries its own
  copy of the mutation — deliberately left alone to avoid touching the
  MP path; a future cleanup can point it at `execute_buyout`.

## QA
`qa_buyout_window.py` — 17/17: strapped team's dead weight bought out
(correct $2M/yr × 4 dead cap, $4M year-1 savings), comfortable team /
NMC holder / franchise star untouched, user message queued with the
math and nothing auto-executed, `apply_buyout_decision` end-to-end.
Regressions: `qa_transaction_windows` 40/40, `qa_rfa_arbitration`
88/88, `qa_season_review` 21/21, `qa_board_season_review` 9/9,
`qa_cards_inbox` 31/31.

## Known limitation (not a bug)
Arbitration still files and resolves instantly inside the June RFA
pass; the real Jul 5 filings / late-Jul–Aug hearings cadence is a
future feature, not part of this window.
