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

## What not to touch

- `trade_engine.ai_consider_trade` verdict semantics — the patience
  parameter is additive; don't change existing accept/counter thresholds
  without Muck's sign-off (engine boundary).
- `tn._complete` owns trade execution (rosters, cap, media, news). Don't
  duplicate it — the old `TradeWindow._complete_trade` was removed
  deliberately.
- Popup `modal=True` + `grab_set` semantics — modals still block;
  click-out is opt-in only.
