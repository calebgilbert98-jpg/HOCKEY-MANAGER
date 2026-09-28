"""QA: real-life draft eligibility age max + re-entry restrictions."""
import random, sys
from types import SimpleNamespace

from draft_generator import is_draft_eligible, age_on_sept15

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print(f"FAIL: {name}")

# --- age_on_sept15 ---
check("age 18.0 boundary", age_on_sept15("2006-09-15", 2024) == 18)
check("age 17 day after", age_on_sept15("2006-09-16", 2024) == 17)
check("age 20 boundary", age_on_sept15("2003-09-16", 2024) == 20)
check("age 21 boundary", age_on_sept15("2003-09-15", 2024) == 21)
check("malformed -> None", age_on_sept15("nonsense", 2024) is None)

# --- is_draft_eligible: younger edge ---
check("NA turns 18 ON Sept 15 eligible",
      is_draft_eligible("2006-09-15", "Canada", 2024))
check("NA turns 18 day AFTER Sept 15 ineligible",
      not is_draft_eligible("2006-09-16", "Canada", 2024))
check("Euro turns 18 ON Sept 15 eligible",
      is_draft_eligible("2006-09-15", "Sweden", 2024))

# --- is_draft_eligible: NA age max 20 ---
check("NA 20 on Sept 15 eligible",
      is_draft_eligible("2003-09-16", "Canada", 2024))
check("NA 21 on Sept 15 INELIGIBLE (ages out -> UFA)",
      not is_draft_eligible("2003-09-15", "Canada", 2024))
check("USA 21 on Sept 15 INELIGIBLE",
      not is_draft_eligible("2002-06-01", "USA", 2024))

# --- is_draft_eligible: Europeans no max ---
check("Euro age 24 eligible", is_draft_eligible("2000-01-01", "Sweden", 2024))
check("Euro age 28 eligible", is_draft_eligible("1996-05-05", "Russia", 2024))
check("Euro age 30 eligible", is_draft_eligible("1994-03-03", "Finland", 2024))

# --- re-entry age rule: undrafted re-enters iff <= 20 on Sept 15 ---
def would_reenter(birthdate, nationality, draft_year):
    a = age_on_sept15(birthdate, draft_year)
    return (a is not None and a <= 20
            and is_draft_eligible(birthdate, nationality, draft_year))

check("undrafted NA 19 re-enters", would_reenter("2005-04-01", "Canada", 2024))
check("undrafted NA 20 re-enters (last kick)",
      would_reenter("2003-12-01", "Canada", 2024))
check("undrafted NA 21 -> UFA, no re-entry",
      not would_reenter("2003-01-01", "Canada", 2024))
check("undrafted Euro 19 re-enters",
      would_reenter("2005-04-01", "Sweden", 2024))
check("undrafted Euro 23 -> FA, no re-entry (pool rule)",
      not would_reenter("2001-04-01", "Sweden", 2024))

# --- original-team re-draft ban logic (DraftView._redraft_banned) ---
from windows import DraftView
team_a = SimpleNamespace(team_name="Sharks")
team_b = SimpleNamespace(team_name="Bruins")
reentry = SimpleNamespace(draft_reentry_from="Sharks")
fresh = SimpleNamespace(draft_reentry_from="")
plain = SimpleNamespace()
check("original team BANNED from re-drafting own re-entry",
      DraftView._redraft_banned(None, team_a, reentry) is True)
check("other team MAY draft the re-entry",
      DraftView._redraft_banned(None, team_b, reentry) is False)
check("fresh prospect not banned",
      DraftView._redraft_banned(None, team_a, fresh) is False)
check("missing attr not banned",
      DraftView._redraft_banned(None, team_a, plain) is False)

# --- ban is one-draft only: cleared flag restores eligibility ---
reentry.draft_reentry_from = ""
check("ban lifts after the re-entry draft",
      DraftView._redraft_banned(None, team_a, reentry) is False)

# --- generated classes: NA prospects never 21+, deterministic ---
random.seed(20260928)
from draft_generator import generate_draft_class
cls = generate_draft_class(num_prospects=224, draft_year=2027)
bad = [p for p in cls
       if p.nationality in ("Canada", "USA")
       and age_on_sept15(p.birth_date, 2027) not in (18, 19, 20)]
check("no NA prospect outside 18-20 in generated class", not bad)
inelig = [p for p in cls
          if not is_draft_eligible(p.birth_date, p.nationality, 2027)]
check("every generated prospect eligible", not inelig)
euros_old = [p for p in cls
             if p.nationality not in ("Canada", "USA")
             and (age_on_sept15(p.birth_date, 2027) or 0) >= 21]
check("European overagers present (no max age)", len(euros_old) >= 1)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
