# Copyright (c) 2026 Puck Dynasty contributors. All rights reserved.
"""Star-surname filter for generated players.

P-5 (playtest 2026-09-28): the fictional name pools contain real NHL star
surnames, so generated free agents / prospects showed up as "Mikko Rantanen",
"Klaus Draisaitl", "Artturi Granlund" -- real surnames attached to invented
first names. In a league that also carries the real players, that breaks the
fiction and confuses.

Fix: a curated blocklist of instantly-recognizable real-player surnames.
Generation re-rolls while the pick is blocked (bounded -- always terminates).
Real players are untouched; only fictional generation goes through this.

The bar for the list is "would a casual fan recognize the surname and assume
it's the real guy". Common surnames shared with a star (Smith, Johnson) stay
legal -- the pools need their flavor, and "Lars Johnson" confuses nobody.
"""

import random
import unicodedata


def _fold(s):
    """Lowercase ASCII fold for comparison (handles accents/umlauts)."""
    try:
        return unicodedata.normalize("NFKD", str(s)).encode(
            "ascii", "ignore").decode("ascii").lower()
    except Exception:
        return str(s).lower()


# Recognizable real-NHL surnames, folded. Generated players may not use these.
BLOCKED_SURNAMES = frozenset(_fold(n) for n in [
    # The three reported collisions
    "Rantanen", "Draisaitl", "Granlund",
    # Current superstars
    "McDavid", "MacKinnon", "Kucherov", "Matthews", "Crosby", "Ovechkin",
    "Malkin", "Stamkos", "Tavares", "Marner", "Nylander", "Pastrnak",
    "Marchand", "Point", "Barkov", "Laine", "Aho", "Eichel", "Stone",
    "Gaudreau", "Kachuk", "Kaprizov", "Kane", "Toews", "Kopitar", "Bedard",
    "Celebrini", "Michkov", "Suzuki", "Caufield", "Reinhart", "Verhaeghe",
    # Star defensemen
    "Makar", "Josi", "Fox", "Karlsson", "Heiskanen", "Dahlin", "Hughes",
    "Ekblad", "Pietrangelo", "Hedman", "Letang", "Burns", "Weber", "Chara",
    "Keith", "Doughty", "Subban", "Seider",
    # Star goalies
    "Vasilevskiy", "Hellebuyck", "Saros", "Sorokin", "Shesterkin",
    "Oettinger", "Bobrovsky", "Price", "Lundqvist", "Rask", "Rinne",
    "Fleury", "Brodeur", "Roy", "Hasek", "Quick",
    # All-time icons
    "Gretzky", "Lemieux", "Howe", "Orr", "Messier", "Yzerman", "Sakic",
    "Forsberg", "Jagr", "Selanne", "Bure", "Fedorov", "Modano", "Hull",
    "Lindros", "Trottier", "Bossy", "Lafleur", "Beliveau", "Plante",
    "Sawchuk", "Chelios", "Lidstrom", "Pronger", "Niedermayer", "Stevens",
])


def is_blocked_surname(surname):
    """True if a generated player may not use this surname."""
    try:
        return _fold(surname) in BLOCKED_SURNAMES
    except Exception:
        return False


def pick_surname(pool, tries=12):
    """Pick a surname from pool, re-rolling blocked star names.

    Bounded: after `tries` blocked picks it accepts the last candidate
    rather than looping forever on a pathological pool. Never raises.
    """
    try:
        pool = list(pool or [])
        if not pool:
            return ""
        cand = random.choice(pool)
        for _ in range(tries):
            if not is_blocked_surname(cand):
                return cand
            cand = random.choice(pool)
        return cand
    except Exception:
        try:
            return random.choice(list(pool or ["Player"]))
        except Exception:
            return "Player"
