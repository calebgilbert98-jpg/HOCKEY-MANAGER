# 2K-Style Playoff Tree + League Tension Gauge + Bad Blood — Guide

**What:** The playoff bracket was restyled to match Muck's NBA 2K26 "Playoff Tree"
reference exactly (mirrored conferences, team-colored 2K cards, Cup emblem,
bottom ticker), and the season-long **LEAGUE TENSION** gauge was added to the
Playoffs header — the in-game INTENSITY meter's big brother. Bad blood now
flows from real in-game injuries into the gauge, the rivalry system, the
narrative ledger, and series storylines.

**Files:** `playoff_system.py` (tree restyle, gauge widget, bad-blood
storylines), `season_intensity.py` (new: league heat aggregation + gauge
drawing), `simulation.py` (`_apply_hit_injury` hook). QA: `qa_playoff_2k.py`
(23/23). Screenshots: `~/workspace/ahl_shots/bracket_2k_{west,center,east}.png`.

---

## 1. The 2K-style tree (all in `playoff_system.py`)

**Mirrored layout.** `BRACKET_COLUMNS` puts West R1/R2/CF down the *left* edge
growing inward, East R1/R2/CF down the *right* edge growing inward, and the
Stanley Cup Final dead center:

```python
BRACKET_COLUMNS = [
    ("wild_card", "Western"), ("division_semifinals", "Western"),
    ("division_finals", "Western"), ("stanley_cup_final", None),
    ("division_finals", "Eastern"), ("division_semifinals", "Eastern"),
    ("wild_card", "Eastern"),
]
```

`BRACKET_LAYOUT_ORDER = (0, 6, 1, 5, 2, 4, 3)` places both R1 columns first,
then R2s, then CFs, then the SCF last — feeders must exist before the center
column can average their y positions.

**2K cards** (`_series_card`, rewritten): each card is a small CTkFrame with two
team-colored rows (`team_identity_system.accent_for_team`, WCAG-safe text via
`text_color_for_team`). Losers of decided series dim to the hover color.
Higher seed on top. The series-wins badge sits at the **outer** edge — left for
West, right for East (`mirror` flag). Decided series get a gold border.
Per-game mini-rows were dropped from cards (still in the detail popup) for the
reference's clean look.

**Connectors:** white elbows (`#DCE3EB`, 2px), same routing as before. Canvas
background is navy `#0A1428`. **No round headers** — the reference has none
(the old QA expectation was updated to assert this). The 🏆 "STANLEY CUP /
PLAYOFFS" emblem floats above the Final; the champion banner below stays.

**Ticker bar:** a navy bar pinned under the canvas shows the selected series —
`ROUND 1: Boston Bruins vs Toronto Maple Leafs — BOS leads 3-2`, or
`🔮 PROJECTION — …` in projection mode. Updates on card click (`_open_series_detail`
→ `_update_ticker`), defaults to the top West R1 series on draw.

Click behavior is unchanged: cards still open `SeriesDetailPopup` (games,
splits, storylines, players, road ahead).

## 2. LEAGUE TENSION gauge (`season_intensity.py`)

`season_intensity(ledger, window_days=14)` aggregates ledger `"incident"` events
with `incident_kind` in `{star_injured, player_injured, controversial_hit,
brawl}` over the trailing window. Weights come from the ledger event
(`star_injured` 25, `brawl` 15, etc.); value = `min(100, total_weight × 1.5)`.
Bands and colors mirror the in-game meter exactly: **BOILING** `#ff6b6b`
(75–100), **CHIPPY** `#ff9f5c` (50–75), **HEATING** `#ffd166` (25–50),
**CALM** `#7bc96f` (0–25). Returns the value plus the top-4 driving incidents.

The PlayoffView header carries a 210×150 gauge canvas + a driver line
("Driven by: …"), drawn by `draw_gauge()` (semicircular canvas gauge: four
band arcs, needle, numeric + mood readout). Refreshed on view open and every
`refresh_bracket()`. Never raises — all wrapped.

## 3. Bad blood: injury → rivalry → ledger → storyline

`GameSim._apply_hit_injury()` (in `simulation.py`, called from `_record_hit_stats`
when `HitResult.INJURY_CAUSED`): the victim now gets a **real injury** —
`is_injured=True`, `injury_type`, `games_remaining_injured` (1–4 clean,
2–6 big, 4–10 dirty; same attribute convention as quick-sim so downstream
systems read it), `injured_today=True`. It then calls
`reputation_system.record_game_incident()` (`star_injured` if overall ≥ 85,
else `player_injured`), which creates/escalates the team–team rivalry record
**and** bridges to the narrative ledger — feeding the in-game tension meter,
headlines, and now the season gauge.

`_series_storylines()` leads with bad-blood lines from
`ledger.between(a, b, kinds=["incident"])`:

> 🩸 Bad blood: Rival Slugger injured Star Victim with a charging hit — expect
> this series to have an edge.

These run **before** the no-games early return, so projected series get them
too. Fallback: rivalry-record incidents when the ledger is empty.

## What NOT to touch

- `HitResult.INJURY_CAUSED` call sites and hit-resolution math — the hook is
  purely additive (`_record_hit_stats` flow unchanged).
- `record_game_incident`'s weight map in `reputation_system.py` — the gauge
  reads those weights; retune there, not in `season_intensity.py`.
- The 14-day window default — changing it changes what "league tension" means
  mid-season vs. playoffs; discuss with Muck first.

## QA

`qa_playoff_2k.py` (23/23): builds a real 32-team league through the actual
`generate_playoff_bracket`/`advance_to_next_round` paths to a live SCF; asserts
mirrored card placement, navy canvas, ticker text, projection mode (8 R1
cards); asserts gauge value/mood/drivers from seeded ledger incidents; asserts
`_apply_hit_injury` sets injury attrs (4–10 games for a dirty hit), creates the
rivalry incident, and bridges to the ledger; asserts the 🩸 storyline
surfaces. One deliberate note: `_is_eastern_team` keys on **division**
(`Atlantic`/`Metropolitan`) — fake leagues must use real division names.
