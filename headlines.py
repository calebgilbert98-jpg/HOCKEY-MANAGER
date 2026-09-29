"""League headline / lore system.

Rare, high-drama events -- line brawls, trade requests, blockbuster deals --
become news-feed stories AND inbox emails so the league's narrative develops
in front of the user. FM24/EHM-inspired:

- The NEWS FEED carries the league-wide story (every brawl, every saga).
- The INBOX carries what matters to YOUR club, flagged important when your
  team is involved.

Headline emails expire after HEADLINE_TTL_DAYS game-days. They never linger
past that unless the user explicitly SAVES one ("save for later") or it marks
a major milestone for the user's own team (your brawl, your star asking out,
your Cup).

Anti-flood / performance design (the game must stay fast):
- Only genuinely rare events enter this system. Nothing per-game routine,
  nothing per-player routine.
- DAILY_HEADLINE_CAP is a safety valve: no more than a few headlines per
  game-day, no matter what.
- prune_expired() runs once per day-advance: O(inbox size), no scans on load.
- The news feed itself is capped (NEWS_LOG_CAP) so the log can't grow
  unbounded across seasons.
"""

from datetime import date
from typing import (Any, Dict, Optional, Tuple)

HEADLINE_TTL_DAYS = 7          # news items live 7 game-days unless saved/milestone
DAILY_HEADLINE_CAP = 4         # safety valve: max headlines delivered per game-day
NEWS_LOG_CAP = 500            # news feed keeps the 500 most recent stories
TRADE_REQUEST_MONTHLY_CAP = 2  # league-wide trade-request fires per month, max


# ---------------------------------------------------------------------------
# Builders: event kind -> EmailMessage (a "headline")
# ---------------------------------------------------------------------------

def make_headline(kind: str, game_date: date, **kw) -> Optional["EmailMessage"]:
    """Build a headline EmailMessage for a rare event. Returns None for
    unknown kinds. The message carries news_ttl_days=7 and the game date it
    was sent so the inbox can expire it."""
    from game_classes import EmailMessage

    builders = {
        "line_brawl": _brawl_headline,
        "line_brawl_quick": _quick_brawl_headline,
        "trade_request": _trade_request_headline,
        "star_injury": _star_injury_headline,
        "blockbuster_trade": _blockbuster_headline,
        "coaching_change": _coaching_change_headline,
        "rivalry_declared": _rivalry_declared_headline,
        "controversial_call": _controversial_call_headline,
        "media_fine": _media_fine_headline,
        "suspension": _suspension_headline,
        "media_beef": _media_beef_headline,
        "narrative_shutdown": _narrative_shutdown_headline,
        "grudge_callback": _grudge_callback_headline,
        "game_story": _game_story_headline,
        "outdoor_pregame": _outdoor_pregame_headline,
        "milestone_hit": _milestone_headline,
        "lottery_results": _lottery_headline,
        "international_results": _intl_headline,
    }
    fn = builders.get(kind)
    if fn is None:
        return None
    msg = fn(game_date, **kw)
    if msg is not None:
        msg.news_ttl_days = HEADLINE_TTL_DAYS
        msg.game_date_sent = game_date
        msg.date_sent = game_date  # game-world email: show the game date
    return msg


def _quick_brawl_headline(game_date, home="", away="", home_score=0,
                          away_score=0, **kw):
    """League headline for a line brawl in a quick-simmed game: no live
    pair data, so the story is told from the scoresheet and the bad
    blood, not the play-by-play."""
    from game_classes import EmailMessage
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🥊 LINE BRAWL: {away} at {home}",
        content=(
            f"It turned ugly in {home} late in the game. With the score "
            f"{away} {away_score}, {home} {home_score}, the gloves came "
            f"off all over the ice -- multiple fights at once, both "
            f"benches emptying onto the fringes.\n\n"
            f"Every skater involved was handed a 10-minute misconduct, "
            f"the NHL's standard answer to a line brawl. The league says "
            f"it will review the incident, but no suspensions are "
            f"expected.\n\n"
            f"Circle the rematch on the calendar. These two won't have "
            f"forgotten."
        ),
        category="League",
        priority=3,
        is_important=True,
    )


def _brawl_headline(game_date, home, away, pairs, home_score=0,
                    away_score=0, period=3, **kw):
    from game_classes import EmailMessage
    pair_names = ", ".join(f"{h} vs {a}" for h, a in (pairs or []))
    pim = len(pairs or []) * 10 + 20  # rough: fighting majors + misconducts
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🥊 LINE BRAWL: {away} at {home}",
        content=(
            f"It turned ugly in {home} late in the game. With the score "
            f"{away} {away_score}, {home} {home_score}, {len(pairs or [])} "
            f"pairs dropped the gloves at once -- {pair_names}.\n\n"
            f"Every skater on the ice was handed a 10-minute misconduct. "
            f"An estimated {pim} penalty minutes in one sequence. The league "
            f"says it will review the incident, but no suspensions are "
            f"expected -- this is how the NHL handles line brawls.\n\n"
            f"Circle the rematch on the calendar. These two won't have "
            f"forgotten."
        ),
        category="League",
        priority=3,
        is_important=True,
    )


def _trade_request_headline(game_date, player_name, team_name, age=None,
                            position=None, overall=None, reason=None, **kw):
    from game_classes import EmailMessage
    detail = f"{position}, {age}" if position and age else (position or "")
    why = f" {reason}" if reason else ""
    return EmailMessage(
        sender="League Insider",
        sender_type="Media",
        subject=f"📣 {player_name} has requested a trade from {team_name}",
        content=(
            f"{player_name} ({detail}) has formally asked {team_name} for a "
            f"trade.{why}\n\n"
            f"Sources say the relationship has been strained for weeks. "
            f"Expect the phones to start ringing -- a player of this calibre "
            f"doesn't hit the market quietly."
        ),
        category="Trade",
        priority=3,
        is_important=True,
    )


def _star_injury_headline(game_date, player_name, team_name, injury=None,
                          out_weeks=None, **kw):
    from game_classes import EmailMessage
    timeline = f" -- out roughly {out_weeks} weeks" if out_weeks else ""
    what = f" ({injury})" if injury else ""
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🚑 {player_name} ({team_name}) sidelined{what}",
        content=(
            f"Brutal news for {team_name}: {player_name} is expected to miss "
            f"significant time{what}{timeline}.\n\n"
            f"The playoff race just shifted."
        ),
        category="Injuries",
        priority=3,
        is_important=True,
    )


def _blockbuster_headline(game_date, team_a, team_b, pieces_a, pieces_b, **kw):
    from game_classes import EmailMessage
    return EmailMessage(
        sender="League Insider",
        sender_type="Media",
        subject=f"🔁 BLOCKBUSTER: {team_a} and {team_b} complete major trade",
        content=(
            f"{team_a} receive: {pieces_a}\n"
            f"{team_b} receive: {pieces_b}\n\n"
            f"The landscape of the league just changed."
        ),
        category="Trade",
        priority=3,
        is_important=True,
    )


def _coaching_change_headline(game_date, team_name, coach_name,
                              change="fired", **kw):
    from game_classes import EmailMessage
    if change == "reprieve":
        return EmailMessage(
            sender="League News Desk",
            sender_type="Media",
            subject=f"📋 {team_name}: vote of confidence for {coach_name}",
            content=(
                f"{team_name} ownership publicly backed {coach_name} today, "
                f"calling him \"our coach\" -- the dreaded vote of confidence. "
                f"He bought himself another month. The room -- and the "
                f"fanbase -- will be watching very closely."
            ),
            category="League",
            priority=2,
        )
    verb = "has been relieved of his duties" if change == "fired" else \
        "has been named head coach"
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"📋 {team_name}: {coach_name} {verb}",
        content=(
            f"{team_name} announced today that {coach_name} {verb}.\n\n"
            f"The room -- and the fanbase -- will be watching the next "
            f"ten games very closely."
        ),
        category="League",
        priority=2,
    )


def _rivalry_declared_headline(game_date, declarer_name, target_name,
                               target_kind="team", **kw):
    from game_classes import EmailMessage
    if target_kind == "coach":
        subject = (f"\U0001f525 {declarer_name} GM publicly declares "
                   f"{target_name} a personal rival")
        content = (
            f"The {declarer_name} general manager didn't mince words today, "
            f"publicly declaring {target_name} a personal rival.\n\n"
            f"\"It's not about the standings. It's about him. Every time we "
            f"play his team, my guys will know.\"\n\n"
            f"Coaches around the league called it \"rare and spicy\". The next "
            f"meeting just got a lot more interesting."
        )
    else:
        subject = (f"\U0001f525 {declarer_name} declares {target_name} "
                   f"the enemy")
        content = (
            f"The {declarer_name} general manager drew a line in the sand "
            f"today, publicly declaring the {target_name} the team's sworn "
            f"rivals.\n\n"
            f"\"Circle those dates. Our fans deserve games that mean "
            f"something, and from now on, these do.\"\n\n"
            f"Ticket offices on both sides are already reporting a spike for "
            f"the next meeting."
        )
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=subject,
        content=content,
        category="League",
        priority=2,
    )


def _controversial_call_headline(game_date, event="disallowed_goal",
                                 scoring_team="", defending_team="",
                                 shooter="", call_kind="goaltender interference",
                                 period=3, home_score=0, away_score=0, **kw):
    from game_classes import EmailMessage
    if event == "disallowed_goal":
        subject = (f"🚨 {defending_team} survive review -- {shooter}'s goal "
                   f"wiped off the board")
        content = (
            f"A {shooter} goal for the {scoring_team} was disallowed after a "
            f"coach's challenge for {call_kind} in period {period}, and the "
            f"{defending_team} bench erupted.\n\n"
            f"\"That's as clear as it gets,\" one assistant coach said. \"You "
            f"can't do that to a goaltender and expect it to count.\"\n\n"
            f"The {scoring_team} room, meanwhile, looked stunned -- a goal "
            f"taken off the board this late changes everything."
        )
    else:  # failed_challenge
        subject = (f"🚨 Failed challenge burns {defending_team} -- "
                   f"delay-of-game minor after {shooter}'s goal stands")
        content = (
            f"The {defending_team} challenged {shooter}'s goal for {call_kind} in "
            f"period {period}, lost, and paid the real price: a delay-of-game "
            f"minor with the goal still counting.\n\n"
            f"\"You only throw that flag if you're sure,\" a rival coach said. "
            f"\"They weren't sure. Now they're killing a penalty instead of "
            f"playing hockey.\"\n\n"
            f"Whether the {defending_team} room rallies or folds from here "
            f"will say everything about their leadership."
        )
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=subject,
        content=content,
        category="League",
        priority=2,
    )


def _media_fine_headline(game_date, name="", team="", amount=0,
                         reason="", role="player", **kw):
    from game_classes import EmailMessage
    amt = f"${int(amount):,}"
    who = f"{role} {name}" if role == "coach" else name
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"💸 FINED: {name} ({team}) -- {amt}",
        content=(
            f"The league has fined {who} {amt} for {reason}.\n\n"
            f"No suspension -- just the wallet getting lighter. The {team} "
            f"had no further comment."
        ),
        category="League",
        priority=3,
        is_important=True,
    )


def _suspension_headline(game_date, name="", team="", games=0,
                         victim="", **kw):
    from game_classes import EmailMessage
    try:
        _g = int(games)
    except Exception:
        _g = 0
    _plural = "" if _g == 1 else "s"
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🚫 SUSPENDED: {name} ({team}) -- {_g} game{_plural}",
        content=(
            f"The league has suspended {name} {_g} game{_plural} for "
            f"an illegal hit on {victim}.\n\n"
            f"Department of Player Safety ruling: the hit was late and "
            f"targeted the head. {name} is eligible to return once the "
            f"games are served -- the {team} will have to fill the hole "
            f"in the lineup. No further comment from the club."
        ),
        category="League",
        priority=2,
        is_important=True,
    )


def _media_beef_headline(game_date, coach="", reporter="", team="",
                         level=1, **kw):
    from game_classes import EmailMessage
    heat = {1: ("TESTY", "Things got testy"),
            2: ("HEATED", "It got heated"),
            3: ("CIRCUS", "Full circus")}[min(3, int(level))]
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🎙️ {heat[0]}: {coach} vs {reporter}",
        content=(
            f"{heat[1]} between {team} coach {coach} and reporter "
            f"{reporter} after the game. The exchange lasted well past the "
            f"usual two questions, and neither side was smiling walking "
            f"away.\n\n"
            f"This is the latest chapter in a running feud -- the room is "
            f"starting to notice."
        ),
        category="League",
        priority=3,
        is_important=True,
    )


def _narrative_shutdown_headline(game_date, player="", team="",
                                 reporter="", narrative="", quote="",
                                 **kw):
    from game_classes import EmailMessage
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🎙️ {player} shuts down the {narrative} talk",
        content=(
            f"Asked about the {narrative} story by {reporter}, {player} "
            f"({team}) ended it on the spot:\n\n{quote}\n\n"
            f"The clip is everywhere tonight. That narrative is dead."
        ),
        category="League",
        priority=2,
        is_important=True,
    )


def _epithet_line(epithet):
    """One tag-colored line for a game-story email. Graceful: the caller
    only passes a non-empty epithet."""
    if epithet == "Mr. Game 7":
        return ("The man they call \"Mr. Game 7\" delivers when it matters "
                "most.")
    return f"The {epithet} delivers when it matters most."


def _game_story_headline(game_date, story_kind="", text="",
                         home="", away="", epithet="", **kw):
    """A night worth remembering: hat trick, shutout, steal, blowout,
    OT thriller. Delivered only for the user's games.

    epithet (additive): a clutch tag label ("Mr. Game 7" / "Playoff
    Performer") for the story's subject player -- appended as a
    tag-colored line. Empty (the common case) leaves the story exactly
    as before."""
    from game_classes import EmailMessage
    _emoji = {"hat_trick": "🎩", "shutout": "🧱", "goalie_steal": "🥅",
              "blowout": "💥", "ot_thriller": "⚡"}.get(story_kind, "🏒")
    subject = f"{_emoji} {_label(story_kind)}: {away} @ {home}"
    content = f"{text}\n\nSome nights are bigger than the score."
    if epithet:
        content = (f"{text}\n\n{_epithet_line(epithet)}\n\n"
                   f"Some nights are bigger than the score.")
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=subject,
        content=content,
        category="Game Story",
        priority=2,
    )


def _label(story_kind):
    return {"hat_trick": "Hat trick", "shutout": "Shutout",
            "goalie_steal": "Goalie steal", "blowout": "Statement win",
            "ot_thriller": "OT thriller"}.get(story_kind, "Big night")


def _grudge_callback_headline(game_date, home="", away="", short="",
                              room_line="", fans_line="", media_line="",
                              league_line="", first_meeting=True, **kw):
    """'First meeting since the hit' — the incident callback card.

    One event, four viewpoints: the disagreement is the story. The league
    only speaks when the event was large enough (league_line empty otherwise).
    """
    from game_classes import EmailMessage
    hook = ("First meeting since" if first_meeting
            else "Another chapter in")
    subject = f"🥊 {hook} {short}: {away} @ {home}"
    parts = [f"{hook} {short}, {away} visit {home} tonight.\n"]
    if media_line:
        parts.append(f"MEDIA — {media_line}")
    if room_line:
        parts.append(f"ROOM — {room_line}")
    if fans_line:
        parts.append(f"FANS — {fans_line}")
    if league_line:
        parts.append(f"LEAGUE — {league_line}")
    parts.append("\nThe disagreement is the story.")
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=subject,
        content="\n\n".join(parts),
        category="Rivalry",
        priority=2,
        is_important=True,
    )


def _outdoor_pregame_headline(game_date, event="", host="", away="",
                              venue_line="", alumni_line="", rivalry_line="",
                              **kw):
    """Winter Classic / Stadium Series pre-game billing card."""
    from game_classes import EmailMessage
    subject = f"🏟️ {event}: {away} @ {host} -- outdoors"
    parts = [f"{venue_line}\n"]
    if rivalry_line:
        parts.append(rivalry_line)
    if alumni_line:
        parts.append(alumni_line)
    parts.append("\nPuck drop under the open sky. The loudest night of the "
                 "regular season.")
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=subject,
        content="\n\n".join(parts),
        category="Spectacle",
        priority=2,
        is_important=True,
    )


def _lottery_headline(game_date, year=0, summary="", watch_hint=True, **kw):
    """Draft lottery results card. Subject carries the 🎰 DRAFT LOTTERY
    marker so the inbox can offer the watch-the-reveal action."""
    from game_classes import EmailMessage
    content = summary
    if watch_hint:
        content += ("\n\nSelect this message and hit WATCH THE REVEAL for the "
                    "full televised countdown, 16 to 1.")
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🎰 DRAFT LOTTERY {year}: results are in",
        content=content,
        category="League",
        priority=3,
        is_important=True,
    )


def _intl_headline(game_date, title="", year=0, summary="", **kw):
    """International tournament results card (Olympics / Worlds)."""
    from game_classes import EmailMessage
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=f"🏅 {title} {year}: {summary.splitlines()[0] if summary else 'final'}",
        content=summary,
        category="League",
        priority=2,
        is_important=True,
    )


def _milestone_headline(game_date, player="", milestone="", team="",
                        room_line="", fans_line="", media_line="",
                        league_line="", **kw):
    """A career milestone, one event through four viewpoints."""
    from game_classes import EmailMessage
    subject = f"⭐ {player}: {milestone}"
    parts = [f"{player} ({team}) reaches {milestone}.\n"]
    if media_line:
        parts.append(f"MEDIA — {media_line}")
    if room_line:
        parts.append(f"ROOM — {room_line}")
    if fans_line:
        parts.append(f"FANS — {fans_line}")
    if league_line:
        parts.append(f"LEAGUE — {league_line}")
    parts.append("\nSome nights are bigger than the score.")
    return EmailMessage(
        sender="League News Desk",
        sender_type="Media",
        subject=subject,
        content="\n\n".join(parts),
        category="Milestone",
        priority=2,
        is_important=True,
    )


def announce_rivalry_declaration(app, declarer_team_name, target_team_name,
                                 target_label, target_kind="team") -> bool:
    """Build + deliver the 'declared rival' headline. Both GMs involved get
    milestone copies; every human manager gets the news. Returns delivered."""
    game_date = getattr(app, "current_date", None) or date.today()
    msg = make_headline("rivalry_declared", game_date,
                        declarer_name=declarer_team_name,
                        target_name=target_label, target_kind=target_kind)
    if msg is None:
        return False
    return deliver(app, msg, involved=(declarer_team_name, target_team_name))


# ---------------------------------------------------------------------------
# Delivery
# ---------------------------------------------------------------------------

def _daily_count(app, game_date) -> Tuple[dict, int]:
    """(tracker_dict, count_used_today) for the DAILY_HEADLINE_CAP valve."""
    tracker = getattr(app, "_headline_daily", None)
    if not isinstance(tracker, dict) or tracker.get("date") != game_date:
        tracker = {"date": game_date, "count": 0}
        app._headline_daily = tracker
    return tracker, tracker["count"]


def _team_name(team) -> str:
    return getattr(team, "team_name", getattr(team, "name", "")) if team else ""


def human_teams(app):
    """Every human-managed team: the local user_team plus any teams claimed
    by connected multiplayer clients. Single-player returns [user_team]."""
    teams, seen = [], set()

    def _add(t):
        if t is None or id(t) in seen:
            return
        seen.add(id(t))
        teams.append(t)

    _add(getattr(app, "user_team", None))
    claimed = []
    host = getattr(app, "mp_host", None)
    if host is not None:
        try:
            claimed = host.claimed_teams()
        except Exception:
            claimed = []
    if claimed:
        gm = getattr(app, "game_manager", None)
        league = getattr(gm, "league", None) or getattr(app, "league", None)
        # Match claimed ids against every plausible team identifier (full
        # name, abbreviation, short name, id), case-insensitively. A claim
        # is a claim no matter which id format the lobby hands out, so a
        # future lobby change can never silently drop a human manager
        # from headline fan-out.
        wanted = {str(c).strip().lower() for c in claimed if c}
        for t in getattr(league, "teams", []) or []:
            ids = {
                str(_team_name(t)).strip().lower(),
                str(getattr(t, "abbreviation", "") or "").strip().lower(),
                str(getattr(t, "name", "") or "").strip().lower(),
                str(getattr(t, "id", "") or "").strip().lower(),
            }
            ids.discard("")
            if ids & wanted:
                _add(t)
    return teams


def deliver(app, msg, involved=()) -> bool:
    """Deliver a headline: news feed always, inbox for every human manager.

    involved: team names touched by the event. Each human manager whose team
    is among them gets the email flagged is_milestone (never auto-expires)
    and important; everyone else gets a normal 7-day copy.
    Returns True if delivered, False if the daily cap blocked it.
    """
    import copy
    import uuid
    from game_classes import EmailMessage
    if not isinstance(msg, EmailMessage):
        return False
    game_date = getattr(app, "current_date", None) or date.today()
    tracker, used = _daily_count(app, game_date)
    if used >= DAILY_HEADLINE_CAP:
        return False

    involved = tuple(involved or ())

    # News feed: the league-wide lore, one line.
    try:
        feed_line = f"{msg.subject}"
        app.add_news(feed_line)
    except Exception:
        pass

    # Inbox: every human manager gets their own copy (per-team milestone).
    delivered = 0
    for team in human_teams(app):
        try:
            inbox = team.inbox
            team_copy = copy.deepcopy(msg)
            team_copy.id = str(uuid.uuid4())
            if _team_name(team) in involved:
                team_copy.is_milestone = True
                team_copy.is_important = True
            inbox.add_message(team_copy)
            delivered += 1
        except Exception:
            continue
    if not delivered:
        return False
    tracker["count"] = used + 1
    return True


def deliver_spec(app, spec: Dict[str, Any]) -> bool:
    """Build + deliver from a pending spec dict (kind + kwargs)."""
    game_date = getattr(app, "current_date", None) or date.today()
    kind = spec.get("kind", "")
    msg = make_headline(kind, game_date, **{k: v for k, v in spec.items()
                                            if k != "kind"})
    if msg is None:
        return False
    return deliver(app, msg, involved=spec.get("involved", ()))


def drain_sim_headlines(app, sim) -> int:
    """Deliver headlines a finished GameSim collected (brawls, ...)."""
    pending = list(getattr(sim, "pending_headlines", None) or [])
    try:
        sim.pending_headlines = []
    except Exception:
        pass
    n = 0
    for spec in pending:
        try:
            if deliver_spec(app, spec):
                n += 1
        except Exception:
            continue
    return n


def drain_bracket_headlines(app, bracket) -> int:
    """Deliver headlines stashed by PlayoffBracket.simulate_playoff_game."""
    pending = list(getattr(bracket, "_pending_headlines", None) or [])
    try:
        bracket._pending_headlines = []
    except Exception:
        pass
    n = 0
    for spec in pending:
        try:
            if deliver_spec(app, spec):
                n += 1
        except Exception:
            continue
    return n


# ---------------------------------------------------------------------------
# Trade-request generator (monthly, rare by design)
# ---------------------------------------------------------------------------

def monthly_trade_request_check(app) -> int:
    """Roll monthly trade requests using the reputation risk model.

    Rare by construction: only unhappy/volatile players (risk >= 0.45) roll,
    and the league-wide monthly cap keeps it to a couple of sagas at most.
    Headlines go out for notable players; depth players just get the flag
    set for the trade AI to notice later.
    Returns the number of requests fired.
    """
    import random
    try:
        from reputation_system import trade_request_risk, ensure_reputation_fields
    except Exception:
        return 0
    league = getattr(app, "league", None)
    teams = getattr(league, "teams", None) or []
    game_date = getattr(app, "current_date", None) or date.today()

    fired = 0
    for team in teams:
        if fired >= TRADE_REQUEST_MONTHLY_CAP:
            break
        if getattr(team, "league_name", "National Hockey League") != \
                "National Hockey League":
            continue
        try:
            win_pct = _team_win_pct(team)
        except Exception:
            win_pct = 0.5
        roster = list(getattr(team, "roster", None) or [])
        random.shuffle(roster)
        for player in roster:
            if fired >= TRADE_REQUEST_MONTHLY_CAP:
                break
            try:
                if getattr(player, "transfer_requested", False):
                    continue
                ensure_reputation_fields(player)
                risk = trade_request_risk(
                    player, {"win_pct": win_pct,
                             "team_name": getattr(team, "team_name", "")})
                if risk < 0.45:
                    continue
                if random.random() < (risk - 0.35) * 0.5:
                    player.transfer_requested = True
                    fired += 1
                    if _is_notable(player):
                        _headline_trade_request(app, game_date, player, team)
            except Exception:
                continue
    return fired


def _team_win_pct(team) -> float:
    w = getattr(team, "wins", 0) or 0
    l = getattr(team, "losses", 0) or 0
    t = getattr(team, "ties", 0) or 0
    otl = getattr(team, "otl", 0) or 0
    gp = w + l + t + otl
    return (w + 0.5 * t) / gp if gp else 0.5


def _is_notable(player) -> bool:
    """Headline-worthy: established NHLer, not roster filler."""
    try:
        ovr = player.overall_rating() if callable(
            getattr(player, "overall_rating", None)) else 0
    except Exception:
        ovr = 0
    rep = getattr(player, "reputation", 0) or 0
    return (ovr or 0) >= 74 or rep >= 55


def _headline_trade_request(app, game_date, player, team):
    pname = getattr(player, "full_name",
                    f"{getattr(player, 'first_name', '')} "
                    f"{getattr(player, 'last_name', '')}").strip()
    tname = getattr(team, "team_name", getattr(team, "name", ""))
    try:
        ovr = player.overall_rating() if callable(
            getattr(player, "overall_rating", None)) else None
    except Exception:
        ovr = None
    reason_bits = []
    try:
        if (getattr(player, "happiness", 70) or 70) < 55:
            reason_bits.append("unhappy with his role")
        if (getattr(player, "playing_time_concern", 0) or 0) > 50:
            reason_bits.append("wants more ice time")
        if _team_win_pct(team) < 0.45:
            reason_bits.append("tired of losing")
    except Exception:
        pass
    reason = (" He is reportedly " + " and ".join(reason_bits) + "."
              if reason_bits else "")
    msg = make_headline(
        "trade_request", game_date,
        player_name=pname, team_name=tname,
        age=getattr(player, "age", None),
        position=str(getattr(player, "primary_position", "") or ""),
        overall=ovr, reason=reason)
    if msg is not None:
        try:
            msg.related_player_id = getattr(player, "id", None)
            msg.related_team = tname
        except Exception:
            pass
        # Blindsided fanbase: a beloved star asking out stings. The fans turn
    # on him -- a fringe malcontent asking out surprises nobody.
    try:
        import reputation_system as _rs
        _gm = getattr(app, "game_manager", None)
        _league = getattr(_gm, "league", None) or getattr(app, "league", None)
        if _league is not None and _rs.is_fan_favourite(player, team):
            _rs.record_fan_hate(
                _rs._rivalry_store(_league), player, team, "trade_demand",
                f"{pname} blindsided the {tname} faithful with a trade demand.",
                intensity=40, grudge=55)
            _rs.record_team_event(
                team, "fan_backlash",
                f"The fanbase is stunned -- {pname} demanded a trade.",
                morale_delta=-2, tone="down")
    except Exception:
        pass
    deliver(app, msg, involved=(tname,))
