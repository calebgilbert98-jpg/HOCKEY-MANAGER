"""Real-time trade negotiation.

FM24/EHM-style dealing: offers are *sent*, not resolved instantly. The AI
GM takes 1-3 days to respond, counters come back as inbox messages you can
answer on your own time, and every round of haggling wears the other GM's
patience thinner.

The negotiation lives outside any window: closing the Trade Center (click
out, Escape, X) never answers the offer -- it just waits in the inbox.

State is kept on ``game_manager.trade_negotiations`` as TradeNegotiation
dataclasses and survives save/load via to_dict/from_dict.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class TradeNegotiation:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    partner_team_name: str = ""
    direction: str = "outgoing"  # 'outgoing' (user offered) | 'incoming' (AI offered)
    status: str = "awaiting_ai"  # awaiting_ai | awaiting_user | accepted | declined | expired
    rounds: int = 0
    patience: float = 1.0        # 1.0 fresh -> decays per counter round
    user_assets: List[dict] = field(default_factory=list)     # serialized (user gives)
    partner_assets: List[dict] = field(default_factory=list)  # serialized (partner gives)
    response_due: Optional[date] = None
    created: Optional[date] = None
    history: List[dict] = field(default_factory=list)
    last_message: str = ""
    inbox_message_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        for k in ("response_due", "created"):
            v = d.get(k)
            d[k] = v.isoformat() if isinstance(v, (date, datetime)) else None
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "TradeNegotiation":
        kw = dict(d)
        for k in ("response_due", "created"):
            v = kw.get(k)
            if isinstance(v, str):
                try:
                    kw[k] = date.fromisoformat(v)
                except Exception:
                    kw[k] = None
        return cls(**{f: kw.get(f, getattr(cls, f, None))
                      for f in ("id", "partner_team_name", "direction", "status",
                                "rounds", "patience", "user_assets", "partner_assets",
                                "response_due", "created", "history", "last_message",
                                "inbox_message_id")})

    @property
    def is_open(self) -> bool:
        return self.status in ("awaiting_ai", "awaiting_user")


# ---------------------------------------------------------------------------
# App helpers
# ---------------------------------------------------------------------------

def _today(app) -> date:
    d = getattr(app, "current_date", None)
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return date.today()


def _gm(app):
    return getattr(app, "game_manager", None)


def _store(app) -> List[TradeNegotiation]:
    gm = _gm(app)
    if gm is None:
        return []
    negs = getattr(gm, "trade_negotiations", None)
    if negs is None:
        negs = []
        gm.trade_negotiations = negs
    # tolerate raw dicts from old saves
    for i, n in enumerate(negs):
        if isinstance(n, dict):
            try:
                negs[i] = TradeNegotiation.from_dict(n)
            except Exception:
                pass
    return negs


def get_negotiation(app, neg_id: str) -> Optional[TradeNegotiation]:
    for n in _store(app):
        if isinstance(n, TradeNegotiation) and n.id == neg_id:
            return n
    return None


def open_negotiations(app) -> List[TradeNegotiation]:
    return [n for n in _store(app)
            if isinstance(n, TradeNegotiation) and n.is_open]


def find_team(app, team_name: str):
    league = getattr(_gm(app), "league", None) or getattr(app, "league", None)
    if league is None:
        return None
    for t in getattr(league, "teams", []) or []:
        if getattr(t, "team_name", "") == team_name:
            return t
    return None


def _all_players(app) -> List:
    league = getattr(_gm(app), "league", None) or getattr(app, "league", None)
    out = []
    if league is None:
        return out
    for t in getattr(league, "teams", []) or []:
        for attr in ("roster", "ahl_roster", "prospects"):
            out.extend(getattr(t, attr, None) or [])
    out.extend(getattr(league, "free_agents", None) or [])
    return out


def asset_to_dict(asset, owner_team_name: str = "") -> dict:
    """Serialize one trade asset (player or pick) to a plain dict."""
    try:
        from game_classes import DraftPick
        if isinstance(asset, DraftPick):
            return {
                "kind": "pick",
                "id": str(getattr(asset, "id", "")),
                "label": f"{getattr(asset, 'year', '?')} "
                         f"Round {getattr(asset, 'round', '?')} pick",
                "year": getattr(asset, "year", None),
                "round": getattr(asset, "round", None),
                "team": getattr(asset, "current_team", owner_team_name),
            }
    except Exception:
        pass
    return {
        "kind": "player",
        "id": getattr(asset, "id", None),
        "name": getattr(asset, "full_name", str(asset)),
        "team": owner_team_name,
        "pos": str(getattr(getattr(asset, "primary_position", None), "name", "")),
        "ovr": int(getattr(asset, "overall_rating", lambda: 0)()),
    }


def assets_to_dicts(assets, owner_team_name: str = "") -> List[dict]:
    return [asset_to_dict(a, owner_team_name) for a in (assets or [])]


def resolve_assets(app, asset_dicts: List[dict]) -> Tuple[List, List[str]]:
    """Turn serialized asset dicts back into live objects.

    Returns (objects, missing_labels). Players that changed teams since the
    offer are still found by id; truly unresolvable assets are reported so
    the negotiation can be expired gracefully instead of crashing.
    """
    from game_classes import DraftPick
    objs, missing = [], []
    if not asset_dicts:
        return objs, missing
    players = {getattr(p, "id", None): p for p in _all_players(app)}
    players_by_name = {}
    for p in _all_players(app):
        players_by_name.setdefault(getattr(p, "full_name", ""), []).append(p)
    league = getattr(_gm(app), "league", None) or getattr(app, "league", None)
    picks = {}
    if league is not None:
        for t in getattr(league, "teams", []) or []:
            dp = getattr(t, "draft_picks", None) or {}
            for _yr, lst in (dp.items() if isinstance(dp, dict) else []):
                for pk in lst or []:
                    if isinstance(pk, DraftPick):
                        picks[str(getattr(pk, "id", ""))] = pk
    for ad in asset_dicts:
        if not isinstance(ad, dict):
            continue
        if ad.get("kind") == "pick":
            pk = picks.get(str(ad.get("id", "")))
            if pk is not None:
                objs.append(pk)
            else:
                missing.append(ad.get("label", "draft pick"))
            continue
        p = players.get(ad.get("id"))
        if p is None:
            cands = players_by_name.get(ad.get("name", ""), [])
            p = cands[0] if cands else None
        if p is not None:
            objs.append(p)
        else:
            missing.append(ad.get("name", "player"))
    return objs, missing


def asset_summary(asset_dicts: List[dict]) -> str:
    parts = []
    for ad in asset_dicts or []:
        if not isinstance(ad, dict):
            continue
        if ad.get("kind") == "pick":
            parts.append(ad.get("label", "pick"))
        else:
            parts.append(f"{ad.get('name', '?')} "
                         f"({ad.get('pos', '')} {ad.get('ovr', '')})".strip())
    return ", ".join(parts) if parts else "nothing"


# ---------------------------------------------------------------------------
# Inbox delivery
# ---------------------------------------------------------------------------

def _deliver(app, subject: str, content: str, sender: str,
             action_type: Optional[str] = None,
             action_data: Optional[dict] = None,
             priority: int = 2) -> Optional[str]:
    try:
        from game_classes import EmailMessage
        msg = EmailMessage(
            sender=sender,
            sender_type="GM",
            subject=subject,
            content=content,
            date_sent=_today(app),
            category="Trade",
            action_type=action_type,
            action_data=action_data or {},
            priority=priority,
            requires_response=action_type is not None,
        )
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        if inbox is not None and hasattr(inbox, "add_message"):
            inbox.add_message(msg)
            try:
                app.update_inbox_notification()
            except Exception:
                pass
            return msg.id
    except Exception as e:
        print(f"trade negotiation inbox delivery failed: {e}")
    return None


# ---------------------------------------------------------------------------
# Offer lifecycle
# ---------------------------------------------------------------------------

def is_deadline_rush(app) -> bool:
    """True when the game date is trade deadline day -- AI GMs answer
    instantly (the deadline-day phone-call feel) instead of in 1-3 days."""
    try:
        from trade_deadline_manager import get_deadline_manager
        mgr = get_deadline_manager(getattr(app, 'game_manager', None))
        return mgr.is_deadline_day(_today(app))
    except Exception:
        return False


def is_cap_crunch_rush(app) -> bool:
    """True when the user's roster is over the salary cap and must shed
    salary -- trade responses come back instantly so the user isn't stuck
    waiting days while blocked from advancing."""
    try:
        return bool(app.is_over_cap())
    except Exception:
        return False


def send_offer(app, partner_team, user_assets, partner_assets) -> TradeNegotiation:
    """User sends an offer. The AI GM replies in 1-3 days via the inbox --
    instantly on trade deadline day."""
    today = _today(app)
    rush = is_deadline_rush(app) or is_cap_crunch_rush(app)
    neg = TradeNegotiation(
        partner_team_name=getattr(partner_team, "team_name", str(partner_team)),
        direction="outgoing",
        status="awaiting_ai",
        rounds=1,
        patience=1.0,
        user_assets=assets_to_dicts(user_assets, getattr(app.user_team, "team_name", "")),
        partner_assets=assets_to_dicts(partner_assets,
                                       getattr(partner_team, "team_name", "")),
        response_due=today if rush else today + timedelta(days=random.randint(1, 3)),
        created=today,
        history=[{"date": today.isoformat(), "by": "user",
                  "summary": f"Offered {asset_summary(assets_to_dicts(user_assets))} "
                             f"for {asset_summary(assets_to_dicts(partner_assets))}"}],
    )
    _store(app).append(neg)
    wait_note = ("Their GM is on the line -- expect an answer right away."
                 if rush else
                 "Expect an answer within a few days. You can keep working -- "
                 "this won't interrupt you.")
    neg.inbox_message_id = _deliver(
        app,
        subject=f"Trade offer sent to {neg.partner_team_name}",
        content=(f"Your offer is with {neg.partner_team_name}'s front office:\n\n"
                 f"YOU SEND: {asset_summary(neg.user_assets)}\n"
                 f"YOU GET: {asset_summary(neg.partner_assets)}\n\n"
                 f"{wait_note}"),
        sender=f"{neg.partner_team_name} (pending)",
    )
    if rush:
        # Deadline day: the AI answers on the spot. Process immediately so
        # the reply lands in the inbox within the same interaction.
        try:
            process_due_negotiations(app)
        except Exception as e:
            print(f"deadline rush instant answer failed: {e}")
    return neg


def incoming_offer(app, partner_team, package, player_wanted=None) -> TradeNegotiation:
    """AI GM opens talks: lands in the inbox, never a popup."""
    today = _today(app)
    pname = getattr(partner_team, "team_name", str(partner_team))
    neg = TradeNegotiation(
        partner_team_name=pname,
        direction="incoming",
        status="awaiting_user",
        rounds=1,
        patience=1.0,
        user_assets=assets_to_dicts(
            [player_wanted] if player_wanted else [],
            getattr(app.user_team, "team_name", "")),
        partner_assets=assets_to_dicts(package, pname),
        created=today,
        history=[{"date": today.isoformat(), "by": "ai",
                  "summary": f"{pname} opened talks"}],
        last_message=f"{pname} are interested in making a deal.",
    )
    _store(app).append(neg)
    neg.inbox_message_id = _deliver(
        app,
        subject=f"Trade proposal from {pname}",
        content=(f"{pname} have put a proposal on the table. Open this "
                 f"message to review it -- no rush, it will wait for you."),
        sender=f"{pname} GM",
        action_type="trade_offer",
        action_data={"negotiation_id": neg.id},
        priority=3,
    )
    return neg


def send_counter(app, neg: TradeNegotiation,
                 user_assets, partner_assets) -> TradeNegotiation:
    """User answers an AI counter with adjusted terms. Patience decays."""
    today = _today(app)
    neg.rounds += 1
    neg.patience = max(0.35, neg.patience - 0.15)
    neg.direction = "outgoing"
    neg.status = "awaiting_ai"
    neg.user_assets = assets_to_dicts(user_assets,
                                      getattr(app.user_team, "team_name", ""))
    neg.partner_assets = assets_to_dicts(partner_assets, neg.partner_team_name)
    rush = is_deadline_rush(app)
    neg.response_due = today if rush else today + timedelta(days=random.randint(1, 3))
    neg.history.append({"date": today.isoformat(), "by": "user",
                        "summary": f"Countered (round {neg.rounds})"})
    wait_note = ("They're still on the line -- answer coming right up."
                 if rush else "They'll get back to you in a few days. ")
    neg.inbox_message_id = _deliver(
        app,
        subject=f"Counter-offer sent to {neg.partner_team_name}",
        content=(f"Your revised proposal is with {neg.partner_team_name}:\n\n"
                 f"YOU SEND: {asset_summary(neg.user_assets)}\n"
                 f"YOU GET: {asset_summary(neg.partner_assets)}\n\n"
                 f"{wait_note}"
                 f"{'They are losing patience -- make this one count.' if neg.patience < 0.7 else ''}"),
        sender=f"{neg.partner_team_name} (pending)",
    )
    if rush:
        try:
            process_due_negotiations(app)
        except Exception as e:
            print(f"deadline rush instant answer failed: {e}")
    return neg


def _complete(app, neg: TradeNegotiation, user_objs, partner_objs) -> bool:
    """Execute the agreed deal. Returns False if it can no longer happen."""
    import trade_engine as te
    user_team = getattr(app, "user_team", None)
    partner = find_team(app, neg.partner_team_name)
    if user_team is None or partner is None:
        return False
    if not te._cap_ok_after(user_team, user_objs, partner_objs):
        _deliver(app,
                 subject=f"Trade with {neg.partner_team_name} fell through",
                 content="The agreed deal can't fit under your salary cap anymore. "
                         "Shed salary and re-open talks if you still want it.",
                 sender="League Office")
        neg.status = "expired"
        return False
    date_str = str(_today(app))
    trade = te.execute_trade(user_team, partner, user_objs, partner_objs, date_str)
    gm = _gm(app)
    if gm is not None:
        if not hasattr(gm, "trade_history"):
            gm.trade_history = []
        gm.trade_history.append(trade)
        # Media + news (parity with the old instant Trade Center flow)
        try:
            traded = [a for a in user_objs if not te._is_pick(a)]
            received = [a for a in partner_objs if not te._is_pick(a)]
            if hasattr(gm, "media_system") and gm.media_system:
                gm.media_system.process_trade(
                    user_team=user_team, other_team=partner,
                    traded_players=traded, received_players=received)
        except Exception:
            pass
    try:
        app.add_news_story(f"TRADE: {trade.summary}")
    except Exception:
        pass
    try:
        app.update_all_views()
    except Exception:
        pass
    neg.status = "accepted"
    _deliver(app,
             subject=f"Trade completed with {neg.partner_team_name}",
             content=f"Done deal:\n\n{trade.summary}",
             sender=f"{neg.partner_team_name} GM", priority=3)
    return True


def accept_negotiation(app, neg_id: str) -> bool:
    neg = get_negotiation(app, neg_id)
    if neg is None or not neg.is_open:
        return False
    user_objs, missing_u = resolve_assets(app, neg.user_assets)
    partner_objs, missing_p = resolve_assets(app, neg.partner_assets)
    if missing_u or missing_p:
        neg.status = "expired"
        _deliver(app, subject=f"Trade with {neg.partner_team_name} expired",
                 content="One of the players involved is no longer available, "
                         "so this deal is off the table.",
                 sender="League Office")
        return False
    ok = _complete(app, neg, user_objs, partner_objs)
    _mark_action_done(app, neg)
    return ok


def decline_negotiation(app, neg_id: str) -> bool:
    neg = get_negotiation(app, neg_id)
    if neg is None or not neg.is_open:
        return False
    neg.status = "declined"
    neg.history.append({"date": _today(app).isoformat(), "by": "user",
                        "summary": "Walked away"})
    _mark_action_done(app, neg)
    _deliver(app,
             subject=f"Talks ended with {neg.partner_team_name}",
             content="You walked away from the table. They'll remember that "
                     "next time you call.",
             sender="Assistant GM")
    return True


def _mark_action_done(app, neg: TradeNegotiation):
    """Flip the inbox action message to done so its buttons retire."""
    try:
        inbox = getattr(getattr(app, "user_team", None), "inbox", None)
        msgs = getattr(inbox, "messages", None) or []
        for m in msgs:
            if getattr(m, "action_data", None) and \
               m.action_data.get("negotiation_id") == neg.id:
                m.action_done = True
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Daily processing: the AI GM answers when it's ready
# ---------------------------------------------------------------------------

def process_due_negotiations(app):
    """Called once per sim day. Resolves offers whose response is due."""
    import trade_engine as te
    today = _today(app)
    for neg in list(_store(app)):
        if not isinstance(neg, TradeNegotiation):
            continue
        if neg.status != "awaiting_ai":
            continue
        if neg.response_due is not None and neg.response_due > today:
            continue
        try:
            _resolve_one(app, neg, te, today)
        except Exception as e:
            print(f"trade negotiation resolution failed ({neg.id}): {e}")
    # stale incoming offers expire after 14 days of silence
    for neg in list(_store(app)):
        if not isinstance(neg, TradeNegotiation):
            continue
        if neg.status == "awaiting_user" and neg.created is not None:
            if (today - neg.created).days > 14:
                neg.status = "expired"
                _mark_action_done(app, neg)


def _resolve_one(app, neg: TradeNegotiation, te, today: date):
    partner = find_team(app, neg.partner_team_name)
    user_team = getattr(app, "user_team", None)
    if partner is None or user_team is None:
        neg.status = "expired"
        return
    user_objs, missing_u = resolve_assets(app, neg.user_assets)
    partner_objs, missing_p = resolve_assets(app, neg.partner_assets)
    if missing_u or missing_p or not user_objs or not partner_objs:
        neg.status = "expired"
        _deliver(app, subject=f"Talks with {neg.partner_team_name} fizzled",
                 content="The pieces involved have moved -- this one is dead.",
                 sender="Assistant GM")
        _mark_action_done(app, neg)
        return
    resp = None
    try:
        # Storyline-aware context: standings stance, streaks, rivalries,
        # deadline urgency. Additive nudge on the AI's eagerness -- the
        # core evaluation logic in trade_engine is untouched.
        situational = None
        try:
            import trade_storylines
            situational = trade_storylines.situational_context(
                app, partner, user_team)
        except Exception:
            situational = None
        resp = te.ai_consider_trade(partner, user_objs, partner_objs,
                                    user_team=user_team, patience=neg.patience,
                                    situational=situational)
    except TypeError:
        # Older ai_consider_trade without the situational kwarg
        resp = te.ai_consider_trade(partner, user_objs, partner_objs,
                                    user_team=user_team, patience=neg.patience)
    if resp.decision == "accept":
        _complete(app, neg, user_objs, partner_objs)
        _mark_action_done(app, neg)
    elif resp.decision == "reject":
        neg.status = "declined"
        neg.last_message = resp.message
        neg.history.append({"date": today.isoformat(), "by": "ai",
                            "summary": f"Rejected: {resp.message}"})
        _mark_action_done(app, neg)
        _deliver(app,
                 subject=f"{neg.partner_team_name} rejected your offer",
                 content=f"Their answer:\n\n\"{resp.message}\"\n\n"
                         f"You can open the Trade Center and try a new "
                         f"proposal whenever you like.",
                 sender=f"{neg.partner_team_name} GM", priority=3)
    else:
        # Counter: adjust the live terms, hand the decision to the user
        # via the inbox. Nothing blocks -- they answer when ready.
        new_user = list(user_objs) + list(getattr(resp, "want_added", None) or [])
        new_partner = list(partner_objs) + list(getattr(resp, "will_add", None) or [])
        neg.user_assets = assets_to_dicts(new_user, getattr(user_team, "team_name", ""))
        neg.partner_assets = assets_to_dicts(new_partner, neg.partner_team_name)
        neg.status = "awaiting_user"
        neg.direction = "incoming"
        neg.last_message = resp.message
        neg.history.append({"date": today.isoformat(), "by": "ai",
                            "summary": f"Countered: {resp.message}"})
        _mark_action_done(app, neg)
        neg.inbox_message_id = _deliver(
            app,
            subject=f"Counter-offer from {neg.partner_team_name}",
            content=(f"{neg.partner_team_name} answered your proposal with "
                     f"a counter. Open this message to review the new terms."),
            sender=f"{neg.partner_team_name} GM",
            action_type="trade_counter",
            action_data={"negotiation_id": neg.id},
            priority=3,
        )


# ---------------------------------------------------------------------------
# Save / load
# ---------------------------------------------------------------------------

def save_state(app) -> List[dict]:
    return [n.to_dict() for n in _store(app) if isinstance(n, TradeNegotiation)]


def load_state(app, data) -> None:
    gm = _gm(app)
    if gm is None:
        return
    negs = []
    for d in data or []:
        try:
            negs.append(TradeNegotiation.from_dict(d) if isinstance(d, dict) else d)
        except Exception:
            pass
    gm.trade_negotiations = negs
