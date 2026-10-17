# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""NHL buyout math (tkinter-free engine module).

Extracted verbatim from ``windows.buyout_schedule`` (R18 bundle hygiene):
the PyInstaller bundle hard-excludes tkinter, so the native finances
screen can no longer import the helper through the Tk-only ``windows``
module -- importing it there raises ImportError and the bundle silently
shows empty buyout candidates. This module has no UI imports at all, so
it is safe to bundle and to import headless.

Behavior is byte-identical to the original: the differential test in
``tests/test_r18_bundle_hygiene.py`` asserts identical results against
``windows.buyout_schedule`` across the fixture matrix, including with
``tkinter`` blocked from import (simulating the bundle).
"""


def buyout_schedule(player):
    """NHL buyout math. Returns (total_cost, annual_hit, buyout_years, rows).

    rows: list of (season_offset, cap_hit, savings) for each buyout year.
    """
    salary = player.contract.salary
    years = player.contract.years_remaining
    if years <= 0 or salary <= 0:
        return 0, 0, 0, []
    fraction = 1 / 3 if player.age < 26 else 2 / 3
    total_cost = salary * years * fraction
    buyout_years = 2 * years
    annual = total_cost / buyout_years
    rows = []
    for i in range(1, buyout_years + 1):
        if i <= years:
            savings = salary - annual
        else:
            savings = -annual
        rows.append((i, annual, savings))
    return total_cost, annual, buyout_years, rows
