# Puck Dynasty Web UI — Painstaking Migration Plan

**Source:** `main` branch v0.18.4 (Tkinter) — the complete, working game  
**Target:** `web-ui` branch — must reach full functional parity, screen by screen  
**Rule:** Each screen is migrated COMPLETELY or not at all. No shallow ports.  
**Testing:** Every screen tested against LIVE game data (real GameManager, not mocks) before marking complete.

## Phase 1 — Core Loop (P0) — Current Focus

These are the screens Caleb uses every session. Must be rock-solid.

### 1.1 Continue / Day Advance ✅ FIXED (2026-10-04)
- [x] Bridge calls `_on_continue_pressed` (was calling non-existent `advance_day`)
- [ ] Test: advance 7 days, verify date changes, games sim, inbox fills
- [ ] Blocker modal appears when blockers exist
- [ ] Auto-resolve options work

### 1.2 Hub / Dashboard ✅ DONE (2026-10-04)
- [x] Tiles render with live data (record nesting fixed)
- [x] All 10 tiles link to correct screens (verified)
- [x] Tile data refreshes after Continue (page reload)
- [x] Next game panel shows real opponent/date (BOS @ DET Sep 22)
- [x] Stat strip: Record/Points/G-Gm/GA-Gm/Cap Space (live)
- [x] Inbox peek shows 3 most recent live messages

### 1.3 Inbox
- [x] Gmail-style cards render
- [ ] Action buttons work (trade offers, contract counters, etc.)
- [ ] Mark read/unread persists
- [ ] Mandatory messages block Continue until resolved

### 1.4 Lines — ✅ VERIFIED (2026-10-04)
- [x] Falls back to `best_lines()` when lineup empty
- [x] Key normalization (F1_LW → LW1)
- [x] Edit mode exists; POST /api/lines/set queues set_lines_real
- [x] Save persists via apply_lines_payload + flatten_lineup (real machinery)
- [ ] PP/PK units editable (GAP: only ES slots; Tkinter has PP1/PP2/PK1/PK2)

### 1.5 Trades — ✅ VERIFIED (2026-10-04)
- [x] TEAM_ABBR map (BOS not BB)
- [x] `/api/trades/assets` implemented (200 with 27 players on live data)
- [x] Trade builder UI exists with AI verdict via /api/trades/evaluate
- [x] Retention (0/25/50%) ported; pick protection UI ported
- [ ] Full E2E: propose → inbox response (needs live negotiation test)
- [ ] Async AI response (1-3 days via inbox) — web does immediate execution

## Phase 2 — Club Management (P1)

### 2.1 Roster (5 tabs) ✅ DONE (2026-10-04, commit 7c4e5bd)
- [x] NHL / AHL / Prospects / Depth Chart / Salary Cap tabs
- [x] Sort/filter/search
- [x] Bulk moves with CBA validation (CHL-NHL, ELC gate, junior return)
- [x] Right-click player menu (context menu)
- [x] Click → player profile (modal with attributes)

### 2.2 Tactics (6 groups) ✅ DONE (2026-10-04, commit 313060e)
- [x] Even Strength / PP / PK / Line Matching / Forecheck / OZ pickers
- [x] Expected impact readout (same xG tables as sim)
- [x] Practice tab (focus/intensity/bag skate)

### 2.3 Morale / Dressing Room
- [ ] Full morale view (not read-only stub)
- [ ] Team talks, Bag Skate, etc.

## Phase 3 — Trades & Contracts (P2)

### 3.1 Trade Block (full)
### 3.2 Free Agents (3 tabs + negotiation)
### 3.3 Draft (war room)
### 3.4 Contracts/Extensions (full negotiation)

## Phase 4 — Everything Else (P3+)

Per MIGRATION_AUDIT.md priority order.

---

## Process Per Screen

1. **Read** the Tkinter implementation completely (find the View class)
2. **List** every feature: data shown, buttons, dialogs, writes
3. **Implement** web version with ALL features (not a subset)
4. **Test** against live GameManager (`/tmp/test_gm.pkl` pattern)
5. **Verify** no mock data, no 404s, no empty states
6. **Commit** with clear message; update this checklist

## Known Issues to Fix

- [ ] Visualizer double-sim: watched games need "played" flag so advance-day skips them
- [ ] Artifact visual parity: hub doesn't match puck-dynasty-tile-hub artifact design
