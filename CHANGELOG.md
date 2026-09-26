# Changelog

All notable changes to Puck Dynasty are documented here. Dates are in
America/Halifax time.

## [0.9.0] - 2026-09-26

### Simulation engine
- Realistic shot distribution: recent-shooter rotation and flattened
  shoot-tendency weighting so shot generation spreads across the lineup
  instead of funneling to one star (top-shooter share 0.358 -> 0.306 over
  100-game samples; hat-trick rate 0.112 -> 0.089).
- Rebound recipients now use a weighted lottery instead of always going
  to the highest anticipation/awareness player.
- Offensive-zone base shot chance raised 0.36 -> 0.40 to preserve
  shot/scoring volume after the distribution changes.
- Line rotations unified: a clock-phase flip now forces a stored-unit
  refresh (previously a desynced random timer), so every part of the sim
  agrees on who is on the ice.
- Possession transfers to the same-position player on the fresh line when
  lines change; a benched player can no longer carry the puck.
- Broadcast milestones (presentation only): hat-trick watch/banner and
  shutout-bid banner with lower-thirds and feed messages.

### Broadcast visualizer
- Tactical positioning engine: EHM-style formation slots (offensive-zone
  spread, breakout support lanes, neutral-zone 1-2-2, defensive-zone
  wedge-plus-one, 2-1-2 forecheck, PP umbrella, PK box, weak-side
  integrity, limited loose-puck pursuit, teammate separation).
- Authoritative on-ice sync: the visualizer's dots now follow the sim's
  real on-ice units (line rotation, PP/PK, icing, line matching) instead
  of an independent, desynchronized rotation. Measured: puck carrier
  among the dots went from 74% wrong to 0% wrong.
- Puck-carrier ring: subtle pulsing halo so the eye tracks the play,
  with a fallback that slots an undotted carrier into his position's dot.
- Faceoff ceremony (4.2s real-time: whistle, skate to dot, set, drop),
  pause-safe and blocking; slower broadcast pace (GAME_RATE 12 -> 8).
- TV score bug, win-probability meter, puck-follow camera with toggle,
  animated lower-thirds, period broadcast cards, goal celebrations with
  slow-mo replays and deferred victory laps, skate marks, hit bursts,
  goalie lunges, Three Stars, shot trails and shot map, clickable dots.

### UI
- All legacy windows modernized to the charcoal/teal theme
  (#0e0e11 / #00ceb8); emoji stripped from UI chrome.
- Faces v5 (11 hairstyles, 6 facial hair styles, age effects).
- Live sim upgrades: on-ice lines, momentum, Next Big Moment, period
  summaries, richer commentary, live goalie stats.
- QoL: Space/Ctrl+S/Esc/? shortcuts, styled confirms, tooltips,
  sortable tables, empty states, lines-editor face thumbnails.
- Settings window restyled (dark UI, custom tab bar, teal checkboxes);
  Simulation tab scrollable; scoring-level setting (Low/Medium/High).

## [0.8.x] - 2026-09-25 and earlier

- Full 1,312-game season validation (32x82, W+L+OTL==GP, GF==GA,
  no 3-in-a-row, sane goalie SV%).
- Scoring-level setting calibrated via paired 50-game batches
  (Low ~5.5, Medium ~6.0, High 7+ goals/game).
- Ratings display on 1-100 scale; player generator attribute fix.
- Lines editor with canonical chemistry and archetype display.
- Settings crash fix; top-bar menus verified; trade center reachable.
- EHM roster import framework committed (shelved; not wired to real
  ECK databases yet).
