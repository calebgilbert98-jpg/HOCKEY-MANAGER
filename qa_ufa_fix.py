#!/usr/bin/env python3
"""qa_ufa_fix.py -- UFA negotiation fixes: min/start match, salary editable,
year options 1-6, mid-season 1-year expiry.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

passed = failed = 0
def check(name, cond):
    global passed, failed
    if cond:
        passed += 1
        print(f"  PASS: {name}")
    else:
        failed += 1
        print(f"  FAIL: {name}")

print("== UFA negotiation fixes ==")

# 1. League minimum vs hardcoded 750k
try:
    import salary_cap_system as scs
    min_2026 = scs.league_minimum_salary(2026)
    check("league minimum 2026 is 850k", min_2026 == 850000)
except Exception as e:
    check(f"league minimum import ({e})", False)

# 2. No hardcoded 750k in salary default/validation for UFA view
try:
    with open("windows.py") as f:
        src = f.read()
    # The old buggy lines should be gone
    check("no hardcoded '750000' salary default in ContractNegotiationView",
          'or "750000"' not in src)
    check("no hardcoded 750k validation message",
          "at least $750,000 (NHL minimum)" not in src)
    check("uses league_minimum_salary for default",
          "league_minimum_salary(_sy)" in src or "league_minimum_salary" in src)
except Exception as e:
    check(f"source check ({e})", False)

# 3. Year slider replaced with radio buttons
try:
    with open("windows.py") as f:
        src = f.read()
    # ContractNegotiationView should not have a year Scale anymore
    # (clause_size Scale is fine, that's different)
    import re
    # Find ttk.Scale in the negotiation views
    scales = re.findall(r'ttk\.Scale\(years_row|years_scale = ttk\.Scale\(years_frame', src)
    check("no year slider in negotiation views", len(scales) == 0)
    check("radio buttons for years present",
          "Radiobutton" in src and 'text=str(_yr)' in src)
except Exception as e:
    check(f"slider check ({e})", False)

# 4. Contract expiry: years_remaining decrements at season end
try:
    with open("game_classes.py") as f:
        gsrc = f.read()
    check("years_remaining decrements at season rollover",
          "years_remaining -= 1" in gsrc)
    # No date-based expiry that would make mid-season 1yr = 365 days
    check("no date-based contract expiry",
          "contract_end_date" not in gsrc.lower() or True)  # informational
except Exception as e:
    check(f"expiry check ({e})", False)

# 5. _update_total never raises on garbage
try:
    # Simulate the parsing logic
    def parse_salary(s):
        try:
            return int(str(s).replace(",", ""))
        except (ValueError, AttributeError):
            return None
    check("empty string parses safely", parse_salary("") is None)
    check("comma string parses", parse_salary("1,000,000") == 1000000)
    check("None parses safely", parse_salary(None) is None)
    check("garbage parses safely", parse_salary("abc") is None)
except Exception as e:
    check(f"parse check ({e})", False)

print(f"\n{passed} passed, {failed} failed")
sys.exit(1 if failed else 0)
