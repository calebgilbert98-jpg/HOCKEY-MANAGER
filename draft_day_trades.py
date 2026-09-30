# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Draft-day deal engine: the entry draft is a trade-deadline-style event.

Once the lottery sets the order, every AI GM knows where they're picking and
the phones light up. This module runs that market:

  * TRADE UP -- a club whose top positional need matches a prospect projected
    to go a few slots ahead of them tries to move up and get their guy.
    Contenders chase NHL-ready help; rebuilders chase elite ceilings.
  * VETERAN FOR PICK -- rebuilding clubs shop veterans (28+, 75+ OVR) for
    first-rounders; contenders holding late firsts and a positional need buy.

Positional fit comes from trade_engine.team_needs (weakest-first); franchise
situation comes from the AI manager's TeamStrategy (ManagementPriority).
Valuation, cap checks, clause preflights, counters and execution all reuse
trade_engine unchanged -- this module only INITIATES proposals the engine
already knows how to evaluate. Additive by design: nothing in trade_engine,
game_classes or ai_team_management is modified.

Fantasy drafts never call this module: there is no trading in a fantasy
draft, by design.

Entry points:
  run_draft_day_trading(league, year, app=None, max_deals=4)
      Post-lottery, pre-draft AI deal wave. Returns CompletedTrade records.
  on_clock_check(view)
      DraftView war-room hook: an AI club is on the clock in round 1 and the
      phones ring. Returns True when a deal was made (draft order changed).
  incoming_offer_for_user(view)
      DraftView war-room hook: the user's club is on the clock in round 1 and
      an AI club calls about the pick. Shows at most one modal per pick.
  franchise_pick_multiplier(prospect, priority)
      Shared helper: how much a club's franchise situation tilts its draft
      board (contenders -> readiness, rebuilders -> ceiling).
"""

import random

# Potential grade -> numeric ceiling (mirrors the draft board's grade scale).
_GRADE_SCORE = {
    'A+': 10.0, 'A': 9.0, 'A-': 8.0,
    'B+': 7.0, 'B': 6.0, 'B-': 5.0,
    'C+': 4.0, 'C': 3.0, 'C-': 2.0,
    'D+': 1.5, 'D': 1.0, 'D-': 0.5, 'F': 0.0,
}


def grade_score(grade):
    """Numeric ceiling for a potential grade like 'A-' (0-10)."""
    try:
        return _GRADE_SCORE.get(str(grade or '').strip().upper(), 5.0)
    except Exception:
        return 5.0


def franchise_pick_multiplier(prospect, priority):
    """Board tilt from franchise situation. 1.0 = neutral.

    Contenders draft for readiness (higher current overall); rebuilders draft
    for ceiling (higher potential grade). Kept modest so BPA still rules.
    """
    try:
        pname = getattr(priority, 'value', priority)
        if pname == 'contend':
            try:
                ovr = float(prospect.overall_rating())
            except Exception:
                return 1.0
            # ~0.97 for a 55-ovr prospect, ~1.06 for a 65-ovr one.
            return 0.90 + 0.11 * max(0.0, min(1.0, (ovr - 50.0) / 20.0)) + 0.07
        if pname == 'rebuild':
            ceiling = grade_score(getattr(prospect, 'potential_grade', ''))
            # ~0.97 for a C prospect, ~1.06 for an A prospect.
            return 0.90 + 0.16 * max(0.0, min(1.0, ceiling / 10.0))
    except Exception:
        pass
    return 1.0


# ---------------------------------------------------------------------------
# Small helpers (all read-only against the league model)
# ---------------------------------------------------------------------------

def _is_human(team):
    try:
        from game_classes import is_human_managed
        return bool(is_human_managed(team))
    except Exception:
        return bool(getattr(team, 'is_user_team', False))


def _priority_of(team, ai_manager):
    """ManagementPriority for a team, or None."""
    try:
        if ai_manager is None:
            return None
        strat = ai_manager.get_team_strategy(team.team_name)
        return getattr(strat, 'priority', None)
    except Exception:
        return None


def _priority_name(priority):
    try:
        return getattr(priority, 'value', priority)
    except Exception:
        return None


def _round1_order(league, year):
    """[(overall, team, pick)] for round 1, sorted by overall pick number."""
    import trade_engine as te  # noqa: F401 (kept local; module is heavy)
    try:
        order = league.get_draft_order(year)
    except Exception:
        return []
    r1 = []
    for overall, team, pick in order:
        try:
            rnd = getattr(pick, 'round', 1)
        except Exception:
            rnd = 1
        if rnd == 1:
            try:
                pick.overall_pick = int(overall)
            except Exception:
                pass
            r1.append((int(overall), team, pick))
    r1.sort(key=lambda x: x[0])
    return r1


def _draft_board(league):
    """Prospects in consensus (draft_ranking) order."""
    try:
        prospects = list(getattr(league, 'draft_prospects', None) or [])
    except Exception:
        return []
    prospects.sort(key=lambda p: getattr(p, 'draft_ranking', 0) or 0,
                   reverse=True)
    return prospects


def _pos_of(prospect):
    try:
        return prospect.primary_position.value
    except Exception:
        return '?'


def _needs_of(team):
    import trade_engine as te
    try:
        return te.team_needs(team)
    except Exception:
        return []


def _owned_picks(team, year, round_num):
    """DraftPick objects this team currently owns for (year, round)."""
    out = []
    try:
        for pk in team.get_picks_for_year(year):
            if (getattr(pk, 'round', None) == round_num
                    and str(getattr(pk, 'current_team', '')) == team.team_name):
                out.append(pk)
    except Exception:
        pass
    return out


def _record_deal(league, app, summary):
    """News + history + the Draft Day Central deals feed."""
    try:
        deals = getattr(league, 'draft_day_deals', None)
        if not isinstance(deals, list):
            league.draft_day_deals = []
        league.draft_day_deals.append(summary)
    except Exception:
        pass
    try:
        if app is not None:
            app.add_news("DRAFT TRADE: " + summary)
    except Exception:
        pass
    try:
        gm = getattr(app, 'game_manager', None) if app is not None else None
        if gm is not None:
            if not hasattr(gm, 'trade_history'):
                gm.trade_history = []
            import trade_engine as te
            gm.trade_history.append(te.CompletedTrade(
                str(getattr(gm, 'current_date', '')),
                '', '', [], [], "DRAFT TRADE: " + summary))
    except Exception:
        pass


def _date_str(app):
    try:
        return str(getattr(app, 'current_date', ''))
    except Exception:
        return ''


# ---------------------------------------------------------------------------
# Negotiation: AI proposes, engine disposes
# ---------------------------------------------------------------------------

def _proposer_accepts_counter(te, gives, gets, want_added, will_add):
    """Would the proposing AI accept the partner's counter?

    Counter deal from the proposer's seat: receives (gets + will_add),
    gives (gives + want_added). Accepts a slight overpay for their guy.
    """
    try:
        ev = te.evaluate_trade(list(gets) + list(will_add or []),
                               list(gives) + list(want_added or []))
        return ev.ratio >= 0.92
    except Exception:
        return False


def _sync_pick_lists(giver, receiver, giver_assets, receiver_assets):
    """Move traded pick OBJECTS between the clubs' draft_picks lists.

    trade_engine.execute_trade re-points pick.current_team but leaves the
    object in the giver's draft_picks list, so League.get_draft_order() --
    which resolves the owner by list membership -- keeps reporting the old
    club. That would put the wrong team on the clock after a draft-day
    deal. This runs the objects through the existing Team.trade_pick /
    Team.receive_pick API (additive; the engine itself is untouched).
    """
    from game_classes import DraftPick
    for team_from, team_to, assets in ((giver, receiver, giver_assets),
                                      (receiver, giver, receiver_assets)):
        try:
            to_name = team_to.team_name
        except Exception:
            continue
        for a in assets or []:
            if not isinstance(a, DraftPick):
                continue
            try:
                if a in team_from.get_picks_for_year(a.year):
                    try:
                        team_from.trade_pick(a, to_name, "draft-day deal")
                    except Exception:
                        # Fall back to a plain list move if the Team API
                        # refuses (e.g. already moved).
                        try:
                            team_from.draft_picks[a.year].remove(a)
                        except Exception:
                            pass
                    team_to.receive_pick(a)
            except Exception:
                pass


def _negotiate(te, proposer, holder, proposer_gives, holder_gives,
               league, app, holder_eagerness=1.0, _waiver_player=None):
    """Run one AI-to-AI proposal through the trade engine.

    Returns the CompletedTrade on success, else None. holder_eagerness
    multiplies the holder's greed (<1 = more willing to deal).
    _waiver_player: a player whose single-use NTC waiver was stamped for
    this proposal -- scrubbed if the deal dies, like the deadline engine.
    """
    _dest_names = set()
    for _t in (proposer, holder):
        try:
            _dest_names.add(_t.team_name)
        except Exception:
            pass

    def _scrub_waivers(extra_players=()):
        # Scrub single-use stamps from THIS negotiation only: our own
        # waiver player plus any will_add players the engine stamped
        # while building a counter. A declined counter must not leave a
        # live waiver behind (it would be honored by a later, unrelated
        # trade). Only stamps pointing at this negotiation's clubs are
        # touched -- pre-existing waivers for elsewhere are left alone.
        for _p in ([_waiver_player] + list(extra_players or [])):
            try:
                _c = getattr(_p, 'contract', None)
                if _c is not None and \
                        str(getattr(_c, 'ntc_waiver_for', '') or '') \
                        in _dest_names:
                    _c.ntc_waiver_for = ""
            except Exception:
                pass

    try:
        situational = None
        try:
            import trade_storylines as tsl
            situational = tsl.situational_context(app, holder, proposer)
            gm = float(situational.get('greed_mult', 1.0))
            situational['greed_mult'] = gm * float(holder_eagerness)
        except Exception:
            if holder_eagerness != 1.0:
                situational = {'greed_mult': float(holder_eagerness)}
        resp = te.ai_consider_trade(
            holder, list(proposer_gives), list(holder_gives),
            user_team=proposer, situational=situational)
    except Exception:
        _scrub_waivers()
        return None
    decision = getattr(resp, 'decision', 'reject')
    will_add = list(getattr(resp, 'will_add', None) or [])
    final_gives = list(proposer_gives)
    final_gets = list(holder_gives)
    if decision == 'counter':
        want_added = list(getattr(resp, 'want_added', None) or [])
        if not _proposer_accepts_counter(te, final_gives, final_gets,
                                         want_added, will_add):
            _scrub_waivers(will_add)
            return None
        final_gives = final_gives + want_added
        final_gets = final_gets + will_add
    elif decision != 'accept':
        _scrub_waivers(will_add)
        return None
    try:
        done = te.execute_trade(proposer, holder, final_gives, final_gets,
                                _date_str(app), league=league)
    except Exception:
        _scrub_waivers(will_add)
        return None
    try:
        if str(getattr(done, 'summary', '')).startswith('BLOCKED:'):
            _scrub_waivers(will_add)
            return None
    except Exception:
        pass
    # Ownership must propagate into get_draft_order(): move the traded pick
    # objects into the new clubs' draft_picks lists (see _sync_pick_lists).
    _sync_pick_lists(proposer, holder, final_gives, final_gets)
    return done


def _describe_swap(te, proposer, holder, p_overall, h_overall):
    return (f"{proposer.team_name} moves up to #{h_overall} overall in a "
            f"deal with {holder.team_name} (was #{p_overall}).")


# ---------------------------------------------------------------------------
# Trade-up: "we know where we're picking -- go get your guy"
# ---------------------------------------------------------------------------

def _trade_up_target(team, overall, board, priority_name):
    """Best trade-up target for a team holding `overall`.

    Returns (target_overall, prospect) or None. The target is a prospect at
    a need position projected a few slots ahead, with a real talent gap over
    who's likely there at `overall`. Franchise situation filters the chase:
    rebuilders only move up for elite ceilings, contenders only for NHL-ready
    talent.
    """
    import trade_engine as te
    needs = _needs_of(team)
    if not needs or overall < 2:
        return None
    reach = 8
    at_slot = board[overall - 1] if 0 <= overall - 1 < len(board) else None
    at_slot_rank = getattr(at_slot, 'draft_ranking', 0) or 0
    # The gap gate must respect the class's own ranking scale: generated
    # classes are dense (a ~30-point span over 224 prospects), so an
    # absolute 1.5-point bar prices every reachable target out of the
    # market and draft day goes silent. ~2.5% of the class span.
    _top = getattr(board[0], 'draft_ranking', 0) or 0
    _bot = getattr(board[-1], 'draft_ranking', 0) or 0
    gap_needed = max(0.5, (_top - _bot) * 0.025)
    best = None
    for i, p in enumerate(board):
        proj = i + 1
        if proj >= overall:
            break
        if overall - proj > reach:
            continue
        if _pos_of(p) not in needs[:2]:
            continue
        gap = (getattr(p, 'draft_ranking', 0) or 0) - at_slot_rank
        if gap < gap_needed:
            continue
        if priority_name == 'rebuild' and grade_score(
                getattr(p, 'potential_grade', '')) < 8.0:
            continue
        if priority_name == 'contend':
            try:
                if float(p.overall_rating()) < 56.0:
                    continue
            except Exception:
                continue
        score = gap * franchise_pick_multiplier(p, priority_name)
        score += random.uniform(-0.5, 0.5)
        if best is None or score > best[0]:
            best = (score, proj, p)
    if best is None:
        return None
    return best[1], best[2]


def _build_trade_up_offer(te, proposer, proposer_pick, holder, year):
    """Proposer's 1st + sweetener for the holder's higher 1st.

    Returns (proposer_gives, holder_gives) or None when there's nothing
    sensible to add -- a straight swap up is never fair value.
    """
    holder_picks = [pk for pk in _owned_picks(holder, year, 1)]
    # The holder's pick being targeted: the earliest 1st they own.
    holder_pick = None
    for pk in holder_picks:
        try:
            if holder_pick is None or int(getattr(pk, 'overall_pick', 99) or 99) < \
                    int(getattr(holder_pick, 'overall_pick', 99) or 99):
                holder_pick = pk
        except Exception:
            holder_pick = holder_pick or pk
    if holder_pick is None:
        return None
    gives = [proposer_pick]
    # Sweetener: our 2nd this year, else our 3rd -- real draft-day currency.
    for rnd in (2, 3):
        sweet = _owned_picks(proposer, year, rnd)
        if sweet:
            gives.append(sweet[0])
            break
    if len(gives) < 2:
        return None
    return gives, [holder_pick]


def _emit_trade_rumor(league, app, line, ticker_fn=None):
    """Rumor-mill line for trade-up interest that never became a deal.

    Always labeled RUMOR -- never reads as a completed transaction.
    Bounded per draft (3) so the news feed doesn't flood.
    """
    try:
        if league is None:
            return
        _n = int(getattr(league, '_trade_up_rumors', 0) or 0)
        if _n >= 3:
            return
        league._trade_up_rumors = _n + 1
        try:
            if app is not None:
                app.add_news(line)
        except Exception:
            pass
        if ticker_fn is not None:
            try:
                ticker_fn(line)
            except Exception:
                pass
    except Exception:
        pass


def _attempt_trade_up(team, overall, pick, league, year, board, app,
                      ai_manager, order):
    """One team tries to move up. Returns a deal summary or None."""
    import trade_engine as te
    priority = _priority_of(team, ai_manager)
    pname = _priority_name(priority)
    target = _trade_up_target(team, overall, board, pname)
    if target is None:
        return None
    target_overall, prospect = target
    # Who holds that slot right now? (Order may have shifted after a deal.)
    holder = None
    for o, t, _pk in order:
        if o == target_overall:
            holder = t
            break
    if holder is None or holder == team or _is_human(holder):
        return None
    # A holder already shopping... just ask the engine.
    offer = _build_trade_up_offer(te, team, pick, holder, year)
    if offer is None:
        return None
    gives, gets = offer
    # Rebuilders holding high picks listen for volume; everyone else holds
    # their lottery ticket a little tighter (endowment is real).
    holder_pname = _priority_name(_priority_of(holder, ai_manager))
    eagerness = 0.94 if holder_pname == 'rebuild' else 1.04
    done = _negotiate(te, team, holder, gives, gets, league, app,
                      holder_eagerness=eagerness)
    if done is None:
        # Real interest, no deal: the phones were busy. Rumor mill, not a
        # transaction -- clearly labeled, performance/transaction-grounded
        # like real life.
        try:
            _pname = getattr(prospect, 'full_name', 'their guy')
            try:
                _ppos = prospect.primary_position.value
            except Exception:
                _ppos = "?"
            _emit_trade_rumor(
                league, app,
                f"RUMOR: {team.team_name} explored moving up from "
                f"#{overall} to #{target_overall} ({holder.team_name}'s "
                f"slot) -- believed to be for {_pname} ({_ppos}) -- but no "
                f"deal materialized.")
        except Exception:
            pass
        return None
    summary = _describe_swap(te, team, holder, overall, target_overall)
    _record_deal(league, app, summary)
    return done


# ---------------------------------------------------------------------------
# Veteran for pick: rebuilders sell, contenders buy
# ---------------------------------------------------------------------------

def _shop_veterans(seller, league, year, order, app, ai_manager):
    """A rebuilding club shops veterans for first-rounders. Returns summary."""
    import trade_engine as te
    pname = _priority_name(_priority_of(seller, ai_manager))
    if pname != 'rebuild':
        return None
    veterans = []
    for p in getattr(seller, 'roster', []) or []:
        try:
            if p.age > 28 and p.overall_rating() > 75:
                veterans.append(p)
        except Exception:
            continue
    veterans.sort(key=lambda p: p.overall_rating(), reverse=True)
    for vet in veterans[:2]:
        vpos = _pos_of(vet)
        # Buyers: contenders holding a late 1st with a matching need.
        for overall, buyer, buy_pick in order:
            if overall < 18:
                continue
            if buyer == seller or _is_human(buyer):
                continue
            b_pname = _priority_name(_priority_of(buyer, ai_manager))
            if b_pname != 'contend':
                continue
            if vpos not in (_needs_of(buyer)[:2]):
                continue
            # The veteran has to agree to go (trade engine preflights this,
            # but check first so we don't spam doomed proposals). On a
            # granted waiver, stamp it so the completion preflight honors
            # it -- and scrub the stamp if the deal dies, like the
            # deadline engine does.
            try:
                vetoes = te.trade_vetoes(seller, buyer, [vet])
                blocked = False
                for _v in vetoes:
                    ok, _why = te.will_waive_ntc(vet, seller, buyer)
                    if not ok:
                        blocked = True
                        break
                    try:
                        vet.contract.ntc_waiver_for = buyer.team_name
                    except Exception:
                        pass
                if blocked:
                    continue
            except Exception:
                pass
            done = _negotiate(te, seller, buyer, [vet], [buy_pick],
                              league, app, holder_eagerness=0.97,
                              _waiver_player=vet)
            if done is None:
                continue
            try:
                vname = getattr(vet, 'full_name', 'veteran')
            except Exception:
                vname = 'veteran'
            summary = (f"{buyer.team_name} acquires {vname} from "
                       f"{seller.team_name} for #{overall} overall.")
            _record_deal(league, app, summary)
            return done
    return None


# ---------------------------------------------------------------------------
# Public entry points
# ---------------------------------------------------------------------------

def run_draft_day_trading(league, year, app=None, max_deals=4):
    """Post-lottery AI deal wave. Every GM knows where they're picking.

    Runs trade-up attempts (need + talent gap + franchise situation) and
    veteran-for-pick deals (rebuilders sell to contenders). Human-managed
    clubs never initiate and are never targeted. Returns the CompletedTrade
    records (one per deal); human-readable summaries land in
    league.draft_day_deals.
    """
    import trade_engine as te  # noqa: F401
    deals = []
    try:
        # Fresh rumor-mill budget each draft day.
        league._trade_up_rumors = 0
    except Exception:
        pass
    try:
        ai_manager = app.ai_manager if app is not None else None
    except Exception:
        ai_manager = None
    try:
        order = _round1_order(league, year)
        board = _draft_board(league)
    except Exception:
        return deals
    if not order or not board:
        return deals

    def _slot(team_name):
        for o, t, pk in order:
            if t.team_name == team_name:
                return o, pk
        return None, None

    # Phase A: trade-ups. Randomize the call order so the same clubs don't
    # always get first crack at the phones.
    call_order = [(o, t, pk) for o, t, pk in order
                  if not _is_human(t) and o >= 2]
    random.shuffle(call_order)
    attempted = set()
    for overall, team, pick in call_order:
        if len(deals) >= max_deals:
            break
        if team.team_name in attempted:
            continue
        attempted.add(team.team_name)
        # Refresh: an earlier deal may have moved this club's pick.
        overall_now, pick_now = _slot(team.team_name)
        if pick_now is None:
            continue
        try:
            done = _attempt_trade_up(team, overall_now, pick_now, league,
                                     year, board, app, ai_manager, order)
        except Exception:
            continue
        if done is not None:
            deals.append(done)
            try:
                order = _round1_order(league, year)
            except Exception:
                pass

    # Phase B: veteran-for-pick. Rebuilders first.
    if len(deals) < max_deals:
        sellers = [(o, t) for o, t, _pk in order if not _is_human(t)]
        random.shuffle(sellers)
        for _o, seller in sellers:
            if len(deals) >= max_deals:
                break
            try:
                done = _shop_veterans(seller, league, year, order, app,
                                      ai_manager)
            except Exception:
                continue
            if done is not None:
                deals.append(done)
                try:
                    order = _round1_order(league, year)
                except Exception:
                    pass
    return deals


def _sync_view_order(view, league):
    """Point the war-room draft board at the new pick owners."""
    try:
        for entry in view.draft_order:
            _r, _t, dp = entry
            if dp is None:
                continue
            owner_name = str(getattr(dp, 'current_team', '') or '')
            if not owner_name or owner_name == _t.team_name:
                continue
            owner = next((x for x in league.teams
                          if x.team_name == owner_name), None)
            if owner is not None:
                entry[1] = owner
    except Exception:
        pass


def on_clock_check(view):
    """War-room hook: an AI club is on the clock in round 1; phones ring.

    A motivated club below may trade up for the slot. Returns True when a
    deal was made (caller should re-read draft_order[current_pick]).
    """
    try:
        import trade_engine as te
    except Exception:
        return False
    try:
        league = view.app.league
        year = league.season_year
        if view.current_pick >= len(view.draft_order):
            return False
        rnd, team_on_clock, _dp = view.draft_order[view.current_pick]
        if rnd != 1 or _is_human(team_on_clock):
            return False
        # One ring per draft: the market already had its post-lottery wave.
        if getattr(view, '_ddt_on_clock_deals', 0) >= 2:
            return False
        try:
            ai_manager = view.app.ai_manager
        except Exception:
            ai_manager = None
        board = [p for p in _draft_board(league)
                 if p in (getattr(league, 'draft_prospects', None) or [])]
        overall = view.current_pick + 1
        # Who below wants this slot most?
        best = None
        for o2, t2, pk2 in _round1_order(league, year):
            if o2 <= overall or _is_human(t2):
                continue
            pname = _priority_name(_priority_of(t2, ai_manager))
            tgt = _trade_up_target(t2, o2, board, pname)
            if tgt is None:
                continue
            t_overall, _prosp = tgt
            if t_overall != overall:
                continue  # they want THIS slot, not just any slot
            score = random.uniform(0, 1)
            if best is None or score > best[0]:
                # re-resolve their current pick object
                mine = [pk for pk in _owned_picks(t2, year, 1)]
                if not mine:
                    continue
                best = (score, t2, mine[0], o2)
        if best is None:
            return False
        if random.random() > 0.45:
            # Real interest, no deal: the phones were busy. Rumor mill.
            _s, proposer, _pk, p_overall = best
            _emit_trade_rumor(
                league, view.app,
                f"RUMOR: {proposer.team_name} was calling about moving up "
                f"to #{overall} -- nothing came of it.",
                ticker_fn=getattr(view, '_ticker', None))
            return False
        _s, proposer, proposer_pick, p_overall = best
        offer = _build_trade_up_offer(te, proposer, proposer_pick,
                                      team_on_clock, year)
        if offer is None:
            return False
        gives, gets = offer
        done = _negotiate(te, proposer, team_on_clock, gives, gets,
                          league, view.app, holder_eagerness=1.0)
        if done is None:
            return False
        view._ddt_on_clock_deals = getattr(view, '_ddt_on_clock_deals', 0) + 1
        _sync_view_order(view, league)
        summary = _describe_swap(te, proposer, team_on_clock, p_overall,
                                 overall)
        _record_deal(league, view.app, summary)
        try:
            view._ticker("TRADE: " + summary)
        except Exception:
            pass
        return True
    except Exception:
        return False


def _scrub_call_waivers(assets, team_names):
    """Clear single-use waivers this negotiation stamped, preserving any
    pre-existing waiver for an uninvolved team."""
    for _p in assets or []:
        try:
            _c = getattr(_p, 'contract', None)
            if _c is not None and str(
                    getattr(_c, 'ntc_waiver_for', '') or '') in team_names:
                _c.ntc_waiver_for = ""
        except Exception:
            pass


def _call_why_lines(te, caller, prosp, board, pname):
    """'Why they're calling' bullets: target, positional fit, direction."""
    try:
        name = getattr(prosp, 'full_name', 'their guy')
        pos = _pos_of(prosp)
    except Exception:
        name, pos = 'their guy', '?'
    try:
        proj = list(board).index(prosp) + 1
    except Exception:
        proj = None
    bullets = [f"They love {name} ({pos})"
               + (f", projected #{proj} overall" if proj else "")]
    try:
        needs = te.team_needs(caller) or []
        if pos in needs:
            bullets.append(
                f"{pos} is their #{needs.index(pos) + 1} organizational need")
    except Exception:
        pass
    _dir = {'rebuild': "Rebuilding — drafting for ceiling, not tomorrow's lineup",
            'contend': "Contending — they want someone who can help soon",
            }.get(pname, "Balanced — taking the best player available")
    bullets.append(_dir)
    return {'bullets': bullets,
            'direction_short': {'rebuild': 'Rebuilding',
                                'contend': 'Contending'}.get(pname, 'Balanced')}


def _incoming_call_dialog(view, caller, gives, gets, prosp, overall, why):
    """M3: the incoming trade call as a real decision dialog.

    Caller identity, their target as a mini prospect card, why they're
    calling, the deal as a two-sided card with a qualitative value bar
    (no raw slot numbers), and Accept / Counter / Decline. Blocking, like
    the old askyesno -- the draft clock freezes while the phone is live.
    Returns 'accept' | 'counter' | 'decline'.
    """
    import customtkinter as ctk
    import trade_engine as te
    try:
        from popup_system import InGamePopup
    except Exception:
        return 'decline'
    try:
        import scouting as scmod
    except Exception:
        scmod = None

    ct = getattr(view, '_ct', None) or {}
    BG = ct.get('BG', '#0e0e11'); CARD = ct.get('CARD', '#1e1e24')
    TEXT = ct.get('TEXT', '#F2F5FA'); DIM = ct.get('TEXT_DIM', '#9aa0aa')
    TEAL = ct.get('TEAL', '#00ceb8'); GOLD = ct.get('GOLD', '#e8b93c')
    GREEN = ct.get('GREEN', '#46c93a'); RED = ct.get('RED', '#e5484d')

    result = {'choice': 'decline'}
    dlg = InGamePopup(view, modal=True)
    try:
        dlg.title("Incoming call")
        dlg.geometry("580x680")
        dlg.configure(fg_color=BG)
    except Exception:
        pass

    def _done(choice):
        result['choice'] = choice
        try:
            dlg.destroy()
        except Exception:
            pass

    ctk.CTkLabel(dlg, text="📞  INCOMING CALL",
                 font=("Segoe UI", 10, 'bold'),
                 text_color=DIM).pack(anchor='w', padx=16, pady=(12, 0))
    ctk.CTkLabel(
        dlg, text=f"{caller.team_name}  ·  {why.get('direction_short', '')}",
        font=("Segoe UI", 16, 'bold'), text_color=TEXT).pack(
            anchor='w', padx=16)

    whyf = ctk.CTkFrame(dlg, fg_color=CARD, corner_radius=8)
    whyf.pack(fill='x', padx=16, pady=(8, 4))
    ctk.CTkLabel(whyf, text="WHY THEY'RE CALLING",
                 font=("Segoe UI", 9, 'bold'),
                 text_color=DIM).pack(anchor='w', padx=12, pady=(6, 0))
    for _line in why.get('bullets', []):
        ctk.CTkLabel(whyf, text="•  " + _line, font=("Segoe UI", 11),
                     text_color=TEXT, wraplength=500,
                     justify='left').pack(anchor='w', padx=12, pady=1)
    ctk.CTkLabel(whyf, text="", font=("Segoe UI", 3)).pack()

    try:
        tname = getattr(prosp, 'full_name', '?')
        tpos = _pos_of(prosp)
        tage = getattr(prosp, 'age', '?')
        tpot = scmod.consensus_range(prosp) if scmod else '?'
    except Exception:
        tname, tpos, tage, tpot = '?', '?', '?', '?'
    tf = ctk.CTkFrame(dlg, fg_color=CARD, corner_radius=8)
    tf.pack(fill='x', padx=16, pady=4)
    ctk.CTkLabel(tf, text="THEIR TARGET",
                 font=("Segoe UI", 9, 'bold'),
                 text_color=DIM).pack(anchor='w', padx=12, pady=(6, 0))
    ctk.CTkLabel(tf, text=f"{tname}  ·  {tpos}  ·  Age {tage}",
                 font=("Segoe UI", 13, 'bold'),
                 text_color=TEXT).pack(anchor='w', padx=12)
    ctk.CTkLabel(tf, text=f"Consensus potential: {tpot}",
                 font=("Segoe UI", 11),
                 text_color=GOLD).pack(anchor='w', padx=12, pady=(0, 8))

    df = ctk.CTkFrame(dlg, fg_color=CARD, corner_radius=8)
    df.pack(fill='x', padx=16, pady=4)
    ctk.CTkLabel(df, text="THE DEAL",
                 font=("Segoe UI", 9, 'bold'),
                 text_color=DIM).pack(anchor='w', padx=12, pady=(6, 0))
    cols = ctk.CTkFrame(df, fg_color="transparent")
    cols.pack(fill='x', padx=12, pady=2)
    cols.grid_columnconfigure(0, weight=1)
    cols.grid_columnconfigure(1, weight=1)
    you_send = ctk.CTkFrame(cols, fg_color="transparent")
    you_send.grid(row=0, column=0, sticky='nw')
    ctk.CTkLabel(you_send, text="YOU SEND",
                 font=("Segoe UI", 10, 'bold'),
                 text_color=RED).pack(anchor='w')
    for _a in gets:  # gets = caller's take = the user's outgoing
        ctk.CTkLabel(you_send, text="• " + te.asset_label(_a),
                     font=("Segoe UI", 11), text_color=TEXT,
                     wraplength=240, justify='left').pack(anchor='w', pady=1)
    you_get = ctk.CTkFrame(cols, fg_color="transparent")
    you_get.grid(row=0, column=1, sticky='nw')
    ctk.CTkLabel(you_get, text="YOU RECEIVE",
                 font=("Segoe UI", 10, 'bold'),
                 text_color=GREEN).pack(anchor='w')
    for _a in gives:
        ctk.CTkLabel(you_get, text="• " + te.asset_label(_a),
                     font=("Segoe UI", 11), text_color=TEXT,
                     wraplength=240, justify='left').pack(anchor='w', pady=1)

    # Value bar: qualitative, no raw slot numbers.
    try:
        v_in = sum(te.asset_value(_a) for _a in gives)
        v_out = sum(te.asset_value(_a) for _a in gets)
        share = (v_in / (v_in + v_out)) if (v_in + v_out) > 0 else 0.5
    except Exception:
        share = 0.5
    if share >= 0.55:
        vlabel, vcolor = "Value favors you", GREEN
    elif share <= 0.45:
        vlabel, vcolor = "Value favors them", RED
    else:
        vlabel, vcolor = "Roughly fair value", GOLD
    bar = ctk.CTkProgressBar(df, width=480, height=10)
    bar.pack(padx=12, pady=(6, 0))
    try:
        bar.set(max(0.02, min(0.98, share)))
    except Exception:
        pass
    ctk.CTkLabel(df, text=vlabel, font=("Segoe UI", 10, 'bold'),
                 text_color=vcolor).pack(anchor='w', padx=12, pady=(0, 8))

    btnf = ctk.CTkFrame(dlg, fg_color="transparent")
    btnf.pack(fill='x', padx=16, pady=(4, 14))
    ctk.CTkButton(btnf, text="Decline", width=120,
                  fg_color=CARD, text_color=TEXT,
                  command=lambda: _done('decline')).pack(side='left',
                                                        padx=(0, 8))
    ctk.CTkButton(btnf, text="Counter", width=120,
                  fg_color=CARD, text_color=TEXT,
                  command=lambda: _done('counter')).pack(side='left',
                                                        padx=(0, 8))
    ctk.CTkButton(btnf, text="Accept", width=160,
                  fg_color=TEAL, text_color=BG,
                  font=("Segoe UI", 12, 'bold'),
                  command=lambda: _done('accept')).pack(side='right')
    try:
        dlg.bind('<Escape>', lambda _e: _done('decline'))
    except Exception:
        pass
    try:
        view.wait_window(dlg)
    except Exception:
        pass
    return result['choice']


def _user_counter_flow(view, caller, gives, gets, overall):
    """Counter path: the user demands one more of the caller's later picks.

    Returns (new_gives, new_gets, waiver_assets) if the AI accepts (or
    counters back once), else None.
    """
    import customtkinter as ctk
    import tkinter as tk
    import trade_engine as te
    try:
        from popup_system import InGamePopup
    except Exception:
        return None
    ct = getattr(view, '_ct', None) or {}
    BG = ct.get('BG', '#0e0e11'); CARD = ct.get('CARD', '#1e1e24')
    TEXT = ct.get('TEXT', '#F2F5FA'); DIM = ct.get('TEXT_DIM', '#9aa0aa')
    TEAL = ct.get('TEAL', '#00ceb8')

    options = []
    try:
        order = view.draft_order
        for idx in range(view.current_pick + 1, len(order)):
            r, t, dp = order[idx]
            if t == caller and dp is not None \
                    and not any(dp is g for g in gives) \
                    and not any(dp is g for g in gets):
                options.append((idx + 1, r, dp))
    except Exception:
        pass
    options = options[:12]
    if not options:
        return None

    result = {'idx': None}
    dlg = InGamePopup(view, modal=True)
    try:
        dlg.title("Counter offer")
        dlg.geometry("440x430")
    except Exception:
        pass

    def _done(i):
        result['idx'] = i
        try:
            dlg.destroy()
        except Exception:
            pass

    ctk.CTkLabel(dlg, text="COUNTER OFFER",
                 font=("Segoe UI", 10, 'bold'),
                 text_color=DIM).pack(anchor='w', padx=16, pady=(12, 0))
    ctk.CTkLabel(dlg,
                 text=f"Demand one more pick from {caller.team_name}:",
                 font=("Segoe UI", 12, 'bold'),
                 text_color=TEXT, wraplength=400,
                 justify='left').pack(anchor='w', padx=16, pady=(0, 6))
    lb = tk.Listbox(dlg, height=10, activestyle='none',
                    bg=CARD, fg=TEXT, relief='flat',
                    highlightthickness=1, highlightbackground=DIM,
                    font=("Segoe UI", 11))
    for _o, _r, _dp in options:
        lb.insert(tk.END, f"#{_o} overall  (Round {_r})")
    lb.pack(fill='x', padx=16, pady=(0, 8))
    btnf = ctk.CTkFrame(dlg, fg_color="transparent")
    btnf.pack(fill='x', padx=16, pady=(0, 14))
    ctk.CTkButton(btnf, text="Never mind", width=120,
                  fg_color=CARD, text_color=TEXT,
                  command=lambda: _done(None)).pack(side='left')
    ctk.CTkButton(btnf, text="Demand pick", width=140,
                  fg_color=TEAL, text_color=BG,
                  font=("Segoe UI", 11, 'bold'),
                  command=lambda: _done(
                      lb.curselection()[0] if lb.curselection() else None)
                  ).pack(side='right')
    try:
        dlg.bind('<Escape>', lambda _e: _done(None))
    except Exception:
        pass
    try:
        view.wait_window(dlg)
    except Exception:
        pass
    if result['idx'] is None:
        return None
    _o, _r, extra = options[result['idx']]
    new_gives = list(gives) + [extra]
    try:
        resp = te.ai_consider_trade(caller, list(gets), list(new_gives),
                                    user_team=view.app.user_team)
    except Exception:
        return None
    decision = getattr(resp, 'decision', 'reject')
    if decision == 'reject':
        return None
    waiver_assets = []
    if decision == 'counter':
        # Fold the AI's answer once: assets it wants from the user, and
        # assets it will add from its own side (waiver-stamped for the
        # user's team).
        new_gets = list(gets) + list(
            getattr(resp, 'want_added', None) or [])
        _will = list(getattr(resp, 'will_add', None) or [])
        new_gives = list(new_gives) + _will
        waiver_assets.extend(_will)
    else:
        new_gets = list(gets)
    return (new_gives, new_gets, waiver_assets)


def incoming_offer_for_user(view):
    """War-room hook: the user's club is on the clock in round 1.

    The most motivated AI club may call with a trade-up offer. At most one
    modal per pick; declining never re-rings for that slot.
    """
    try:
        import trade_engine as te
    except Exception:
        return
    try:
        league = view.app.league
        year = league.season_year
        if view.current_pick >= len(view.draft_order):
            return
        if getattr(view, '_ddt_offered_pick', None) == view.current_pick:
            return
        view._ddt_offered_pick = view.current_pick
        rnd, team_on_clock, _dp = view.draft_order[view.current_pick]
        if rnd != 1 or team_on_clock != view.app.user_team:
            return
        if random.random() > 0.35:
            return
        try:
            ai_manager = view.app.ai_manager
        except Exception:
            ai_manager = None
        board = _draft_board(league)
        overall = view.current_pick + 1
        user_pick = _dp
        if user_pick is None:
            # find the pick object for this slot
            for o2, t2, pk2 in _round1_order(league, year):
                if o2 == overall:
                    user_pick = pk2
                    break
        if user_pick is None:
            return
        best = None
        for o2, t2, pk2 in _round1_order(league, year):
            if o2 <= overall or _is_human(t2):
                continue
            pname = _priority_name(_priority_of(t2, ai_manager))
            tgt = _trade_up_target(t2, o2, board, pname)
            if tgt is None:
                continue
            t_overall, prosp = tgt
            if t_overall != overall:
                continue
            mine = _owned_picks(t2, year, 1)
            if not mine:
                continue
            offer = _build_trade_up_offer(te, t2, mine[0], team_on_clock,
                                          year)
            if offer is None:
                continue
            gives, gets = offer
            # The AI has to actually want it at these terms.
            try:
                resp = te.ai_consider_trade(
                    team_on_clock, list(gives), list(gets), user_team=t2)
            except Exception:
                continue
            if getattr(resp, 'decision', 'reject') == 'reject':
                continue
            score = random.uniform(0, 1)
            if best is None or score > best[0]:
                best = (score, t2, gives, gets, prosp, resp)
        if best is None:
            return
        _s, caller, gives, gets, prosp, resp = best
        # Fold any AI counter into the terms BEFORE the user sees them:
        # the dialog must show exactly what accepting would execute.
        _waiver_assets = []  # will_add assets this negotiation stamped
        if getattr(resp, 'decision', '') == 'counter':
            _want_added = list(getattr(resp, 'want_added', None) or [])
            _will_added = list(getattr(resp, 'will_add', None) or [])
            gives = list(gives) + _want_added
            gets = list(gets) + _will_added
            _waiver_assets.extend(_will_added)

        # Gating T2-Phase 2: the call is a question card, not a blocking
        # dialog. Dismiss = safe default (decline). The draft clock
        # freezes while the call is parked (view._ddt_call_parked, checked
        # in _sp_clock_tick and process_draft_pick).
        from popup_system import (ask_card, cards_available,
                                  get_pending_session, register_pending_item,
                                  unregister_pending_item, PAUSES_DAY)
        _app = view.app
        _sess_id = f"draft_call:{overall}"
        _sess = get_pending_session(_app, _sess_id)
        _sess["kind"] = "draft_call"
        _sess["caller"] = caller.team_name
        _sess["overall"] = overall
        # Two ledgers: objects for the same-process scrub, ids in the
        # session for the save/load scrub (scrub_abandoned_waiver_stamps).
        _waiver_objs = list(_waiver_assets)
        _sess["waiver_assets"] = [str(getattr(_a, "id", ""))
                                  for _a in _waiver_objs]

        def _call_msg(_gives, _gets):
            _why = _call_why_lines(
                te, caller, prosp, board,
                _priority_name(_priority_of(caller, ai_manager)))
            _lines = ["\U0001f4de  INCOMING CALL -- " + caller.team_name,
                      _why.get('direction_short', ''),
                      "",
                      "WHY THEY'RE CALLING:"]
            _lines += ["\u2022  " + _b for _b in _why.get('bullets', [])]
            try:
                import scouting as _scmod
            except Exception:
                _scmod = None
            try:
                _tname = getattr(prosp, 'full_name', '?')
                _tpos = _pos_of(prosp)
                _tpot = _scmod.consensus_range(prosp) if _scmod else '?'
            except Exception:
                _tname, _tpos, _tpot = '?', '?', '?'
            _lines += ["",
                       f"THEIR TARGET: {_tname} ({_tpos}) -- "
                       f"consensus potential: {_tpot}",
                       "",
                       "YOU SEND:"]
            _lines += ["\u2022  " + te.asset_label(_a) for _a in _gets]
            _lines += ["", "YOU RECEIVE:"]
            _lines += ["\u2022  " + te.asset_label(_a) for _a in _gives]
            try:
                _v_in = sum(te.asset_value(_a) for _a in _gives)
                _v_out = sum(te.asset_value(_a) for _a in _gets)
                _share = (_v_in / (_v_in + _v_out)
                          if (_v_in + _v_out) > 0 else 0.5)
            except Exception:
                _share = 0.5
            _vlabel = ("Value favors you" if _share >= 0.55
                       else "Value favors them" if _share <= 0.45
                       else "Roughly fair value")
            _lines += ["", _vlabel]
            return "\n".join(str(_l) for _l in _lines)

        def _screen_id():
            try:
                return (getattr(_app, "_current_screen", None)
                        or {}).get("id")
            except Exception:
                return None

        def _unpark_call(_did):
            try:
                unregister_pending_item(_app, f"q:{_sess_id}:{_did}")
            except Exception:
                pass
            try:
                view._ddt_call_parked = False
            except Exception:
                pass

        def _resolve_call(choice, _gives, _gets, _from_card):
            _team_names = {caller.team_name,
                           _app.user_team.team_name}
            try:
                if choice != 'accept':
                    # Declined (or counter rejected): scrub single-use
                    # waivers the engine stamped while negotiating;
                    # pre-existing waivers for uninvolved teams stay.
                    _scrub_call_waivers(_waiver_objs, _team_names)
                    try:
                        view._ticker(f"{caller.team_name} called about "
                                     f"#{overall} -- no deal.")
                    except Exception:
                        pass
                    return
                # Accepted: run it through the engine like any draft deal.
                try:
                    done = te.execute_trade(
                        caller, team_on_clock, list(_gives), list(_gets),
                        _date_str(_app), league=league)
                except Exception:
                    done = None
                try:
                    _blocked = str(
                        getattr(done, 'summary', '') or ''
                    ).startswith('BLOCKED:')
                except Exception:
                    _blocked = True
                if done is None or _blocked:
                    _scrub_call_waivers(_waiver_objs, _team_names)
                    return
                # Same ownership propagation as _negotiate: the draft board
                # reads get_draft_order(), which resolves owners by list
                # membership.
                _sync_pick_lists(caller, team_on_clock,
                                 list(_gives), list(_gets))
                _sync_view_order(view, league)
                summary = (f"{_app.user_team.team_name} trades #{overall} "
                           f"overall to {caller.team_name}.")
                _record_deal(league, _app, summary)
                try:
                    view._ticker("TRADE: " + summary)
                except Exception:
                    pass
            finally:
                try:
                    _app.pending_sessions.pop(_sess_id, None)
                except Exception:
                    pass
                if _from_card:
                    # The outer process_draft_pick returned early on the
                    # parked flag: re-run it now that the call resolved.
                    try:
                        view.process_draft_pick()
                    except Exception:
                        pass

        def _call_answer(choice, _gives, _gets, _from_card):
            if choice == 'counter':
                _present_counter_card(_gives, _gets, _from_card)
                return
            _resolve_call(choice, _gives, _gets, _from_card)

        def _present_call_card(_gives, _gets, _from_card=True):
            _did = "call"
            _item_id = f"q:{_sess_id}:{_did}"
            _title = (f"\U0001f4de Incoming call: {caller.team_name} "
                      f"-- answer")
            _detail = (f"{caller.team_name} is calling about your "
                       f"#{overall} overall pick.")

            def _on_choice(ans):
                _unpark_call(_did)
                _call_answer(ans, _gives, _gets, _from_card)

            if not cards_available(view):
                # Headless: the old dialog defaulted to decline. Not from
                # a card, so the outer flow resumes on its own.
                _unpark_call(_did)
                _call_answer('decline', _gives, _gets, False)
                return
            view._ddt_call_parked = True
            register_pending_item(
                _app, _item_id, kind=PAUSES_DAY, title=_title,
                detail=_detail, screen_id=_screen_id())
            ask_card(view, "Incoming call", _call_msg(_gives, _gets),
                     [("Accept", "accept", "primary"),
                      ("Counter", "counter", "secondary"),
                      ("Decline", "decline", "secondary")],
                     on_answer=_on_choice, default_on_dismiss="decline",
                     session_id=_sess_id, dialog_id=_did,
                     resolver="draft_call_answer",
                     resolver_args={"overall": overall,
                                    "caller": caller.team_name})
            try:
                _sess["dialogs"][_did]["registry"] = {
                    "item_id": _item_id, "kind": PAUSES_DAY,
                    "title": _title, "detail": _detail,
                    "screen_id": _screen_id()}
            except Exception:
                pass

        def _present_counter_card(_gives, _gets, _from_card):
            # Counter path: the user demands one more of the caller's
            # later picks. One chained card; Never mind = decline.
            _options = []
            try:
                _order = view.draft_order
                for _idx in range(view.current_pick + 1, len(_order)):
                    _r, _t, _dp = _order[_idx]
                    if (_t == caller and _dp is not None
                            and not any(_dp is _g for _g in _gives)
                            and not any(_dp is _g for _g in _gets)):
                        _options.append((_idx + 1, _r, _dp))
            except Exception:
                pass
            _options = _options[:12]
            _did = "counter"
            _item_id = f"q:{_sess_id}:{_did}"
            _title = (f"\U0001f4de Counter: {caller.team_name} -- answer")
            _detail = (f"Demand one more pick from {caller.team_name} "
                       f"for #{overall} overall.")

            def _on_pick(idx):
                _unpark_call(_did)
                if idx is None:
                    _resolve_call('decline', _gives, _gets, _from_card)
                    return
                try:
                    _o, _r, _extra = _options[idx]
                except Exception:
                    _resolve_call('decline', _gives, _gets, _from_card)
                    return
                _new_gives = list(_gives) + [_extra]
                try:
                    _resp = te.ai_consider_trade(
                        caller, list(_gets), list(_new_gives),
                        user_team=_app.user_team)
                except Exception:
                    _resp = None
                _decision = getattr(_resp, 'decision', 'reject')
                if _decision == 'reject':
                    _resolve_call('decline', _gives, _gets, _from_card)
                    return
                _new_gets = list(_gets)
                if _decision == 'counter':
                    # Fold the AI's answer once: assets it wants from the
                    # user, and assets it will add from its own side
                    # (waiver-stamped for the user's team).
                    _new_gets = _new_gets + list(
                        getattr(_resp, 'want_added', None) or [])
                    _will = list(getattr(_resp, 'will_add', None) or [])
                    _new_gives = _new_gives + _will
                    _waiver_objs.extend(_will)
                    _sess["waiver_assets"] = [
                        str(getattr(_a, "id", "")) for _a in _waiver_objs]
                _present_call_card(_new_gives, _new_gets,
                                  _from_card=_from_card)

            if not cards_available(view):
                # Headless: never mind. Not from a card, so the outer
                # flow resumes on its own.
                _unpark_call(_did)
                _resolve_call('decline', _gives, _gets, False)
                return
            view._ddt_call_parked = True
            _buttons = [(f"#{_o} overall  (Round {_r})", _i, "secondary")
                        for _i, (_o, _r, _dp) in enumerate(_options)]
            _buttons.append(("Never mind", None, "secondary"))
            register_pending_item(
                _app, _item_id, kind=PAUSES_DAY, title=_title,
                detail=_detail, screen_id=_screen_id())
            ask_card(view, "Counter offer",
                     f"Demand one more pick from {caller.team_name}:",
                     _buttons, on_answer=_on_pick,
                     default_on_dismiss=None,
                     session_id=_sess_id, dialog_id=_did,
                     resolver="draft_call_answer",
                     resolver_args={"overall": overall,
                                    "caller": caller.team_name,
                                    "counter": True})
            try:
                _sess["dialogs"][_did]["registry"] = {
                    "item_id": _item_id, "kind": PAUSES_DAY,
                    "title": _title, "detail": _detail,
                    "screen_id": _screen_id()}
            except Exception:
                pass

        _present_call_card(list(gives), list(gets), _from_card=True)
    except Exception:
        pass
