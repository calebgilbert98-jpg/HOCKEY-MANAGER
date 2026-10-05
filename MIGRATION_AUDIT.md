# Puck Dynasty — Tkinter → Web UI Migration Audit

**Source of truth:** `main` branch, v0.18.4 (Tkinter desktop app)
**Migration target:** `web-ui` branch (Flask + HTML/JS, served on localhost)
**Date:** 2026-10-04
**Status legend:** ✅ Complete · 🟡 Partial · ❌ Missing · 🔧 Broken (exists but doesn't work)

> Priority order: core loop first (Continue/hub/inbox), then roster/lines,
> then trades/contracts, then everything else.

---

## P0 — Core loop

### Dashboard (Tkinter: `HomeDashboard`, dashboard_home.py — 1381 lines)
| Tkinter feature | Web status |
|---|---|
| Header: logo, name, record/streak/division pills, date, smart Continue button + status line | 🟡 Web hub: team header + Continue; no pills/date |
| Stat strip: Record, Points, G/Gm, GA/Gm, PP%, PK%, Streak, Cap Space (live w/ LTIR) | ❌ |
| Cards: Standings (scope dropdown, click-through) / Team Leaders (sort dropdown) / Schedule (upcoming/results) / Next Game / Injuries / Morale / Top Prospects / Milestones / Iconic Games (star toggle) / Inbox (3 recent) | ❌ Web: 10 tiles linking to screens only |
| Section-nav pills; quick-action grid (Roster/Lines/Tactics/Schedule/Standings/Trades/Inbox/Finances) | 🟡 Web: tiles serve as quick actions |
| Continue button variants (Continue/Next Day/Deadline Day/Game Day) + blocker count "Continue (N)" + ⏩ Auto toggle | 🟡 Web: Continue + blocker modal; no auto-advance |
| Global shortcuts: Space=advance, Ctrl+S=quicksave, Esc=cancel, ?=cheatsheet | ❌ |

### Continue / Day advance (Tkinter: `_on_continue_pressed` → `get_continue_state` → `_show_blocker_modal` → `simulate_day`)
| Tkinter feature | Web status |
|---|---|
| Blocker modal: every blocker card with Primary (jump to fix) + ⚡ Auto-resolve + Secondary actions | 🟡 Web modal lists blockers w/ resolve; auto-resolve ops ported (cap/roster/captains) |
| Blocker types: fantasy_draft (no auto), entry_draft (no auto), salary_cap (waiver-safe auto), salary_floor, roster_limit_23 (waiver-safe auto), dress_minimum (auto-recall / emergency fill-ins), captaincy (auto-pick), season_integrity (hard stop, no auto) | 🟡 Partial — verify each auto path |
| Game-day bundle: pre-match presser + team talk + coach instruction + WATCH LIVE / QUICK SIM | ❌ |
| Auto-advance loop (~800ms/tick, stops on game day/blockers/messages/Esc) | ❌ |
| Loading overlay + double-trigger guard | ❌ |
| Post-advance landing: game results window or inbox | ❌ |

### Inbox (Tkinter: `InboxView`, inbox_window.py — Gmail-style)
| Tkinter feature | Web status |
|---|---|
| Filter pills: All/Unread/Urgent/Saved/Story/Trade/Scouting/Contracts/Injuries/Media/League; live search | 🟡 Web: filter pills; no search confirmed |
| Color legend (red=action, gold=urgent, blue=unread); mandatory red bar + "Action needed" pill | 🟡 Partial |
| Preview pane; Story view (developing now / story so far / championships) | ❌ |
| Interactive message bodies: game_day, trade_offer/counter, contract_counter, rfa_qualifying, buyout_window, staff_renewal, media_fine, offer_sheet_match, arbitration_walkaway — each with decision buttons | ❌ Web: mark-read/delete only |
| Compose/Reply/Forward editor; Mark All Read; Delete Read | ❌ |
| Right-click menu (Read/Unread/Reply/Forward/Important/Save/Delete) | ❌ |

### Save / Load (Tkinter: `SaveLoadView`, save_load_system.py)
| Tkinter feature | Web status |
|---|---|
| 6 quick-save slots; Advanced tab (name/desc/category/compress/backup/screenshot/stats) | 🟡 Web: save via `save_game` op; slot UI unknown |
| Manage tab: sortable file list, rename/export/import/delete/properties, right-click menu | ❌ |
| Load with replace-confirm; autosave (background thread) | 🟡 Load via setup flow |

### Settings (Tkinter: `SettingsView`, settings_window.py — 5 tabs)
| Tkinter feature | Web status |
|---|---|
| Game Results / Interface (font scale, theme) / Simulation (auto-continue, viewer mode, draft quality, scoring) / Notifications / Career (board can sack GM) | ❌ `/settings` read-only stub |
| Reset to Defaults / Apply / Save with dirty tracking | ❌ |

### Game Results (Tkinter: `_show_game_results_window` + `GameResultsView` + `GameBoxScoreView`)
| Tkinter feature | Web status |
|---|---|
| Single-game modal: Summary / Scoring / Player Stats / Team Stats / Game Viewer tabs | ❌ |
| Daily results: Games (box score drill-down) / Standings / News tabs | ❌ |
| Box score: Scoring Summary / Player Stats / Lines (grades) / Team Stats; 3 stars; click-through to profiles | ❌ |

### Watch / Visualizer (Tkinter: `PBPVisualSim` pbp_visual_sim.py — live; `RebuiltNHLGameViewer` — replay)
| Tkinter feature | Web status |
|---|---|
| Live: play/pause, 1x/2x/4x, auto, end-sim; shot map/cam/sound toggles; detail levels | 🔧 Web: canvas + SSE, MOCK sim (real-GameSim wiring in progress) |
| Score bug: NHL-color abbrs, clock, win-prob bar, intensity meter + drivers, momentum strip, next-big-moment jump | ❌ |
| Tactics tab (live 7-system whiteboard, suggest/enforce/takeover) | ❌ |
| Replay: Watch All / Highlights / Text modes; camera zones; speed | ❌ |
| Blocks until final whistle; shot chart exported on close | ❌ |

### Awards Ceremony & Season Summary
| Tkinter feature | Web status |
|---|---|
| 11-trophy ceremony order; finalists; reveal flow; electorate stories | ❌ No web screen |
| Human Vezina ballot (top-3 ranked vote, 5-3-1) | ❌ |
| Season summary: Awards / League Leaders / Your Team tabs | ❌ |

---

## P1 — Club (team management)

### Roster (Tkinter: `RosterView`, windows.py:282 — 2300 lines)
| Tkinter feature | Web status |
|---|---|
| 5 tabs: NHL Roster / AHL Roster / Prospects / Depth Chart / Salary Cap | ❌ `/roster` single flat table only |
| NHL columns: select, #, Name, Pos, Age, Tier (label not numeric), Pot, Salary, Contract, Morale, Health badges (IR/LTIR/SUSPENDED/EMERGENCY), TOI/GP, Performance grade | 🟡 Web shows attribute bars; missing most columns, health badges, tier display |
| AHL tab (Call Up bulk, Return to Junior bulk w/ CHL-eligibility rules) | ❌ |
| Prospects tab (Promote to AHL bulk, Rights Watch w/ expiry color-coding, ELC talks routing) | ❌ |
| Depth Chart tab (4 lines + 3 pairs + goalies, tier-colored tiles) | ❌ |
| Salary Cap tab (usage bar, payroll/space/dead cap/retained/bonus overage/buyouts, contract table) | ❌ `/finances` is a stub |
| Toolbar filter pills (Position/Age/Min OVR) + text search + named column presets; sortable headers | ❌ Web: no sort/filter/search |
| Bulk moves with CBA validation (CHL-NHL agreement, 23-man limit, ELC gate, recall paper-transaction rule) | ❌ |
| Right-click universal player menu (12+ items: Scout, Physio, Shortlist, Compare, Training Focus, IR/LTIR, Trade Block, Extension...) | ❌ |
| Click name → player profile card | ❌ |
| Footer: Trade Block, Contract Extensions, Export Roster CSV, Refresh | ❌ |

### Edit Lines (Tkinter: `CleanEditLinesView`, main.py:23030 — 2200 lines)
| Tkinter feature | Web status |
|---|---|
| ES / PP / PK unit switcher; 4 forward lines + 3 D pairs + Starter/Backup | 🟡 Web shows units; PP/PK coverage unknown |
| Point-click assignment (pick up/move/swap/clear, Esc cancels); × clear; double-click clears | 🟡 Web has edit mode; interaction model differs |
| OFF POS amber badge; footer warning "N off-position · M empty slots" | ❌ |
| Auto Best (ES+PP+PK via `best_lines`); Reset (confirm); Save Lines | 🟡 Web: set via `/api/lines/set`; Auto Best unknown |
| Line chemistry breakdown popup (per-pairing drivers, archetype legend) | ❌ |
| Ice-time hints per line; line vs opponent-line matchup dropdowns (`team.line_matchups`) | ❌ |
| View options popup (ratings/ice-time/chemistry toggles, persisted) | ❌ |
| Invalid-position hard gate (goalie vs skater only); dressability advisory not blocking | 🟡 |

### Tactics (Tkinter: `TacticsView`, main.py:25227)
| Tkinter feature | Web status |
|---|---|
| 6 tactic groups: Even Strength / Power Play / Penalty Kill / Line Matching / Forecheck / Offensive Zone — pill pickers, immediate write | ❌ No web screen |
| Expected Impact readout (xG multipliers from sim tables) | ❌ |
| Practice tab: weekly planner (focus/intensity pills, bag skate, assistants, last-week receipt, Set & Run) | ❌ |

### Dressing Room (Tkinter: `DressingRoomView`, dressing_room.py:1892)
| Tkinter feature | Web status |
|---|---|
| Room mood 0-100; hierarchy w/ influence bars; social groups/cliques; room feed | ❌ No web screen |
| Team talks: 3 tones × coach/captain speaker, pre-game + intermission queue | ❌ |
| Captaincy-crisis banner + resolution (Keep/Challenge/Strip/Reassign, successor flow) | ❌ |
| Coaching card: fire/hire coach, GM trust, shelf-life; Clear-the-air repair | ❌ |

### Morale (Tkinter: `MoraleView`, morale_window.py:17)
| Tkinter feature | Web status |
|---|---|
| Team morale header; coaching card; watch list (severity icons); player response table; dynamics feed; hierarchy; social groups; rivalries | ❌ `/morale` read-only stub |
| Advise Coach popup; Line Control popup (GM vs coach); Bag Skate / Speech / Practice / Back Room actions; Declare Rival popup | ❌ |

### Analytics Hub (Tkinter: `AnalyticsHubView`, analytics_hub.py:1 — read-only)
| Tkinter feature | Web status |
|---|---|
| 5 tabs: Shots & xG (rink shot map, xG table) / Momentum (chart) / Zone Entries / Lines / Ask the Analyst | ❌ No web screen |

### Practice Center (Tkinter: `PracticeCenterView`, enhanced_practice_system.py:1894)
| Tkinter feature | Web status |
|---|---|
| Player list w/ fatigue/condition/current practice; 10 drill types; intensity; sessions/week + duration spinboxes | ❌ No web screen |
| Coach Runs Practice (auto-assign weakness-targeted, fatigue-aware) | ❌ |
| Single session / schedule / stop; coaching read box | ❌ |
| Position training UI: NOT in Tkinter either (model exists, no UI) — gap on both | ❌ |

### Training Camp (Tkinter: `TrainingCampWindow`, training_camp_ui.py:46 — read-only)
| Tkinter feature | Web status |
|---|---|
| Camp ratings tab (per-scrimmage 1-10, avg, condition, auto-flags); scrimmages tab | ❌ `/camp` read-only stub |

### Captains (Tkinter: `SetCaptainsView`, windows.py:15928)
| Tkinter feature | Web status |
|---|---|
| C + 2A dropdowns; deposition flow (Speak first / Announce cold / Cancel → pushback handling) | 🟡 Web: set via `set_captains` op; no deposition flow |
| Mandatory captains blocker variant (live validation, no cancel) | 🟡 Partial (blocker modal) |

### Jersey Numbers / Season Goals / Offseason Programs
| Tkinter feature | Web status |
|---|---|
| Jersey number editor (retired-number + duplicate guards) | ❌ No web screen |
| Season goals per player (type picker, target, hit/miss effects) | ❌ No web screen |
| Offseason programs (8 focuses × intensity, Jul-Aug ticks) | ❌ No web screen |

---

## P2 — Trades & contracts

### Trade Center (Tkinter: `TradeWindow`, windows.py:5130)
| Tkinter feature | Web status |
|---|---|
| Partner picker (31 teams); your/partner roster lists grouped NHL/AHL/Prospects | 🟡 Web: team picker + asset lists via `/api/trades/assets` |
| Double-click adds to offer; right-click removes; offer lists both sides | 🟡 Web builder has add/remove |
| Live AI verdict meter (Fair/You overpay/They overpay) + cap-impact delta | 🟡 Web: `/api/trades/evaluate` verdict |
| Per-player retention dropdown (0/25/50%) | ✅ Ported |
| Add Pick dialog (round 1-7, year, lottery protection none/top-3/top-10) | ✅ Ported (protection UI-only, AI doesn't price it) |
| NTC waiver question-chain; cap preflight | ❌ |
| Propose → AI answers in 1-3 days via inbox (async); instant on deadline day | ❌ Web: immediate execution on accept |
| Counter offers: Review & Adjust / Accept / Walk Away via inbox TRADE TALKS | ❌ |
| Trade history list; NTC/NMC inline flags | ❌ |
| Parked-deal restore (Tier-B session revalidation) | ❌ |

### Trade Block (Tkinter: `TradeBlockWindow`, main.py:25669)
| Tkinter feature | Web status |
|---|---|
| Tabs: Your Block / Trade Interest / Other Teams; filter pills; sortable tree w/ checkboxes | ❌ `/trade_block` read-only stub |
| Bulk Add/Remove; Shop Player; Suggest Trade Value; Simulate Trade Offers; Generate Interest | ❌ |
| Negotiate Trade (pre-loads center); Decline Interest; Express Interest | ❌ |

### Trade Deadline Center (Tkinter: `trade_deadline_center.py` — deadline-day only)
| Tkinter feature | Web status |
|---|---|
| Countdown header; breaking-news ticker; market activity grid; buyer/seller stance | ❌ No web screen |
| QUICK TRADE (live eval, instant answers); ADVANCE 30 MIN; EMERGENCY TRADE fire sale | ❌ |
| Market browser tabs: overview/buyers/position needs/predictions/cap analysis | ❌ |

### Free Agents (Tkinter: `FreeAgencyView`, windows.py:2597)
| Tkinter feature | Web status |
|---|---|
| 3 tabs: Players / Staff / Market Overview; sortable tree; search + pill filters | 🟡 Web: player list + signing; no staff tab, no filters |
| Market Analysis window (value vs salary, comparables, projection) | ❌ |
| Sign → legality check → contract negotiation window | 🟡 Web: direct offer → `sign_free_agent_real` |
| Staff hiring tab; Compare Players; Export List; Help | ❌ |

### Free Agent Frenzy (Tkinter: `FreeAgencyFrenzy`, event_day_hubs.py:691 — July 1)
| Tkinter feature | Web status |
|---|---|
| Signing wire; top-8 FA cards; done deals; cap picture; ticker | ❌ No web screen |

### Offer Sheets (Tkinter: `OfferSheetWindow`, offer_sheet_ui.py:73)
| Tkinter feature | Web status |
|---|---|
| RFA target list; AAV slider; term menu; compensation preview (real bands + pick availability); legality checks | ❌ No web screen |
| Present → gates → accept/refusal → AI match decision → execute | ❌ |

### Waivers (Tkinter: `WaiversView`, windows.py:13761)
| Tkinter feature | Web status |
|---|---|
| Tabs: Waiver-Eligible / Waiver Wire; claim priority strip; eligibility rules | 🟡 Web: list + claim via `claim_waiver` op |
| Place on waivers (NMC consent card, dressed-minimum warning) | ❌ |
| Claim → pending flag → noon processor in priority order | 🟡 Web: immediate claim |

### Draft (Tkinter: `DraftView`, windows.py:7346)
| Tkinter feature | Web status |
|---|---|
| Draft board (Available/Results/My Picks/Scout Report); war room; ticker; pace controls | ❌ `/draft` read-only stub |
| Draft Selected (2-step confirm); Sim Pick; Trade This Pick (pick-swap dialog, AI accept/counter/reject) | ❌ |
| Draft Day Central event hub (live wire, on-the-clock, top prospects, deals) | ❌ |
| Fantasy Draft (separate flow) | ❌ |

### Contracts / Extensions (Tkinter: `ContractExtensionsView` windows.py:14230 + `ExtensionNegotiationView` + `ContractNegotiationView` windows.py:12939)
| Tkinter feature | Web status |
|---|---|
| Expiring/All tabs; Negotiate; Auto-Negotiate All (simulated decisions) | 🟡 Web: extension terms + `extend_real`; no auto-negotiate |
| Extension dialog: salary presets, term radios, NTC checkbox, bonus; acceptance chance; agent counter panel | 🟡 Web: negotiation dialog (accept/counter/walk-away) |
| UFA dialog: salary/term/clauses (NMC/NTC/MNTC w/ blocked-teams slider), ELC mode, comparables, offer history, 4-day consideration | 🟡 Partial |
| Tier-B session parking of draft terms | ❌ |

### Finances (Tkinter: `FinancesView`, windows.py:11125)
| Tkinter feature | Web status |
|---|---|
| 5 tabs: Salary Cap / Contracts / Projections / Management / Reports | ❌ `/finances` read-only stub |
| Cap utilization bar; salary by position; contract filters; expiring table; recommendations; generated reports; export | ❌ |
| Quick actions: extensions, trade evaluator, buyout calculator, cap compliance check | ❌ |

### GM Options (Tkinter: `GMOptionsView` — launcher panel, no own toggles)
| Tkinter feature | Web status |
|---|---|
| Nav hub: Trade Block / Waivers / Captains / Extensions / Settings | ❌ No web screen (hub covers nav) |

### Systems — TRACK C (all read-only, `trackc_common.py` shell)
| Tkinter feature | Web status |
|---|---|
| Ice-Time Deployment / Roster Condition / Discipline List / Rivalry Dashboard / Clutch Factors / Circumstance Shifts / Fan Buzz | ❌ No web screens |

---

## P3 — Personnel

### Staff Management (Tkinter: `StaffManagementView`, staff_management_window.py)
| Tkinter feature | Web status |
|---|---|
| 3 tabs: Current Staff / Hire Staff (→ FA staff page) / Organization chart | ❌ `/staff` read-only stub |
| Filter bar (department/rating/salary/contract); 11-col sortable table; morale+rating color tags | ❌ |
| Staff details popup: 6-7 tabs (Overview/Attributes/Standing/Personality/Record/Track Record/Analytics) | ❌ |
| View Details / Negotiate Contract / Reassign Role / Release Staff (multi-select, severance) | ❌ |
| Right-click: View Details, Negotiate, Reassign, Declare Rival, Release | ❌ |

### Scouting (Tkinter: `ScoutingView` windows.py:6680 + `ModernScoutingView` modern_scouting_window.py)
| Tkinter feature | Web status |
|---|---|
| 6 tabs: Players / Scouts / Draft / Assignments / Reports / Targets | 🟡 `/scouting` single page; assignments via `add_scouting_assignment_real` |
| Scout region assignment; hire scout; draft board (add/reorder/reset, drives auto-draft) | ❌ Draft board not ported |
| Report viewer (accuracy, viewings, strengths/weaknesses) | ❌ |
| Cancel assignment (keeps filed reports) | ❌ |

### Player Development (Tkinter: `PlayerDevelopmentViewProfessional`)
| Tkinter feature | Web status |
|---|---|
| Overview tab: sortable tree + details pane (summary, attributes, recommendations) | ❌ `/development` read-only stub |
| Individual tab: 8 training focuses × 3 intensities, assign program, progress tracking | ❌ |
| Team Analysis tab (pipeline, age distribution) | ❌ |
| Development history popup; contract details popup; compare players | ❌ |

### GM Relationships (Tkinter: `GMRelationshipsView`, gm_relationships_window.py — read-only)
| Tkinter feature | Web status |
|---|---|
| 31-GM table: Stature/Respect/Heat/Trend, sortable, color-coded | ❌ No web screen |

### Manager Hub (Tkinter: `ManagerHubView`, manager_hub_window.py)
| Tkinter feature | Web status |
|---|---|
| 6 tabs: Board (confidence, expectations, patience) / Squad (chat actions, statuses, captaincy) / Training / Prospects / Press / Profile | ❌ No web screen |

### Shortlist (Tkinter: `ShortlistView`, shortlist_system.py)
| Tkinter feature | Web status |
|---|---|
| Category/priority filters, add/remove/edit-notes/change-priority, per-save JSON | ❌ No web screen |

### Player Profile (Tkinter: `PlayerProfileView`, ui_components.py — read-only, 6 tabs)
| Tkinter feature | Web status |
|---|---|
| Overview / Attributes (1-100 bars) / Personality / Statistics / Contract / Development | ❌ No web player card |
| Injury history, accolades, market value, scouting report, advanced analytics | ❌ |

### Recall picker (Tkinter: inline, main.py:21633 — non-modal)
| Tkinter feature | Web status |
|---|---|
| Triggers on dress-18+2 shortfall; ranked candidates; emergency fillers escape hatch | ❌ No web equivalent (blocker modal covers part) |

---

## P4 — League

### Schedule (Tkinter: `ScheduleView`, windows.py:10264)
| Tkinter feature | Web status |
|---|---|
| Month filter combobox + My Team / League tabs; Date/Away/Score/Home/Status columns, sortable headers | ❌ `/schedule` read-only list; no month filter, no tabs, no sorting |
| Watch Game: played → replay event_log in viewer; unplayed past → "Simulate & Watch / Not Now" ask_card; future → "Watch Preview" (never recorded) | ❌ No watch/replay flow |
| Simulate Game (past unplayed only, duplicate-guarded, writes result + team records) | ❌ |
| Double-click row = Watch; right-click menu (Watch/Simulate/Game Stats/Game Recap) | ❌ |
| Game Stats / Game Recap dialogs (`GameDetailWindow` tabs) | ❌ |
| Refresh | 🟡 Page reload only |

### Calendar (Tkinter: `CalendarView`, calendar_window.py:19)
| Tkinter feature | Web status |
|---|---|
| Month grid with event markers; legend; Prev/Today/Next | ❌ `/calendar` read-only stub (2 fetches) |
| Day Details pane: games, special events, deadline, All-Star, ceremonies, Olympic window; user result + form + season series + narrative | ❌ |
| Deadline-day action row: Trade Deadline Center / Trade Center / Market Analysis / Deadline News | ❌ |
| Click-through to Schedule / Roster / News screens | ❌ |

### News (Tkinter: `NewsView`, windows.py:12536)
| Tkinter feature | Web status |
|---|---|
| Category pills (All/Injuries/Trades/Signings/Development/Draft/Scores/League/Other), live search, two-pane reader | ❌ `/news` read-only stub; no filters/search |
| Live refresh while open (`populate_news`) | ❌ |

### Media Center (Tkinter: `MediaCenterView`, media_center_window.py:15)
| Tkinter feature | Web status |
|---|---|
| Engagement level setting (Disabled/Minimal/Standard/Full), auto-handle checkbox | ❌ No web screen |
| Pending media events: Handle/Skip/Auto-handle per event; Skip All | ❌ |
| Interview flow: 6 response styles, Preview Answers, Give Interview → journalist relations + storylines mutate | ❌ |
| Journalist relations table; Active storylines; Fines ledger | ❌ |

### Stats & Standings (Tkinter: `StatsStandingsView`, stats_standings_window.py:52)
| Tkinter feature | Web status |
|---|---|
| 6 main tabs: Standings / Team Analytics / Player Leaders / Analytics & Trends / Division Analysis / Divisions | ❌ `/standings` + `/stats` are flat read-only stubs |
| Standings views (League/Conf/Wildcard/Div leaders/Playoff picture), sort, advanced-metrics toggle | ❌ |
| Player Leaders sub-tabs: Scoring, Advanced, Goaltending, Breakout, Rookie, Award Races, Milestone Watch, NHL Records (5 sub-sub-tabs) | ❌ |
| Period + Season (regular/playoff) global filters; position filter; min-games spinbox; per-game toggle | ❌ |
| Right-click PlayerContextMenu on leader rows | ❌ |
| Export Data → CSV to `./exports/` | ❌ |
| Records = focus_tab='records' (not a separate screen) | — |

### Shot chart viewer (Tkinter: `ShotChartViewerView`, main.py:28566)
| Tkinter feature | Web status |
|---|---|
| Rink canvas with goal/save/block/miss markers; game/team/player modes | ❌ No web screen (view-only; entry point currently dead in Tkinter too) |

### AHL (Tkinter: `AHLLeagueView`, ahl_league_window.py:34)
| Tkinter feature | Web status |
|---|---|
| Tabs: Standings / Scores / Calder Cup bracket / Team (picker + roster + upcoming) / Prospects (scorers, cooking, goalies) | ❌ No web screen |
| Double-click standings row → that club's Team tab | ❌ |

### Playoffs (Tkinter: `PlayoffView`, playoff_system.py:1480)
| Tkinter feature | Web status |
|---|---|
| 2K-style canvas bracket, zoom-to-fit, projection banner pre-playoffs | ❌ `/playoffs` read-only stub |
| Generate Bracket / Simulate Round / Simulate All (threaded, cancelable, fallback saves) / Refresh | ❌ |
| Click series → SeriesDetailPopup (tale of the tape, game-by-game, splits, storylines, players to watch, road ahead) | ❌ |
| Conn Smythe decided at clinch (surfaces via awards/history, no dedicated panel) | ❌ |

### League History (Tkinter: `LeagueHistoryView`, main.py:28076)
| Tkinter feature | Web status |
|---|---|
| 7 tabs: Champions / Awards (season combo) / Career Leaders (category combo) / Hall of Fame / Advanced Stats (hover glossary) / Franchise Records / Season Reviews | ❌ `/history` read-only stub |

### Watch / Visualizer
| Tkinter feature | Web status |
|---|---|
| _TBD from core-loop audit (GAME_VIEWER)_ | 🔧 `/watch`: canvas + SSE but MOCK sim; real-GameSim wiring in progress |

---

## P5 — Systems (TRACK C)

All read-only; shared `trackc_common.py` shell (title + Refresh + scrollable body).

| Screen (Tkinter module) | What it surfaces | Web status |
|---|---|---|
| Ice-Time Deployment (`trackc_deployment_view.py`) | Live `deployment_policy`: coach style, tactical family, per-unit ice-share bars (F L1-4, D pairs, PP/PK), soft-cap governor rules, honored GM advice | ❌ |
| Roster Condition (`trackc_condition_view.py`) | Condition/fatigue: Fresh/Good/Worn/Gassed counts, worst-first table w/ injury-risk multipliers | ❌ |
| Discipline List (`trackc_discipline_view.py`) | DoPS ledger: active suspensions + season rap sheet by club | ❌ |
| Rivalry Dashboard (`trackc_rivalry_view.py`) | User rivalries (heat bands, kinds, grudge bars) + league's 8 hottest feuds | ❌ |
| Clutch Factors (`trackc_clutch_view.py`) | 7-factor clutch breakdown (qualitative, weights hidden) | ❌ |
| Circumstance Shifts (`trackc_circumstance_view.py`) | Tonight's circumstance baseline per player (energy/morale/home/rivalry) | ❌ |
| Fan Buzz (`trackc_fanbuzz_view.py`) | Fan favourites / on-the-rise / coach appeal | ❌ |

---

## Notes

- Web write path pattern: `POST /api/command {op, ...}` → Python command queue → drained on Tk mainloop → `_execute_command`. All game mutations must go through this; Flask never touches game state directly.
- Known fixed Oct 4 (post-audit): Continue method name, lines empty-lineup fallback, trade team abbreviations.
- The web port was built breadth-first against mock data; every screen needs live-data verification (the source of the Oct 4 tiles/lines/trades bugs).
