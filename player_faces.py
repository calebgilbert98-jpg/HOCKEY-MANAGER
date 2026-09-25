# player_faces.py
# Video-game quality player portraits (stylized, not photorealistic).
# Layered rendering: base shapes -> soft shading -> features -> highlights.
# Drawn at 2x and downscaled for anti-aliasing.
# Faces are deterministic per player (seeded by player id).
# PIL only, no external assets.

import hashlib
import os
import random

try:
    from PIL import Image, ImageDraw, ImageFilter
    _PIL_OK = True
except Exception:
    _PIL_OK = False

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_cache")
_CACHE_TAG = "v3"  # bump when the art style changes so old cached faces refresh
_MEMO = {}

# Skin tones with undertones (base, shadow, highlight)
SKIN_TONES = [
    ((255, 224, 189), (232, 190, 155), (255, 240, 215)),  # fair
    ((241, 194, 125), (215, 160, 100), (255, 215, 155)),  # light
    ((224, 172, 105), (198, 140, 80),  (245, 195, 130)),  # medium
    ((198, 134, 66),  (170, 105, 45),  (220, 160, 95)),   # tan
    ((141, 85, 36),   (115, 65, 25),   (165, 110, 55)),   # brown
    ((92, 56, 28),    (70, 40, 18),    (115, 75, 40)),    # dark
]

HELMET_COLORS = [
    (25, 25, 28), (235, 235, 235), (22, 42, 78),
    (170, 30, 35), (25, 80, 55), (45, 70, 110),
    (200, 120, 20), (90, 30, 90),
]

JERSEY_COLORS = [
    (170, 30, 35), (22, 42, 78), (25, 80, 55), (45, 70, 110),
    (200, 120, 20), (90, 30, 90), (25, 25, 28), (120, 150, 170),
    (200, 200, 200), (30, 100, 120),
]

HAIR_COLORS = [
    (45, 34, 27), (92, 64, 38), (150, 105, 60),
    (200, 150, 80), (210, 180, 120), (170, 60, 40),
    (120, 120, 125), (30, 30, 32),
]

HAIR_STYLES = ["short", "flow", "buzz", "side_part", "curly", "bald"]

# Iris colors
IRIS_COLORS = [
    (85, 60, 40), (60, 45, 30), (100, 75, 50),   # browns
    (70, 100, 130), (90, 120, 150),               # blues
    (85, 110, 70), (100, 125, 85),                # greens/hazels
    (50, 50, 55),                                 # dark
]

FACE_SHAPES = ["oval", "round", "square", "oblong"]


def _seed_for(player):
    pid = getattr(player, "id", None) or getattr(player, "full_name", str(player))
    h = hashlib.md5(str(pid).encode("utf-8")).hexdigest()
    return int(h[:8], 16)


def _shade(color, amt):
    """Darken/lighten an RGB color by amt (-255 to 255)."""
    return tuple(max(0, min(255, c + amt)) for c in color)


def _blend(c1, c2, t):
    """Blend two RGB colors. t=0 -> c1, t=1 -> c2."""
    return tuple(int(c1[i] * (1 - t) + c2[i] * t) for i in range(3))


def _overlay(img, draw_fn):
    """Draw alpha-blended shapes via an overlay layer (PIL fills don't blend).

    draw_fn receives an ImageDraw for a transparent layer; the layer is then
    alpha-composited onto img. Returns a fresh ImageDraw for img.
    """
    from PIL import ImageDraw as _ID
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = _ID.Draw(layer, "RGBA")
    draw_fn(ld)
    img.alpha_composite(layer)
    return _ID.Draw(img, "RGBA")


def generate_face_image(player, size=128):
    """Return a PIL Image of the player's stylized hockey portrait.

    All semi-transparent shading goes through _overlay() so it blends with
    the face, not the background (PIL fills don't alpha-blend).
    """
    if not _PIL_OK:
        return None

    rng = random.Random(_seed_for(player))
    age = getattr(player, "age", 25)

    # --- Randomize appearance ---
    skin_base, skin_shadow, skin_hi = rng.choice(SKIN_TONES)
    helmet_c = rng.choice(HELMET_COLORS)
    jersey_c = rng.choice(JERSEY_COLORS)
    hair_c = rng.choice(HAIR_COLORS)
    iris_c = rng.choice(IRIS_COLORS)
    face_shape = rng.choice(FACE_SHAPES)
    hair_style = rng.choice(HAIR_STYLES)
    visor = rng.random() < 0.65
    beard_style = rng.choices(
        ["clean", "stubble", "beard", "goatee"],
        weights=[0.40, 0.30, 0.20, 0.10]
    )[0]
    if age > 30 and beard_style == "clean" and rng.random() < 0.4:
        beard_style = rng.choice(["stubble", "beard"])
    mouth_style = rng.choice(["neutral", "smile", "smirk"])

    # Work at 2x for anti-aliasing
    S = size * 2
    k = S / 256.0
    W = lambda v: int(v * k)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    cx = S / 2

    # Face shape dimensions
    if face_shape == "oval":
        fw, fh_top, fh_bot, jaw_w = W(68), W(44), W(188), W(52)
    elif face_shape == "round":
        fw, fh_top, fh_bot, jaw_w = W(72), W(48), W(184), W(60)
    elif face_shape == "square":
        fw, fh_top, fh_bot, jaw_w = W(66), W(46), W(186), W(62)
    else:  # oblong
        fw, fh_top, fh_bot, jaw_w = W(62), W(42), W(192), W(48)
    face_top, face_bot = fh_top, fh_bot

    eye_y = W(108)
    eye_spacing = fw * 0.48
    eye_w, eye_h = W(14), W(9)
    mouth_y = W(168)

    # ================= JERSEY =================
    shoulder_top = W(190)
    d.polygon([
        (cx - W(105), S), (cx + W(105), S),
        (cx + W(68), shoulder_top), (cx - W(68), shoulder_top)
    ], fill=jersey_c)

    def _shoulder_shade(ld):
        for i in range(3):
            inset = W(8 + i * 10)
            alpha = 40 - i * 12
            ld.polygon([
                (cx - W(105) + inset, S), (cx - W(68) + inset * 0.6, shoulder_top),
                (cx - W(68) + inset * 0.6 + W(4), shoulder_top), (cx - W(105) + inset + W(4), S)
            ], fill=(0, 0, 0, alpha))
            ld.polygon([
                (cx + W(105) - inset, S), (cx + W(68) - inset * 0.6, shoulder_top),
                (cx + W(68) - inset * 0.6 - W(4), shoulder_top), (cx + W(105) - inset - W(4), S)
            ], fill=(0, 0, 0, alpha))
    d = _overlay(img, _shoulder_shade)

    stripe_c = (235, 235, 235) if sum(jersey_c) < 400 else (30, 30, 35)
    d.polygon([
        (cx - W(92), W(236)), (cx + W(92), W(236)),
        (cx + W(84), W(216)), (cx - W(84), W(216))
    ], fill=stripe_c)
    d.polygon([
        (cx - W(28), shoulder_top), (cx + W(28), shoulder_top), (cx, W(212))
    ], fill=_shade(jersey_c, -30))
    d.polygon([
        (cx - W(22), shoulder_top + W(2)), (cx + W(22), shoulder_top + W(2)), (cx, W(206))
    ], fill=stripe_c)
    d.line([(cx - W(105), S), (cx - W(68), shoulder_top)],
           fill=(20, 18, 16, 255), width=W(4))
    d.line([(cx + W(105), S), (cx - W(68), shoulder_top)],
           fill=(20, 18, 16, 255), width=W(4))

    # ================= NECK =================
    neck_w = W(24)
    d.rectangle([cx - neck_w, W(158), cx + neck_w, shoulder_top + W(4)], fill=skin_shadow)
    d.rectangle([cx - neck_w // 2, W(158), cx + neck_w // 2, shoulder_top + W(4)],
                fill=_shade(skin_base, 10))

    # ================= FACE BASE =================
    d.ellipse([cx - fw, face_top, cx + fw, face_bot], fill=skin_base)
    if face_shape == "square":
        d.rectangle([cx - jaw_w, W(130), cx - fw + W(8), W(175)], fill=skin_base)
        d.rectangle([cx + fw - W(8), W(130), cx + jaw_w, W(175)], fill=skin_base)

    def _face_shade(ld):
        for side in (-1, 1):
            cheek_x = cx + side * fw * 0.55
            ld.ellipse([cheek_x - W(18), W(108), cheek_x + W(18), W(138)],
                       fill=(0, 0, 0, 18))
        ld.ellipse([cx - jaw_w, face_bot - W(20), cx + jaw_w, face_bot + W(6)],
                   fill=(0, 0, 0, 25))
        for side in (-1, 1):
            tx = cx + side * fw * 0.85
            ld.ellipse([tx - W(10), W(60), tx + W(10), W(95)], fill=(0, 0, 0, 15))
        ld.ellipse([cx - fw * 0.6, face_top + W(4), cx + fw * 0.6, W(78)],
                   fill=(255, 255, 255, 22))
        ld.polygon([(cx - W(5), W(95)), (cx + W(5), W(95)),
                    (cx + W(7), W(125)), (cx - W(7), W(125))],
                   fill=(255, 255, 255, 18))
    # Blur the shade layer for softness
    from PIL import ImageFilter as _IF
    _sl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _sld = ImageDraw.Draw(_sl, "RGBA")
    _face_shade(_sld)
    _sl = _sl.filter(_IF.GaussianBlur(W(6)))
    img.alpha_composite(_sl)
    d = ImageDraw.Draw(img, "RGBA")

    d.ellipse([cx - fw, face_top, cx + fw, face_bot],
              outline=(45, 32, 24, 255), width=W(2))

    # ================= EARS =================
    for side in (-1, 1):
        ex = cx + side * (fw - W(1))
        d.ellipse([ex - W(8), W(108), ex + W(8), W(132)], fill=skin_base)
    def _ear_shade(ld):
        for side in (-1, 1):
            ex = cx + side * (fw - W(1))
            ld.ellipse([ex - W(4), W(114), ex + W(4), W(126)], fill=(0, 0, 0, 40))
    d = _overlay(img, _ear_shade)

    # ================= EYES =================
    for side in (-1, 1):
        ex = cx + side * eye_spacing
        # Sclera
        d.ellipse([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h],
                  fill=(238, 232, 222))
        # Iris
        iris_r = W(7)
        d.ellipse([ex - iris_r, eye_y - iris_r, ex + iris_r, eye_y + iris_r], fill=iris_c)
        d.ellipse([ex - iris_r, eye_y - iris_r, ex + iris_r, eye_y + iris_r],
                  outline=_shade(iris_c, -40), width=W(2))
        # Pupil
        pup_r = W(3)
        d.ellipse([ex - pup_r, eye_y - pup_r, ex + pup_r, eye_y + pup_r], fill=(15, 12, 12))
        # Upper lid
        d.arc([ex - eye_w - W(2), eye_y - eye_h - W(4), ex + eye_w + W(2), eye_y + eye_h],
              start=195, end=345, fill=(35, 25, 20, 255), width=W(3))

    def _eye_shade(ld):
        for side in (-1, 1):
            ex = cx + side * eye_spacing
            # Socket shadow
            ld.ellipse([ex - eye_w - W(3), eye_y - eye_h - W(5),
                        ex + eye_w + W(3), eye_y + W(2)], fill=(0, 0, 0, 30))
            # Catchlight
            ld.ellipse([ex - W(5), eye_y - W(6), ex - W(2), eye_y - W(3)],
                       fill=(255, 255, 255, 230))
            # Lower lid
            ld.arc([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h + W(3)],
                   start=15, end=165, fill=(35, 25, 20, 120), width=W(2))
    d = _overlay(img, _eye_shade)

    # Eyebrows
    brow_y = eye_y - eye_h - W(10)
    brow_c = _shade(_blend(hair_c, (55, 48, 44), 0.62), -18)
    for side in (-1, 1):
        ex = cx + side * eye_spacing
        d.polygon([
            (ex - W(13), brow_y + W(4)), (ex - W(8), brow_y - W(1)),
            (ex + W(6), brow_y), (ex + W(13), brow_y + W(3)),
            (ex + W(11), brow_y + W(6)), (ex - W(6), brow_y + W(5)),
            (ex - W(11), brow_y + W(6)),
        ], fill=brow_c)

    # ================= NOSE =================
    nose_bot = W(148)
    d.ellipse([cx - W(11), nose_bot - W(14), cx + W(11), nose_bot + W(2)],
              fill=_shade(skin_base, -8))
    def _nose_detail(ld):
        # Bridge shadow
        ld.polygon([(cx - W(4), W(118)), (cx - W(2), nose_bot - W(8)),
                    (cx - W(9), nose_bot - W(4)), (cx - W(10), W(128))],
                   fill=(0, 0, 0, 35))
        # Nostrils
        for side in (-1, 1):
            nx = cx + side * W(7)
            ld.ellipse([nx - W(4), nose_bot - W(6), nx + W(4), nose_bot],
                       fill=(50, 35, 28, 220))
        # Highlight
        ld.line([(cx + W(2), W(124)), (cx + W(3), nose_bot - W(10))],
                fill=(255, 255, 255, 70), width=W(3))
    d = _overlay(img, _nose_detail)

    # ================= FACIAL HAIR =================
    beard_c = _shade(_blend(hair_c, (70, 60, 55), 0.35), -12)
    if beard_style == "beard":
        bw = jaw_w - W(6)
        d.pieslice([cx - bw, W(140), cx + bw, face_bot + W(6)], 18, 162, fill=beard_c)
        def _beard_tex(ld):
            for _ in range(50):
                bx = rng.uniform(cx - bw + W(4), cx + bw - W(4))
                by = rng.uniform(W(148), face_bot - W(2))
                if ((bx - cx) / bw) ** 2 + ((by - W(162)) / W(26)) ** 2 < 1:
                    if abs(bx - cx) < W(14) and abs(by - mouth_y) < W(8):
                        continue
                    ld.point((int(bx), int(by)),
                             fill=(*_shade(beard_c, rng.randint(-25, 15)), 140))
        d = _overlay(img, _beard_tex)
    elif beard_style == "goatee":
        d.ellipse([cx - W(18), W(152), cx + W(18), W(184)], fill=beard_c)
        d.ellipse([cx - W(14), mouth_y - W(9), cx + W(14), mouth_y - W(2)], fill=beard_c)
    elif beard_style == "stubble":
        def _stubble(ld):
            stubble_c = _blend(hair_c, (90, 80, 75), 0.55)
            ld.pieslice([cx - jaw_w + W(6), W(138), cx + jaw_w - W(6), face_bot - W(2)],
                        15, 165, fill=(*stubble_c, 50))
            ld.ellipse([cx - W(20), mouth_y - W(14), cx + W(20), mouth_y - W(6)],
                       fill=(*stubble_c, 35))
        _stubl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        _stld = ImageDraw.Draw(_stubl, "RGBA")
        _stubble(_stld)
        _stubl = _stubl.filter(_IF.GaussianBlur(W(4)))
        img.alpha_composite(_stubl)
        d = ImageDraw.Draw(img, "RGBA")

    # ================= MOUTH =================
    mouth_w = W(14)
    lip_c = _blend(skin_base, (160, 100, 95), 0.22)
    d.ellipse([cx - mouth_w, mouth_y - W(5), cx + mouth_w, mouth_y + W(5)],
              fill=_shade(lip_c, -10))
    if mouth_style == "smile":
        d.arc([cx - mouth_w, mouth_y - W(10), cx + mouth_w, mouth_y + W(8)],
              20, 160, fill=(70, 40, 35, 255), width=W(3))
    elif mouth_style == "smirk":
        d.arc([cx - mouth_w, mouth_y - W(8), cx + mouth_w, mouth_y + W(6)],
              25, 155, fill=(70, 40, 35, 255), width=W(3))
    else:
        d.line([cx - mouth_w + W(3), mouth_y, cx + mouth_w - W(3), mouth_y],
               fill=(70, 40, 35, 255), width=W(3))
    def _chin_hi(ld):
        ld.ellipse([cx - W(14), mouth_y + W(10), cx + W(14), mouth_y + W(18)],
                   fill=(255, 255, 255, 30))
    d = _overlay(img, _chin_hi)

    # ================= HAIR =================
    if hair_style == "flow":
        for side in (-1, 1):
            hx = cx + side * (fw - W(2))
            x0 = hx - W(14) if side < 0 else hx - W(2)
            x1 = hx + W(2) if side < 0 else hx + W(14)
            d.ellipse([x0, W(100), x1, W(165)], fill=hair_c)
    elif hair_style == "curly":
        for i in range(8):
            side = -1 if i % 2 == 0 else 1
            hx = cx + side * (fw * 0.9)
            hy = W(88) + (i // 2) * W(12)
            d.ellipse([hx - W(8), hy - W(8), hx + W(8), hy + W(8)], fill=hair_c)

    # ================= HELMET =================
    helm_top, helm_bot = W(8), W(78)
    helm_w = fw + W(14)
    d.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
               180, 360, fill=helmet_c)

    _hs = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _hsd = ImageDraw.Draw(_hs, "RGBA")
    _hsd.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
                  270, 360, fill=(0, 0, 0, 55))
    _hsd.ellipse([cx - helm_w + W(10), helm_top + W(4), cx - W(10), helm_top + W(36)],
                 fill=(255, 255, 255, 70))
    _hs = _hs.filter(_IF.GaussianBlur(W(8)))
    _hm = Image.new("L", (S, S), 0)
    _hmd = ImageDraw.Draw(_hm)
    _hmd.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
                  180, 360, fill=255)
    _hs.putalpha(_hm)
    img.alpha_composite(_hs)
    d = ImageDraw.Draw(img, "RGBA")

    d.arc([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
          180, 360, fill=(20, 18, 16, 255), width=W(3))
    d.line([(cx - helm_w + W(4), helm_bot), (cx + helm_w - W(4), helm_bot)],
           fill=(20, 18, 16, 255), width=W(3))
    # Vents
    def _vents(ld):
        for side in (-1, 1):
            vx = cx + side * helm_w * 0.55
            for i in range(3):
                vy = W(28) + i * W(10)
                ld.ellipse([vx - W(4), vy - W(3), vx + W(4), vy + W(3)],
                           fill=(0, 0, 0, 100))
    d = _overlay(img, _vents)
    # Center stripe
    if sum(helmet_c) > 100:
        d.rectangle([cx - W(4), helm_top + W(2), cx + W(4), W(50)],
                    fill=(255, 255, 255, 255))
    # Ear loops
    for side in (-1, 1):
        lx = cx + side * (helm_w - W(2))
        d.rectangle([lx - W(5), W(62), lx + W(5), W(86)], fill=_shade(helmet_c, -40))
    # Chin strap (short, to jaw edge)
    for side in (-1, 1):
        sx = cx + side * (helm_w - W(8))
        d.line([(sx, W(82)), (cx + side * (jaw_w - W(2)), W(150))],
               fill=(225, 225, 225, 255), width=W(3))

    # ================= VISOR =================
    if visor:
        visor_top, visor_bot = W(96), W(132)
        visor_w = fw * 0.88
        def _visor(ld):
            ld.rounded_rectangle(
                [cx - visor_w, visor_top, cx + visor_w, visor_bot],
                radius=W(10), fill=(140, 165, 190, 45))
            ld.polygon([
                (cx - visor_w + W(12), visor_top + W(4)),
                (cx - visor_w + W(34), visor_top + W(4)),
                (cx - visor_w + W(18), visor_bot - W(4)),
                (cx - visor_w - W(4), visor_bot - W(4)),
            ], fill=(180, 205, 230, 60))
        d = _overlay(img, _visor)
        d.line([(cx - visor_w, visor_top), (cx + visor_w, visor_top)],
               fill=(20, 18, 16, 255), width=W(3))

    # ================= AGE =================
    if age >= 28:
        def _age(ld):
            for side in (-1, 1):
                ex = cx + side * eye_spacing
                n_lines = 2 if age >= 32 else 1
                for i in range(n_lines):
                    ld.line([(ex + side * (eye_w + W(2)), eye_y - W(2) + i * W(5)),
                             (ex + side * (eye_w + W(7)), eye_y + i * W(5))],
                            fill=(0, 0, 0, 45), width=W(2))
            if age >= 32:
                for i in range(2):
                    ly = W(58) + i * W(10)
                    ld.arc([cx - W(40), ly - W(6), cx + W(40), ly + W(6)],
                           200, 340, fill=(0, 0, 0, 35), width=W(2))
        d = _overlay(img, _age)

    # Downscale for anti-aliasing
    img = img.resize((size, size), Image.LANCZOS)
    return img


def get_face_photo(player, size=128):
    """Return a cached ImageTk.PhotoImage for a player (or None without PIL)."""
    if not _PIL_OK:
        return None
    try:
        from PIL import ImageTk
    except Exception:
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
