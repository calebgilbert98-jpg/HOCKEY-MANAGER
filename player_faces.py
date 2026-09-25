# player_faces.py
# Very basic cartoon face generator for player profiles.
# Faces are deterministic per player (seeded by player id) so a player
# always shows the same face. Kept intentionally simple: flat cartoon
# style drawn with PIL, no external assets.

import hashlib
import os
import random

try:
    from PIL import Image, ImageDraw, ImageTk
    _PIL_OK = True
except Exception:
    _PIL_OK = False

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_cache")
_MEMO = {}

SKIN_TONES = [
    (255, 224, 189),  # light
    (241, 194, 125),  # tan
    (224, 172, 105),  # medium
    (198, 134, 66),   # brown
    (141, 85, 36),    # dark brown
    (92, 56, 28),     # deep
]

HAIR_COLORS = [
    (45, 34, 27),    # black
    (92, 64, 38),    # dark brown
    (150, 105, 60),  # light brown
    (200, 150, 80),  # dirty blond
    (230, 200, 130), # blond
    (170, 60, 40),   # ginger
    (120, 120, 125),# grey
]

EYE_COLORS = [
    (60, 45, 30), (80, 60, 35), (50, 90, 60),
    (70, 110, 140), (100, 140, 170), (45, 45, 45),
]

HAIR_STYLES = [
    "short", "messy", "buzz", "long", "bald", "side_part", "mohawk", "curly",
]


def _seed_for(player):
    pid = getattr(player, "id", None) or getattr(player, "full_name", str(player))
    h = hashlib.md5(str(pid).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _draw_hair(d, style, rng, skin, hair, w, h, cx, top, face_w, face_h):
    """Draw a simple cartoon hairdo behind/around the face ellipse."""
    # Back hair mass (drawn before face for long styles)
    if style == "long":
        d.rectangle([cx - face_w * 0.62, top - 6, cx + face_w * 0.62, top + face_h * 0.95],
                    fill=hair)
    # Top hairdos (drawn after face)
    if style == "short":
        d.pieslice([cx - face_w * 0.58, top - 14, cx + face_w * 0.58, top + face_h * 0.38],
                   180, 360, fill=hair)
        d.rectangle([cx - face_w * 0.58, top + face_h * 0.10,
                     cx + face_w * 0.58, top + face_h * 0.20], fill=hair)
    elif style == "messy":
        pts = []
        n = 9
        for i in range(n + 1):
            x = cx - face_w * 0.60 + (face_w * 1.20) * i / n
            y = top - 4 - (14 if i % 2 == 0 else 2) - rng.randint(0, 6)
            pts.append((x, y))
        pts.append((cx + face_w * 0.60, top + face_h * 0.22))
        pts.append((cx - face_w * 0.60, top + face_h * 0.22))
        d.polygon(pts, fill=hair)
    elif style == "buzz":
        d.pieslice([cx - face_w * 0.55, top - 8, cx + face_w * 0.55, top + face_h * 0.30],
                   180, 360, fill=hair)
    elif style == "side_part":
        d.pieslice([cx - face_w * 0.58, top - 12, cx + face_w * 0.58, top + face_h * 0.34],
                   180, 360, fill=hair)
        d.polygon([(cx - face_w * 0.58, top + face_h * 0.16),
                   (cx + face_w * 0.10, top - 12),
                   (cx + face_w * 0.30, top + face_h * 0.16)], fill=hair)
    elif style == "mohawk":
        d.polygon([(cx - 10, top + face_h * 0.18), (cx + 10, top + face_h * 0.18),
                   (cx + 6, top - 26), (cx - 6, top - 26)], fill=hair)
    elif style == "curly":
        for i in range(7):
            x = cx - face_w * 0.55 + (face_w * 1.10) * i / 6
            d.ellipse([x - 13, top - 16, x + 13, top + 10], fill=hair)
    # "bald": nothing on top (maybe slight fringe)
    if style == "bald" and rng.random() < 0.5:
        d.arc([cx - face_w * 0.55, top - 6, cx + face_w * 0.55, top + face_h * 0.30],
              180, 360, fill=hair, width=4)


def generate_face_image(player, size=128):
    """Return a PIL Image of the player's cartoon face (deterministic)."""
    if not _PIL_OK:
        return None
    rng = random.Random(_seed_for(player))
    skin = rng.choice(SKIN_TONES)
    hair = rng.choice(HAIR_COLORS)
    eye = rng.choice(EYE_COLORS)
    style = rng.choice(HAIR_STYLES)
    beard = rng.random() < 0.28
    glasses = rng.random() < 0.12

    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = s / 2, s / 2 + 4
    face_w, face_h = s * 0.36, s * 0.42
    top = cy - face_h

    # Long hair goes behind the face
    if style == "long":
        _draw_hair(d, style, rng, skin, hair, s, s, cx, top, face_w, face_h)

    # Face
    d.ellipse([cx - face_w, top, cx + face_w, top + face_h * 2], fill=skin)
    # Ears
    d.ellipse([cx - face_w - 8, cy - 14, cx - face_w + 8, cy + 10], fill=skin)
    d.ellipse([cx + face_w - 8, cy - 14, cx + face_w + 8, cy + 10], fill=skin)

    # Hair on top
    if style != "long":
        _draw_hair(d, style, rng, skin, hair, s, s, cx, top, face_w, face_h)

    # Eyebrows
    brow_y = cy - face_h * 0.28
    for side in (-1, 1):
        ex = cx + side * face_w * 0.38
        thick = rng.choice([3, 4, 5])
        d.line([ex - 16, brow_y - rng.randint(0, 3), ex + 16, brow_y + rng.randint(0, 3)],
               fill=hair, width=thick)

    # Eyes
    eye_y = cy - face_h * 0.08
    for side in (-1, 1):
        ex = cx + side * face_w * 0.38
        d.ellipse([ex - 11, eye_y - 8, ex + 11, eye_y + 8], fill=(255, 255, 255))
        px = ex + rng.randint(-3, 3)
        d.ellipse([px - 5, eye_y - 5, px + 5, eye_y + 5], fill=eye)
        d.ellipse([px - 2, eye_y - 2, px + 2, eye_y + 2], fill=(20, 20, 20))

    # Glasses
    if glasses:
        for side in (-1, 1):
            ex = cx + side * face_w * 0.38
            d.ellipse([ex - 14, eye_y - 11, ex + 14, eye_y + 11],
                      outline=(40, 40, 40), width=3)
        d.line([cx - face_w * 0.38 + 14, eye_y, cx + face_w * 0.38 - 14, eye_y],
               fill=(40, 40, 40), width=3)

    # Nose
    nose_y = cy + face_h * 0.18
    d.line([cx, nose_y - 8, cx - 4, nose_y + 8], fill=tuple(max(0, c - 40) for c in skin), width=3)

    # Beard
    if beard:
        beard_color = hair
        d.pieslice([cx - face_w * 0.92, cy - 6, cx + face_w * 0.92, top + face_h * 2 + 4],
                   15, 165, fill=beard_color)

    # Mouth (smile / flat / smirk)
    mouth_y = cy + face_h * (0.52 if not beard else 0.42)
    mouth = rng.choice(["smile", "flat", "smirk"])
    dark = (120, 60, 50)
    if mouth == "smile":
        d.arc([cx - 22, mouth_y - 14, cx + 22, mouth_y + 14], 20, 160, fill=dark, width=4)
    elif mouth == "smirk":
        d.arc([cx - 22, mouth_y - 14, cx + 22, mouth_y + 14], 25, 150, fill=dark, width=4)
    else:
        d.line([cx - 18, mouth_y, cx + 18, mouth_y], fill=dark, width=4)

    # Subtle cheek shading for depth
    shade = tuple(max(0, c - 18) for c in skin)
    d.arc([cx - face_w, top, cx + face_w, top + face_h * 2], 300, 360, fill=shade, width=3)

    return img


def get_face_photo(player, size=128):
    """Return a cached ImageTk.PhotoImage for a player (or None without PIL).

    Keeps a strong reference in the module cache so Tk doesn't garbage
    collect the image.
    """
    if not _PIL_OK:
        return None
    pid = getattr(player, "id", None) or str(getattr(player, "full_name", player))
    key = (pid, size)
    if key in _MEMO:
        return _MEMO[key]

    # Disk cache so faces survive restarts without regeneration cost.
    path = None
    try:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        safe = "".join(c if c.isalnum() else "_" for c in str(pid))[:40]
        path = os.path.join(_CACHE_DIR, f"{safe}_{size}.png")
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
