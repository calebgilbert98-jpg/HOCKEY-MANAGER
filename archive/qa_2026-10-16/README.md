# qa_2026-10-16 — script-style QA (NOT pytest tests)

These scripts were untracked one-off verification scripts (Oct 11-13, 2026).
They were moved out of `tests/` by R17 (2026-10-16) because they execute
their checks at import time and call `sys.exit()`, which kills pytest
collection with INTERNALERROR. They contain zero `test_` functions.

Run them directly, never via pytest:

    python3 archive/qa_2026-10-16/test_cap_paper_transaction.py
    python3 archive/qa_2026-10-16/test_cap_paper_transaction_integration.py
    python3 archive/qa_2026-10-16/test_floor_guard_margin.py   # slow: full fantasy draft

What each verifies:
- test_cap_paper_transaction.py — cap auto-fix Step 3 (demote+recall paper
  transactions) acceptance + adversarial checks against auto_resolve.py.
- test_cap_paper_transaction_integration.py — same path with REAL
  game_classes Player/Team objects (was PASS at archival).
- test_floor_guard_margin.py — salary floor guard: full headless setup +
  fantasy draft, then every NHL club must be above the cap floor.

If the cap logic they cover needs ongoing regression protection, convert the
checks into proper pytest test_ functions under tests/ instead of
resurrecting these scripts.
