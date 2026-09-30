"""transaction_windows.py -- the NHL transaction calendar as one rulebook.

Every roster move in Puck Dynasty is gated by the real league calendar.
This module is the single source of truth; the views and engines call
check_window() at their chokepoints and surface the returned reason when
an action is blocked. Dates follow the current NHL CBA:

  Buyouts ......... June 15 - June 30 (first window; the one the game models)
  UFA signings .... July 1 onward (no signings from the market in June)
  Offer sheets .... July 1 - December 1 (and never once arbitration is filed)
  Trades .......... frozen after the deadline (40 days before the last
                    regular-season game, per the CBA) until the Cup is
                    awarded, plus the holiday roster freeze (Dec 20-27)
  Extensions ...... final contract year only (years_remaining <= 1)
  Waivers ......... not during the June dead month

Design notes:
- Gates fail OPEN when the date can't be parsed (QA harnesses, legacy
  callers) -- a gate that can't tell what day it is must not block.
- The trade-deadline freeze itself lives in trade_engine._trade_freeze_active
  (it needs league/season-year context); this module adds the holiday
  freeze and owns every other window.
- All checks are pure functions of (action, date, ctx) so the QA suite
  can sweep the whole calendar year without a GUI.
"""

from datetime import date as _date

# -- window definitions (month, day) -----------------------------------------
BUYOUT_OPEN = (6, 15)
BUYOUT_CLOSE = (6, 30)
UFA_OPEN = (7, 1)
OFFER_SHEET_OPEN = (7, 1)
OFFER_SHEET_CLOSE = (12, 1)
HOLIDAY_FREEZE_OPEN = (12, 20)
HOLIDAY_FREEZE_CLOSE = (12, 27)

ACTIONS = ("buyout", "sign_ufa", "offer_sheet", "trade", "extension",
           "waiver_claim", "waiver_place")


def _parse(d):
    """date from a date/datetime/ISO string; None when unparseable."""
    try:
        if isinstance(d, _date):
            return d
        s = str(d or "")[:10]
        return _date.fromisoformat(s)
    except Exception:
        return None


def _md_in_window(month, day, open_md, close_md):
    """True when (month, day) falls inside the [open, close] window."""
    cur, o, c = (month, day), open_md, close_md
    if o <= c:
        return o <= cur <= c
    return cur >= o or cur <= c  # wraps new year


def buyout_window(d):
    """Real NHL: the first buyout window runs June 15-30."""
    gd = _parse(d)
    if gd is None:
        return True  # fail open
    return _md_in_window(gd.month, gd.day, BUYOUT_OPEN, BUYOUT_CLOSE)


def ufa_signing_open(d):
    """UFA market opens July 1. June is the dead month: last season's
    deals haven't expired yet and next season's can't be signed."""
    gd = _parse(d)
    if gd is None:
        return True
    return gd.month != 6


def offer_sheet_window(d):
    """Offer sheets: July 1 through December 1. (Arbitration-filed players
    are excluded separately in rfa_system.)"""
    gd = _parse(d)
    if gd is None:
        return True
    return _md_in_window(gd.month, gd.day, OFFER_SHEET_OPEN, OFFER_SHEET_CLOSE)


def holiday_freeze_active(d):
    """The holiday roster freeze: no trades Dec 20-27."""
    gd = _parse(d)
    if gd is None:
        return False
    return _md_in_window(gd.month, gd.day, HOLIDAY_FREEZE_OPEN,
                         HOLIDAY_FREEZE_CLOSE)


def waivers_open(d):
    """The waiver wire doesn't run in the June dead month."""
    gd = _parse(d)
    if gd is None:
        return True
    return gd.month != 6


def extension_eligible(player):
    """Real NHL: a player may sign an extension only in the final year of
    his deal (from the July 1 that opens that final league year)."""
    try:
        yrs = int(getattr(getattr(player, "contract", None),
                          "years_remaining", 1) or 0)
    except Exception:
        return True  # fail open
    return yrs <= 1


def window_opens(action):
    """Human-readable next opening for a gated action (for UI messaging)."""
    return {
        "buyout": "June 15-30",
        "sign_ufa": "July 1",
        "offer_sheet": "July 1 - December 1",
        "trade": "when the freeze lifts",
        "extension": "the final year of the player's contract",
        "waiver_claim": "outside June",
        "waiver_place": "outside June",
    }.get(action, "")


def check_window(action, d, ctx=None):
    """(allowed, reason). The one gate every chokepoint calls.

    ctx is an optional dict for action-specific context:
      trade       -> {"league": league, "date_str": str} (deadline freeze
                     needs the league; the holiday freeze needs the date)
      extension   -> {"player": player}
    """
    ctx = ctx or {}
    if action == "buyout":
        if buyout_window(d):
            return True, ""
        return False, ("Buyouts are only permitted during the buyout window "
                        "(June 15-30).")
    if action == "sign_ufa":
        if ufa_signing_open(d):
            return True, ""
        return False, ("The UFA market opens July 1 -- no free-agent "
                        "signings in June.")
    if action == "offer_sheet":
        if offer_sheet_window(d):
            return True, ""
        return False, ("Offer sheets can only be signed July 1 - "
                        "December 1.")
    if action == "trade":
        if holiday_freeze_active(d):
            return False, ("The holiday roster freeze is in effect "
                            "(Dec 20-27) -- no trades.")
        # The deadline freeze keeps its own context (league/season year).
        try:
            from trade_engine import _trade_freeze_active as _fz
            _frozen, _why = _fz(ctx.get("date_str", d),
                                ctx.get("league", None))
            if _frozen:
                return False, _why
        except Exception:
            pass
        return True, ""
    if action == "extension":
        if extension_eligible(ctx.get("player")):
            return True, ""
        return False, ("Extensions can only be signed in the final year of "
                        "a player's contract.")
    if action in ("waiver_claim", "waiver_place"):
        if waivers_open(d):
            return True, ""
        return False, "The waiver wire is closed in June."
    return True, ""
