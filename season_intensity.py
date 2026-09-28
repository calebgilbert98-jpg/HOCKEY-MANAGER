"""Season-long league tension gauge.

The in-game engine carries a 0-100 INTENSITY meter per game
(pbp_visual_sim._tension_value: pre-game drivers + live moments). This
module aggregates the same heat one level up: every bad-blood incident the
narrative ledger records (a star hurt, a player injured, a controversial
hit, a brawl) feeds a league-wide season gauge, so the league can see at a
glance whether tensions are high -- and which incident is driving it.

Additive by design: pure reads over the ledger, no sim behavior changes.
The mood bands and colors mirror the in-game meter exactly (BOILING red,
CHIPPY orange, HEATING yellow, CALM green) so the two meters read as one
system: the game meter is tonight, this one is the season.
"""

import math
from typing import Any, Dict, List

WINDOW_DAYS = 14
VALUE_SCALE = 1.5  # summed incident weight -> 0-100

# Ledger "incident" facts.incident_kind values that count as heat. Mirrors
# reputation_system.INCIDENT_WEIGHTS' violent set.
HEAT_INCIDENT_KINDS = frozenset({
    "star_injured",
    "player_injured",
    "controversial_hit",
    "brawl",
})


def mood_and_color(value: float):
    """(mood label, hex color) -- same bands as the in-game meter."""
    try:
        v = float(value)
    except Exception:
        v = 0.0
    if v >= 75:
        return "BOILING", "#ff6b6b"
    if v >= 50:
        return "CHIPPY", "#ff9f5c"
    if v >= 25:
        return "HEATING", "#ffd166"
    return "CALM", "#7bc96f"


def season_intensity(ledger: Any, window_days: int = WINDOW_DAYS) -> Dict[str, Any]:
    """League tension 0-100 from recent heat incidents, plus drivers.

    Returns {"value", "label", "color", "drivers", "window_days",
    "incident_count"}. Drivers are the top heat events newest-weight-first:
    {"label", "weight", "teams"}. Never raises; empty ledger -> CALM 0.
    """
    out: Dict[str, Any] = {
        "value": 0.0, "label": "CALM", "color": "#7bc96f",
        "drivers": [], "window_days": window_days, "incident_count": 0,
    }
    if ledger is None:
        return out
    try:
        season = getattr(ledger, "season", None)
        day = getattr(ledger, "day", None)
        cutoff = (day - window_days) if isinstance(day, (int, float)) else None
        heat: List[Dict[str, Any]] = []
        for ev in getattr(ledger, "events", None) or []:
            try:
                if ev.get("kind") != "incident":
                    continue
                facts = ev.get("facts") or {}
                if facts.get("incident_kind") not in HEAT_INCIDENT_KINDS:
                    continue
                if season is not None and ev.get("season") != season:
                    continue
                if cutoff is not None and (ev.get("day") or 0) < cutoff:
                    continue
                heat.append(ev)
            except Exception:
                continue
        total = sum(float(ev.get("weight", 0) or 0) for ev in heat)
        value = max(0.0, min(100.0, round(total * VALUE_SCALE, 1)))
        label, color = mood_and_color(value)
        heat.sort(key=lambda e: float(e.get("weight", 0) or 0), reverse=True)
        drivers: List[Dict[str, Any]] = []
        for ev in heat[:4]:
            facts = ev.get("facts") or {}
            txt = (ev.get("text") or facts.get("detail")
                   or facts.get("incident_kind") or "incident")
            drivers.append({
                "label": str(txt),
                "weight": float(ev.get("weight", 0) or 0),
                "teams": list(ev.get("teams") or []),
            })
        out.update(value=value, label=label, color=color, drivers=drivers,
                   incident_count=len(heat))
    except Exception:
        pass
    return out


def draw_gauge(canvas: Any, cx: float, cy: float, radius: float,
               info: Dict[str, Any], font_family: str = "Arial") -> None:
    """Draw a semicircular tension gauge on a tk.Canvas. Never raises.

    Layout: "LEAGUE TENSION" title above the arc, four colored band
    segments (green->yellow->orange->red), a needle at the value, and the
    numeric value + mood below the hub. Caller sizes the canvas at least
    (2*radius + 30) x (radius + 62).
    """
    try:
        value = max(0.0, min(100.0, float(info.get("value", 0.0))))
        label = str(info.get("label", "CALM"))
        color = str(info.get("color", "#7bc96f"))
        x0, y0, x1, y1 = cx - radius, cy - radius, cx + radius, cy + radius
        # Band segments: value 0 at west, 100 at east. tkinter arcs run
        # counterclockwise from 3 o'clock, so each band steps clockwise.
        bands = [
            (180, -45, "#7bc96f"),   # 0-25 calm
            (135, -45, "#ffd166"),   # 25-50 heating
            (90, -45, "#ff9f5c"),    # 50-75 chippy
            (45, -45, "#ff6b6b"),    # 75-100 boiling
        ]
        for start, extent, fill in bands:
            try:
                canvas.create_arc(x0, y0, x1, y1, start=start, extent=extent,
                                  style="arc", outline=fill, width=11)
            except Exception:
                continue
        # Needle.
        try:
            ang = math.radians(180.0 - value * 1.8)
            nx, ny = cx + radius * 0.88 * math.cos(ang), cy - radius * 0.88 * math.sin(ang)
            canvas.create_line(cx, cy, nx, ny, fill="#F2F2F2", width=3)
            canvas.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                               fill="#2A3441", outline="#8A94A0", width=1)
        except Exception:
            pass
        # Ticks at 0 / 50 / 100.
        try:
            for tv in (0, 50, 100):
                ta = math.radians(180.0 - tv * 1.8)
                tx = cx + (radius + 12) * math.cos(ta)
                ty = cy - (radius + 12) * math.sin(ta)
                canvas.create_text(tx, ty, text=str(tv), fill="#8A94A0",
                                   font=(font_family, 8))
        except Exception:
            pass
        # Title + readout.
        try:
            canvas.create_text(cx, cy - radius - 20, text="LEAGUE TENSION",
                               fill="#AEB6C8", font=(font_family, 10, "bold"))
            canvas.create_text(cx, cy + 20,
                               text=f"{value:.0f} — {label}",
                               fill=color, font=(font_family, 13, "bold"))
        except Exception:
            pass
    except Exception:
        pass
