# State of the Game — Puck Dynasty

**Built from scratch 2026-10-02 ~19:35 EDT.** Eight read-only system audits against Muck's 7 core design parameters. No sugar-coating.

---

## Executive Summary

The game is further along than any single session's memory suggests — and further from beta than the commit log implies.

**The good:** The scoring engine's shared decision layer is real (one finishing composite, byte-verified identical across engines). The trade engine's core math, UFA bidding, and RFA machinery are genuinely well-built and consistent with Muck's directives. The narrative ledger is the best-connected part of the game — story systems actually talk to each other. Staff, coaching, deployment, and AI GMs are implemented, not aspirational. The UI clears the Eastside/FM bar on the player card, navigation, dashboard, inbox, and box score.

**The bad:** Ten beta-blockers, most of them silent. The full GameSim acceptance **failed** — every GameSim game on main sims ~11% under the scoring target because the OT-parity luck fix erased the s3 re-anchor. Top prospects are bust-proof (a surge floor guarantees +24 overall in the worst situation imaginable), directly contradicting Muck's written bust directive. The fan and board narrative pipelines — the most user-facing story addition of the last two days — are completely dark due to a wrong-attribute bug. Franchise pricing is dead code despite memory claiming it's live. Coach personality is dead in both engines due to a 1-100 vs 1-20 scale bug. The GameSim block path ignores the positioning split Muck ordered. Treeview lists (including the inbox message list) don't scroll with the wheel.

**The pattern:** the *designs* are good; the *wiring* keeps failing at the last inch. Dead code that claims to be live (`franchise_price_mult`, `shot_fate`'s block arm, `scout_adjusted_value`), comments that lie (D11 "ONE decision", quick_sim's energy-pool claims, the "1-20 scale" docstring), and QA that tests functions instead of systems (the "87 vs 59" bust verification never runs through the real pipeline). Memory itself is stale in at least four places (L2, L3, Performance column, L4).

**What beta needs:** the ten blockers fixed, the luck-fix merged and re-validated with a full 82-game GameSim season, and Muck's calls on ~25 design questions — most importantly bust-rate targets, PP% direction, fatigue unification, and whether AdvGS's synthetic stats are acceptable long-term.

---

## Parameter-by-Parameter Assessment

### 1. Separation by probability, not caps — MOSTLY HOLDING, TWO VIOLATIONS

**Holding:** No hard performance caps were found in the scoring engine. Separation runs through the personal grade ceiling (within the protected envelope) plus additive scenario windows with diminishing returns. The trade engine has no hard caps either.

**Violation 1 — the development surge floor is a guarantee, not a probability** (game_classes.py:1384). `gain = max(gain, 2.0 * development_speed)` means an A+ teen gains ≥3.0 overall/year *in the worst situation imaginable*. Combined with the A+ env damp ("generational talent develops regardless") and grade-production circularity, 117/120 simulated A+ prospects hit 85+ regardless of organization quality. This is the opposite of separation by probability — it's separation by label.

**Violation 2 — the top-end gradient is flat** (development audit). A+ good-org mean 89.4 vs A good-org mean 88.4 — one point separates generational from elite. Stars are not otherworldly *relative to each other*.

### 2. One decision, two fidelities — VIOLATED IN AT LEAST 10 PLACES

**Holding:** `mesh_system.finishing_rating()` (13-member blend) is one table, byte-verified identical across engines. Grade rolls, schemed factors, line chemistry, and the goalie skill model are shared.

**Violations:**
- E4 personal floor is dead code on GameSim — D29's league clamp runs first, so the floor branch can never fire (mesh_system.py:2073-2077 vs simulation.py:6047-6080). quick_sim does it right.
- AdvGS line rotation ignores all coach deployment weights (talent/form/morale/relationships/direction) — GameSim rotates weighted, AdvGS picks least-fatigued (quick_sim.py:1612-1666 vs shift_engine.py:211-246). Star TOI compresses in quick-sim.
- Two fatigue pools, two curves: GameSim drains its own `player_fatigue` dict (floor 0.90); AdvGS drains `condition_system.game_energy` (floor 0.40). Comments claiming unification are false.
- Shootout: edge passed only on AdvGS; shooter pools differ (forwards-only vs full roster); sudden-death tiebreak is a fair coin flip on GameSim but home-auto-win on AdvGS (competitive integrity).
- OT 3v3 volume: 1.25× (GameSim) vs 2.50× (AdvGS), with a comment claiming 2.00×.
- Injuries: GameSim hardcodes a 4-type table; AdvGS uses the shared `injury_data.roll_general_injury`.
- Penalties: AdvGS only does 2-minute minors live; majors/fights are synthesized post-game.
- Goalie development: yearly engine uses skater peak ages for goalies; monthly engine shifts +2 years. Two goalie theories.
- Shot blocking: D11's "ONE decision" `shot_fate()` has zero production callers — GameSim uses bespoke `_check_shot_blocking`, quick_sim uses `approx_shot_fate`. Only the miss half was consolidated.
- Trade Block screen runs a legacy $-denominated valuation with hard tier thresholds (overall ≥85 / <75) — the exact logic Muck rejected.

### 3. Sim-style parity — BROKEN ON THE SCORING NUMBER

**The failure:** Full 82-game GameSim acceptance FAILED 2026-10-02. Smoke: **2.291 GPG vs 2.58 target** — the OT-parity luck fix placed the mean-one luck factor *after* binding ceilings (D29 + personal), clipping luck's ×1.3 upside while keeping its ×0.7 downside. Every GameSim game on main is ~11% under target. A `luck-fix` branch exists (moves luck into the xG chain) but is **unmerged and unvalidated** — and the scoring audit disputes its diagnosis (the 0.98 cap it blames essentially never binds; the real clipping is at the D29/personal ceilings, which the branch's new position doesn't escape either).

**Also:** scenario narrative moments are GameSim-only (quick-sim loses up to 2 post-game headlines per game); AdvGS defensive stats (hits/blocks/faceoffs) are synthetic post-game rolls, not live events; the watched-vs-quick parity check on the day-advance path has never been run; the visualizer runs on the global `random` module so watched games aren't seed-reproducible (distributions hold, reproducibility doesn't).

**Holding:** the visualizer never writes sim state — it renders the event stream from a background-thread sim. Presentation-only, as required.

### 4. Attribute-vs-attribute — BROADLY WIRED, WITH DEAD ZONES

**Wired:** 13 finishing attributes, 5 situational goalie weight profiles, net-front forward-vs-(defense+goalie), matchup matrix, IQ-gated relief, fit-gated linemate lifts. The positioning split (offensive/defensive) is engine-wired in the finishing and defensive composites.

**Dead or bypassed:**
- `consistency` — exists on every player, scout-visible, read by neither engine. EHM's signature variance attribute does nothing.
- `adaptability` (players) — zero reads anywhere. Display filler.
- `defense` / `conditioning` in the monthly development engine — not Player fields; 2 of 11 dev slots silently skipped league-wide every month.
- quick_sim event selection: `if creativity > 15` etc. on the 1-100 scale (live range 66–87) — always true, so four "attribute-driven" multipliers are constants.
- Faceoff composite — never used on the faceoff path; GameSim uses bespoke `player.faceoffs × 1.0`.
- Physicality composite — never read by the hit path (GameSim uses a 3-attribute subset).
- Goalie archetypes — all four map to the same save composite; no in-sim differentiation.
- 14 of 18 scenario composites defined but never called.
- **GameSim's block path reads the legacy single `positioning`** (simulation.py:4851, 10209), ignoring the split Muck ordered — and the positioning-split unicorn mechanic never runs on the live database (only draftees get it).

### 5. NHL-real targets — SCORING TARGET CURRENTLY MISSED

| Target | Status |
|---|---|
| GPG ~2.58 | **2.291 measured — FAIL** (luck bug; fix unmerged) |
| Art Ross ~137 | Unmeasured since the break |
| 8–10× 50G, max ~83 | Unmeasured since the break |
| D-share ~18.8%, none in top-10 | Unmeasured since the break |
| A/G ~1.534 | ~1.53–1.58 in code (unmeasured live) |
| OT rate ~22% | 24.5% AdvGS (smoke) — tuning question open |
| PP% ~21% | **Structurally capped at mid-teens** — both engines' PP factors land before the grade ceilings, which clip PP chances at the same ≤0.18 envelope as EV. 21% needs a PP-specific ceiling (touches protected levers) or permanent acceptance of mid-teens. Muck accepted mid-teens "for now." |

Also: `balance_validate.py`'s own bands contradict the accepted target (team GPG band 2.70–3.60 fails the 2.58 target by construction), and `advanced_metrics.py` fabricates PP% as `21.0 + (talent-70)*0.45` in the UI — masking the real mid-teens number.

### 6. Story-driven ecosystem — BEST-CONNECTED, BUT MUTE IN TWO PLACES

**The spine is real.** `narrative_ledger.py` (append-only, indexed, season-stamped, persisted) feeds grudge-week callbacks, arena bad-blood, calendar hype tags, season-review BAD BLOOD reports, and playoff memory. `headlines.deliver()` → news feed + inbox with a 4/day cap; a League News reader exists. Chemistry Watch routes user-team→inbox, others→news-only (his precedent). Pressers have teeth (morale ±5, board effects, fan nudges ×2.5, persisted history). DOPS pipeline heats future meetings. Draft stories, AHL narratives, coach checkins, accolades all wired.

**Beta-blocker: fan and board narratives are dead on arrival.** `fan_narratives.py:406, 555` read `game_manager.inbox` — the GUI app has no `.inbox` attribute (inboxes live on teams). The messages are silently dropped while the function returns success and updates its cooldown. The weekly fan-narrative and board-narrative pipelines built 2026-10-02 **never reach the user**. One-line fix each.

**Also:** Bucket-5 sentiment reactions (trades, signings, firings) are dead code — zero callers. Inbox routing is inconsistent (only chemistry uses the restricted routing; everything else spams every inbox). Scenario moments are GameSim-only. The 4/day headline cap is split-brained (pressers and bundles bypass it). No player-level cross-season arcs (draft stories die at the draft; the ledger's player index has no callback consumer).

### 7. Eastside/FM bar — CLEARS IT, WITH ONE DAILY PAPERCUT

**Clears:** Player card is FM24-shaped (6 tabs, archetype pill, contract/rights strips, career totals, playoff lines, scout fog-of-war). Navigation: 6 dropdowns + Inbox + Advance + date/countdown, zero dead menu items. Dashboard is EHM-dense. Inbox is a real email client with inline interactive renderers. Box score has 4 tabs including the Lines tab with combined ratings. Visualizer has broadcast feel (score bug, win probability, intensity meter, full-rink camera). Right-click cards are universal. Tactics, practice, training camp, scouting/fog-of-war, shortlist, player comparison, depth chart, staff management, GM relationships, dressing room, AHL hub all exist.

**Beta-blocker (papercut): `ttk.Treeview` lists are wheel-dead everywhere** — including the inbox message list, the highest-traffic screen. The scroll router only handles Canvases. Wheeling over the message list does nothing or misroutes to the wrong pane.

**Missing vs FM:** inbox free-text search; xG on the box score (engine computes it, box score doesn't show it); conditional menu items (Trade Deadline/Draft Day) are hidden rather than grayed; visualizer has no replay scrubber.

---

## System-by-System Deep Dive

### Scoring engine
The chain (shot volume → grade roll → conversion → goalie → goal) is genuinely attribute-driven and shared where it counts. Protected levers (grade clamps A 0.10–0.18 / B 0.04–0.12 / C 0.015–0.09) are intact. But: the E4 floor ordering bug silently flattens the finishing gradient on the watched path; the shot-volume inversion persists across archetypes (a 65-finishing sniper takes the same volume as a 95-finishing playmaker); the schemed-against "zero-sum budget" is documented but discarded at both call sites (three unbudgeted relief paths); and the GPG number is broken until the luck fix lands and is re-tuned honestly.

### Trade / FA / contracts
Core negotiation math is Muck-compliant (granular 1-point overall, performance ±25% wired on both sim paths, D42 anti-fleece holding). UFA consideration genuinely works (3–7 day windows, AI bidding, `contract_appeal()` resolution, frontrunner headlines). RFA is complete (sign-and-trade order fixed, offer-sheet no-trade enforced at both gates). GM reputation has teeth (greed mult, FA/staff appeal deltas, board drift, decay, UI). **But:** franchise pricing is dead code (franchise stars move at face value — beta-blocker); user untouchables don't exist despite the comment promising them; `scout_adjusted_value` is QA-only; the Trade Block screen runs legacy tier-threshold math. Memory's "L6/L8 live" and "L2 dead" are both wrong.

### Development / prospects / draft
The *design* is genuinely good (hidden truth vs scouted belief, NHLe translation, pedigree cushions, gem seeds, arc variance, goalie-aware monthly engine). The *numbers* defeat it: the surge floor + A+ env damp + production circularity make top prospects bust-proof (117/120 A+ hit 85+ in any org). NHL-level potential movement is cosmetic (displayed grade drops, true cap unchanged — rushing kids is never punished). The signature top-up can push overall above the potential cap. The yearly engine has no goalie curve. Ice time, injuries, and macro coaching don't affect development at all. Potential is shown raw and sortable in the UI — no scouting fog. Long-term talent inflation is unvalidated (only-upward ratchets + zero busts).

### Attributes / archetypes
The finishing composite is verified byte-identical across engines — the shared layer holds. Generation floors (80+ elite signatures, 85+ generational at 23+, no floor for prospects) are coherent. Archetype classification is sane and self-maintaining. **But:** the GameSim block path ignores the positioning split; D11's block consolidation never happened (false docstring); the split mechanic is inert on the live veteran database; `consistency` and player `adaptability` are dead; the trade AI doesn't scout composites (half of Muck's valuation directive); 14 of 18 scenarios are unwired; goalie archetypes are flavor-only.

### Sim parity
Shared cores are genuinely shared (finishing, goalie model, grades, chemistry, shootout core). The visualizer is clean presentation. **But:** the luck asymmetry broke scoring; fatigue is two systems wearing one name (different pools, different curves, false unification comments); shootout has four divergences (edge, pools, tiebreak integrity, downstream visibility); OT volume is 1.25× vs 2.50×; injuries and penalties are two copies each; AdvGS defensive stats are synthetic post-game rolls; a third Poisson sim path exists outside the parity contract entirely; AdvGS rotation ignores deployment weights (star TOI compresses).

### Story systems
Best-connected part of the game — ledger, headlines, atmosphere, calendar, season reviews genuinely interoperate, and cross-season memory mechanically works. **But:** the fan/board voice pipelines are silently dead (beta-blocker); sentiment reactions to trades/signings/firings are unwired; inbox routing wasn't generalized from the chemistry precedent; scenario moments are GameSim-only; no player-level story arcs cross seasons.

### UI/UX
Clears the Eastside/FM bar on every major surface. **But:** Treeview wheel-dead (beta-blocker papercut on the inbox); no inbox search; no xG on the box score; hidden (not grayed) conditional menu items.

### World systems (staff / coaching / AI GMs / AHL)
Staff exist and mostly matter (coach quality → skid adjustments, assistants → U26 development, practice → drill ratings, scouts → accuracy, medical → recovery). Deployment ecosystem is genuinely implemented (talent 0.90 + performance 0.10, vibe clamp, ~30-min governor, fatigue → injury risk). AI GMs run the world (weekly FA/trades/rosters/extensions, AI-vs-AI trades execute). AHL is coherent. **But:** the coach scale bug kills all personality differentiation in both engines (beta-blocker — 200/200 coaches classify "demanding"); AdvGS ignores deployment weights (beta-blocker parity); PP/PK/video/conditioning coach roles are flavor-only; user can't set AHL lines.

---

## Gap Analysis

### Beta-blockers (fix before beta, no design call needed)
1. **Luck asymmetry** — merge a validated luck fix, re-tune the xG base with luck in final position, re-run full 82-game GameSim acceptance. Nothing downstream is valid until GPG is back at ~2.58.
2. **E4 floor ordering** — reconcile D29 clamp vs personal floor on GameSim (or confirm D29's flat floor is the intent).
3. **Franchise pricing dead code** — wire `franchise_price_mult()` into valuation or cut it.
4. **Bust rate ~zero** — the surge floor (game_classes.py:1384) must go or be re-gated; A+ env damp reconsidered.
5. **Fan/board narrative delivery** — route `fan_narratives.py:406, 555` to the real inbox. One line each.
6. **Coach scale bug** — normalize 1-100 staff attrs at the mesh_system read sites (mesh_system.py:2217, 2238).
7. **AdvGS rotation** — mirror deployment weights or get Muck's acceptance of TOI compression.
8. **GameSim block path** — use `defensive_positioning()` (simulation.py:4851, 10209); wire or re-scope D11's block arm.
9. **Positioning split on live DB** — roll it in `create_player`'s live path, not just draftees.
10. **Treeview wheel scrolling** — inbox message list first.

### Needs Muck's design call
- **Bust-rate target:** what hit rate at the top of the draft? Can a bad org ruin a prospect, or just slow him?
- **PP%:** mid-teens permanent, or a PP-specific ceiling to chase 21%?
- **Luck vs the envelope:** can a lucky day exceed protected ceilings, or does the envelope stay absolute (requiring base re-tune)?
- **Shot volume:** widen the talent gate or accept cross-archetype inversion as "windows"?
- **OT:** accept 24.5% or tune sigma for 22%? One OT mechanism or two?
- **Fatigue:** unify onto one pool+curve, or bless the two shapes as calibrated?
- **AdvGS synthetic stats:** acceptable long-term or invest in live recording?
- **Tier quantization:** kill `tier_proxy_overall` everywhere or keep as fog-parity compromise?
- **User untouchables:** roster-level absolute flag? Scope?
- **Scout tips in trades:** wire `scout_adjusted_value` into negotiation?
- **Ice time → development:** EHM model in or out for beta?
- **AHL stash:** 1.25 dev multiplier + ELC slide + no cap hit — intended or exploit?
- **Potential visibility:** scouting fog or transparent for beta?
- **Coaching macro weight:** yearly-curve influence or monthly-texture only?
- **Consistency attribute:** wire into variance or cut?
- **Trade valuation depth:** should signature composites carry value premiums?
- **Positioning split economics:** feed overall_rating or stay engine-only?
- **Scenario catalog:** wire the 14 dead scenarios or prune?
- **Goalie archetypes:** in-sim differentiation or flavor?
- **Inbox vs League News default:** generalize the chemistry routing everywhere?
- **Presser cadence:** every game or notable games only?
- **Draft arcs:** rookie-year callbacks or draft-week only?
- **Headline cap:** 4/day still right?
- **Staff flavor roles:** mechanics for PP/PK/video/conditioning coaches or org depth?
- **Fan sentiment:** discrete per-game nudges or weekly drift?
- **Relationships clamp:** is ±3% "heavy" enough?
- **AHL lines:** user-settable or auto?
- **L5 neutral point:** awaiting his calibration call (untouched per instruction).
- **Lightweight Poisson path:** hold to parity or background-only?
- **Visualizer audio:** text templates or TTS voice?
- **xG on box score:** hub-only or visible?
- **Inbox search:** add or filters-only?

### Polish (no design call needed)
- Remove dead `_check_shot_miss`; fix false docstrings (D11, energy pool, "1-20 scale", tier-proxy claims); pin the 1.5 scenario cap in QA; fix `balance_validate` bands vs s3 target; stop fabricating PP% in analytics UI; dead `TrainingProgram` cruft + latent TypeError; dead `defense`/`conditioning` dev slots; AdvGS `creativity > 15` thresholds; shootout edge/pools/period-5 on GameSim; visualizer RNG seeding per thread; dashboard full-rebuild cost; box score period shot bars; replay scrubber; gray (not hide) conditional menu items.

### Stale memory corrected by this audit
- **L2 is LIVE** (diminishing returns, notifications, trend all implemented) — "still dead" is wrong.
- **L3 is FIXED** — schemed gate reads 90.0 (scenario_composites.py:367).
- **Performance column is DONE** — last-10-games average, QA 18/18.
- **L4 is WIRED** — weekly drift to results baseline + discrete trade/signing/coaching/presser nudges; only per-game win/loss nudges are absent (design choice).
- **"L6/L8 live" is half-wrong** — franchise pricing is dead code.

---

## Open Design Questions for Muck

Consolidated above under "Needs Muck's design call" — 30 items. The five that matter most:

1. **Busts:** what should the top-of-draft hit rate be, and can bad organizations ruin prospects?
2. **Scoring:** is the luck envelope absolute (re-tune the base) or permeable (lucky days exceed ceilings)?
3. **PP%:** mid-teens forever or chase 21%?
4. **Parity depth:** unify fatigue/rotation/shootout/injuries, or bless per-engine shapes as calibrated?
5. **Development inputs:** does ice time drive development in your game?

---

*Method: 8 read-only audits (scoring, parity, attributes, trades, development, story, UI, world), each against the 7 parameters, with file:line evidence. Empirical probes where it mattered (200-coach scale test, 120-prospect bust sim, finishing-composite byte check). No code changed.*
