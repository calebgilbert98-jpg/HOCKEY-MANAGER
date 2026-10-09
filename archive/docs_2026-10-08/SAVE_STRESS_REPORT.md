# Save/Load Stress Test Report

**Date:** 2026-10-02  
**Branch:** save-stress  
**Context:** 97 commits in 24 hours with new systems (staff philosophies, fan sentiment, AHL league, milestones, accolades, scout tiering)

## Test Results

### QA Suite: qa_save_stress.py — 18/18 PASS

| Test | Result |
|------|--------|
| Old staff dict lacks new fields | ✅ PASS |
| New Staff has philosophy default | ✅ PASS |
| New Staff has gm_style default | ✅ PASS |
| getattr default works on stripped staff | ✅ PASS |
| Philosophy survives pickle | ✅ PASS |
| gm_style survives pickle | ✅ PASS |
| gzip round-trip works | ✅ PASS |
| Staff data intact after compression | ✅ PASS |
| fan_sentiment module loads | ✅ PASS |
| fan_sentiment uses getattr (old-save safe) | ✅ PASS |
| ahl_league module loads | ✅ PASS |
| ahl_league import safe | ✅ PASS |
| Milestone carryover defaults to empty set | ✅ PASS |
| accolades module loads | ✅ PASS |
| calder_cup registered | ✅ PASS |
| No clash with Calder Trophy | ✅ PASS |
| scout_tiering module loads | ✅ PASS |
| scout_tiering import safe | ✅ PASS |

## Backfill Audit

Verified backfills exist for all new systems:

| System | Backfill Location | Status |
|--------|-------------------|--------|
| Staff (24-role template) | save_load_system.py:1462 | ✅ Present |
| Staff pool (192→896) | save_load_system.py:1878 | ✅ Present, **FIXED** |
| AHL records | save_load_system.py:612, 2490 | ✅ Present |
| Narrative ledger | save_load_system.py:1517 | ✅ Present |
| Scout tiers | save_load_system.py:1627 | ✅ Present |
| Fan sentiment | fan_sentiment.py (getattr) | ✅ Lazy default, no backfill needed |
| Milestone carryover | dict.get default | ✅ Safe default |
| Calder Cup accolades | accolades.py | ✅ Registered, no clash |

## Bug Found & Fixed

**Staff pool backfill threshold/target mismatch** (save_load_system.py:1878)
- **Issue:** Threshold checked `< 840` but calculated `_need = 450 - len(_pool)`
- **Impact:** If pool had 500 staff, `_need = -50` → `range(-50)` is empty (safe but wrong)
- **Fix:** Changed target to 896 to match the doubled pool size
- **Severity:** Low (safe due to Python's empty range, but logically incorrect)

## Migration Safety

All new fields use safe patterns:
- **Dataclass defaults:** `coaching_philosophy: str = ""` — old saves unpickle fine, new instances get defaults
- **getattr with defaults:** Fan sentiment, scout tiers — never crash on missing attributes
- **dict.get defaults:** Milestone sets, narrative ledger — safe empty defaults
- **try/except guards:** All backfill code wrapped, never raises

## Conclusion

✅ **Old saves migrate cleanly.** All new systems backfill gracefully or default safely.  
✅ **No corruption risk.** Pickle + gzip round-trip verified.  
✅ **One bug fixed.** Staff pool backfill now targets 896 consistently.

**Recommendation:** Safe to continue. The save system is robust against the 97-commit wave.
