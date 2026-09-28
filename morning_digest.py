"""
Morning digest (roadmap F4: the inbox ritual).

The inbox is sacred — message → decision → match → message. This adds the
one missing ritual: a morning-digest message when the day advances,
summarizing what happened overnight and what needs the manager's decision.

This does NOT rebuild the inbox; it feeds it.
"""

from datetime import datetime


def build_morning_digest(date_str, events):
    """Create a morning-digest message dict.

    events: list of dicts with 'category' ('result', 'injury', 'trade',
            'news', 'decision') and 'text'.
    Returns a message dict for the inbox.
    """
    lines = [f"Good morning. Here's your digest for {date_str}.\n"]
    by_cat = {}
    for e in events:
        by_cat.setdefault(e.get('category', 'news'), []).append(e.get('text', ''))

    if by_cat.get('result'):
        lines.append("RESULTS:")
        lines.extend(f"  • {t}" for t in by_cat['result'])
        lines.append("")
    if by_cat.get('injury'):
        lines.append("INJURIES:")
        lines.extend(f"  • {t}" for t in by_cat['injury'])
        lines.append("")
    if by_cat.get('trade'):
        lines.append("TRANSACTIONS:")
        lines.extend(f"  • {t}" for t in by_cat['trade'])
        lines.append("")
    if by_cat.get('decision'):
        lines.append("NEEDS YOUR DECISION:")
        lines.extend(f"  • {t}" for t in by_cat['decision'])
        lines.append("")
    if by_cat.get('news'):
        lines.append("AROUND THE LEAGUE:")
        lines.extend(f"  • {t}" for t in by_cat['news'])

    return {
        'subject': f"Morning Digest — {date_str}",
        'sender': 'Assistant GM',
        'body': "\n".join(lines),
        'timestamp': datetime.now().isoformat(),
        'category': 'digest',
        'priority': 'normal',
    }


def deliver_morning_digest(team, date_str, events):
    """Build the digest and deliver it to the team's inbox.

    team: Team object with an `inbox` attribute.
    Returns the EmailMessage, or None if delivery failed.
    """
    try:
        from game_classes import EmailMessage
        digest = build_morning_digest(date_str, events)
        msg = EmailMessage(
            sender=digest['sender'],
            sender_type="Staff",
            subject=digest['subject'],
            content=digest['body'],
            category="General",
            is_important=True,
            priority=3,
        )
        inbox = getattr(team, 'inbox', None)
        if inbox is not None and hasattr(inbox, 'messages'):
            inbox.messages.append(msg)
            return msg
        elif inbox is not None and hasattr(inbox, 'add_message'):
            inbox.add_message(msg)
            return msg
    except Exception:
        pass
    return None
