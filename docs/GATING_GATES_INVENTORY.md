# Gate Inventory — Gating Migration, Slice 4 (Phase 4 audit)

Audited 2026-09-30 on branch `gating-migration`. Every gate that can
stop the day from advancing, whether it is a genuinely mandatory
decision, and how dismissal behaves. Standing rule: dismissing a gate
surface never resolves the gate — only the underlying decision does.

## Day-advance blockers (BLOCKS_ADVANCE semantics)

These are computed live by `HockeyManagerGUI.get_continue_state()`
(main.py). Pressing Continue with any of them present shows the
non-modal "Action Required" card (`_show_continue_blockers`, one jump
button per blocker); the day never advances until all are resolved.

| id | Surface | Mandatory? | Dismiss behavior |
|---|---|---|---|
| `fantasy_draft` | Fantasy draft in progress | Yes — rosters are mid-redistribution; advancing the day would corrupt the draft | Card dismisses; draft still pending, pill still "Continue" |
| `salary_cap` | Over-cap roster | Yes — NHL rule; an over-cap roster is illegal. Computed by `_cap_compliance_blocker`, the same math as trade validation and the cap UI | Card dismisses; cap breach persists until fixed |
| `captaincy_choice` | Name your captains (1C + 2A) | Yes — NHL Rule 6.1, and only inside the mandatory window. Outside the window the game repairs quietly instead of blocking (R1(a): never fires mid-season) | Card dismisses; picker still mandatory, pill still "Continue" |
| `season_meeting` | Coach expectations meeting | Yes — season pilot. Non-modal by design: the user can navigate anywhere; only day-advance is gated | Card dismisses; meeting still pending |

## Registry gates (pending-items registry)

`get_continue_state()` also reads `BLOCKS_ADVANCE` and `PAUSES_DAY`
entries from the pending-items registry (popup_system.py), so flows can
gate the day without hardcoding. Invariants:

- **No Tier-2 dialog may register BLOCKS_ADVANCE.** Enforced by a
  `ValueError` in `register_pending_item` (popup_system.py). Dialogs
  never block the day; their parent flows might.
- **PAUSES_DAY** (draft-night call, MP ready votes): pauses the
  day-clock / sim tick while the question is open; answering resumes.
  The draft-night call card additionally freezes the draft clock.
- **RESUMABLE** entries never block; they surface via resume chips.

Current PAUSES_DAY entries: draft-night call (`draft_call_answer`
resolver), MP host/client ready votes (multiplayer semantics — owned
by the MP protocol, not redesigned by this migration).

## MP ready gate

`_mp_toggle_host_ready` / `_mp_toggle_client_ready` refuse to vote
ready while any blocker exists (they show the same non-modal card).
This is EHM/MP protocol semantics; the migration did not change it.

## Absent gates (audited, intentionally not added)

- **Preseason → regular-season cutdown gate.** No cutdown mechanic
  exists anywhere in the codebase (no `cutdown`/`cut_down`/`roster_cut`
  references at all), so there is nothing to gate. Per the standing
  no-new-blockers rule, no gate was added. If a cutdown system is ever
  built, it should arrive with its own gate audit.
- **Playoff gates.** None exist and none are needed: the playoffs-mode
  choice (interactive bracket vs quick-sim) is a RESUMABLE decision,
  not a block — declining quick-sims the tournament headless so the
  season always crowns a champion, then rolls to the offseason. There
  is no dead end to guard.

## Presentation (Phase 4)

`_show_continue_blockers` was a modal `InGamePopup` with `grab_set()`
showing only the FIRST blocker's jump button. It is now a non-modal
`ask_card`: one jump button per blocker, Close, dismiss = defer.
Jumping re-reads the LIVE blockers by id (a parked card can go stale),
runs the matching action, and refreshes the top-nav pill so it never
sticks on "Continue (1)". Post-load re-presents answer through the
named `continue_blockers_answer` resolver. The MP snapshot-busy guard
is unchanged.

QA: `/tmp/qa_gates.py` (34/34 headless).
