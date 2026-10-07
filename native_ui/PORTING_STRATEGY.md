# Puck Dynasty Native UI — Screen Porting Strategy

## Architecture

```
native_ui/
├── __init__.py
├── theme.py              # 2K/NHL 14 QSS theme (done)
├── main_window.py        # QMainWindow shell, nav, hub (done)
├── screens/
│   ├── __init__.py
│   ├── base.py           # BaseScreen: game ref, refresh(), navigation helpers
│   ├── hub.py            # Dashboard (done in main_window, extract later)
│   ├── roster.py         # Team roster with player table
│   ├── player_profile.py # Player detail with attribute bars
│   ├── lines.py          # Line editor with tabs
│   ├── staff.py          # Coaches & management
│   ├── ...               # (50 screens total)
├── widgets/
│   ├── __init__.py
│   ├── player_table.py   # Reusable sortable player table
│   ├── attribute_bar.py   # Red/yellow/green attribute bars
│   ├── tile.py           # Dashboard tile cards
│   └── blocker_modal.py  # Continue blocker dialog
└── dialogs/
    ├── __init__.py
    └── ...
```

## Porting Method (per screen)

For each web UI screen:
1. **Read** `web_ui/templates/<name>.html` — layout reference
2. **Read** `web_ui/static/js/<name>.js` — interaction reference
3. **Read** the `/api/<name>*` endpoints in `web_ui/bridge.py` — these show
   exactly which game-logic methods to call and what data shapes to expect
4. **Build** a QWidget subclass that calls the game object directly
   (no HTTP, no JSON serialization)
5. **Style** with the theme QSS — no per-screen CSS files needed

## Priority Order

### Phase 1: Core Loop (Steam MVP)
- [x] Hub/dashboard
- [ ] Setup wizard (new career)
- [ ] Roster
- [ ] Player profile
- [ ] Lines editor
- [ ] Continue/advance + blocker modal (done)
- [ ] Daily results

### Phase 2: Team Management
- [ ] Practice Center (with "Coach Runs Practice" — v0.15.0 headline, missing from web-ui)
- [ ] Staff
- [ ] Contracts
- [ ] Morale
- [ ] Development
- [ ] Tactics
- [ ] Camp
- [ ] Season Goals (missing from web-ui)
- [ ] Offseason Programs (missing from web-ui)
- [ ] Jersey Numbers Editor (missing from web-ui)
- [ ] GM Relationships Dashboard (missing from web-ui)

### Phase 3: Transactions
- [ ] Trades
- [ ] Free agents
- [ ] Waivers
- [ ] Offer sheets
- [ ] Trade block
- [ ] Deadline

### Phase 4: League
- [ ] Standings
- [ ] Stats/leaders
- [ ] Schedule
- [ ] Playoffs
- [ ] Draft
- [ ] Lottery
- [ ] History
- [ ] Season summary
- [ ] AHL

### Phase 5: Front Office
- [ ] Inbox (receive-only)
- [ ] News
- [ ] Finances
- [ ] Settings
- [ ] Save/load

### Phase 6: Systems
- [ ] Clutch, Circumstance, Discipline, Rivalry, Deployment, Condition

### Phase 7: Extras
- [ ] Watch, Replay, Boxscore, Compare, Calendar, Coach checkin,
      Captains, FA Frenzy, Fantasy draft, Manager

## Key Differences from Web UI

| Web UI | Native UI |
|--------|-----------|
| Flask HTTP API | Direct Python method calls |
| JSON serialization | Native Python objects |
| Page reloads | Widget stacking (instant) |
| Browser back button | Qt navigation stack |
| CSS files per screen | Single QSS theme |
| JS event handlers | Qt signals/slots |
| `fetch()` calls | Direct `self.game.method()` |

## Performance Wins

- No HTTP overhead (the 13-25s blocker delay was HTTP + serialization)
- No page reloads (the 30s back-button delay is gone)
- Direct object access (no JSON round-trip)
- Qt's model/view is faster than DOM for large tables

## Deep Audit Findings (Oct 6, 4-bot audit)

Caleb was right — the first audit missed significant surface area.

### Total Scope
- **60 full screens** (via `open_*` methods)
- **22 popup dialogs** (modal + non-modal + automatic event-driven)
- **342 API routes** (14 core + 328 screen blueprints)
- **106 `/api/command` ops** (the master write dispatcher)
- **15-item player context menu**

### Critical Port-Risk Items

**Interaction patterns:**
1. Lines drag-and-drop with green/yellow/red position-fit feedback + `justDragged` 150ms anti-misclick guard
2. Non-modal popups (Jersey Numbers, Offseason Programs, Season Goals) stay open during navigation
3. Nested dialogs ("Set Goal" inside Season Goals)
4. Right-click context menus EVERYWHERE (roster rows, players, teams, staff) — Qt `customContextMenuPolicy`
5. Keyboard shortcuts: `?` cheatsheet, `Space` advance/pause, `Ctrl+S` quicksave, `C` camera, `Escape` closes everything

**Hidden features (no nav entry):**
6. Hub auto-advance loop (800ms state machine, stops on blockers/game days)
7. Staged reveals: lottery + awards ceremony (client-side theater)
8. Fantasy draft + lottery hidden inside `inbox_actions.py` (not own modules)
9. Daily results + boxscore inside `schedule.py`; Replay inside `watch.py`
10. Staff hiring inside `free_agents.py`; Jersey numbers inside `roster.py`
11. Season goals + GM relationships inside `manager.py` (endpoints exist, not linked)
12. MP bar injected into every page via nav.js (invisible in single-player)
13. Iconic game starring (`/api/hub/iconic_toggle`)

**URL deep-links (must preserve):**
- `/compare?p1=&p2=&p3=&p4=` (bookmarkable)
- `/contracts?player=` (+`&elc=1`)
- `/trades?team=&player=` (+ draft-day pick params)
- `/replay?idx=N`, boxscore `?date=&home=&away=`

**Stateful flows:**
14. Coach check-in multi-beat conversation (answer → nonce → poll → finish)
15. Draft war room: incoming-call polling, pace system (1x/4x), sessionStorage counter handoff
16. Contract negotiation: two-step counter, 3s live sync, ELC validation chain
17. Morale: two-step fire-coach arm (4s auto-disarm), talk preview with outcome tiers
