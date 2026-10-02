# Roster limits — design (true NHL, Chris's rulings 2026-10-01)

## Rules
- **23-man active roster max**: day gate for user AND AI. Emergency fillers
  exempt (NHL emergency-recall exemption). Unsigned players (no active
  contract) don't count — they're not under contract.
- **50 SPC limit**: ADVISORY ONLY (Chris's call 2026-10-02) -- a daily
  league-office FYI, never a blocker. The only hard pre-game gates are
  cap compliance + the 23-man active roster. Same exemptions.
- **Minimums**: the NHL has no roster minimum. Enforced at the dressed
  lineup: 18 skaters + 2 goalies must be available (not injured, not
  season-ineligible). Outbound moves (demote / waive / trade) that would
  break the ability to dress a lineup are blocked with a plain reason.
- **Deadlock (Chris's ruling)**: over-cap AND under-minimum resolves via
  **emergency fillers** — league-minimum, scrub-overall (≤60) players the
  club can always summon, even over the cap. NHL-plausible (emergency
  recall / league exception): exempt from the 23-man count, cap-exempt at
  the day gate, clearly marked EMERGENCY, user+AI identical.
- **Rights (true NHL)**: RFA rights retained indefinitely — never
  relinquished. Qualified-but-unsigned RFA past Dec 1: ineligible for the
  rest of that season (can't sign, can't dress). Unsigned UFAs (expired
  contracts): off the roster AND off the cap at the July pass — the
  structural fix for Sim A's $31.36M phantom overage. Drafted-prospect
  rights: existing `_rollover_draft_rights` windows (CHL 2yr → re-enter;
  NCAA/Europe 4yr → UFA) verified, not rebuilt.

## Anti-gaming (emergency fillers)
- Overall capped at 60 by construction (attributes 55–60, F/F potential).
- Development systems skip them explicitly.
- Cannot be traded (execute_trade rejects), extended, or waived.
- Auto-released when no longer needed + at the July pass.
- Summon capped at the exact shortfall — no stockpiling.

## Files
- `roster_limits.py` (new): all logic.
- Wiring (additive, guarded): `main.py` (day gates, cap exclusion, daily
  tick, demote/waive guards, contract-offer refusal), `trade_engine.py`
  (asset + dress-minimum validation), `rfa_system.py` (July UFA release,
  _sign_player guard), `player_development_system.py` (dev skip),
  `ai_team_management.py` (AI compliance sweep).
- `qa_roster_limits.py` (new).
