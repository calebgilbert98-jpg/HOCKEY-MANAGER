# player_faces.py
# Hockey clip-art style player portraits.
# Flat vector look: bold outlines, helmet + visor, jersey shoulders.
# Faces are deterministic per player (seeded by player id) so a player
# always shows the same face. PIL only, no external assets.

import hashlib
import os
import random

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_cache")
_CACHE_TAG = "v2"  # bump when the art style changes so old cached faces refresh
_MEMO = {}

OUTLINE = (32, 24, 20)

SKIN_TONES = [
    (255, 224, 189),
    (241, 194, 125),
    (224, 172, 105),
    (198, 134, 66),
    (141, 85, 36),
    (92, 56, 28),
]

# Helmet shell colors (classic hockey looks)
HELMET_COLORS = [
    (25, 25, 28),      # black
    (235, 235, 235),   # white
    (22, 42, 78),      # navy
    (170, 30, 35),     # red
    (25, 80, 55),      # dark green
    (45, 70, 110),     # royal blue
]

JERSEY_COLORS = [
    (170, 30, 35), (22, 42, 78), (25, 80, 55), (45, 70, 110),
    (200, 120, 20), (90, 30, 90), (25, 25, 28), (120, 150, 170),
]

HAIR_COLORS = [
    (45, 34, 27), (92, 64, 38), (150, 105, 60),
    (200, 150, 80), (230, 200, 130), (170, 60, 40), (120, 120, 125),
]


def _seed_for(player):
    pid = getattr(player, "id", None) or getattr(player, "full_name", str(player))
    h = hashlib.md5(str(pid).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _rr(d, box, radius, **kw):
    """Rounded rectangle helper."""
    d.rounded_rectangle(box, radius=radius, **kw)


def generate_face_image(player, size=128):
    """Return a PIL Image of the player's clip-art hockey portrait."""
    if not _PIL_OK:
        return None
    rng = random.Random(_seed_for(player))
    skin = rng.choice(SKIN_TONES)
    helmet = rng.choice(HELMET_COLORS)
    jersey = rng.choice(JERSEY_COLORS)
    hair_c = rng.choice(HAIR_COLORS)
    visor = rng.random() < 0.62          # most hockey players wear one
    flow = rng.random() < 0.30          # hockey flow out the back
    beard = rng.random() < 0.35         # playoff beard energy
    shade = tuple(max(0, c - 22) for c in skin)
    dark_helmet = tuple(max(0, c - 35) for c in helmet)

    s = size
    k = s / 128.0  # scale factor so the art works at any size
    W = lambda v: int(v * k)

    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = s / 2

    # ---- hockey flow (behind everything) ----
    if flow:
        d.polygon([(cx - W(30), W(64)), (cx + W(30), W(64)),
                   (cx + W(36), W(98)), (cx - W(36), W(98))], fill=hair_c)

    # ---- jersey shoulders ----
    d.polygon([(cx - W(52), s), (cx + W(52), s),
               (cx + W(34), W(96)), (cx - W(34), W(96))],
              fill=jersey, outline=OUTLINE, width=W(3))
    # jersey stripe
    d.polygon([(cx - W(46), W(118)), (cx + W(46), W(118)),
               (cx + W(42), W(108)), (cx - W(42), W(108))], fill=(235, 235, 235))
    # collar
    d.polygon([(cx - W(14), W(96)), (cx + W(14), W(96)),
               (cx + W(10), W(106)), (cx - W(10), W(106))],
              fill=(235, 235, 235), outline=OUTLINE, width=W(2))

    # ---- neck ----
    d.rectangle([cx - W(11), W(78), cx + W(11), W(100)],
                fill=shade, outline=OUTLINE, width=W(2))

    # ---- ears ----
    for side in (-1, 1):
        ex = cx + side * W(33)
        d.ellipse([ex - W(7), W(52), ex + W(7), W(66)],
                  fill=skin, outline=OUTLINE, width=W(2))

    # ---- face (jaw slightly tapered, clip-art style) ----
    d.ellipse([cx - W(34), W(22), cx + W(34), W(94)],
              fill=skin, outline=OUTLINE, width=W(3))

    # ---- helmet dome ----
    # shell
    d.pieslice([cx - W(40), W(-6), cx + W(40), W(66)], 180, 360,
               fill=helmet, outline=OUTLINE, width=W(3))
    # helmet rim band
    d.chord([cx - W(40), W(6), cx + W(40), W(66)], 180, 360, fill=dark_helmet)
    d.arc([cx - W(40), W(6), cx + W(40), W(66)], 180, 360,
          fill=OUTLINE, width=W(2))
    # helmet highlight stripe (clip-art shine)
    d.arc([cx - W(28), W(2), cx + W(28), W(58)], 200, 250,
          fill=(255, 255, 255), width=W(4))
    # ear loops / J-clips
    for side in (-1, 1):
        lx = cx + side * W(37)
        d.rectangle([lx - W(4), W(44), lx + W(4), W(62)],
                    fill=dark_helmet, outline=OUTLINE, width=W(2))

    # ---- visor ----
    if visor:
        _rr(d, [cx - W(27), W(50), cx + W(27), W(66)], W(7),
            fill=(38, 52, 68), outline=OUTLINE, width=W(2))
        # visor shine
        d.line([cx - W(18), W(55), cx - W(6), W(55)],
               fill=(150, 180, 205), width=W(2))
    else:
        # plain eyes, clip-art simple
        for side in (-1, 1):
            ex = cx + side * W(14)
            d.ellipse([ex - W(7), W(52), ex + W(7), W(62)], fill=(255, 255, 255),
                      outline=OUTLINE, width=W(2))
            d.ellipse([ex - W(3), W(54), ex + W(3), W(60)], fill=(25, 25, 25))
        # brows
        for side in (-1, 1):
            ex = cx + side * W(14)
            d.line([ex - W(8), W(47), ex + W(8), W(47)], fill=OUTLINE, width=W(3))

    # ---- nose ----
    d.line([cx, W(64), cx - W(3), W(72)], fill=shade, width=W(3))

    # ---- beard or clean jaw ----
    if beard:
        d.pieslice([cx - W(31), W(52), cx + W(31), W(98)], 20, 160, fill=hair_c)
        d.arc([cx - W(31), W(52), cx + W(31), W(98)], 20, 160,
              fill=OUTLINE, width=W(2))

    # ---- mouth ----
    mouth = rng.choice(["flat", "smirk", "grin"])
    my = W(82)
    if mouth == "grin":
        d.arc([cx - W(12), my - W(8), cx + W(12), my + W(8)], 25, 155,
              fill=OUTLINE, width=W(3))
    elif mouth == "smirk":
        d.arc([cx - W(12), my - W(8), cx + W(12), my + W(8)], 30, 150,
              fill=OUTLINE, width=W(3))
    else:
        d.line([cx - W(10), my, cx + W(10), my], fill=OUTLINE, width=W(3))

    return img


def get_face_photo(player, size=128):
    """Return a cached ImageTk.PhotoImage for a player (or None without PIL)."""
    if not _PIL_OK:
        return None
    pid = getattr(player, "id", None) or str(getattr(player, "full_name", player))
    key = (pid, size, _CACHE_TAG)
    if key in _MEMO:
        return _MEMO[key]

    path = None
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in str(pid))[:40]
        path = os.path.join(_CACHE_DIR, f"{safe}_{size}_{_CACHE_TAG}.png")
        if os.path.exists(path):
            from PIL import Image as _I
            img = _I.open(path).convert("RGBA")
        else:
            raise FileNotFoundError
    except Exception:
        img = generate_face_image(player, size=size)
        if img is None:
            return None
        try:
            if path:
                img.save(path)
        except Exception:
            pass

    try:
        photo = ImageTk.PhotoImage(img)
    except Exception:
        return None
    _MEMO[key] = photo
    return photo


def clear_memory_cache():
    _MEMO.clear()
