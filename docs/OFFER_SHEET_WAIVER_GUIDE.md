# Offer Sheets & AI Waivers — Guide (BUG-019 / BUG-020)

Two fundamental trading systems completed 2026-09-28. Both were
engine-complete but one-sided: the waiver wire had claims but no AI
supply; offer sheets had AI offense but no user offense.

## AI waiver management — `waiver_logic.py` (new)

`process_ai_waivers(league, app=None, rng=None, camp_cuts=False)` — the AI
GMs' logic, mirroring `buyout_window.py`. Called every **Monday** from the
daily tick in `main.py` (next to the waiver clock/claim processing);
never touches the user's club. Three reasons, matching real GM behavior:

1. **Cap compliance** — club over the cap (or within $1M): waive the
   fringe veteran making too much (cap hit ≥ $2M at ≤ 79 OVR, or
   32+/≥$4M/<82 OVR with 2+ years). Burial (~$1.925M exemption) is the
   savings; the cap engine already sheds the wire hit on placement.
2. **AHL shuttle** — roster over 23: waive bottom-of-roster
   waiver-eligible extras (never stranding the crease at 1 goalie).
3. **Camp cuts** (`camp_cuts=True`, first Monday on/before Oct 7, once per
   year via `league._waiver_camp_year`) — trim to 23. Waiver-exempt kids
   are assigned straight to the AHL (with the `ahl_system` stamp);
   eligible veterans go through the wire.

Guards: NMC blocks placement (AI doesn't ask, moves on); 86+ OVR
franchise pieces never waived; max 2 placements per club per week;
shrewder GMs (`gm_ability01`) work the wire more; June dead month
respected via `transaction_windows.check_window("waiver_place", ...)`.
Wire list: `app.waiver_list`, falling back to `league.waiver_list` for
engine-only callers. News + `narrative_ledger` kind `"waiver"` on every
placement.

**Changed behavior in `main.py` `process_waivers`:** on clearance the
player is now demoted to the original club's AHL roster for **all**
clubs, not just human-managed ones (the old `_human` gate was defensive
— AI clubs never placed anyone before BUG-019, so the branch never fired
for them). Junior/ChL routing and the AHL-assignment stamp are unchanged.

QA: `qa_ai_waivers.py` 17/17. Existing `qa_waiver_shed.py` 24/24 still
green.

## Offer-sheet UI — `offer_sheet_ui.py` (new)

`OfferSheetWindow(InGamePopup)` — opened via `app.open_offer_sheet_window()`,
with a **📝 Offer Sheets** button in the Free Agency view footer. Layout:

- Left: unsigned RFAs on rival NHL clubs (arbitration filers excluded —
  filing blocks offer sheets, same as the July pass), sorted by the
  engine's market read.
- Right: AAV slider ($1M–$12M, defaults to market read) + 1–5 year term;
  live compensation preview from the real `offer_sheet_compensation`
  bands with per-pick own-pick availability (`compensation_pick_status`
  mirrors `execute_offer_sheet`'s year/year+1 fallback with a used-set,
  so the preview never promises the same pick twice); cap-space, roster
  room, and window checks; a qualitative read of the player's interest.
- **Present Offer Sheet**: validates window (Jul 1 – Dec 1), own picks,
  cap space, roster room → `player_decision.player_accepts_offer_sheet`
  (refusals show his camp's reasons, no sheet signed) → the original
  club matches/declines on the spot via the **same**
  `ai_match_decision` the July pass uses → decline runs
  `execute_offer_sheet` (real pick transfer, reputation hooks, news).

One rulebook in both directions: the UI drives the exact engine calls.

**`rfa_system.py` additions (additive only):** public wrappers
`own_pick_available`, `market_value_estimate`; **bug fix** in
`_transfer_pick` — `(getattr(to_team, "draft_picks", {}) or {})` built a
throwaway dict when the receiver's pool map was empty, silently dropping
transferred picks. Now it materializes the dict on the team.

QA: `qa_offer_sheet.py` 16/16 (decline path incl. pick transfer, match
path, preview dedup, window gating). Existing `qa_rfa_arbitration.py`
88/88 still green. Window also rendered headless under Xvfb with select →
preview → submit exercised.

## What's NOT done

- AI clubs still never *initiate* offer sheets against the user's RFAs
  outside the July pass (unchanged behavior, not a regression).
- `execute_offer_sheet`'s year/year+1 pick fallback means the top
  compensation band (four 1sts) can only ever find two years of picks —
  a pre-existing engine limitation, flagged but untouched (engine
  boundary).
