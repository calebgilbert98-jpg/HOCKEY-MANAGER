# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Staff contract renewals (D5 follow-up): expiry -> offer -> pool.

When tick_staff_contracts (game_classes) finds an expired deal on the
USER's club, it holds the staffer employed and stashes the offer on
league.staff_renewal_offers instead of releasing him. This module:

  * queues the interactive inbox message (action_type="staff_renewal")
    carrying the re-sign (1/2/3-year) / let-walk decision -- inbox, never
    a popout, per Muck's standing rule;
  * applies one decision (apply_renewal_decision): re-sign on a fresh
    deal (same role, same salary), or walk to the free-agent pool --
    with the head-coach in-house promote fallback when a bench boss
    walks, same as the automatic path;
  * resolves undecided offers (resolve_pending_renewals): the ignore
    path. Called at the season's first game day and as a backstop for
    headless rollovers -- undecided staff walk to the pool.

AI clubs never see this module: they auto-decide inside the tick via
game_classes.ai_renew_staff_decision.

Headless-safe: no UI imports. The inbox renderer lives in
inbox_window._render_staff_renewal; the app entry point is
HockeyManagerGUI.apply_staff_renewal_decision (main.py).
"""
import game_classes as gc
from game_classes import EmailMessage

# Renewal terms: same role, same salary, fresh deal. The user picks the
# length in the inbox message (2 years is the recommended default, shown
# as the primary button); AI re-signs are 3 years for a head coach and
# 2 years for everyone else (see tick_staff_contracts).
RENEWAL_YEAR_OPTIONS = (1, 2, 3)
RENEWAL_DEFAULT_YEARS = 2


def _offer_cards(league, user_team):
    """Plain-dict cards for the user's pending renewal offers."""
    cards = []
    for o in list(getattr(league, "staff_renewal_offers", None) or []):
        try:
            if (o or {}).get("team") is not user_team:
                continue
            s = (o or {}).get("staff")
            if s is None:
                continue
            nm = (f"{getattr(s, 'first_name', '')} "
                  f"{getattr(s, 'last_name', '')}").strip() or "A staffer"
            cards.append({
                "staff_id": str(getattr(s, "id", "")),
                "name": nm,
                "role": getattr(getattr(s, "role", None),
                                "value", "staffer"),
                "age": int(getattr(s, "age", 0) or 0),
                "reputation": int(getattr(s, "career_reputation", 0) or 0),
                "years_with_team": int(
                    getattr(s, "years_with_team", 0) or 0),
                "salary": int(getattr(s, "salary", 0) or 0),
                "assignment": str(getattr(s, "assignment", "nhl") or "nhl"),
            })
        except Exception:
            continue
    # Head coach first, then by career standing.
    cards.sort(key=lambda c: (c["role"] != "Head Coach",
                              -c["reputation"]))
    return cards


def queue_user_renewal_message(league, user_team, app):
    """Queue the interactive renewal inbox message for the user's pending
    offers. Returns the number of offers queued (0 when there are none).
    Never raises."""
    try:
        if user_team is None or app is None:
            return 0
        cards = _offer_cards(league, user_team)
        if not cards:
            return 0
        n = len(cards)
        lines = [
            (f"{n} of your staff {'is' if n == 1 else 'are'} out of "
             f"contract."),
            "",
            "Re-sign them below on a fresh deal (same role, same salary) "
            "or let them walk. Unsigned staff join the free-agent pool, "
            "where any club can hire them -- including your rivals.",
            "",
            "Undecided staff walk when the new season starts.",
        ]
        for c in cards:
            ahl = " (AHL)" if c["assignment"] != "nhl" else ""
            lines.append(
                f"• {c['name']} — {c['role']}{ahl}, age {c['age']}, "
                f"career standing {c['reputation']}/100, "
                f"${c['salary']:,}/yr.")
        msg = EmailMessage(
            sender="Assistant GM",
            sender_type="Staff",
            subject=(f"Staff renewals — {n} contract"
                     f"{'s' if n != 1 else ''} expired"),
            content="\n".join(lines),
            category="Contracts",
            is_important=True,
            requires_response=True,
            action_type="staff_renewal",
            action_data={"offers": cards,
                         "decided": {},
                         "team_id": getattr(user_team, "id", None)},
        )
        try:
            _sender = getattr(app, "send_email_to_team", None)
            if callable(_sender):
                _sender(user_team, msg)
            else:
                app.send_email_to_user(msg)
        except Exception:
            return 0
        return n
    except Exception:
        return 0


def apply_renewal_decision(league, staff_id, years):
    """Apply one renewal decision for a pending offer.

    years in (1, 2, 3): re-sign on a fresh deal (same role, same
    salary). years=None (or anything else): the staffer walks to the
    free-agent pool, with the head-coach promote fallback when a bench
    boss walks. Returns (ok, news_lines). Never raises.
    """
    try:
        box = getattr(league, "staff_renewal_offers", None) or []
        target = None
        for o in list(box):
            try:
                s = (o or {}).get("staff")
                if (s is not None
                        and str(getattr(s, "id", "")) == str(staff_id)):
                    target = o
                    break
            except Exception:
                continue
        if target is None:
            return False, []
        team = target.get("team")
        staff = target.get("staff")
        try:
            box.remove(target)
        except ValueError:
            pass
        if team is None or staff is None:
            return False, []
        nm = gc._staff_full_name(staff)
        role_v = getattr(getattr(staff, "role", None), "value", "staffer")
        tname = getattr(team, "team_name", "?") or "?"
        if years in RENEWAL_YEAR_OPTIONS:
            staff.contract_years = int(years)
            return True, [f"You re-signed {nm} ({role_v}) to a "
                          f"{int(years)}-year deal."]
        pool = getattr(league, "free_agent_staff", None)
        if pool is None:
            pool = []
            league.free_agent_staff = pool
        lines = gc._release_expired_staff(
            league, pool, team, tname, staff, None,
            walk_note="contract expired")
        return True, lines
    except Exception:
        return False, []


def resolve_pending_renewals(league):
    """The ignore path: release every undecided renewal offer to the
    free-agent pool (head-coach promote fallback included). Also closes
    out any open staff_renewal inbox messages. Returns news lines;
    never raises."""
    news = []
    try:
        box = list(getattr(league, "staff_renewal_offers", None) or [])
        if not box:
            return news
        league.staff_renewal_offers = []
        pool = getattr(league, "free_agent_staff", None)
        if pool is None:
            pool = []
            league.free_agent_staff = pool
        for o in box:
            try:
                team = (o or {}).get("team")
                staff = (o or {}).get("staff")
                if team is None or staff is None:
                    continue
                tname = getattr(team, "team_name", "?") or "?"
                news.extend(gc._release_expired_staff(
                    league, pool, team, tname, staff, None,
                    walk_note="contract expired, no renewal agreed"))
            except Exception:
                continue
        # Sync the inbox: undecided offers on open renewal messages are
        # decided (walked) by the lapse.
        try:
            user_team = getattr(league, "user_team", None)
            inbox = getattr(user_team, "inbox", None)
            for m in list(getattr(inbox, "messages", None) or []):
                if getattr(m, "action_type", None) != "staff_renewal":
                    continue
                if getattr(m, "action_done", False):
                    continue
                data = getattr(m, "action_data", None) or {}
                decided = data.get("decided", {}) or {}
                for oc in data.get("offers", []) or []:
                    decided.setdefault(str(oc.get("staff_id")), None)
                data["decided"] = decided
                m.action_done = True
        except Exception:
            pass
    except Exception:
        pass
    return news
