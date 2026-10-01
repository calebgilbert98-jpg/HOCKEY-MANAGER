# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Narrative surfacing for scenario-composite battles.

Caleb's scenario_composites engine already computes a story + decisiveness
band per battle (apply_scenario(detail=True)). This module only READS that
layer and routes standout moments into channels that already exist
(headlines, the pbp feed). It never touches sim math, never re-tunes, and
never raises.

Rules (additive, bounded):
- Only battles the engine itself marks "decisive" earn ink, and only when
  the attacking side won the battle decisively (the story fragments are
  written from the attacker's perspective).
- At most 2 moments per game become post-game headlines.
- Decisive moments also go to the live pbp feed (the watch-live visualizer
  renders them; _emit_pbp is a no-op when nobody listens).
- Everything is narrative hockey language. Edges, amplifiers, and all
  other numbers stay inside the engine -- nothing numeric reaches a
  renderer, ever.
"""

_MAX_HEADLINE_MOMENTS_PER_GAME = 2


def _team_name(team):
    try:
        return str(getattr(team, "team_name", "") or "").strip()
    except Exception:
        return ""


def _moments(sim):
    """Per-game standout-moment log on the sim (created lazily)."""
    try:
        m = getattr(sim, "_scenario_moments", None)
        if m is None:
            m = []
            setattr(sim, "_scenario_moments", m)
        return m if isinstance(m, list) else None
    except Exception:
        return None


def _headlines_sent(sim):
    try:
        return int(getattr(sim, "_scenario_headlines_sent", 0) or 0)
    except Exception:
        return 0


def compose_moment_text(off_name, def_name, info):
    """Narrative text for a decisive attacking scenario battle.

    Built from the scenario spec's own story fragment -- no numbers, no
    edges, no amplifiers. Returns "" when there is nothing to say.
    """
    try:
        info = info or {}
        story = str(info.get("story", "") or "").strip()
        if not story:
            return ""
        off_name = (off_name or "The attackers").strip()
        def_name = (def_name or "the defense").strip()
        return f"{off_name} -- {story} -- and the {def_name} had no answer."
    except Exception:
        return ""


def note_scenario_moment(sim, scenario_key, off_team, def_team, info):
    """Record a standout scenario battle for media + live feed.

    Call AFTER apply_scenario(..., detail=True); pass its info dict.
    Returns True when the moment earned ink. Never raises, never touches
    the sim math -- the probability was already computed by the caller.
    """
    try:
        if not isinstance(info, dict):
            return False
        # Decisive band only, and only when the ATTACK won it decisively:
        # the story fragments are written from the attacker's perspective.
        if info.get("decisiveness") != "decisive":
            return False
        try:
            if float(info.get("edge", 0)) < 12.0:
                return False
        except (TypeError, ValueError):
            return False
        moments = _moments(sim)
        if moments is None:
            return False
        off_name = _team_name(off_team) or "The attackers"
        def_name = _team_name(def_team) or "the defense"
        text = compose_moment_text(off_name, def_name, info)
        if not text:
            return False
        event = str(info.get("event", "") or "a key moment").strip()

        # Live feed (watch-live visualizer). No-op when nobody listens.
        emit = getattr(sim, "_emit_pbp", None)
        if callable(emit):
            try:
                emit("scenario_moment", text=text, event=event,
                     off_team=off_name, def_team=def_name)
            except Exception:
                pass

        # Post-game media: at most 2 per game, via the existing
        # pending_headlines channel (drained by headlines.drain_sim_headlines).
        if _headlines_sent(sim) < _MAX_HEADLINE_MOMENTS_PER_GAME:
            headlines = getattr(sim, "pending_headlines", None)
            if isinstance(headlines, list):
                headlines.append({
                    "kind": "scenario_moment",
                    "off": off_name,
                    "defense": def_name,
                    "story": text,
                    "event": event,
                    "involved": (off_name, def_name),
                })
                try:
                    sim._scenario_headlines_sent = _headlines_sent(sim) + 1
                except Exception:
                    pass

        moments.append({"scenario": str(scenario_key or ""), "text": text})
        return True
    except Exception:
        return False
