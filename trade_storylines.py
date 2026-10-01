# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Storyline-aware trade context (additive).

Computes situational modifiers for the AI trade logic from live league
state: standings stance (buyer/seller), streaks, rivalries, and deadline
urgency. Everything here is a *nudge* on top of trade_engine's core
evaluation -- the ratio/needs/greed logic is untouched. Neutral default
(greed_mult 1.0, no notes) means no behavior change when storylines are
absent or unavailable.
"""


# Tuning (conservative: storylines whisper, they don't shout)
_BUYER_MULT = 0.92        # contender: will overpay a little to win now
_SELLER_MULT = 0.95       # seller: eager to move pieces for futures
_BUBBLE_MULT = 0.97       # playoff bubble: slight buyer lean
_LOSING_STREAK_MULT = 0.95  # 4+ losses: shake-up urgency
_WINNING_STREAK_MULT = 1.05  # 5+ wins: don't fix what isn't broken
_DEADLINE_BUYER_DROP = 0.10  # max extra buyer desperation at 3 PM
_DEADLINE_SELLER_DROP = 0.06


def _league(app):
    gm = getattr(app, 'game_manager', None)
    return getattr(gm, 'league', None) or getattr(app, 'league', None)


def _standings_rows(app):
    league = _league(app)
    try:
        st = getattr(league, 'standings', {}) or {}
    except Exception:
        return []
    rows = []
    for name, rec in st.items():
        try:
            pts = int(rec.get('Points', rec.get('points', 0)))
        except Exception:
            pts = 0
        rows.append((name, pts))
    rows.sort(key=lambda r: r[1], reverse=True)
    return rows


def _conference_of(app, team_name):
    league = _league(app)
    try:
        for t in getattr(league, 'teams', []):
            if getattr(t, 'team_name', None) == team_name:
                return getattr(t, 'conference', None)
    except Exception:
        pass
    return None


def stance(app, team_name):
    """'buyer' | 'seller' | 'bubble' | 'neutral' from conference rank."""
    rows = _standings_rows(app)
    if not rows:
        return 'neutral'
    conf = _conference_of(app, team_name)
    if conf:
        names = [n for n, _ in rows
                 if _conference_of(app, n) == conf]
    else:
        names = [n for n, _ in rows]
    if team_name not in names:
        return 'neutral'
    rank = names.index(team_name)  # 0-based
    pts = dict(rows).get(team_name, 0)
    # playoff line: 8th in conference (~16 teams)
    line_pts = 0
    if len(names) >= 8:
        line_pts = dict(rows).get(names[7], 0)
    if rank < 4:
        return 'buyer'
    if len(names) - rank <= 5:
        return 'seller'
    if abs(pts - line_pts) <= 6:
        return 'bubble'
    return 'neutral'


def _streak(app, team_name):
    """Signed streak: +N wins / -N losses, 0 if unknown."""
    league = _league(app)
    try:
        results = getattr(league, 'game_results', []) or []
    except Exception:
        return 0
    streak = 0
    for g in reversed(results):
        try:
            home = g.get('home_team', g.get('home'))
            away = g.get('away_team', g.get('away'))
            if team_name not in (home, away):
                continue
            hs = g.get('home_score', g.get('home_goals'))
            aws = g.get('away_score', g.get('away_goals'))
            if hs is None or aws is None:
                continue
            won = (hs > aws and home == team_name) or \
                  (aws > hs and away == team_name)
            if streak == 0:
                streak = 1 if won else -1
            elif (won and streak > 0) or (not won and streak < 0):
                streak += 1 if won else -1
            else:
                break
        except Exception:
            continue
    return streak


def _rivalry_intensity(app, team_a, team_b):
    """0-100 team-vs-team rivalry intensity, 0 if none."""
    league = _league(app)
    try:
        rivalries = getattr(league, 'rivalries', []) or []
    except Exception:
        return 0
    best = 0
    for r in rivalries:
        try:
            kind = str(r.get('kind', ''))
            if 'team' not in kind:
                continue
            names = {str(r.get('a_name', '')), str(r.get('b_name', '')),
                     str(r.get('a', '')), str(r.get('b', ''))}
            if team_a in names and team_b in names:
                best = max(best, int(r.get('intensity', 0)))
        except Exception:
            continue
    return best


def _deadline_progress(app):
    try:
        from trade_deadline_manager import get_deadline_manager
        mgr = get_deadline_manager(getattr(app, 'game_manager', None))
        if mgr.clock_active():
            return mgr.clock_progress()
    except Exception:
        pass
    return 0.0


def situational_context(app, team, partner=None):
    """Additive trade context for one AI team.

    Returns {'greed_mult': float, 'notes': [str]}. Multiply the AI's greed
    threshold by greed_mult: < 1 = more eager to deal, > 1 = drives a
    harder bargain.

    Also carries 'rivalry_intensity01' (0..1, Wave B D40 gate) and 'stance'
    ('buyer'/'seller'/'bubble'/'neutral', Wave B D40/D42) -- "" / 0.0 when
    the caller has no app context.
    """
    ctx = {'greed_mult': 1.0, 'notes': []}
    try:
        name = getattr(team, 'team_name', '')
        if not name:
            return ctx

        mult = 1.0
        notes = []

        # Standings stance: contenders buy, cellar teams sell
        st = stance(app, name)
        # Wave B (D40/D42): the stance itself, for the rivalry gate and the
        # stinginess pass. Additive key -- "" when unknown.
        try:
            ctx['stance'] = str(st or "")
        except Exception:
            ctx['stance'] = ""
        if st == 'buyer':
            mult *= _BUYER_MULT
            notes.append('buying for a Cup run')
        elif st == 'seller':
            mult *= _SELLER_MULT
            notes.append('selling')
        elif st == 'bubble':
            mult *= _BUBBLE_MULT
            notes.append('in the playoff hunt')

        # Streaks: losing skids force shake-ups; win streaks breed patience
        sk = _streak(app, name)
        if sk <= -4:
            mult *= _LOSING_STREAK_MULT
            notes.append(f'{abs(sk)}-game skid -- shake-up urgency')
        elif sk >= 5:
            mult *= _WINNING_STREAK_MULT
            notes.append(f'{sk}-game win streak -- no need to tinker')

        # Rivalries: priced by the Wave B circumstantial gate
        # (trade_engine.rivalry_trade_gate -- open / taxed / closed), not
        # here. The note stays so the talking points can name the bad
        # blood; the gate owns the number, on both the direct and market
        # paths. (B41's old +2% mirror retired with the gate.)
        if partner is not None:
            pname = getattr(partner, 'team_name', '')
            inten = _rivalry_intensity(app, name, pname)
            # Wave B (D40): the raw intensity, 0..1, for the circumstantial
            # rivalry gate in trade_engine (open / taxed / closed). Additive
            # key -- 0.0 when the caller has no app context (gate stays
            # open, never blocks blind).
            try:
                ctx['rivalry_intensity01'] = max(
                    0.0, min(1.0, float(inten) / 100.0))
            except Exception:
                ctx['rivalry_intensity01'] = 0.0
            if inten >= 50:
                notes.append('bitter rivals -- premium demanded')

        # GM stature: the league judges YOU. Personal gm_gm heat was
        # invisible here (only team_team counted) -- a GM you burned
        # taxes you harder than any team rivalry. Stature moves the
        # needle softly: respect earns a small discount, a clown
        # reputation gets you squeezed. Additive; the clamp below keeps
        # it a whisper.
        if partner is not None:
            try:
                import reputation_system as _rs
                _gmult, _gnotes = _rs.gm_trade_greed_mult(
                    _league(app), partner, team)
                mult *= _gmult
                notes.extend(_gnotes)
            except Exception:
                pass

        # Deadline rush: as 3 PM nears, buyers get desperate, sellers deal
        prog = _deadline_progress(app)
        if prog > 0:
            if st in ('buyer', 'bubble'):
                mult *= (1.0 - _DEADLINE_BUYER_DROP * prog)
                if prog > 0.66:
                    notes.append('deadline looming -- getting desperate')
            elif st == 'seller':
                mult *= (1.0 - _DEADLINE_SELLER_DROP * prog)

        # Clamp: storylines whisper, never shout
        mult = max(0.80, min(1.30, mult))
        ctx['greed_mult'] = mult
        ctx['notes'] = notes
        return ctx
    except Exception:
        return ctx


def ai_initiative_odds(app, team):
    """How likely is this AI team to *start* a trade (deadline week)?

    Returns 0.0-1.0. Buyers and desperate teams shop; win-streak teams
    and rivals of the user mostly stand pat.
    """
    try:
        st = stance(app, getattr(team, 'team_name', ''))
        base = {'buyer': 0.55, 'bubble': 0.35, 'seller': 0.45,
                'neutral': 0.15}.get(st, 0.15)
        sk = _streak(app, getattr(team, 'team_name', ''))
        if sk <= -4:
            base += 0.15
        prog = _deadline_progress(app)
        base += 0.25 * prog  # everyone shops more as 3 PM nears
        return max(0.05, min(0.9, base))
    except Exception:
        return 0.15
