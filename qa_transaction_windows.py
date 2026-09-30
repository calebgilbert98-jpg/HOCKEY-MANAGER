"""qa_transaction_windows.py -- the NHL transaction calendar gates.

Sweeps check_window() across a full calendar year plus the engine
chokepoints (execute_trade holiday freeze, execute_offer_sheet window).
Headless: python3 qa_transaction_windows.py
"""
import sys
from datetime import date

sys.path.insert(0, ".")
import transaction_windows as tw

PASS = 0
FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        print(f"FAIL: {name}")


def allowed(action, d, ctx=None):
    ok, _why = tw.check_window(action, d, ctx=ctx)
    return ok


# -- 1. buyout window: June 15-30 -------------------------------------------
check("buyout blocked Jun 14", not allowed("buyout", date(2027, 6, 14)))
check("buyout open Jun 15", allowed("buyout", date(2027, 6, 15)))
check("buyout open Jun 30", allowed("buyout", date(2027, 6, 30)))
check("buyout blocked Jul 1", not allowed("buyout", date(2027, 7, 1)))
check("buyout blocked Oct", not allowed("buyout", date(2026, 10, 15)))
check("buyout blocked Feb", not allowed("buyout", date(2027, 2, 1)))

# -- 2. UFA signings: July 1+, never June ------------------------------------
check("ufa blocked all June", not allowed("sign_ufa", date(2027, 6, 20)))
check("ufa open Jul 1", allowed("sign_ufa", date(2027, 7, 1)))
check("ufa open mid-season", allowed("sign_ufa", date(2027, 1, 15)))
check("ufa open Oct", allowed("sign_ufa", date(2026, 10, 10)))

# -- 3. offer sheets: July 1 - Dec 1 -----------------------------------------
check("sheet blocked Jun 30", not allowed("offer_sheet", date(2027, 6, 30)))
check("sheet open Jul 1", allowed("offer_sheet", date(2027, 7, 1)))
check("sheet open Nov 30", allowed("offer_sheet", date(2027, 11, 30)))
check("sheet open Dec 1", allowed("offer_sheet", date(2027, 12, 1)))
check("sheet blocked Dec 2", not allowed("offer_sheet", date(2027, 12, 2)))
check("sheet blocked Mar", not allowed("offer_sheet", date(2027, 3, 1)))

# -- 4. holiday freeze: Dec 20-27 ---------------------------------------------
class FakeLeague:
    season_year = 2026
    playoff_bracket = None


_FL = FakeLeague()
check("trade open Dec 19",
      allowed("trade", date(2026, 12, 19),
              ctx={"league": _FL, "date_str": "2026-12-19"}))
check("trade frozen Dec 20",
      not allowed("trade", date(2026, 12, 20),
                  ctx={"league": _FL, "date_str": "2026-12-20"}))
check("trade frozen Dec 27",
      not allowed("trade", date(2026, 12, 27),
                  ctx={"league": _FL, "date_str": "2026-12-27"}))
check("trade open Dec 28",
      allowed("trade", date(2026, 12, 28),
              ctx={"league": _FL, "date_str": "2026-12-28"}))
# deadline freeze still intact through the unified gate
check("trade open Mar 7 (deadline day)",
      allowed("trade", date(2027, 3, 7),
              ctx={"league": _FL, "date_str": "2027-03-07"}))
check("trade frozen Mar 10 (post-deadline, season running)",
      not allowed("trade", date(2027, 3, 10),
                  ctx={"league": _FL, "date_str": "2027-03-10"}))

# -- 5. extensions: final year only -------------------------------------------
class FakeContract:
    def __init__(self, yrs):
        self.years_remaining = yrs


class FakePlayer:
    def __init__(self, yrs):
        self.contract = FakeContract(yrs)


check("extension blocked with 2 yrs left",
      not allowed("extension", date(2027, 1, 15),
                  ctx={"player": FakePlayer(2)}))
check("extension blocked with 3 yrs left",
      not allowed("extension", date(2026, 10, 15),
                  ctx={"player": FakePlayer(3)}))
check("extension open final year",
      allowed("extension", date(2026, 10, 15),
              ctx={"player": FakePlayer(1)}))
check("extension open expiring",
      allowed("extension", date(2027, 6, 20),
              ctx={"player": FakePlayer(0)}))

# -- 6. waivers: closed in June -----------------------------------------------
check("waiver claim blocked June",
      not allowed("waiver_claim", date(2027, 6, 10)))
check("waiver claim open July",
      allowed("waiver_claim", date(2027, 7, 5)))
check("waiver claim open Oct",
      allowed("waiver_claim", date(2026, 10, 20)))
check("waiver place blocked June",
      not allowed("waiver_place", date(2027, 6, 10)))
check("waiver place open Feb",
      allowed("waiver_place", date(2027, 2, 10)))

# -- 7. reasons are human-readable --------------------------------------------
_ok, _why = tw.check_window("buyout", date(2027, 3, 1))
check("buyout reason names the window",
      not _ok and "June 15-30" in _why)
_ok, _why = tw.check_window("sign_ufa", date(2027, 6, 1))
check("ufa reason names July 1", not _ok and "July 1" in _why)
_ok, _why = tw.check_window("extension", date(2027, 1, 1),
                            ctx={"player": FakePlayer(4)})
check("extension reason names final year",
      not _ok and "final year" in _why)

# -- 8. engine chokepoint: execute_trade blocked in holiday freeze ------------
import trade_engine as te


class FakeTeam:
    def __init__(self, name):
        self.team_name = name


_t = te.execute_trade(FakeTeam("A"), FakeTeam("B"), [], [],
                      date_str="2026-12-22", league=_FL)
check("execute_trade blocked Dec 22",
      "BLOCKED" in _t.summary and "freeze" in _t.summary)
_t = te.execute_trade(FakeTeam("A"), FakeTeam("B"), [], [],
                      date_str="2026-12-19", league=_FL)
check("execute_trade passes Dec 19 (past the gate)",
      "BLOCKED: The holiday" not in _t.summary)

# -- 9. engine chokepoint: execute_offer_sheet window --------------------------
import rfa_system as rfa


class FakeApp:
    current_date = date(2027, 6, 20)


_res = rfa.execute_offer_sheet(_FL, FakeTeam("A"), FakeTeam("B"),
                               FakePlayer(1), 1_000_000, 2,
                               app=FakeApp())
check("offer sheet blocked in June",
      _res.get("ok") is False and _res.get("reason") == "window_closed")


class FakeApp2:
    current_date = date(2027, 7, 10)


# July date passes the window gate (it will fail later on picks, which is
# fine -- the gate is what we're testing).
_res = rfa.execute_offer_sheet(_FL, FakeTeam("A"), FakeTeam("B"),
                               FakePlayer(1), 1_000_000, 2,
                               app=FakeApp2())
check("offer sheet passes gate in July",
      _res.get("reason") != "window_closed")

# -- 10. fail-open on garbage dates ----------------------------------------------
check("garbage date fails open (buyout)",
      allowed("buyout", "not-a-date"))
check("garbage date fails open (trade)",
      allowed("trade", None, ctx={"league": _FL}))

print(f"\n{PASS} passed, {FAIL} failed")
sys.exit(1 if FAIL else 0)
