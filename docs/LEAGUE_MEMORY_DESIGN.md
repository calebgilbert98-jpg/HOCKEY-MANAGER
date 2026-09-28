# League Memory — Design

## Problem
The league has no memory. Awards are calculated at season end
(`_calculate_season_awards`, main.py ~9665) and shown in a summary window, then
lost. The Cup champion is resolved from the playoff window and only used for
reputation bumps. Player records exist (`nhl_records.py`) but cover single
feats, not history. There is no answer to "who won the Cup in 2028?", "who has
the most career points?", or "show me every Hart winner."

## Target
A persistent league archive, written every season end and readable from a
League History screen:

1. **Season archive** — one record per season: year, Cup champion, runner-up,
   Presidents' Trophy winner, Conn Smythe, and every award winner
   (Hart, Art Ross, Rocket Richard, Vezina, Norris, Calder, Selke,
   Jack Adams), plus final standings snapshot (top 8 per conference is enough).
2. **Career leaderboards** — all-time points, goals, assists (skaters);
   wins, shutouts, save% (goalies, min 200 games). Combines active players'
   `career_*` totals (already accumulated on `Player`) with retired legends.
3. **Hall of Fame** — at retirement, players clearing a bar (1000+ points,
   500+ goals, 300+ goalie wins, or `icon_level == "icon"`) are snapshotted
   {name, teams, career line, cups, awards} into a permanent registry.
   Induction gets a news item ("X elected to the Hall of Fame").
4. **UI** — League History window, tabs: Champions | Awards | Career Leaders
   | Hall of Fame. Champions tab shows a banner list (year — champion def.
   runner-up, series score); Awards tab is a year × award grid; Leaders are
   sortable columns.

## Implementation plan
- New `league_history.py`: `LeagueHistory` class
  {`seasons: []`, `hall_of_fame: []`}, with `record_season(...)`,
  `induct(...)`, `career_leaders(players, category)`, save/load dict.
- Hook 1: `end_of_season` in main.py — after `_calculate_season_awards`
  returns and the champion is resolved, call
  `league_history.record_season(...)`. All inputs already exist at that
  point; this is purely additive.
- Hook 2: retirement flow — where the retirement news fires, call
  `league_history.induct(player)` if they clear the bar.
- Persistence: store on the career object, saved/loaded via the existing
  `save_load_system` path (same pattern as `youth_history` compat fields).
- UI: `LeagueHistoryWindow` (InGamePopup card, per the popup system —
  non-modal). Open from the League menu / nav.

## Engine boundary
Read-only with respect to gameplay: this records outcomes, never changes
them. Award *calculation* logic is untouched — we only persist its results.

## Backfill / old saves
Histories start at career creation; old saves begin their archive from the
current season forward. No fake backfill — an honest "history begins in
2026" note in the UI.

## QA
- Simulate 3 seasons headless: archive has 3 season records, champions match
  playoff winners, award winners match `_calculate_season_awards` output.
- Retire a scripted 1200-point player: appears in Hall of Fame + Leaders.
- Save/load round-trip: archive survives.
- Window opens as a card, all 4 tabs render, no tk errors.
