# Playoff / AHL Stats Split — Guide for calebgilbert98

Three asks from Muck, one build: (1) the league Stats & Standings screen now
splits **Regular Season / Playoffs** everywhere it shows stats; (2) **AHL
numbers never bleed into NHL stats** — they got their own screen and their own
ledger; (3) the **Conn Smythe** follows real-life criteria, including the
McDavid historic-run exception.

## 1. Season toggle (Regular Season / Playoffs)

`stats_standings_window.py` — a "Season:" combo in the title card
(`self.season_type`, defaults to "Regular Season"). Everything stat-bearing on
the screen re-reads from the matching ledger:

- **Team Analytics** (`add_advanced_stats_data`): playoff mode shows one
  honest table — GP/W/L/GF/GA/+/−/Playoff Result per playoff team, built
  read-only from `bracket.playoff_series[].game_results` via
  `get_team_playoff_stats()`. No new stored data; non-playoff teams don't
  appear (they played zero playoff games).
- **Player Leaders** (`load_all_players_data`): the active ledger is
  `player.playoff_stats` in playoff mode via the `_stat_ledger(player)` /
  `_pstat(player, attr)` helpers. Scoring sorts by playoff points;
  Goaltending sorts by (wins, SV%) — the Smythe lens; Advanced Stats becomes
  a playoff rate table (P/GP, G/GP) because the season xG model doesn't apply
  to the playoff sample (GSAx/HDSV% show "—"). RS-only tabs (Breakout,
  Rookie Leaders, Award Races, Milestone Watch, NHL Records) auto-park on
  Scoring Leaders when you flip to Playoffs. The Min Games filter genuinely
  applies in playoff mode (a 1-game 3-point night must not top a P/GP board).
- **Analytics Dashboard** (`_fill_metric_cards`): playoff metric cards
  (Playoff Goals / Playoff Games / OT Games / Champion). Also fixed the AHL
  bleed Muck flagged: "Total Goals" summed `team.roster + team.ahl_roster` —
  now `team.roster` only.
- **Standings stay the final regular-season table in both modes** (no fake
  playoff standings).

Old saves: `_stat_ledger` falls back to `stats` when `playoff_stats` is
missing.

## 2. AHL system — separate ledger, separate screen

**No AHL game simulation exists in the codebase** — verified before building.
Per Muck ("don't save as much league data for the ahl"), the AHL is a
lightweight generated stat ledger, not a sim:

- NEW `ahl_system.py`: `ensure_ahl_stats(player)` attaches a `PlayerStats`
  as `player.ahl_stats`. `simulate_ahl_day(league)` runs once per simmed NHL
  day (Oct 1–Apr 20, skipped while NHL playoffs are live): each farm player
  has P(game)≈0.39 (~72-game season), skater P/GP scales with overall
  (floor 0.05 so grinders aren't all zeros), goalies get a 45% start chance
  with SV% ~.880+(ovr−55)×.0012. Readers: `top_skaters`, `top_goalies`,
  `cooking` (best P/GP, min GP). Cost measured ~1.5ms/day for 800 players.
- **No-bleed by construction, not by filtering:** `ahl_stats` is a third
  ledger beside `stats` / `playoff_stats`. Callups/senddowns freeze the other
  ledger. The NHL screen never reads `ahl_stats`; the AHL screen never reads
  `stats`.
- Wiring: `ahl_stats` dataclass field on `Player` (`game_classes.py`,
  old-save-safe via getattr like `playoff_stats`); reset beside the other two
  at season rollover; save/load serialize+restore mirrored on `playoff_stats`
  (`save_load_system.py`); daily hook at the end of `_process_daily_maintenance`
  (`main.py`).
- NEW `ahl_stats_window.py` (`AHLStatsView`, nav pill **AHL** next to Stats,
  `open_ahl_stats_window`): Top Scorers, Who's Cooking (P/GP min 10 GP), Top
  Goalies (min 5 GP), with an All Farms / My Farm Team filter. Reads ONLY
  `team.ahl_roster` + `ahl_stats`.

## 3. Conn Smythe criteria

`playoff_system._decide_conn_smythe` now implements the real-life decision
tree (see `docs/CONN_SMYTHE_COACHES_GUIDE.md` for the full write-up):

1. Default: the Cup champion's playoff scoring leader (points, goals tiebreak).
2. Goalie exception: champion's goalie with SV% ≥ .935 and 12+ wins
   (Vasilevskiy '21, Quick '12, Giguere '03).
3. **Historic-run exception (new):** a skater on the losing side wins only if
   ≥ 35 playoff points AND ≥ 1.5× the champion's best skater total
   (McDavid '24: 42 vs ~24; Leach '76). The 35-point floor means this fires
   about once a decade — as in real life.
4. Known limitation: narrative exceptions the numbers can't capture
   (Crosby '16, Hedman '20, Crozier '66, Hextall '87) — documented, not
   simulated.

The winner still banks into the trophy case immediately and feeds the
offseason reputation rollover (Smythe +12 → `player.reputation` →
`league_perception`) unchanged.

## QA

`qa_stats_playoffs_ahl_smythe.py` — 40/40 headless (DISPLAY=:99):
AHL no-bleed (12), Smythe incl. both exceptions + two near-misses (5),
playoff team table from a fake bracket (5), ledger helpers + old-save
fallback (4), real-view GUI smoke incl. the full toggle refresh path (14).

## What NOT to touch

- `playoff_stats` fold (`_fold_playoff_stats`) and the `stats` ledger — the
  toggle only changes which ledger is *read*.
- The `_decide_conn_smythe` thresholds — they're the real-life criteria;
  retune only with a real-life case to cite.
- `ahl_system`'s date gate — farm stats must not accumulate during the NHL
  playoffs or before opening night.
- caleb's `advanced_metrics` — playoff mode deliberately doesn't call it
  (no xG model for the playoff sample), it doesn't need one.
