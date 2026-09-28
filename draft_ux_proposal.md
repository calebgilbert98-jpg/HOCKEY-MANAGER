# Entry Draft UX — Audit & Redesign Proposal

Date: 2026-09-28. Read-only audit of `DraftView` (`windows.py:4896–5839`),
`DraftDayCentral` (`event_day_hubs.py:243–487`), `draft_night.py`, `draft_stories.py`,
and the `draft_day_trades.py:646–745` incoming-call dialog. No game code changed.
Mockups: `ux_mockups/draft_warroom_mockup.html`, `ux_mockups/draft_call_mockup.html`.

The audit simulated a full user run: open hub → open draft board → sit through
AI picks → make picks → trade → grades, across a 224-pick draft.

## Top findings (short version)

1. The screen titled **DRAFT BOARD shows picks already made, not prospects available**
   (`windows.py:5115` columns are `# / Team / Player / Pos / Pot` of completed
   picks). The actual available board is a 30-row `tk.Listbox` called SHORTLIST
   in the center column. War-room convention is inverted.
2. **No prospect card in the war room.** Selecting a shortlist row fills a
   one-line label (`windows.py:5284`); scout reports, attributes, and storylines
   are only viewable by leaving the draft screen. The player card is Chris's
   "crucial tool" — it's absent at the moment of decision.
3. **The incoming trade call is a bare `askyesno` text box** (`draft_day_trades.py:730`):
   one prospect name, raw asset labels, no value comparison, no stated reasons,
   no counter path, and the accept/decline buttons sit side by side on a
   franchise-altering decision.
4. **Draft Day Central is static, not live.** Wire, prospect cards, and deals are
   written once at build (`event_day_hubs.py:152`); nothing refreshes while the
   draft runs, despite the "Follow every selection live" tagline (`:246`).
5. **No pacing control across 224 picks.** AI auto-picks every 650 ms with
   buttons disabled (`windows.py:5409`); a user with a late first-rounder watches
   minutes of dead UI. No speed toggle, no "sim to my next pick."

---

## Audit detail (by screen)

### DraftView — layout and information hierarchy

- Three columns at weights 2:1:1 (`windows.py:4963`). At 1600×900 the center
  "WAR ROOM" column is ~350 px wide; everything decision-critical is squeezed
  into it while the left column shows a results table nobody needs mid-draft.
- The on-the-clock spotlight is a passive label (`windows.py:4946`): team name +
  pick info, **no countdown**. Multiplayer has a real 60 s draft clock
  (`windows.py:5400`); single-player has none. The draft feels turn-based, not
  televised.
- The center column stacks: next-pick label → strategy pills → position filter →
  30-row shortlist → one-line selection label → 3 buttons. The selection label
  is the only "prospect detail" and it is one line of text
  (`windows.py:5294`: `"Selected: {name} ({pos}, {age}) — Potential {pot}"`).

### Picking flow (clicks and safety)

- Make-a-pick = **3 clicks minimum**: (1) click shortlist row, (2) "Draft
  Selected", (3) modal `askyesno` "This cannot be undone"
  (`windows.py:5528–5549`). No double-click-to-draft, no keyboard shortcut.
- The confirmation modal is the only mis-click guard, but it fires on *every*
  pick (modal fatigue across 7 rounds). A two-step inline confirm (arm → commit)
  would be faster and safer.
- `Auto Pick (My Board)` is the escape hatch, but the strategy pills
  (BPA/Need) only affect *this* button (`windows.py:5539`); the shortlist order
  ignores strategy and follows the user's saved board (`windows.py:5253`). The
  pills read as a global war-room setting but are a local auto-pick modifier.
- Shortlist is capped at 30 and shows `name (pos) potential` only — no age,
  height, scout-viewing depth, or consensus rank (`windows.py:5259`).
  Rows are colored by true potential grade (`windows.py:5271`) — visible to the
  user before their scouts have earned it (fog-of-war leak).

### Prospect evaluation

- `ScoutingReport` data exists and is rich (`scouting.py:76` fog-of-war
  potential, strengths/weaknesses, comparables, viewings, accuracy) — but the
  war room surfaces none of it. `_on_shortlist_select` doesn't even show the
  consensus-vs-scout spread that `_refresh_shortlist` computes.
- Draft storylines (riser/faller/comeback, `draft_stories.py:99`) are delivered
  to the inbox (`:209`), invisible while drafting. Pick drama
  (`windows.py:5574`) also goes to the inbox. The war room — where narrative
  tension pays off — shows none of it.
- The draft board tree binds the player context menu (`windows.py:5129`), but
  only for *already-drafted* players. The shortlist (available players) has no
  context menu: right-click does nothing where it matters.

### Trade UX

- `trade_current_pick` dialog (`windows.py:5650`): pick a partner from a
  combobox, pick one of their later picks from a listbox, see raw slot values
  ("value {val}"), Propose. Problems: raw numbers are a **cheat-sheet**
  (`draft_night.py:67` slot values shown directly); the info line is honest but
  thin ("They may want more"); only 1-for-1 swaps of *your current pick* —
  no shopping the pick, no adding prospects/players to balance (the counter
  path can add assets, but the user can't construct them).
- Incoming AI call (`draft_day_trades.py:646`): the modal fires *during*
  `process_draft_pick` while the clock is already ticking; message text has the
  caller's target name and raw asset labels only. No reasons (positional fit /
  franchise direction are computed in `draft_day_trades.py` but never shown),
  no value bar, no counter option — Accept or Decline on a first-rounder.

### Ticker, wire, and draft grades

- DraftView ticker is newest-first `Listbox`, 120-line cap (`windows.py:5201`).
  Reach/steal lines exist (`draft_night.py:30`) but there's no filter and the
  user's own picks aren't visually distinguished.
- DraftDayCentral's wire only shows the last 30 picks *if the live draft window
  is open* (`event_day_hubs.py:417`); otherwise it shows placeholder text.
  Nothing re-renders as picks happen — `_feed_write` is one-shot.
- Top prospect cards (`event_day_hubs.py:332`) show the top 6 at build time and
  go stale the moment pick #1 is made. The "CLASS SNAPSHOT" counts the full
  class, not remaining players.
- Draft grades (`windows.py:5788`, 420×540 popup): computed ratio is *dropped*
  from the display — only letter + team are shown (`draft_night.py:103` returns
  `ratio`, never rendered). Percentile-curved grades (`draft_night.py:107`)
  with no legend; the user can't tell what an "F" means. `end_draft` opens the
  modal immediately (`windows.py:5838`) with no "review your picks" step.

### Hub actions

- "Open Draft Board" and "War Room / Auto-Draft" both call `_open_draft`
  (`event_day_hubs.py:248–250`) — two buttons, one destination.
- "Trade This Pick" opens the *generic* trade window (`event_day_hubs.py:484`),
  not the pick-swap dialog. Mislabeled.

### Fatigue and accessibility

- 224 picks, no fast-forward: AI cadence is a fixed 650 ms (`windows.py:5453`).
  A user picking at #25 waits through ~24 AI picks plus modals before acting;
  rounds 2–7 are ~3 minutes of watching disabled buttons.
- Three independent scroll regions in DraftView (board tree, shortlist,
  ticker) — project convention is single-level scrolling.
- Hub prospect-card scout notes are 9 px italic (`event_day_hubs.py:388`) and
  low-contrast; the wire font is 10 px. Small but readable at 1600×900; the
  9 px italic is the outlier.
- No keyboard accelerators: can't arrow through the shortlist and hit Enter to
  draft; the shortlist *is* a Listbox so arrows move selection, but nothing
  acts on it.

---

## Redesign proposal

### MUST (usability blockers — fix before calling this "improved")

**M1. Rename and re-role the columns: left = AVAILABLE BOARD, right = DRAFT WIRE.**
What: left column becomes the available-prospect board (ranked, tabbed:
Available / Results / My picks — see mockup 1); right column becomes the pick
wire with reach/steal badges and the user's picks highlighted. The center stays
the war room.
Why: fixes the inverted convention; the most-used surface (who's available)
gets the most space.
Touches: `windows.py:DraftView.__init__` (layout `4961–4970`), `_create_draft_board`
`5115`, `_refresh_shortlist` `5235`, `_ticker` `5198`.

**M2. Add a prospect card to the war room.**
What: selecting a board row renders an inline card — name, pos, age,
height/weight, nationality, consensus rank, *your scout's* fog-of-war potential
with viewing depth, strengths/weaknesses, scout note, storyline tag
(riser/faller — data already exists in `draft_stories.py:99`), and "fits need"
chip. Right-click opens the full player profile (already exists).
Why: the player card is the crucial tool; currently absent at decision time.
Touches: `windows.py:_on_shortlist_select` `5281`; reads `scouting.report_summary`
`scouting.py:85`; storyline lookup from `main.py:9474` output.

**M3. Rebuild the incoming-call dialog as a decision dialog (mockup 2).**
What: replace the `askyesno` (`draft_day_trades.py:730`) with a proper dialog:
caller identity, *their target* as a mini prospect card, "why they're calling"
bullets (positional fit, projected target, franchise direction — all already
computed in `draft_day_trades.py`), the offer as a two-sided deal card with a
*value bar* instead of raw slot numbers, and three buttons:
Accept / Counter / Decline (Esc). Keep: decline never re-rings for that slot.
Why: a first-round trade-up is the highest-stakes click in the game; the
current modal invites mis-clicks and gives no basis for judgment.
Touches: `draft_day_trades.py:incoming_offer_for_user` `646`; new dialog
helper in `windows.py` or a new `draft_call_dialog.py`.

**M4. Two-step inline pick confirmation; drop the per-pick modal.**
What: "DRAFT {name}" button arms on first click (button turns into "CONFIRM —
DRAFT {name}"), commits on second; Esc/right-click disarms. Double-click a
board row arms; Enter commits. Remove the `askyesno` in `make_user_pick`.
Why: 3 clicks + a modal per pick × up to 7 user picks is the core loop — make
it fast *and* safe. Modal fatigue is real across 224 picks.
Touches: `windows.py:make_user_pick` `5528`; button wiring `5063`.

**M5. Pacing controls: speed toggle + "Sim to my next pick".**
What: add draft-pace control (1× / 4× / sim-to-my-pick) to the clock panel,
replacing the fixed 650 ms `after` in `process_draft_pick`. Sim-to-my-pick
fast-forwards AI picks (no per-pick UI churn, wire updated in bulk), pauses on
user pick, on incoming call, or on round 1 drama (top-3 / reach / steal).
Why: rounds 2–7 are currently minutes of dead UI; this is the single biggest
fatigue fix.
Touches: `windows.py:process_draft_pick` `5299`, AI scheduling `5409`,
`execute_pick` `5579` (bulk path), `_ticker` `5198`.

**M6. Make DraftDayCentral live.**
What: refresh the wire, on-the-clock card, top-available cards, and deals feed
on a timer while the draft window is open (or subscribe to a pick-made event);
prospect cards show *remaining* prospects; snapshot counts remaining.
Why: the hub advertises "follow every selection live" (`event_day_hubs.py:245`)
but is a static snapshot. A hub that goes stale at pick #1 is worse than none.
Touches: `event_day_hubs.py:DraftDayCentral` `243–487` (`_wire_lines` `413`,
`_build_prospect_cards` `332`, `_on_the_clock` `395`, `_deals_lines` `422`).

**M7. Fix hub action buttons.**
What: collapse "Open Draft Board" / "War Room / Auto-Draft" into one button;
repoint "Trade This Pick" at the pick-swap dialog (`trade_current_pick`), or
rename to "Trade Center".
Why: two buttons → one destination is a trust bug; the mislabeled trade button
sends users to the wrong screen.
Touches: `event_day_hubs.py:_build_actions` `248–253`, `_open_trade` `484`.

### SHOULD (realism / broadcast feel)

**S1. Single-player draft clock.** Add a visible countdown in the spotlight
panel (e.g. 3:00 round 1, 1:00 later rounds; expiry = Auto Pick). Mirrors the
MP 60 s clock (`windows.py:5400`) and the real broadcast. Pauses during trade
dialogs.
Touches: `windows.py:4946` clock frame, `process_draft_pick`, `make_user_pick`.

**S2. Surface draft drama in the wire.** Reach/steal badges and storyline tags
already exist in data; render them as wire badges and on prospect rows instead
of inbox-only (`draft_stories.py:172`, `windows.py:5574`). A slide to #12
should *feel* like a slide on the war-room screen.

**S3. Strategy pills that actually steer the board.** Make BPA/Need reorder the
available board (not just Auto Pick), and show *why* — e.g. a "need fit" chip
on rows matching `te.team_needs`. Alternatively remove the pills and keep
Auto Pick honest.
Touches: `windows.py:_board_sorted_available` `5249`, `_draft_set_pill` `5257`.

**S4. Draft grades with evidence.** Show the value ratio, the team's best
value pick, and a one-line legend ("grade = drafted value vs slot
expectation, curved across 32 teams"). Add a "review my picks" step before the
grades modal.
Touches: `draft_night.py:draft_grades` `103`, `windows.py:show_grades` `5788`,
`end_draft` `5816`.

**S5. Stop leaking true potential.** Shortlist row colors use the true grade
(`windows.py:5271`); color by the *scout's fog-of-war display* instead, with a
dimmed style for unscouted rows. Same for the board tree's Pot column on
*available* players (results rows for completed picks can stay truthful).
Touches: `windows.py:_refresh_shortlist` `5259–5279`, `_pot_color` `5189`.

**S6. Trade-dialog value bars, not raw numbers.** Replace "value {val}"
(`windows.py:5660`) with a proportional bar + qualitative read
("fair / slight overpay / strong overpay"). Analytics is a puzzle, not a
cheat sheet.
Touches: `windows.py:trade_current_pick` `5650`.

**S7. Let the user shop the pick.** In `trade_current_pick`, allow offering the
pick to all teams (broadcast) and adding a prospect/player to balance, instead
of only 1-for-1 swaps of the current slot. Keep AI evaluation via
`te.ai_consider_trade` — the realism comes from the engine, the UX just needs
to expose it.
Touches: `windows.py:trade_current_pick` `5650`, `_execute_pick_swap` `5717`.

### COULD (polish)

**C1. Wire ticker to the hub's scrolling ticker** — DraftDayCentral has an
animated ticker (`event_day_hubs.py:160`) fed only by top-3 names
(`:464`); feed it live pick lines.
**C2. "Draft class" pre-draft screen** — storylines + top-10 cards + team needs
in one place before the draft starts (data all exists).
**C3. Keyboard map** — arrows move, Enter arms/drafts, T trade, A auto,
Esc disarm; document in a hint line.
**C4. Accessibility pass** — bump hub scout notes off 9 px italic
(`event_day_hubs.py:388`); single scroll region per column; focus ring on the
armed draft button.
**C5. Post-pick flash** — the selected row's card briefly shows drafted
position vs projection ("picked #7, projected #3 — reach?") using the
`prospect_projected_rank` map already read in `execute_pick` (`windows.py:5578`).

---

## Suggested implementation order

1. M1 + M2 (layout + prospect card) — the war room becomes legible.
2. M4 (two-step confirm) + M3 (call dialog) — the two highest-stakes clicks.
3. M5 (pacing) — fatigue fix; biggest perceived-speed win.
4. M6 + M7 (hub live + buttons) — hub stops lying.
5. S1–S3, then S4–S7, then COULD items.

## Mockups

- `ux_mockups/draft_warroom_mockup.html` — redesigned on-the-clock war room:
  spotlight bar with countdown + pace controls, Available/Results/My-picks
  board tabs with scout-depth dots and fog-of-war grades, inline prospect card
  (scout note, storyline tag, need-fit chip), two-step DRAFT button, incoming-
  call banner, draft wire with reach/steal badges and user-pick highlight.
- `ux_mockups/draft_call_mockup.html` — incoming trade-up call as a decision
  dialog: why-they're-calling reasons, target mini-card, two-sided offer with
  value bar and qualitative verdict, Accept / Counter / Decline + keyboard hints.

Both are static HTML, dark palette matching the app theme, sized for
1600×900 review.

## Notes / risks for Chris

- Tuning call: fog-of-war coloring (S5) makes the board *less* informative by
  design — that's the scout-ability puzzle working as intended, but it will
  feel like a nerf next to today's true-grade colors. Flag before shipping.
- The sim-to-my-pick control (M5) must not skip `on_clock_check` AI trade-ups
  or the user's incoming call — pause conditions need care in
  `draft_day_trades.py`.
- Draft grades are percentile-curved (`draft_night.py:107`): someone always
  gets an F. Showing the ratio (S4) softens this but the curve itself is a
  design decision worth a look.
