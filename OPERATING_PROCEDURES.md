# Operating Procedures

Standing rules for native UI and hockey-engine changes, derived from the Oct. 8–9, 2026 native UI findings, quality review, and fix verification.

## Recurring root causes

1. **UI bypasses canonical engine processing — 5 affected paths (watch, schedule, roster, tactics, morale).** Before adding a UI handler, find and reuse the engine API that performs the action and its side effects. Do not reproduce standings, waivers, ownership consequences, or game-result processing in a screen.
2. **UI-derived state disagrees with authoritative state — at least 7 verified cases.** Resolve player stats from `Player.stats`, active roster count from `roster_limits`, game completion/overtime from canonical result metadata, standings from the league sorter, and messages from the actual message model. Do not infer these values from convenient but incomplete UI fields.
3. **Navigation loses context or selection — 5 affected flows.** Pass the selected player/team/pick through a supported screen initializer. Define behavior for own-team assets, every tab, unmapped screens, and empty selections.
4. **Fallbacks hide failure as valid empty/default state — 3 verified regressions or near-misses.** Preserve distinction between “no data” and “could not read data.” Fail closed when transaction eligibility or authority cannot be established.
5. **Partial refactors omit imports, states, or contract variants — 3 regressions plus repeated partial fixes.** After extraction, verify every name used, every model state represented, and every affected screen construction path.
6. **UI controls overpromise unsupported behavior — 3 contract/draft flows.** A visible option must reach a validated engine API and persist; otherwise remove/disable it with an explanation. Labels must describe what the action actually does.
7. **Cross-screen logic is copied instead of shared — 4 explicit redundancy groups.** Use common helpers for safe calls, scroll setup, navigation/context-menu actions, visual styles, contract outcomes, and standings ordering.
8. **Validation proves syntax but not behavior.** Every reported fix needs a focused scenario that checks state changes, side effects, and non-duplication; compile-only validation is insufficient for workflows.

## Pre-commit checks (every dev, every change)

1. Read the target screen, the model/engine implementation, and at least one existing caller of the intended engine operation before editing.
2. Search for the exact engine method, relevant state field, and all call sites. Confirm its accepted arguments, result shape, failure behavior, and side effects; do not guess method names or status values.
3. Identify authoritative data and APIs before using UI copies: `Player.stats` is a `PlayerStats` object; use `stats.goals`/`stats.assists`, not `stats.get(...)`. Use `roster_limits.ACTIVE_ROSTER_MAX` and `active_roster_count(team)` for NHL capacity.
4. Write a focused regression check for both success and failure/boundary states. For game/transaction flows, assert result count, team/player state, standings, and derived indexes update exactly once.
5. Exercise supported input shapes: dictionary/object/tuple schedule entries, absent/zero values, empty data, failed lookups, host/non-host multiplayer, and all selectable tabs where applicable.
6. For UI navigation, verify the selected entity and mode survive screen transition, displayed row sorting, filtering, and direct navigation.
7. For threaded work, establish thread-safety and marshal UI notifications/state refreshes to the Qt UI thread.
8. Run existing focused tests, screen smoke checks, and relevant project validation. Do not claim runtime verification when only source inspection or compilation was performed.
9. Inspect `git diff --check` and changed-file scope; run secret scanning on every changed/created file before commit.
10. Record the tested scenarios, exact commands, and known limitations in the change/PR description. Do not close audit items without evidence.

## Code conventions (mandatory)

1. Import and use `native_ui.safe.safe_call`; do not recreate local `_safe` wrappers. Supply `context="screen/action"` for failure-prone calls.
2. Use canonical model/engine APIs for roster, waiver, contract, standings, schedule, and team-system changes. Keep UI code responsible for inputs, display, and invoking the supported operation.
3. Change roster membership through `Team.add_player`/`Team.remove_player` plus the canonical affiliate synchronization path. Keep `team_name`, roster membership, and player history consistent.
4. Use the shared `systems_common.add_scroll_content` helper for Systems page scroll content and explicitly import every other helper used by the page, including `systems_nav_bar`.
5. Keep one source of truth for standings sort, contract outcome classification, screen-to-section mapping, schedule completion, and result metadata.
6. Store entity references in table item data; never infer the underlying player from a pre-sort row index after sorting/filtering.
7. Keep user-visible offer labels and status text aligned with engine outcomes. “Signed” means an accepted contract; pending, countered, and rejected are distinct states.
8. Centralize policy constants and source limits from engine validation when available. Do not leave duplicate literals in widget initialization, seeding, and validation paths.
9. Keep related public methods as orchestration and extract purpose-specific helpers without changing transaction semantics.
10. Preserve accessible state for toggles and filters, and update labels/icons/checked state from the model rather than maintaining unsynchronized UI-only state.

## Never do this

1. **Never call a transfer primitive to submit a claim.** It bypasses priority resolution; enqueue the claim through the canonical API.
2. **Never mutate `team.roster` or affiliate lists directly.** It skips team-name, history, capacity, and affiliate side effects; use team APIs and the canonical synchronization route.
3. **Never decide waiver eligibility or roster capacity from raw counts or fail-open fallbacks.** Use canonical eligibility and active-roster helpers; block when eligibility is unknown.
4. **Never manually duplicate postgame standings/record updates.** Use the normal postgame path once to avoid missing fields or double-counting.
5. **Never accept fabricated user-entered score/rivalry/streak context in an engine decision.** Derive it from authoritative game/league state or mark it unavailable.
6. **Never convert an exception into a successful empty state for a user action.** A rendering fallback may be fail-soft, but action outcomes must report retrieval/operation failure.
7. **Never use score margin alone to label an overtime loss, raw goals to rank per-game rates, or a stale schedule flag to decide whether a game is complete.** Use authoritative metadata and games-played data.
8. **Never let one context-menu/tab handler silently read another tab's selection.** Pass the selected entity explicitly.
9. **Never show a control for an unsupported contract term or a button label that promises an action the destination does not perform.**
10. **Never dispatch parallel developers to the same file or shared API without an explicit ownership/dependency plan.**
11. **Never consider compile success equivalent to workflow correctness.** Run scenario checks that prove state and side effects.

## Review checklist

### Code correctness reviewer checks

1. Verify every called method exists and the arguments/result shape match its actual implementation and callers.
2. Check exception paths, empty/null/zero values, data-shape variants, and mutation ordering; ensure failures cannot look like success.
3. Verify no direct list edits bypass model APIs, no duplicate transaction/standings updates occur, and rollback restores every staged field.
4. Check imports/names after refactors and instantiate every changed screen, including dependent navigation and shared helper paths.
5. Confirm sorted/filtered row actions use item-associated entity references, not original indexes.
6. Require targeted tests or repeatable manual scenarios for each claimed fix; compare before/after state and assert exactly-once side effects.
7. Review changed-file scope, accessibility state, logs/context, documentation, and secret-scan result.

### Logic/design reviewer checks

1. Confirm one canonical source of truth for the operation, result status, navigation mapping, and derived UI state.
2. Check all states and transitions: accepted/countered/pending/rejected; watched/unplayed/completed; eligible/exempt/unknown; empty/success/error.
3. Verify idempotency and ordering: no game simulation, result recording, standings update, or roster transfer may happen twice.
4. Confirm UI labels, visible options, filters, counts, and destinations accurately represent the operation and preserve user selection.
5. Check fallback behavior is explicit, actionable, and cannot bypass a business rule.
6. Review interfaces shared across screens before parallel work; identify file ownership and prerequisites.

### Hockey realism reviewer checks

1. Confirm 23-player active roster checks use the league's active-contract/waiver/emergency/IR/LTIR rules, not raw list length.
2. Verify waiver claims enter priority resolution and respect host/non-host human claim ordering; no team acquires a player immediately by clicking Claim.
3. Confirm demotions respect waiver eligibility and consent rules, and parent/affiliate rosters stay synchronized.
4. Verify game outcomes distinguish regulation, overtime, and shootout; result processing updates player/team/league records once.
5. Confirm standings and tie-break ordering match the league's canonical rules across screens.
6. Check line assignments against simultaneously deployed units: permit valid PP/PK reuse, reject impossible same-unit duplicate deployment, and preserve goalie roles.
7. Ensure coach-owned tactics use ownership/reputation consequences and GM-owned systems follow their intended separate path.
8. Verify offer terms, bonuses, clauses, status wording, and “Signed” state match what the contract engine actually accepts and stores.
9. Ensure morale/team-talk context is grounded in actual game and team state, never editable substitutes.

## Audit document and dispatch procedure

1. Publish three artifacts for each audit: `AUDIT_[TYPE]_YYYY-MM-DD.md`, `AUDIT_[TYPE]_YYYY-MM-DD_PROMPTS.md`, and this `OPERATING_PROCEDURES.md`.
2. In the issue report, include file, line range, severity, current/broken code, root cause, exact fix or explicit research steps, and executable verification.
3. In the prompt pack, group all issues for a file into one prompt. Include exact file ownership, code evidence, severity, lines, fix, verification, dependencies, and the three-reviewer/integration/commit process.
4. Include dispatch batches and shared-dependency exclusions. Do not parallelize edits to a shared file or state contract.
5. Append new dated procedures and evidence to this file during later audits; do not delete earlier rules. Consolidate wording only when preserving prior safeguards.
6. Mark each issue MATCHES/PARTIAL/MISSING/BETTER with evidence when verifying implementation. List regressions and newly introduced issues separately, and state whether runtime testing occurred.

## Change history

- **2026-10-09:** Initial procedures based on the 2026-10-08 native UI findings, quality/UX audit, and verification of `native-ui` commit `4a6d5f6`.
