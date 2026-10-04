#!/usr/bin/env python3
# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""UFA consideration period: no more instant signings.

Muck (2026-10-02): "when you try to sign a ufa, he has a consideration
period for all teams to offer, then he takes the best one" -- where "best"
means most appealing per contract_appeal(), not just most money.

How it works:
- A serious UFA offer (>=90% of ask) becomes a BID, not a signing.
- The player enters a 3-7 day consideration window (stars get longer).
- AI teams add competing bids during the window (daily tick).
- At expiry, every bid is scored with player_decision.contract_appeal()
  (money + cup contention + ice time + loyalty + hometown + fan buzz).
  Highest appeal wins. Tiebreak: higher AAV.
- Storybuilding: "fielding offers" / "frontrunner emerges" / signing
  headlines through the shared headlines pipeline.
- After signing: no renegotiation (multi-year locked; 1-year may extend
  via the normal extension flow). Signed players leave the FA pool
  (existing _finalize_contract_signing already removes them).

Storage: ``league.ufa_considerations`` -- plain dicts, pickle-safe, lazy.
All public functions never raise.
"""

import random as _random

CONSIDERATION_MIN_DAYS = 3
CONSIDERATION_MAX_DAYS = 7
MAX_BIDDERS = 6  # cap the frenzy so the tick stays cheap


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def _pid(player):
    try:
        return getattr(player, "id", None)
    except Exception:
        return None


def _pname(player):
    try:
        return getattr(player, "full_name",
                       getattr(player, "name", "The player"))
    except Exception:
        return "The player"


def get_considerations(league):
    """Lazy dict: player_id -> consideration dict. Never raises."""
    try:
        cons = getattr(league, "ufa_considerations", None)
        if not isinstance(cons, dict):
            cons = {}
            league.ufa_considerations = cons
        return cons
    except Exception:
        return {}


def has_consideration(league, player):
    try:
        return _pid(player) in get_considerations(league)
    except Exception:
        return False


def get_consideration(league, player):
    try:
        return get_considerations(league).get(_pid(player))
    except Exception:
        return None


def get_player_status(league, player):
    """Short status string for the UFA screen, or None. Never raises."""
    try:
        cons = get_consideration(league, player)
        if not cons or cons.get("stage") != "open":
            return None
        n = len(cons.get("offers", []))
        d = int(cons.get("days_left", 0) or 0)
        return f"fielding offers ({n} bids, {d}d left)"
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Offer submission
# ---------------------------------------------------------------------------

def _team_name(team):
    try:
        return getattr(team, "team_name",
                       getattr(team, "name", "A club"))
    except Exception:
        return "A club"


def _team_id(team):
    try:
        return getattr(team, "team_name",
                       getattr(team, "name", None)) or id(team)
    except Exception:
        return id(team)


def _window_days(player):
    """3-7 day window; stars get the full frenzy."""
    try:
        ovr = float(player.overall_rating())
    except Exception:
        ovr = 75.0
    try:
        if ovr >= 88:
            lo, hi = 5, CONSIDERATION_MAX_DAYS
        elif ovr >= 80:
            lo, hi = 4, 6
        else:
            lo, hi = CONSIDERATION_MIN_DAYS, 4
        return _random.randint(lo, hi)
    except Exception:
        return 4


def submit_ufa_offer(app, league, player, team, aav, years,
                     is_user=False, clause_kind="none", clause_size=10):
    """Submit a bid. Creates the consideration on first offer, updates the
    team's existing bid on re-offer (no duplicates). Fires the "fielding
    offers" headline once. Returns the consideration dict, or None on
    failure. Never raises."""
    try:
        cons_map = get_considerations(league)
        pid = _pid(player)
        if pid is None:
            return None
        tid = _team_id(team)
        offer = {
            "team": team,
            "team_id": tid,
            "team_name": _team_name(team),
            "aav": int(aav),
            "years": int(max(1, years)),
            "is_user": bool(is_user),
            "clause_kind": str(clause_kind or "none"),
            "clause_size": int(clause_size or 10),
        }
        cons = cons_map.get(pid)
        if cons is None or cons.get("stage") != "open":
            days = _window_days(player)
            cons = {
                "player": player,
                "player_id": pid,
                "player_name": _pname(player),
                "days_left": days,
                "total_days": days,
                "offers": [offer],
                "stage": "open",
                "headline_open_fired": False,
                "headline_frontrunner_fired": False,
            }
            cons_map[pid] = cons
            _fire_headline(app, league, cons, stage="considering")
            cons["headline_open_fired"] = True
        else:
            # Update existing bid from this team, else append.
            replaced = False
            for i, o in enumerate(cons.get("offers", [])):
                try:
                    if o.get("team_id") == tid:
                        cons["offers"][i] = offer
                        replaced = True
                        break
                except Exception:
                    continue
            if not replaced:
                if len(cons.get("offers", [])) < MAX_BIDDERS:
                    cons["offers"].append(offer)
        return cons
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Daily tick
# ---------------------------------------------------------------------------

def tick_ufa_considerations(app, league):
    """Advance every open consideration one day: AI teams add competing
    bids, frontrunner narrative fires at midpoint, expired ones resolve.
    Called from daily maintenance. Never raises."""
    try:
        cons_map = get_considerations(league)
        if not cons_map:
            return
        for pid in list(cons_map.keys()):
            try:
                cons = cons_map.get(pid)
                if not cons or cons.get("stage") != "open":
                    continue
                player = cons.get("player")
                # Player gone (signed elsewhere, retired)? Drop it.
                if not _still_available(league, player, pid):
                    cons["stage"] = "done"
                    continue
                _ai_competing_bids(app, league, cons)
                # Frontrunner narrative at midpoint of a real frenzy.
                try:
                    total = int(cons.get("total_days", 4) or 4)
                    left = int(cons.get("days_left", 0) or 0)
                    n = len(cons.get("offers", []))
                    if (not cons.get("headline_frontrunner_fired")
                            and n >= 3 and left <= total // 2):
                        _fire_headline(app, league, cons,
                                       stage="frontrunner")
                        cons["headline_frontrunner_fired"] = True
                except Exception:
                    pass
                cons["days_left"] = int(cons.get("days_left", 1) or 1) - 1
                if cons["days_left"] <= 0:
                    resolve_consideration(app, league, pid)
            except Exception:
                continue
    except Exception:
        pass


def _still_available(league, player, pid):
    """Is the player still on the market?"""
    try:
        pool = getattr(league, "free_agents", None) or []
        for p in pool:
            try:
                if _pid(p) == pid:
                    return True
            except Exception:
                continue
        return False
    except Exception:
        return True  # can't tell: keep the consideration alive


def _ai_competing_bids(app, league, cons):
    """Interested AI clubs add bids to an open consideration. Bounded and
    guarded: never raises, never spams."""
    try:
        teams = list(getattr(league, "teams", []) or [])
        if not teams:
            return
        player = cons.get("player")
        existing_ids = set()
        for o in cons.get("offers", []):
            try:
                existing_ids.add(o.get("team_id"))
            except Exception:
                continue
        if len(existing_ids) >= MAX_BIDDERS:
            return
        try:
            user_team = getattr(app, "user_team", None)
            user_tid = _team_id(user_team) if user_team is not None else None
        except Exception:
            user_tid = None
        try:
            ovr = float(player.overall_rating())
        except Exception:
            ovr = 75.0
        # Star power drives the frenzy: depth guys get a look or two,
        # stars get the league calling.
        base_p = 0.12 + max(0.0, min(0.45, (ovr - 75.0) * 0.03))
        for team in teams:
            try:
                if len(existing_ids) >= MAX_BIDDERS:
                    break
                tid = _team_id(team)
                if tid in existing_ids or tid == user_tid:
                    continue
                if _random.random() > base_p:
                    continue
                if not _ai_wants_player(app, league, team, player):
                    continue
                aav, years = _ai_bid_terms(league, player, cons)
                if aav <= 0:
                    continue
                submit_ufa_offer(app, league, player, team, aav, years,
                                 is_user=False)
                existing_ids.add(tid)
            except Exception:
                continue
    except Exception:
        pass


def _ai_wants_player(app, league, team, player):
    """Cheap fit check: position need + cap room. Defaults True when the
    AI manager can't answer (better a bid than a crash)."""
    try:
        mgr = getattr(app, "ai_manager", None)
        if mgr is None:
            return True
        strategies = getattr(mgr, "team_strategies", None) or {}
        strat = strategies.get(_team_name(team))
        if strat is not None:
            needs = getattr(strat, "position_needs", None)
            pos = getattr(player, "primary_position", None)
            if needs and pos is not None and pos not in needs:
                return False
        # Rough cap room: payroll + a star ask must fit under the cap.
        try:
            cap = float(getattr(app, "get_live_cap", lambda: 0)() or 0)
            if cap > 0:
                roster = getattr(team, "roster", None) or []
                payroll = sum(int(getattr(x, "salary", 0) or 0)
                              for x in roster)
                ask = _estimate_ask(league, player)
                if payroll + ask > cap:
                    return False
        except Exception:
            pass
        return True
    except Exception:
        return True


def _estimate_ask(league, player):
    """Player's ask in dollars. Uses the shared base-ask machinery."""
    try:
        from salary_cap_system import base_ask_dollars as _bad
        from game_classes import to_100_scale as _t100
        try:
            ovr = float(player.overall_rating())
        except Exception:
            ovr = 75.0
        try:
            ovr100 = int(_t100(ovr))
        except Exception:
            ovr100 = int(ovr * 2)
        pos = getattr(player, "primary_position", "")
        pos_name = getattr(pos, "value", str(pos))
        age = int(getattr(player, "age", 27) or 27)
        contract = getattr(player, "contract", None)
        on_elc = bool(getattr(contract, "entry_level", False))
        ask = int(_bad(ovr100, age, on_elc, pos_name))
        try:
            from salary_cap_system import league_minimum_salary as _min_fn
            floor = int(_min_fn(getattr(league, "season_year", None)))
        except Exception:
            floor = 850_000
        return max(ask, floor)
    except Exception:
        return 1_000_000


def _ai_bid_terms(league, player, cons):
    """What the AI offers: competitive with the field, 0.95-1.12x ask."""
    try:
        ask = _estimate_ask(league, player)
        best = 0
        for o in cons.get("offers", []):
            try:
                best = max(best, int(o.get("aav", 0) or 0))
            except Exception:
                continue
        target = max(int(ask * _random.uniform(0.95, 1.12)), int(best * 1.02))
        try:
            age = int(getattr(player, "age", 27) or 27)
        except Exception:
            age = 27
        years = _random.randint(2, 6) if age < 32 else _random.randint(1, 3)
        return target, years
    except Exception:
        return 0, 1


# ---------------------------------------------------------------------------
# Resolution
# ---------------------------------------------------------------------------

def _score_offer(player, offer, league, app):
    """contract_appeal() score for one bid. Falls back to raw AAV."""
    try:
        from player_decision import contract_appeal as _appeal
        score, reasons = _appeal(
            player, offer.get("team"), int(offer.get("aav", 0) or 0),
            int(offer.get("years", 1) or 1),
            league=league, app=app)
        return max(0.0, min(1.0, float(score or 0.0))), list(reasons or [])
    except Exception:
        pass
    try:
        return float(int(offer.get("aav", 0) or 0)) / 20_000_000.0, []
    except Exception:
        return 0.0, []


def resolve_consideration(app, league, pid):
    """Score every bid by contract_appeal(), sign the winner, notify the
    losers, fire the signing headline. Never raises."""
    try:
        cons_map = get_considerations(league)
        cons = cons_map.get(pid)
        if not cons or cons.get("stage") != "open":
            return None
        cons["stage"] = "deciding"
        player = cons.get("player")
        offers = list(cons.get("offers", []) or [])
        if player is None or not offers:
            cons["stage"] = "done"
            try:
                del cons_map[pid]
            except Exception:
                pass
            return None
        if not _still_available(league, player, pid):
            cons["stage"] = "done"
            try:
                del cons_map[pid]
            except Exception:
                pass
            return None
        # Score every bid. Highest appeal wins; tiebreak: higher AAV.
        scored = []
        for o in offers:
            try:
                s, reasons = _score_offer(player, o, league, app)
                scored.append((s, int(o.get("aav", 0) or 0), o, reasons))
            except Exception:
                continue
        if not scored:
            cons["stage"] = "done"
            try:
                del cons_map[pid]
            except Exception:
                pass
            return None
        scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
        # Try bidders in appeal order; an AI club that spent its cap room
        # during the window falls through to the next-best bid.
        signed_winner = None
        for _appeal, _aav, _offer, _reasons in scored:
            try:
                aav = int(_offer.get("aav", 0) or 0)
                years = int(_offer.get("years", 1) or 1)
                # Re-stage the winning clause for the signing path.
                try:
                    player.offered_clause_kind = _offer.get(
                        "clause_kind", "none")
                    player.offered_clause_list_size = _offer.get(
                        "clause_size", 10)
                except Exception:
                    pass
                if _offer.get("is_user"):
                    _sign_user_winner(app, league, player, aav, years)
                else:
                    if not _sign_ai_winner(app, league, player,
                                           _offer.get("team"), aav, years):
                        continue
                signed_winner = (_offer, aav, years)
                break
            except Exception:
                continue
        if signed_winner is None:
            # Nobody could close: window lapses, player stays on the market.
            cons["stage"] = "done"
            try:
                del cons_map[pid]
            except Exception:
                pass
            return None
        winner, aav, years = signed_winner
        # Tell the user when they lost a bidding war.
        try:
            user_in = any(bool(o.get("is_user")) for o in offers)
            if user_in and not winner.get("is_user"):
                _notify_user_loss(app, player, winner, len(offers))
        except Exception:
            pass
        _fire_headline(app, league, cons, stage="signed", winner=winner,
                       n_bidders=len(offers))
        cons["stage"] = "done"
        try:
            del cons_map[pid]
        except Exception:
            pass
        return winner
    except Exception:
        try:
            cons_map = get_considerations(league)
            c = cons_map.get(pid)
            if c is not None:
                c["stage"] = "done"
        except Exception:
            pass
        return None


def _sign_user_winner(app, league, player, aav, years):
    """User won the bidding war: the standard signing path."""
    try:
        # 1-year CBA re-signing ban after a buyout
        from buyout_window import buyout_re_sign_banned as _banned
        _ut = getattr(getattr(app, "user_team", None), "team_name", "")
        if _banned(player, _ut,
                   getattr(app, "current_date", None)):
            try:
                app.add_news(
                    f"⛔ {getattr(player, 'full_name', 'Player')} cannot "
                    f"re-sign with {_ut}: the 1-year buyout re-signing "
                    f"ban is still in effect.")
            except Exception:
                pass
            return
        player.salary = aav
        player.contract_years = years
        app._finalize_contract_signing(player, aav, years, aav, False)
    except Exception:
        pass


def _sign_ai_winner(app, league, player, team, aav, years):
    """AI won: mirror the AI signing core (contract, pool removal, roster
    add, rivalry transfer, room cascade, news). Returns False when the
    club can no longer fit the deal (caller falls through to the next
    bidder). Never raises."""
    try:
        if team is None:
            return False
        # 1-year CBA re-signing ban after a buyout
        try:
            from buyout_window import buyout_re_sign_banned as _banned
            if _banned(player, getattr(team, "team_name", ""),
                       getattr(app, "current_date", None)):
                return False
        except Exception:
            pass
        pool = getattr(league, "free_agents", None)
        if isinstance(pool, list) and player not in pool:
            return False  # someone got him first
        # Affordability re-check: cap room may have vanished mid-window.
        try:
            cap = 0.0
            gcap = getattr(app, "get_live_cap", None)
            if callable(gcap):
                cap = float(gcap() or 0)
            if cap > 0:
                roster = getattr(team, "roster", None) or []
                payroll = sum(int(getattr(x, "salary", 0) or 0)
                              for x in roster)
                if payroll + int(aav or 0) > cap:
                    return False
        except Exception:
            pass
        player.salary = aav
        player.contract_years = years
        try:
            import trade_engine as _te
            _te.clear_retention_state(player)
        except Exception:
            pass
        contract = getattr(player, "contract", None)
        if contract is not None:
            try:
                contract.salary = aav
                contract.years_remaining = years
            except Exception:
                pass
        try:
            if isinstance(pool, list) and player in pool:
                pool.remove(player)
        except Exception:
            pass
        try:
            team.add_player(player, "roster")
        except Exception:
            return
        try:
            from reputation_system import on_player_transfer as _opt
            rivs = getattr(league, "rivalries", None)
            if isinstance(rivs, list):
                _opt(rivs, player, from_team=None, to_team=team)
        except Exception:
            pass
        try:
            import dressing_room as _dr
            _dr.cascade_on_arrival(team, player, how="signing")
        except Exception:
            pass
        try:
            news = getattr(app, "news_log", None)
            if isinstance(news, list):
                from datetime import date as _date
                news.append({
                    "date": getattr(app, "current_date", _date.today()),
                    "story": (f"The {_team_name(team)} have signed "
                              f"{_pname(player)} to a {years}-year, "
                              f"${aav:,} AAV contract."),
                })
        except Exception:
            pass
        try:
            if callable(getattr(app, "update_all_views", None)):
                app.update_all_views()
        except Exception:
            pass
        return True
    except Exception:
        pass
    return False


def _notify_user_loss(app, player, winner, n_bidders):
    """Inbox: you lost the bidding war."""
    try:
        from game_classes import EmailMessage
        from datetime import date as _date
        wname = str(winner.get("team_name", "another club"))
        aav = int(winner.get("aav", 0) or 0)
        years = int(winner.get("years", 1) or 1)
        msg = EmailMessage(
            sender="Player Agent",
            sender_type="Agent",
            subject=f"💔 {_pname(player)} signed elsewhere",
            content=(
                f"{_pname(player)} has signed with {wname} "
                f"(${aav:,} x {years} years), choosing them over "
                f"{n_bidders - 1} other suitor(s) -- including you.\n\n"
                f"The bidding war is over. Time to pivot to the next target."
            ),
            category="Contracts",
            priority=2,
            is_important=True,
        )
        try:
            msg.game_date_sent = getattr(app, "current_date", _date.today())
            msg.date_sent = msg.game_date_sent
        except Exception:
            pass
        send = getattr(app, "send_email_to_user", None)
        if callable(send):
            send(msg)
    except Exception:
        pass


def notify_consideration_started(app, player, aav, years, days):
    """Inbox: your offer is in; the player is deciding."""
    try:
        from game_classes import EmailMessage
        from datetime import date as _date
        msg = EmailMessage(
            sender="Player Agent",
            sender_type="Agent",
            subject=f"⏳ {_pname(player)} considering your offer",
            content=(
                f"Your offer of ${int(aav):,} x {int(years)} year(s) is on "
                f"the table. {_pname(player)} is fielding offers from "
                f"around the league and will decide in about {int(days)} "
                f"days.\n\n"
                f"Other clubs are circling -- you can improve your offer "
                f"any time before he decides."
            ),
            category="Contracts",
            priority=2,
            is_important=True,
        )
        try:
            msg.game_date_sent = getattr(app, "current_date", _date.today())
            msg.date_sent = msg.game_date_sent
        except Exception:
            pass
        send = getattr(app, "send_email_to_user", None)
        if callable(send):
            send(msg)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Headlines (storybuilding)
# ---------------------------------------------------------------------------

def _fire_headline(app, league, cons, stage="considering", winner=None,
                   n_bidders=0):
    """Route a UFA-saga headline through the shared pipeline."""
    try:
        import headlines as _hl
        from datetime import date as _date
        game_date = getattr(app, "current_date", None) or _date.today()
        kw = {
            "player_name": cons.get("player_name", "A free agent"),
            "stage": stage,
        }
        if stage == "considering":
            kw["n_teams"] = max(1, len(cons.get("offers", [])))
            kw["days"] = int(cons.get("days_left", 4) or 4)
        elif stage == "frontrunner":
            kw["n_teams"] = max(1, len(cons.get("offers", [])))
            kw["leader_name"] = _leader_name(cons)
        elif stage == "signed" and winner is not None:
            kw["team_name"] = str(winner.get("team_name", "a club"))
            kw["aav"] = int(winner.get("aav", 0) or 0)
            kw["years"] = int(winner.get("years", 1) or 1)
            kw["n_bidders"] = int(n_bidders or 0)
        msg = _hl.make_headline("ufa_decision", game_date, **kw)
        if msg is None:
            return
        involved = []
        try:
            for o in cons.get("offers", []):
                tn = str(o.get("team_name", ""))
                if tn and tn not in involved:
                    involved.append(tn)
        except Exception:
            pass
        _hl.deliver(app, msg, involved=tuple(involved))
    except Exception:
        pass


def _leader_name(cons):
    """Team with the biggest current bid (the 'frontrunner')."""
    try:
        best, name = -1, "an unnamed club"
        for o in cons.get("offers", []) or []:
            try:
                a = int(o.get("aav", 0) or 0)
                if a > best:
                    best, name = a, str(o.get("team_name", name))
            except Exception:
                continue
        return name
    except Exception:
        return "an unnamed club"


def ufa_decision_headline(game_date, player_name="A free agent",
                          stage="considering", n_teams=1, days=4,
                          leader_name="an unnamed club", team_name="a club",
                          aav=0, years=1, n_bidders=0, **kw):
    """Headline builder registered as the ``ufa_decision`` kind.

    Stages: considering / frontrunner / signed. Always framed as the
    market watching -- never a promise of where he lands.
    """
    from game_classes import EmailMessage
    try:
        import random as _r
        if stage == "frontrunner":
            _templates = [
                (f"📈 {leader_name} frontrunners for {player_name}",
                 f"League sources say {leader_name}'s offer is the one to "
                 f"beat for {player_name}, with {n_teams} clubs in the mix. "
                 f"Nothing is done until the pen hits paper."),
                (f"👀 {player_name} sweepstakes heating up",
                 f"{leader_name} have emerged as the frontrunners for "
                 f"{player_name}. {n_teams} teams are believed to have "
                 f"tabled offers -- but this one has had twists before."),
            ]
        elif stage == "signed":
            _templates = [
                (f"✍️ {player_name} signs with {team_name}",
                 f"It's done: {player_name} has signed a {years}-year, "
                 f"${int(aav):,} AAV deal with {team_name}, choosing them "
                 f"over {max(0, n_bidders - 1)} other suitor(s)."),
            ]
        else:  # considering
            _templates = [
                (f"👀 {player_name} fielding offers",
                 f"{player_name} is considering offers from {n_teams} "
                 f"club(s). A decision is expected in about {days} days -- "
                 f"the phones are buzzing."),
                (f"📞 {player_name} sweepstakes underway",
                 f"The {player_name} sweepstakes are on: {n_teams} team(s) "
                 f"have tabled offers. His camp says he'll decide within "
                 f"{days} days."),
            ]
        _subject, _content = _r.choice(_templates)
    except Exception:
        _subject = f"UFA watch: {player_name}"
        _content = f"{player_name} is weighing his options."
    return EmailMessage(
        sender="League Insider",
        sender_type="Media",
        subject=_subject,
        content=_content,
        category="Free Agency",
        priority=2,
        is_important=(stage == "signed"),
    )
