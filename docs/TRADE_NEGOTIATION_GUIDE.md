# Trade Negotiation + UX Overhaul — Handoff Guide

Covers the work in this commit: FM24/EHM-style trade negotiation, popup
click-out, right-click player menus, and the UI scale pass. Written so you
can build on it without asking me anything.

## 1. Trade negotiation (`trade_negotiation.py`, new)

Trades are no longer instant verdicts. Sending an offer opens a
**negotiation**: the AI GM answers in 1–3 game days, may counter, loses
patience if you haggle too long, and can walk away.

### Core API

```python
import trade_negotiation as tn

# You propose a trade (from the Trade Center)
neg = tn.send_offer(app, partner_team, your_assets, their_assets)
# -> returns TradeNegotiation; AI answers when process_due_negotiations runs

# An AI GM proposes a trade to you (incoming offer)
neg = tn.incoming_offer(app, partner_team, partner_assets,
                        player_wanted=your_player)

# You haggle back
tn.send_counter(app, neg.id, your_assets, their_assets)

# You decide
tn.accept_negotiation(app, neg.id)   # executes the roster swap
tn.decline_negotiation(app, neg.id)  # walks away, no hard feelings logged

# Per simulated day (already wired into main.simulate_day)
tn.process_due_negotiations(app)
```

### The `TradeNegotiation` dataclass

Fields: `id`, `partner_team_name`, `direction` (`"outgoing"` you offered /
`"incoming"` they offered), `status` (`awaiting_ai` / `awaiting_user` /
`accepted` / `declined` / `expired`), `rounds`, `patience` (1.0 start,
−0.15 per counter, floor 0.35), `user_assets` / `partner_assets`
(serialized player-id dicts), `response_due` (date), `history` (list of
round dicts: who offered what, AI verdict + message).

`to_dict()` / `from_dict()` — save/load safe. Assets serialize as player
ids with name+team fallback, resolved back via `tn.resolve_assets(app, …)`.

### AI behavior (additive — existing `trade_engine` logic untouched)

- `trade_engine.ai_consider_trade(..., patience=1.0)`: effective greed is
  divided by patience (floor 0.35). Low patience (< 0.55) can turn a
  "counter" verdict into a flat rejection ("moving on").
- `tn.process_due_negotiations`: accept → executes trade (rosters, cap,
  media, news, views — same `_complete` path as before); reject → inbox
  note; counter → new `trade_counter` inbox action with revised terms.
- Stale offers expire after 14 days.

### Save/load

`save_load_system.py` persists `app.game_manager.trade_negotiations`
(list of dicts). Loaded via `tn.load_state(app, data)`. Nothing else to
wire — if you add fields to the dataclass, extend `to_dict`/`from_dict`.

### Trade Center (`windows.py` → `TradeWindow`)

- Constructor is now `TradeWindow(parent, preset=None)`, non-modal,
  click-out enabled.
- "Send Offer" / "Send Counter-Offer" sends via `tn` and **closes** — no
  more instant AI resolution in the window.
- `preset` dict: `{"partner": team, "user_assets": [...],
  "partner_assets": [...], "mode": "offer"|"counter",
  "negotiation_id": id|None}`. Used by the inbox Negotiate button.
- `main.open_trade_window(preset=None)` always opens a fresh workbench.

### Inbox trade messages

`trade_offer` / `trade_counter` actions render a deal table + AI message +
patience warning, with **Negotiate / Review & Adjust / Accept / Walk Away**
buttons. Routing: `_display_message_preview` forwards those action types
to `_show_interactive_action` → `_render_trade_negotiation`. The old
blocking `present_trade_offers` modal is gone — incoming offers arrive as
inbox negotiations.

## 2. Popup click-out (opt-in contract)

`InGamePopup(master, modal=None, dismiss_on_backdrop=None)`:

- Default: no click-out. Cards with unsaved work (lines editor, settings)
  stay put — pass nothing.
- Opt in: `dismiss_on_backdrop=True` → first click outside the top card
  dismisses it **and the click lands where aimed** (no dimmed
  locked-screen). Escape already closes dismissible cards.
- `modal=True` cards are immune to click-out.

Rule of thumb: browsing/reading cards opt in; editing cards don't.

## 3. Right-click player menu (`player_context_menu.py`)

One-liner for any widget showing a player name:

```python
from player_context_menu import bind_player_context
bind_player_context(widget, player_or_callable, parent_window)
```

Binds Button-3 + Shift-F10 (keyboard fallback). The menu: View Profile,
Propose Trade (opens the Trade Center pre-filled with that player on the
correct side), Add/Remove Shortlist, Compare, etc.

Already wired: Trade Center lists, roster treeviews + depth-chart tiles,
FA / trade block / waivers trees. Long tail (draft lists, inbox text,
profile windows) is yours if you want it — same one-liner.

`CTkPlayerList` also exposes `on_right_click` if you prefer the callback
style used in the Trade Center.

## 4. UI scale (`ui_scale.py`, new)

Settings → Font size (Small / Medium / Large) **actually works now** — it
was saved but never applied.

- `ui_scale.apply_from_prefs()` runs at app startup (`main.py`).
- `settings_window` re-applies on save — new windows pick it up, no
  restart (noted in the settings UI).
- Text factories route through it: `ctk_theme.heading/body`,
  popup card title bars. Small=0.9×, Medium=1.0×, Large=1.12×.
- New/touched surfaces should use `heading()`/`body()` (or
  `ui_scale.scaled(px)`) instead of hardcoded fonts.

## 5. Visual toning

Trade Deadline Center's shouty chrome toned down (title 28→20pt,
countdown 48→32pt, subtitle 16→12pt). Shortlist window is non-modal now
(it called `grab_set()` despite its own "non-modal" comment).

## 6. Deadline-day rush (2026-09-27)

- **30-minute game clock** (`trade_deadline_manager`): on March 8 the day
  runs 9:00 AM → 3:00 PM ET in 30-min increments instead of full-day sims.
  State lives on `game_manager.deadline_clock` (persisted in saves).
  `main.simulate_day` routes deadline day through
  `_maybe_run_deadline_clock_tick()`; when the clock expires the day
  finishes normally (games sim, date advances to March 9).
- **Instant AI answers** (`trade_negotiation.is_deadline_rush`): offers and
  counters sent on deadline day get `response_due = today` and are
  processed immediately — the reply lands in the inbox in the same
  interaction (the deadline-day phone-call feel).
- **Storyline-aware AI** (`trade_storylines.py`, new): computes an additive
  `situational_context` (buyer/seller/bubble stance from conference
  standings, win/loss streaks, team-team rivalry premiums from
  `league.rivalries`, deadline urgency scaling with clock progress).
  Fed into `ai_consider_trade(..., situational=...)` as a `greed_mult`
  nudge clamped to 0.80–1.30. Core ratio/needs/greed logic untouched;
  `situational=None` behaves exactly as before.
- **Real AI-vs-AI deadline deals** (`main._deadline_tick_activity`):
  each 30-min window, AI teams roll `ai_initiative_odds()`; sellers move a
  veteran for a mid-round pick/prospect through the real
  `ai_consider_trade` + `execute_trade` path, and deals break as inbox
  news + ticker items.
- **Deadline gating is game-date now**: `HockeyManagerGUI.is_trade_deadline_day()`
  uses `current_date` (the old module-level check used the wall clock, so
  the Center only ever opened on real-world March 8). The event-day hub
  prompt now fires on the first tick (9 AM), not after 3 PM.
- Deadline Center: countdown follows the game clock ("10:00 AM ET ·
  05:00:00 left") and there's an ADVANCE 30 MIN button (same as Continue).

## What not to touch

- `trade_engine.ai_consider_trade` verdict semantics — the patience
  parameter is additive; don't change existing accept/counter thresholds
  without Muck's sign-off (engine boundary).
- `trade_storylines` nudge clamp (0.80–1.30) — storylines whisper, they
  don't shout. Widen only with Muck's sign-off.
- `tn._complete` owns trade execution (rosters, cap, media, news). Don't
  duplicate it — the old `TradeWindow._complete_trade` was removed
  deliberately.
- Popup `modal=True` + `grab_set` semantics — modals still block;
  click-out is opt-in only.
