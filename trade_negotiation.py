# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
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
from typing import (Dict, List, Optional, Tuple)


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
    # Deal sweeteners, keyed by str(asset id):
    #   retention: player id -> pct of cap hit the USER retains (1-50)
    #   pick_protection: pick id -> "top-3" | "top-10" | "lottery"
    # Only the user sets these (on the trade screen); the engine honors
    # them for both sides symmetrically at completion.
    retention: Dict[str, float] = field(default_factory=dict)
    pick_protection: Dict[str, str] = field(default_factory=dict)

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
        # Normalize term keys to str (old saves predate these fields).
        for k in ("retention", "pick_protection"):
            v = kw.get(k)
            kw[k] = {str(_k): _v for _k, _v in (v or {}).items()} \
                if isinstance(v, dict) else {}
        return cls(**{f: kw.get(f, getattr(cls, f, None))
                      for f in ("id", "partner_team_name", "direction", "status",
                                "rounds", "patience", "user_assets", "partner_assets",
                                "response_due", "created", "history", "last_message",
                                "inbox_message_id", "retention", "pick_protection")})

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


def asset_summary(asset_dicts: List[dict], retention=None,
                  pick_protection=None) -> str:
    """One-line summary of serialized assets, with deal terms annotated."""
    parts = []
    for ad in asset_dicts or []:
        if not isinstance(ad, dict):
            continue
        if ad.get("kind") == "pick":
            label = ad.get("label", "pick")
            try:
                import trade_engine as _te
                prot = (pick_protection or {}).get(str(ad.get("id", "")))
                tag = _te.protection_label(prot)
                if tag:
                    label = f"{label} ({tag})"
            except Exception:
                pass
            parts.append(label)
        else:
            label = (f"{ad.get('name', '?')} "
                     f"({ad.get('pos', '')} {ad.get('ovr', '')})".strip())
            try:
                pct = float((retention or {}).get(str(ad.get("id", "")), 0) or 0)
                if pct > 0:
                    label += f" [{pct:g}% salary retained]"
            except Exception:
                pass
            parts.append(label)
    return ", ".join(parts) if parts else "nothing"


def _terms_note(retention, pick_protection) -> str:
    """Inbox-friendly rendering of the deal's retention/protection terms."""
    bits = []
    for _pid, _pct in (retention or {}).items():
        try:
            if float(_pct or 0) > 0:
                bits.append(f"salary retained: {_pct:g}%")
        except Exception:
            pass
    for _kid, _prot in (pick_protection or {}).items():
        try:
            import trade_engine as _te
            tag = _te.protection_label(_prot)
            if tag:
                bits.append(f"pick protection: {tag}")
        except Exception:
            pass
    return ("Terms: " + "; ".join(bits)) if bits else ""


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


def _pct_ok(v) -> bool:
    """A retention pct is sane: 0 < pct <= 50 (real NHL max)."""
    try:
        return 0 < float(v or 0) <= 50
    except Exception:
        return False


def send_offer(app, partner_team, user_assets, partner_assets,
               retention=None, pick_protection=None) -> TradeNegotiation:
    """User sends an offer. The AI GM replies in 1-3 days via the inbox --
    instantly on trade deadline day.

    retention: {player id: pct} retained-salary terms, BOTH sides:
      terms on user-outgoing players = salary our club keeps;
      terms on partner-outgoing players = salary we ask the partner
      to keep (opponent retention). The engine routes each term to
      the retaining club at execution.
    pick_protection: {pick id: "top-3"|"top-10"|"lottery"} on outgoing picks.
    """
    today = _today(app)
    rush = is_deadline_rush(app) or is_cap_crunch_rush(app)
    retention = {str(k): float(v) for k, v in (retention or {}).items()
                 if _pct_ok(v)}
    pick_protection = {str(k): v for k, v in (pick_protection or {}).items()
                       if v}
    neg = TradeNegotiation(
        partner_team_name=getattr(partner_team, "team_name", str(partner_team)),
        direction="outgoing",
        status="awaiting_ai",
        rounds=1,
        patience=1.0,
        user_assets=assets_to_dicts(user_assets, getattr(app.user_team, "team_name", "")),
        partner_assets=assets_to_dicts(partner_assets,
                                       getattr(partner_team, "team_name", "")),
        retention=retention,
        pick_protection=pick_protection,
        response_due=today if rush else today + timedelta(days=random.randint(1, 3)),
        created=today,
        history=[{"date": today.isoformat(), "by": "user",
                  "summary": f"Offered {asset_summary(assets_to_dicts(user_assets), retention, pick_protection)} "
                             f"for {asset_summary(assets_to_dicts(partner_assets))}"}],
    )
    _store(app).append(neg)
    wait_note = ("Their GM is on the line -- expect an answer right away."
                 if rush else
                 "Expect an answer within a few days. You can keep working -- "
                 "this won't interrupt you.")
    terms = _terms_note(retention, pick_protection)
    neg.inbox_message_id = _deliver(
        app,
        subject=f"Trade offer sent to {neg.partner_team_name}",
        content=(f"Your offer is with {neg.partner_team_name}'s front office:\n\n"
                 f"YOU SEND: {asset_summary(neg.user_assets, retention, pick_protection)}\n"
                 f"YOU GET: {asset_summary(neg.partner_assets)}\n"
                 f"{terms + chr(10) if terms else ''}\n{wait_note}"),
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
    # R3(c): purposeful proposals -- the AI's rationale is grounded in
    # real systems (its positional needs, contention window, cap, age
    # fit, rivalry), never generic filler.
    _rationale = ""
    try:
        import trade_engine as _te
        _pts = _te.trade_talking_points(
            partner_team,
            [player_wanted] if player_wanted else [],
            list(package or []),
            partner=getattr(app, "user_team", None),
            app=app)
        if _pts:
            _rationale = " Our thinking: " + " ".join(_pts)
    except Exception:
        _rationale = ""
    _wanted_txt = ""
    try:
        if player_wanted is not None:
            import trade_engine as _te2
            _wanted_txt = f" We're specifically after {_te2.asset_label(player_wanted)}."
    except Exception:
        _wanted_txt = ""
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
        last_message=(f"{pname} have put a proposal on the table."
                      f"{_wanted_txt}{_rationale}"),
    )
    _store(app).append(neg)
    neg.inbox_message_id = _deliver(
        app,
        subject=f"Trade proposal from {pname}",
        content=(f"{pname} have put a proposal on the table.{_wanted_txt}"
                 f"{_rationale} Open this message to review it -- no rush, "
                 f"it will wait for you."),
        sender=f"{pname} GM",
        action_type="trade_offer",
        action_data={"negotiation_id": neg.id},
        priority=3,
    )
    return neg


def _is_pick_asset(a) -> bool:
    try:
        from game_classes import DraftPick
        return isinstance(a, DraftPick)
    except Exception:
        return False


def send_counter(app, neg: TradeNegotiation,
                 user_assets, partner_assets,
                 retention=None, pick_protection=None) -> TradeNegotiation:
    """User answers an AI counter with adjusted terms. Patience decays.

    retention / pick_protection are the user's CURRENT deal terms from the
    trade screen (the screen is the source of truth each round)."""
    today = _today(app)
    neg.rounds += 1
    neg.patience = max(0.35, neg.patience - 0.15)
    neg.direction = "outgoing"
    neg.status = "awaiting_ai"
    # A counter can drop a clause player from the deal. His single-use
    # waiver was stamped for the previous shape of this trade -- clear it
    # now, or it would linger on his live contract for an unrelated future
    # deal. (The negotiation stays open, so no dead-deal cleanup runs.)
    try:
        _old_user, _ = resolve_assets(app, neg.user_assets)
        _old_partner, _ = resolve_assets(app, neg.partner_assets)
        _new_ids = {str(getattr(a, "id", ""))
                    for a in list(user_assets or [])
                    + list(partner_assets or [])}
        for _a in list(_old_user or []) + list(_old_partner or []):
            try:
                if (str(getattr(_a, "id", "")) not in _new_ids
                        and getattr(_a, "contract", None) is not None):
                    _a.contract.ntc_waiver_for = ""
            except Exception:
                pass
    except Exception:
        pass
    neg.user_assets = assets_to_dicts(user_assets,
                                      getattr(app.user_team, "team_name", ""))
    neg.partner_assets = assets_to_dicts(partner_assets, neg.partner_team_name)
    # Re-stamp the user's deal terms; drop terms for assets no longer offered.
    if retention is not None or pick_protection is not None:
        offered_p = {str(getattr(a, "id", "")) for a in (user_assets or [])
                     if not _is_pick_asset(a)}
        offered_k = {str(getattr(a, "id", "")) for a in (user_assets or [])
                     if _is_pick_asset(a)}
        neg.retention = {str(k): float(v)
                         for k, v in (retention or {}).items()
                         if str(k) in offered_p and _pct_ok(v)}
        neg.pick_protection = {str(k): v
                               for k, v in (pick_protection or {}).items()
                               if str(k) in offered_k and v}
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
                 f"YOU SEND: {asset_summary(neg.user_assets, neg.retention, neg.pick_protection)}\n"
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


def _neg_terms(neg: TradeNegotiation, user_objs, partner_objs, stamp=True):
    """Resolve a negotiation's deal terms against live objects.

    Returns (retention, protected_picks):
      retention: {player id: pct} for players still in the deal, BOTH
      sides (user-outgoing and partner-outgoing/acquired). The engine's
      execute_trade routes each term to the retaining club (whichever
      side traded the player away).
      protected_picks: list of live DraftPick objects with protection stamped
    Stale terms (assets that left the deal during counters) are dropped.
    stamp=False resolves retention without touching the live picks (used
    while the AI is still considering, so a declined deal leaves no flags).
    """
    from game_classes import DraftPick
    retention = {}
    try:
        live_ids = ({getattr(p, "id", None) for p in (user_objs or [])}
                    | {getattr(p, "id", None) for p in (partner_objs or [])})
        for k, v in (getattr(neg, "retention", None) or {}).items():
            if not _pct_ok(v):
                continue
            for p in list(user_objs or []) + list(partner_objs or []):
                if str(getattr(p, "id", "")) == str(k) \
                        and getattr(p, "id", None) in live_ids \
                        and not isinstance(p, DraftPick):
                    retention[getattr(p, "id", None)] = float(v)
                    break
    except Exception:
        pass
    protected = []
    if not stamp:
        return retention, protected
    try:
        import trade_engine as _te
        for p in list(user_objs or []) + list(partner_objs or []):
            if not isinstance(p, DraftPick):
                continue
            prot = (getattr(neg, "pick_protection", None) or {}).get(
                str(getattr(p, "id", "")))
            if prot in ("top-3", "top-10", "lottery"):
                tag = _te.protection_label(prot)
                p.protection = prot
                p.is_conditional = True
                p.condition = (
                    f"{tag}: if this pick falls in the protected range, "
                    f"{getattr(p, 'original_team', 'the original club')} keeps it "
                    f"and the holder receives their next-year 1st-rounder instead.")
                protected.append(p)
    except Exception:
        pass
    return retention, protected


def _complete(app, neg: TradeNegotiation, user_objs, partner_objs) -> bool:
    """Execute the agreed deal. Returns False if it can no longer happen."""
    import trade_engine as te
    user_team = getattr(app, "user_team", None)
    partner = find_team(app, neg.partner_team_name)
    if user_team is None or partner is None:
        return False
    retention, _protected = _neg_terms(neg, user_objs, partner_objs)
    if not te._cap_ok_after(user_team, user_objs, partner_objs,
                            retention=retention):
        _deliver(app,
                 subject=f"Trade with {neg.partner_team_name} fell through",
                 content="The agreed deal can't fit under your salary cap anymore. "
                         "Shed salary and re-open talks if you still want it.",
                 sender="League Office")
        _clear_waivers(app, neg)
        neg.status = "expired"
        return False
    date_str = str(_today(app))
    _lg = getattr(getattr(app, 'game_manager', None), 'league', None) or \
        getattr(app, 'league', None)
    _board = getattr(getattr(app, 'career', None), 'board', None)
    # D15: clause consent recovery. A no-trade/no-movement veto no longer
    # kills the deal silently at the engine preflight: any player who was
    # never asked gets his ONE consent conversation now. Waive and the deal
    # proceeds; refuse and the deal dies with a clear outcome -- never a
    # mystery BLOCKED.
    try:
        import trade_market as _tm
        _ok, _notes, _refused = _tm.resolve_clause_consent(
            app, _lg, user_team, partner, user_objs)
        if _ok:
            _ok2, _notes2, _refused2 = _tm.resolve_clause_consent(
                app, _lg, partner, user_team, partner_objs)
            _ok, _notes, _refused = _ok2, _notes + _notes2, _refused2
        if _notes:
            try:
                neg.history.append(
                    {"date": date_str[:10], "by": "system",
                     "summary": "Clause consent: " + "; ".join(_notes)})
            except Exception:
                pass
        if not _ok:
            _deliver(app,
                     subject=f"Trade with {neg.partner_team_name} fell through",
                     content=(f"{_refused}.\n\nThe deal is dead; no assets "
                              f"moved. Re-open talks without him if you "
                              f"still want it."),
                     sender="League Office")
            _clear_waivers(app, neg)
            neg.status = "expired"
            return False
    except Exception:
        pass
    trade = te.execute_trade(user_team, partner, user_objs, partner_objs,
                             date_str, league=_lg, board=_board,
                             retention=retention)
    if trade.summary.startswith("BLOCKED:"):
        # A clause veto killed the deal at completion (e.g. the player was
        # traded... no -- a waiver expired or was never granted). Nothing
        # moved; tell the user why instead of recording a phantom trade.
        _deliver(app,
                 subject=f"Trade with {neg.partner_team_name} fell through",
                 content=(f"{trade.summary[8:]}\n\nAsk the player to waive his "
                          f"clause and re-open talks if you still want it."),
                 sender="League Office")
        _clear_waivers(app, neg)
        neg.status = "expired"
        return False
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
        _clear_waivers(app, neg)
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
    _clear_waivers(app, neg)
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


def _clear_waivers(app, neg: TradeNegotiation):
    """A dead deal spends nothing: clear one-transaction clause waivers
    stamped on this negotiation's assets so a later, separate trade
    starts from a clean slate."""
    try:
        import trade_engine as te
        user_objs, _u = resolve_assets(app, neg.user_assets)
        partner_objs, _p = resolve_assets(app, neg.partner_assets)
        for a in list(user_objs) + list(partner_objs):
            try:
                if not te._is_pick(a) and getattr(a, "contract", None) is not None:
                    a.contract.ntc_waiver_for = ""
            except Exception:
                pass
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
                _clear_waivers(app, neg)
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
        _clear_waivers(app, neg)
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
                                    situational=situational,
                                    retention=_neg_terms(neg, user_objs,
                                                         partner_objs,
                                                         stamp=False)[0])
    except TypeError:
        # Older ai_consider_trade without the situational kwarg
        resp = te.ai_consider_trade(partner, user_objs, partner_objs,
                                    user_team=user_team, patience=neg.patience)
    if resp.decision == "accept":
        _complete(app, neg, user_objs, partner_objs)
        _mark_action_done(app, neg)
    elif resp.decision == "reject":
        _clear_waivers(app, neg)
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
