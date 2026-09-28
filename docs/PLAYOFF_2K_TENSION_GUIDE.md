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

## 2. Series intensity in the series-detail popup (`season_intensity.py`)

**2026-09-28 change (Muck's call): the league-wide gauge was REMOVED from the
PlayoffView header.** Intensity now lives per-series, in the series-detail
popup (`build_series_detail_content` → `_detail_intensity`), where it reflects
what the in-game INTENSITY meter will show when those two clubs meet.

`series_intensity(ledger, team_a, team_b, window_days=14)` — same incident
kinds, weights, bands, and colors as the in-game meter, scoped to the pair via
`ledger.between(a, b, kinds=["incident"])` (falls back to a manual event scan
when `between` is unavailable). Same formula: `min(100, weight × 1.5)`.
For an unstarted/projected series it's the hype forecast; for a live series it
includes what's already happened. No heat → CALM 0. Never raises.

`hype_line(label, a_abbr, b_abbr)` — grudge-week-style hype copy per band:
BOILING → "🔥 Grudge series — … the building will be sold out and shaking.
This one matters."; CHIPPY → "bad blood is simmering … Expect fireworks.";
HEATING → "something's brewing"; CALM → "All business … for now."

The popup section shows a "Series intensity" gold header, a 200×132 gauge
canvas (`draw_gauge(..., title="SERIES INTENSITY")` — title is now a
parameter, default `"LEAGUE TENSION"`), the hype line in the band color, and
a "Driving it: …" line when ≥ 25. It renders on **both** the projected
(tale-of-the-tape) and live paths.

`season_intensity(ledger, ...)` (league-wide) still exists and is tested, but
nothing in the UI calls it anymore — it's a utility awaiting a future home.

## 3. Big-moment log in the series-detail popup

`_detail_big_moments()` adds a **"Big moments"** section after Storylines,
before Players to watch — the series' defining on-ice moments in game order,
derived from real per-game facts by `_series_big_moments(series)`:

- ⚡ overtime winner (`g["ot"]`)
- 🧱 shutout (loser scores 0)
- 💥 statement win (margin ≥ 4; shutout takes precedence)
- 🧱 `{goalie} stood on his head` (`g["goalie_steal"]`)

No games yet → "No games yet — the moments will write themselves."
Bad-blood incidents stay in Storylines (narrative); the log is the on-ice
highlight reel. (The splits table's `BigW` column = biggest win margin,
unchanged.)

## 4. Bad blood: injury → rivalry → ledger → storyline

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

`qa_playoff_2k.py` (39/39): builds a real 32-team league through the actual
`generate_playoff_bracket`/`advance_to_next_round` paths to a live SCF; asserts
mirrored card placement, navy canvas, ticker text, projection mode (8 R1
cards); asserts **no** league gauge on the bracket header; asserts
`series_intensity` is pair-scoped (60.0 CHIPPY on a seeded feud, unrelated
pair CALM 0, None ledger safe), `hype_line` copy per band; asserts
`_series_big_moments` extracts OT/shutout/statement/steal from crafted games
and is empty for an unplayed series; asserts the real `SeriesDetailPopup`
renders headless with the Series intensity section, Big moments section, hype
line, and a drawn gauge canvas; asserts the projected popup carries the
intensity hype too; asserts `_apply_hit_injury` sets injury attrs (4–10 games for a dirty hit), creates the
rivalry incident, and bridges to the ledger; asserts the 🩸 storyline
surfaces. One deliberate note: `_is_eastern_team` keys on **division**
(`Atlantic`/`Metropolitan`) — fake leagues must use real division names.

## 5. Zoom-to-fit bracket (2026-09-28)

Muck: the full bracket must fit on screen with **no left/right scrolling**,
like the visualizer's ice surface. `_display_bracket` now computes
`_bracket_scale()` = canvas width / natural tree width (2448px at natural
size), clamped to [0.45, 1.0], and scales card width, column gaps, pads,
row heights, fonts, and the Cup emblem proportionally. Vertical scroll
remains for short windows. A debounced `<Configure>` binding (`_refit_bracket`,
250ms) redraws only when the factor moves >0.02, so resizing the window
re-fits live.

**Winner contrast fix** (same screen): `_winner_text_color` — winner rows
render in gold *unless* the club's accent is equally light (BOS/PIT gold,
LA silver), where contrast(gold, accent) < 2.0 falls back to the accent's
designed on-color (black on gold). Fixes gold-on-gold unreadable winners.

**Tight cards** (2026-09-28): card frames now get an explicit height of
`2 * row_h + 18` — exactly two team rows plus padding, no dead space below
the second team. (Root cause of the old slack: `pack_propagate(False)` with
no height froze the frame at CTk's 200px default.) The tree compresses
vertically and everything fits the screen at once. QA asserts every embedded
card's requested height stays within budget.

## 6. Popup card background fix (2026-09-28)

`InGamePopup.__new__` created its tk.Frame with no `bg`, so it took the
platform default light grey — showing through any `fg_color="transparent"`
CTk child (the series-detail popup rendered white/unreadable). The frame
now gets `bg=_BG` (`#14161b`, the card body color) at construction, fixing
all current and future popup subclasses in one place.

## QA (continued)

`qa_bracket_fit.py` (13/13): full 15-series tree to a live SCF at 1600x900;
asserts scale 0.633 (< 1.0), canvas bbox fits canvas width (no h-overflow),
15 card windows drawn; asserts winner contrast (BOS/PIT/LA gold+silver
accents -> black text, TOR navy -> gold); asserts the click journey
(`_open_series_detail` -> real popup card, frame bg `#14161b`, ticker follows
the series); resizes to 1920x1080, waits out the debounce, asserts the scale
grows (0.633 -> 0.763) with still no overflow. Screenshots:
`~/workspace/ahl_shots/bracket_fit_{1600,popup,1920}.png`.

## 7. Playoff tale of the tape (2026-09-28)

Muck: the series popup needed a tale of the tape based on the teams'
**playoff** runs so far (the old tape was regular-season only, and only on
projected series). New `_detail_playoff_tape` sits in the live path right
after Series intensity: a side-by-side table — Record, Goals/game,
Allowed/game, OT losses, Goalie (SV% + shutouts), Top scorer — computed by
`_playoff_team_line` walking every series in the bracket (real game_results),
goalie from per-player `playoff_stats` (most-used: saves/shots_against/
shutouts), skater from `_top_playoff_scorers`. Bracket=None degrades to
dashes, never raises.

`qa_series_popup.py` (24/24): full SCF at 2-2 with crafted games (OT winner,
shutout + goalie steal, statement win) and ledger heat (brawl +
controversial_hit -> 82 BOILING); asserts all eight sections present, tape
rows carry real numbers (records, SV%, shutouts, top scorer), all four big-
moment kinds fire, bad-blood storyline + grudge hype line render, players-to-
watch rows populate. Screenshot: `~/workspace/ahl_shots/series_popup_full.png`
(full stitched popup, header through Road ahead).

## 8. Arena-render restyle (2026-09-28)

Muck's reference: dark brushed-metal arena backdrop, neon-glow connectors,
glassy dark cards with team-color glow. The series-insights popup is
untouched.

- `_bracket_bg_photo(w, h)`: PIL radial glow (`BRACKET_BG_GLOW` center ->
  `BRACKET_BG_EDGE` edge) + faint vertical brushed streaks, rendered at
  quarter res and upscaled, cached per quantized size. Drawn last in
  `_display_bracket` with `tag_lower("bracket_bg")`. Canvas bg is now the
  vignette edge so overshoot blends in.
- `_series_card`: glassy `#12161F` body, border = top-seed team accent
  (gold once decided), dark rows with a team-color accent bar, near-white
  text, series-wins badge right-aligned on every card. Card stashes
  `_bracket_accent` for the halo.
- Connectors: same elbow path in 3 layers -- halo `#0E3A5C` (7px), neon
  cyan `#2FB9E8` (3.5px), core `#C9F1FF` (1.5px), widths scaled by zoom.
- Two-layer darkened-accent halo rectangles behind each card.
- Single centered "STANLEY CUP FINAL" title above the Final (replaces the
  trophy + STANLEY CUP / PLAYOFFS trio).
- QA: `qa_playoff_2k.py` 47/47 (8 new restyle assertions), `qa_bracket_fit.py`
  14/14, `qa_bracket_tree.py` 67/67. Screenshots
  `~/workspace/ahl_shots/bracket_2k_{west,center,east}.png`.

## 9. MP host-only gate + click warnings + fallback autosave (2026-09-28)

- `_is_mp_client()` / `_mp_guard(action)`: in an MP session only the host
  may Generate Bracket / Simulate Round / Simulate All Playoffs. Clients get
  an in-game "Host only" notice and are blocked; the three buttons render
  disabled for clients at build time, handlers re-check.
- The click warning (`sim_progress.confirm_heavy_sim`) and the fallback
  autosave (`sim_progress.create_fallback_save`, `saves/fallback/`) already
  gated both sims and were verified intact -- the warning names the freeze
  and the fallback save; the bulk/headless path skips the dialog by design.
- QA: `qa_playoff_mpguard.py` 12/12 (client blocked x3, buttons disabled,
  host + single-player pass through to the normal warning path).
