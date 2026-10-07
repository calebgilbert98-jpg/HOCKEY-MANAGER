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
