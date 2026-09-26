# player_faces.py
# Video-game quality player portraits (stylized, not photorealistic).
# Layered rendering: base shapes -> soft shading -> features -> highlights.
# Drawn at 3x and downscaled for anti-aliasing.
# Faces are deterministic per player (seeded by player id).
# PIL only, no external assets.

import hashlib
import math
import os
import random

try:
    from PIL import Image, ImageDraw, ImageFilter
    _PIL_OK = True
except Exception:
    _PIL_OK = False

_CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_cache")
_CACHE_TAG = "v5"  # bump when the art style changes so old cached faces refresh
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

# Grey used for aging hair/beards
GREY_HAIR = (205, 205, 210)

HAIR_STYLES = ["short", "flow", "buzz", "side_part", "curly", "bald",
               "long", "ponytail", "fade", "man_bun", "mohawk"]
HAIR_WEIGHTS = [0.16, 0.10, 0.10, 0.12, 0.10, 0.06,
                0.08, 0.07, 0.09, 0.05, 0.07]

BEARD_STYLES = ["clean", "stubble", "short_beard", "full_beard", "goatee", "mustache"]
BEARD_WEIGHTS = [0.34, 0.26, 0.15, 0.10, 0.08, 0.07]

MOUTH_STYLES = ["neutral", "smile", "smirk", "grin"]
MOUTH_WEIGHTS = [0.40, 0.30, 0.15, 0.15]

BROW_STYLES = ["natural", "arched", "flat", "angled"]

# Iris colors
IRIS_COLORS = [
    (85, 60, 40), (60, 45, 30), (100, 75, 50),   # browns
    (70, 100, 130), (90, 120, 150),               # blues
    (85, 110, 70), (100, 125, 85),                # greens/hazels
    (50, 50, 55),                                 # dark
]

FACE_SHAPES = ["oval", "round", "square", "oblong", "heart", "diamond", "pear"]


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


def _blurred_overlay(img, draw_fn, radius):
    """Like _overlay but blurs the layer first (soft shadows)."""
    from PIL import ImageDraw as _ID
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ld = _ID.Draw(layer, "RGBA")
    draw_fn(ld)
    layer = layer.filter(ImageFilter.GaussianBlur(radius))
    img.alpha_composite(layer)
    return ImageDraw.Draw(img, "RGBA")

def generate_face_image(player, size=128):
    """Stylized video-game portrait (NHL 2010/2014 style).

    Deterministic per player id: skin tone, face shape, hair style/color,
    beard, eyes, age effects (grey hair, wrinkles) and more are all derived
    from a seeded RNG. All alpha blending via _overlay().
    """
    if not _PIL_OK:
        return None

    rng = random.Random(_seed_for(player))
    age = getattr(player, "age", 25)

    skin_base, skin_shadow, skin_hi = rng.choice(SKIN_TONES)
    helmet_c = rng.choice(HELMET_COLORS)
    jersey_c = rng.choice(JERSEY_COLORS)
    hair_c = rng.choice(HAIR_COLORS)
    iris_c = rng.choice(IRIS_COLORS)
    face_shape = rng.choice(FACE_SHAPES)
    hair_style = rng.choices(HAIR_STYLES, weights=HAIR_WEIGHTS)[0]
    beard_style = rng.choices(BEARD_STYLES, weights=BEARD_WEIGHTS)[0]
    mouth_style = rng.choices(MOUTH_STYLES, weights=MOUTH_WEIGHTS)[0]
    brow_style = rng.choice(BROW_STYLES)
    brow_thick = rng.choice([0.8, 1.0, 1.0, 1.25, 1.5])
    nose_wf = rng.uniform(0.85, 1.25)     # nose width factor
    nose_len = rng.uniform(-6, 8)         # nose length offset (px at 384)
    ear_size = rng.uniform(0.85, 1.15)
    visor = rng.random() < 0.65
    freckles = rng.random() < 0.30
    mole = rng.random() < 0.12

    # ---- Age effects -------------------------------------------------
    # grey_t: 0 young -> ~0.9 for late-30s. Wrinkle intensity grows 28+.
    if age >= 33:
        grey_t = min(0.9, 0.45 + (age - 33) * 0.09)
    elif age >= 30:
        grey_t = 0.15
    else:
        grey_t = 0.0
    hair_c = _blend(hair_c, GREY_HAIR, grey_t)
    wrinkle = 0.0
    if age >= 28:
        wrinkle = min(1.0, (age - 28) / 10.0)
    youthful = age < 21

    # Beard bias by age: veterans rarely clean-shaven, kids rarely bearded
    if age > 30 and beard_style == "clean" and rng.random() < 0.45:
        beard_style = rng.choices(["stubble", "short_beard", "full_beard"],
                                  weights=[0.4, 0.35, 0.25])[0]
    if age < 21 and beard_style in ("short_beard", "full_beard"):
        beard_style = rng.choices(["clean", "stubble"], weights=[0.7, 0.3])[0]
    beard_c = _shade(_blend(hair_c, (65, 58, 52), 0.4), -10)
    # Grey the beard a touch less than the hair (looks natural)
    beard_c = _blend(beard_c, GREY_HAIR, grey_t * 0.8)

    # Higher res for detail, downscaled at the end for anti-aliasing
    S = size * 3
    k = S / 384.0
    W = lambda v: max(1, int(v * k))

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    cx = S / 2

    # Face geometry per shape: (half-width, top, bottom, jaw half-width)
    if face_shape == "oval":
        fw, fh_top, fh_bot, jaw_w = W(88), W(58), W(258), W(68)
    elif face_shape == "round":
        fw, fh_top, fh_bot, jaw_w = W(94), W(62), W(250), W(78)
    elif face_shape == "square":
        fw, fh_top, fh_bot, jaw_w = W(86), W(60), W(254), W(80)
    elif face_shape == "heart":
        fw, fh_top, fh_bot, jaw_w = W(92), W(58), W(256), W(58)
    elif face_shape == "diamond":
        fw, fh_top, fh_bot, jaw_w = W(84), W(60), W(258), W(62)
    elif face_shape == "pear":
        fw, fh_top, fh_bot, jaw_w = W(82), W(60), W(254), W(84)
    else:  # oblong
        fw, fh_top, fh_bot, jaw_w = W(80), W(56), W(264), W(62)
    face_top, face_bot = fh_top, fh_bot

    # Feature positions
    eye_y = W(148)
    eye_spacing = fw * 0.52
    nose_bot = W(200) + W(nose_len)
    mouth_y = W(228)

    # ================= JERSEY =================
    shoulder_top = W(262)
    d.polygon([
        (cx - W(140), S), (cx + W(140), S),
        (cx + W(90), shoulder_top), (cx - W(90), shoulder_top)
    ], fill=jersey_c)

    def _jersey_shade(ld):
        for i in range(5):
            inset = W(10 + i * 14)
            alpha = 35 - i * 6
            ld.polygon([
                (cx - W(140) + inset, S), (cx - W(90) + inset * 0.6, shoulder_top),
                (cx - W(90) + inset * 0.6 + W(6), shoulder_top), (cx - W(140) + inset + W(6), S)
            ], fill=(0, 0, 0, alpha))
            ld.polygon([
                (cx + W(140) - inset, S), (cx + W(90) - inset * 0.6, shoulder_top),
                (cx + W(90) - inset * 0.6 - W(6), shoulder_top), (cx - W(140) + inset - W(6), S)
            ], fill=(0, 0, 0, alpha))
        ld.polygon([
            (cx - W(30), S), (cx + W(30), S),
            (cx + W(20), shoulder_top), (cx - W(20), shoulder_top)
        ], fill=(255, 255, 255, 18))
    d = _blurred_overlay(img, _jersey_shade, W(8))

    stripe_c = (235, 235, 235) if sum(jersey_c) < 400 else (30, 30, 35)
    d.polygon([
        (cx - W(122), W(322)), (cx + W(122), W(322)),
        (cx + W(112), W(300)), (cx - W(112), W(300))
    ], fill=stripe_c)
    # Collar
    d.polygon([
        (cx - W(36), shoulder_top), (cx + W(36), shoulder_top), (cx, W(290))
    ], fill=_shade(jersey_c, -35))
    d.polygon([
        (cx - W(28), shoulder_top + W(2)), (cx + W(28), shoulder_top + W(2)), (cx, W(282))
    ], fill=stripe_c)

    # ================= NECK =================
    neck_w = W(32)
    d.rectangle([cx - neck_w, W(215), cx + neck_w, shoulder_top + W(4)], fill=skin_shadow)

    def _neck_shade(ld):
        ld.rectangle([cx - neck_w, W(215), cx - neck_w + W(10), shoulder_top],
                     fill=(0, 0, 0, 30))
        ld.rectangle([cx + neck_w - W(10), W(215), cx + neck_w, shoulder_top],
                     fill=(0, 0, 0, 30))
        ld.rectangle([cx - W(10), W(215), cx + W(10), shoulder_top],
                     fill=(255, 255, 255, 15))
    d = _overlay(img, _neck_shade)

    # ================= FACE BASE =================
    d.ellipse([cx - fw, face_top, cx + fw, face_bot], fill=skin_base)
    if face_shape == "square":
        d.rectangle([cx - jaw_w, W(175), cx - fw + W(10), W(235)], fill=skin_base)
        d.rectangle([cx + fw - W(10), W(175), cx + jaw_w, W(235)], fill=skin_base)
    elif face_shape == "pear":
        # Wide jaw: broaden lower face
        d.rectangle([cx - jaw_w, W(180), cx - fw + W(8), W(240)], fill=skin_base)
        d.rectangle([cx + fw - W(8), W(180), cx + jaw_w, W(240)], fill=skin_base)
        d.ellipse([cx - jaw_w, W(195), cx + jaw_w, face_bot + W(6)], fill=skin_base)
    elif face_shape == "heart":
        # Wider forehead/temples, taper handled by narrow jaw_w
        for side in (-1, 1):
            tx = cx + side * fw * 0.82
            d.ellipse([tx - W(16), W(70), tx + W(16), W(120)], fill=skin_base)
    elif face_shape == "diamond":
        # Wide cheekbones
        for side in (-1, 1):
            chx = cx + side * fw * 0.95
            d.ellipse([chx - W(14), W(150), chx + W(14), W(195)], fill=skin_base)

    # Skin texture: subtle pores
    def _skin_tex(ld):
        for _ in range(400):
            bx = rng.uniform(cx - fw + W(8), cx + fw - W(8))
            by = rng.uniform(face_top + W(15), face_bot - W(10))
            if ((bx - cx) / fw) ** 2 + ((by - W(158)) / W(100)) ** 2 < 0.92:
                v = rng.randint(-12, 12)
                ld.point((int(bx), int(by)), fill=(v, v, v, 18))
        # Freckles across nose/cheeks
        if freckles:
            for _ in range(42):
                side = rng.choice((-1, 1))
                bx = cx + side * rng.uniform(0, fw * 0.55)
                by = rng.uniform(W(165), W(200))
                ld.point((int(bx), int(by)), fill=(60, 30, 20, 40))
        # Beauty mark / mole
        if mole:
            side = rng.choice((-1, 1))
            bx = cx + side * rng.uniform(fw * 0.3, fw * 0.7)
            by = rng.uniform(W(185), W(215))
            r = W(2)
            ld.ellipse([bx - r, by - r, bx + r, by + r], fill=(40, 25, 20, 200))
    d = _overlay(img, _skin_tex)

    # Facial structure shading
    def _face_structure(ld):
        # Forehead light from above
        ld.ellipse([cx - fw * 0.65, face_top + W(6), cx + fw * 0.65, W(105)],
                   fill=(255, 255, 255, 28))
        # Brow ridge shadow
        ld.ellipse([cx - fw * 0.7, W(125), cx + fw * 0.7, W(142)],
                   fill=(0, 0, 0, 22))
        # Cheekbones
        for side in (-1, 1):
            chx = cx + side * fw * 0.52
            ld.ellipse([chx - W(22), W(160), chx + W(22), W(182)],
                       fill=(255, 255, 255, 20))
            ld.ellipse([chx - W(20), W(184), chx + W(20), W(205)],
                       fill=(0, 0, 0, 28))
        # Nasolabial folds (deeper with age)
        nl_alpha = int(30 + 30 * wrinkle)
        for side in (-1, 1):
            ld.arc([cx + side * W(28) - W(14), W(185),
                    cx + side * W(28) + W(14), W(220)],
                   300 if side < 0 else 240, 60 if side < 0 else 120,
                   fill=(0, 0, 0, nl_alpha), width=W(3))
        # Jawline definition
        ld.arc([cx - jaw_w - W(6), W(180), cx + jaw_w + W(6), face_bot + W(12)],
               25, 155, fill=(0, 0, 0, 40), width=W(5))
        # Chin shadow
        ld.ellipse([cx - W(30), face_bot - W(18), cx + W(30), face_bot + W(4)],
                   fill=(0, 0, 0, 30))
        # Temple shading
        for side in (-1, 1):
            tx = cx + side * fw * 0.88
            ld.ellipse([tx - W(12), W(80), tx + W(12), W(125)], fill=(0, 0, 0, 20))
        # Youthful cheek fullness
        if youthful:
            for side in (-1, 1):
                chx = cx + side * fw * 0.45
                ld.ellipse([chx - W(24), W(168), chx + W(24), W(200)],
                           fill=(255, 255, 255, 22))
    d = _blurred_overlay(img, _face_structure, W(10))

    # ================= EARS =================
    ear_w, ear_h = W(10) * ear_size, W(16) * ear_size
    for side in (-1, 1):
        ex = cx + side * (fw - W(2))
        d.ellipse([ex - ear_w, W(148), ex + ear_w, W(180)], fill=_shade(skin_base, -5))

    def _ear_detail(ld):
        for side in (-1, 1):
            ex = cx + side * (fw - W(2))
            # Inner ear shadow + ridge
            ld.ellipse([ex - ear_w * 0.5, W(156), ex + ear_w * 0.5, W(172)],
                       fill=(0, 0, 0, 45))
            ld.arc([ex - ear_w * 0.7, W(152), ex + ear_w * 0.7, W(176)],
                   270 if side < 0 else 90, 90 if side < 0 else 270,
                   fill=(255, 255, 255, 35), width=W(2))
    d = _overlay(img, _ear_detail)

    # ================= EYES =================
    eye_w, eye_h = W(17), W(10)

    # Soft upper-lid shadow under the brow (depth before the eye itself)
    def _lid_shadow(ld):
        for side in (-1, 1):
            ex = cx + side * eye_spacing
            ld.ellipse([ex - eye_w - W(6), eye_y - eye_h - W(12),
                        ex + eye_w + W(6), eye_y - W(2)],
                       fill=(0, 0, 0, 35))
    d = _blurred_overlay(img, _lid_shadow, W(4))

    for side in (-1, 1):
        ex = cx + side * eye_spacing

        # Eye white (almond shape)
        d.polygon([
            (ex - eye_w, eye_y),
            (ex - eye_w * 0.6, eye_y - eye_h),
            (ex + eye_w * 0.6, eye_y - eye_h),
            (ex + eye_w, eye_y),
            (ex + eye_w * 0.6, eye_y + eye_h * 0.7),
            (ex - eye_w * 0.6, eye_y + eye_h * 0.7),
        ], fill=(232, 226, 214))

        # Iris
        iris_r = W(8)
        d.ellipse([ex - iris_r, eye_y - iris_r, ex + iris_r, eye_y + iris_r], fill=iris_c)

        def _iris_detail(ld, _ex=ex, _ey=eye_y, _r=iris_r):
            for a in range(0, 360, 30):
                x1 = _ex + math.cos(math.radians(a)) * _r * 0.3
                y1 = _ey + math.sin(math.radians(a)) * _r * 0.3
                x2 = _ex + math.cos(math.radians(a)) * _r * 0.85
                y2 = _ey + math.sin(math.radians(a)) * _r * 0.85
                ld.line([(x1, y1), (x2, y2)], fill=(0, 0, 0, 50), width=W(2))
            ld.ellipse([_ex - _r, _ey - _r, _ex + _r, _ey + _r],
                       outline=(20, 15, 12, 200), width=W(2))
        d = _overlay(img, _iris_detail)

        # Pupil
        pup_r = W(4)
        d.ellipse([ex - pup_r, eye_y - pup_r, ex + pup_r, eye_y + pup_r], fill=(12, 10, 10))

        # Catchlights: main upper-left + tiny secondary lower-right
        d.ellipse([ex - W(4), eye_y - W(5), ex - W(1), eye_y - W(2)],
                  fill=(255, 255, 255, 255))
        d.ellipse([ex + W(2), eye_y + W(2), ex + W(4), eye_y + W(4)],
                  fill=(255, 255, 255, 170))

    def _eye_final(ld):
        for side in (-1, 1):
            ex = cx + side * eye_spacing
            # Upper eyelid line (thick, darker toward outer corner = lashes)
            ld.arc([ex - eye_w - W(3), eye_y - eye_h - W(6),
                    ex + eye_w + W(3), eye_y + eye_h],
                   200, 340, fill=(30, 22, 18, 255), width=W(4))
            ld.arc([ex + side * W(2), eye_y - eye_h - W(6),
                    ex + eye_w + W(3), eye_y + eye_h],
                   250, 340, fill=(15, 10, 8, 255), width=W(5))
            # Lower lid (thin)
            ld.arc([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h + W(4)],
                   20, 160, fill=(30, 22, 18, 140), width=W(2))
            # Inner corner shadow
            ld.ellipse([ex - side * eye_w - W(4), eye_y - W(4),
                        ex - side * eye_w + W(4), eye_y + W(4)],
                       fill=(0, 0, 0, 50))
            # Under-eye bags with age
            if wrinkle > 0.35:
                ld.arc([ex - eye_w, eye_y - W(2), ex + eye_w, eye_y + eye_h + W(10)],
                       15, 165, fill=(0, 0, 0, int(55 * wrinkle)), width=W(3))
    d = _overlay(img, _eye_final)

    # ================= EYEBROWS =================
    brow_c = _shade(_blend(hair_c, (50, 44, 40), 0.65), -15)
    for side in (-1, 1):
        ex = cx + side * eye_spacing
        by = eye_y - W(28)
        t = brow_thick
        # Style controls inner/outer height offsets
        if brow_style == "arched":
            in_dy, mid_dy, out_dy = W(4), -W(6), W(6)
        elif brow_style == "flat":
            in_dy, mid_dy, out_dy = W(2), W(2), W(3)
        elif brow_style == "angled":
            in_dy, mid_dy, out_dy = -W(3), W(1), W(7)
        else:  # natural
            in_dy, mid_dy, out_dy = W(3), -W(3), W(4)
        d.polygon([
            (ex - W(20), by + W(6) * t + in_dy),
            (ex - W(14), by - W(2) * t + in_dy),
            (ex + W(2), by - W(4) * t + mid_dy),
            (ex + W(16), by + out_dy),
            (ex + W(20), by + W(5) * t + out_dy),
            (ex + W(14), by + W(8) * t + out_dy),
            (ex - W(2), by + W(6) * t + mid_dy),
            (ex - W(16), by + W(8) * t + in_dy),
        ], fill=brow_c)

    # ================= NOSE =================
    nw = nose_wf  # width multiplier

    def _nose_bridge(ld):
        ld.polygon([
            (cx - W(7), W(150)), (cx + W(7), W(150)),
            (cx + W(10) * nw, nose_bot - W(12)), (cx - W(10) * nw, nose_bot - W(12))
        ], fill=(255, 255, 255, 25))
        ld.polygon([
            (cx - W(10) * nw, W(155)), (cx - W(7), W(150)),
            (cx - W(10) * nw, nose_bot - W(12)), (cx - W(13) * nw, nose_bot - W(8))
        ], fill=(0, 0, 0, 30))
    d = _overlay(img, _nose_bridge)

    # Tip and nostrils
    d.ellipse([cx - W(14) * nw, nose_bot - W(16), cx + W(14) * nw, nose_bot + W(4)],
              fill=_shade(skin_base, -6))

    def _nostrils(ld):
        for side in (-1, 1):
            nx = cx + side * W(9) * nw
            ld.ellipse([nx - W(5), nose_bot - W(8), nx + W(5), nose_bot - W(1)],
                       fill=(45, 30, 25, 255))
            ld.ellipse([nx + side * W(4) - W(4), nose_bot - W(12),
                        nx + side * W(4) + W(4), nose_bot - W(2)],
                       fill=(0, 0, 0, 40))
    d = _overlay(img, _nostrils)

    # ================= MOUTH =================
    lip_c = _shade(_blend(skin_base, (150, 90, 85), 0.35), -18)
    lip_low_c = _shade(_blend(skin_base, (150, 90, 85), 0.35), -8)

    # Philtrum (faint lines above upper lip)
    def _philtrum(ld):
        for side in (-1, 1):
            px = cx + side * W(5)
            ld.line([(px, mouth_y - W(16)), (px, mouth_y - W(8))],
                    fill=(0, 0, 0, 30), width=W(2))
    d = _overlay(img, _philtrum)

    if mouth_style == "grin":
        # Open smile: dark interior + teeth
        d.rounded_rectangle([cx - W(22), mouth_y - W(6), cx + W(22), mouth_y + W(12)],
                            radius=W(8), fill=(45, 20, 18, 255))
        d.rounded_rectangle([cx - W(19), mouth_y - W(4), cx + W(19), mouth_y + W(4)],
                            radius=W(4), fill=(235, 232, 225, 255))
        for i in range(1, 4):
            tx = cx - W(19) + i * W(38) / 4
            d.line([(tx, mouth_y - W(4)), (tx, mouth_y + W(4))],
                   fill=(120, 115, 110, 255), width=W(1))
        d.arc([cx - W(22), mouth_y - W(8), cx + W(22), mouth_y + W(12)],
              20, 160, fill=(60, 35, 30, 255), width=W(3))
    else:
        # Upper lip (thinner, darker)
        d.polygon([
            (cx - W(20), mouth_y),
            (cx - W(10), mouth_y - W(7)),
            (cx, mouth_y - W(4)),
            (cx + W(10), mouth_y - W(7)),
            (cx + W(20), mouth_y),
            (cx + W(10), mouth_y + W(2)),
            (cx, mouth_y + W(3)),
            (cx - W(10), mouth_y + W(2)),
        ], fill=lip_c)
        # Lower lip (fuller, lighter)
        d.ellipse([cx - W(16), mouth_y - W(1), cx + W(16), mouth_y + W(10)],
                  fill=lip_low_c)
        # Mouth line per style
        if mouth_style == "smile":
            d.arc([cx - W(18), mouth_y - W(8), cx + W(18), mouth_y + W(10)],
                  25, 155, fill=(60, 35, 30, 255), width=W(3))
        elif mouth_style == "smirk":
            d.arc([cx - W(18), mouth_y - W(6), cx + W(18), mouth_y + W(8)],
                  30, 150, fill=(60, 35, 30, 255), width=W(3))
        else:
            d.line([cx - W(14), mouth_y + W(1), cx + W(14), mouth_y + W(1)],
                   fill=(60, 35, 30, 255), width=W(3))

    def _mouth_detail(ld):
        # Corner shadows
        for side in (-1, 1):
            mx = cx + side * W(20)
            ld.ellipse([mx - W(4), mouth_y - W(3), mx + W(4), mouth_y + W(5)],
                       fill=(0, 0, 0, 55))
        # Lower lip highlight
        ld.ellipse([cx - W(10), mouth_y + W(3), cx + W(10), mouth_y + W(7)],
                   fill=(255, 255, 255, 45))
        # Marionette lines with age
        if wrinkle > 0.5:
            for side in (-1, 1):
                ld.line([(cx + side * W(22), mouth_y + W(4)),
                         (cx + side * W(26), mouth_y + W(18))],
                        fill=(0, 0, 0, int(60 * wrinkle)), width=W(2))
    d = _overlay(img, _mouth_detail)

    # ================= FACIAL HAIR =================
    def _mustache_shape(ld, full=False):
        """Mustache above the lip; full=True is bushier (for full beard)."""
        h = W(11) if full else W(8)
        spread = W(22) if full else W(18)
        d_ = [
            (cx - spread, mouth_y - h + W(2)),
            (cx - W(8), mouth_y - h - W(3)),
            (cx, mouth_y - h),
            (cx + W(8), mouth_y - h - W(3)),
            (cx + spread, mouth_y - h + W(2)),
            (cx + spread - W(4), mouth_y - W(3)),
            (cx, mouth_y - W(4)),
            (cx - spread + W(4), mouth_y - W(3)),
        ]
        ld.polygon(d_, fill=beard_c)

    def _beard_texture(ld, bw, top, bot, n):
        for _ in range(n):
            bx = rng.uniform(cx - bw + W(6), cx + bw - W(6))
            by = rng.uniform(top, bot)
            if ((bx - cx) / bw) ** 2 + ((by - W(218)) / W(34)) ** 2 < 1:
                if abs(bx - cx) < W(18) and abs(by - mouth_y) < W(10):
                    continue
                v = rng.randint(-30, 20)
                ld.point((int(bx), int(by)), fill=(v, v, v, 60))

    if beard_style == "short_beard":
        bw = jaw_w - W(8)
        d.pieslice([cx - bw, W(190), cx + bw, face_bot + W(8)], 18, 162, fill=beard_c)
        d = _overlay(img, lambda ld: _beard_texture(ld, bw, W(200), face_bot - W(4), 80))
    elif beard_style == "full_beard":
        # Heavier, longer beard with integrated mustache
        bw = jaw_w + W(2)
        d.pieslice([cx - bw, W(185), cx + bw, face_bot + W(18)], 12, 168, fill=beard_c)
        d.ellipse([cx - W(24), face_bot - W(20), cx + W(24), face_bot + W(16)],
                  fill=beard_c)
        d = _overlay(img, lambda ld: _mustache_shape(ld, full=True))
        d = _overlay(img, lambda ld: _beard_texture(ld, bw, W(195), face_bot + W(8), 150))
    elif beard_style == "goatee":
        d.polygon([
            (cx - W(16), mouth_y + W(12)),
            (cx + W(16), mouth_y + W(12)),
            (cx + W(12), mouth_y + W(32)),
            (cx - W(12), mouth_y + W(32)),
        ], fill=beard_c)
        d = _overlay(img, lambda ld: _mustache_shape(ld))
        # Soul patch
        d.ellipse([cx - W(5), mouth_y + W(8), cx + W(5), mouth_y + W(14)], fill=beard_c)
    elif beard_style == "mustache":
        d = _overlay(img, lambda ld: _mustache_shape(ld))
    elif beard_style == "stubble":
        def _stubble(ld):
            stubble_c = _blend(hair_c, (85, 78, 72), 0.6)
            ld.pieslice([cx - jaw_w + W(8), W(188), cx + jaw_w - W(8), face_bot - W(4)],
                        15, 165, fill=(*stubble_c, 45))
        d = _blurred_overlay(img, _stubble, W(5))

    # ================= HAIR =================
    # Hairline fringe under the helmet front edge (all non-bald styles)
    recede = W(6) if age >= 36 else 0  # temples recede slightly with age

    def _flow_shade(ld):
        for side in (-1, 1):
            hx = cx + side * (fw + W(6))
            for i in range(3):
                lx = hx - W(6) + i * W(6)
                ld.line([(lx, W(160)), (lx, W(208))],
                        fill=(0, 0, 0, 45), width=W(3))

    def _fringe(ld, fullness=1.0, jagged=0):
        top = W(92) + (W(8) if hair_style == "buzz" else 0)
        bot = W(112)
        for x in range(int(cx - fw + recede), int(cx + fw - recede), W(4)):
            if rng.random() > fullness:
                continue
            edge = bot - (jagged and rng.randint(0, jagged))
            # Curve the hairline: higher at the temples
            t = abs(x - cx) / fw
            y_top = top + t * W(10)
            ld.line([(x, y_top), (x, edge)], fill=(*hair_c, 255), width=W(4))

    def _hair_strand_tex(ld, x0, x1, y0, y1, n):
        for _ in range(n):
            sx = rng.uniform(x0, x1)
            ld.line([(sx, y0), (sx + rng.uniform(-W(3), W(3)), y1)],
                    fill=(0, 0, 0, 40), width=W(2))

    if hair_style not in ("bald",):
        if hair_style in ("short", "buzz", "fade"):
            d = _overlay(img, lambda ld: _fringe(ld, fullness=0.9 if hair_style != "buzz" else 0.55))
            if hair_style == "fade":
                # Faded temples: stippled short hair at the sides
                def _fade_sides(ld):
                    for side in (-1, 1):
                        for _ in range(40):
                            bx = cx + side * rng.uniform(fw - W(14), fw - W(2))
                            by = rng.uniform(W(105), W(140))
                            v = rng.randint(-20, 20)
                            ld.point((int(bx), int(by)), fill=(v, v, v, 70))
                d = _overlay(img, _fade_sides)
        elif hair_style == "side_part":
            d = _overlay(img, lambda ld: _fringe(ld, fullness=1.0))
            # Part line off-center
            px = cx - W(24)
            d.line([(px, W(94)), (px + W(6), W(112))], fill=(0, 0, 0, 90), width=W(3))
        elif hair_style == "flow":
            for side in (-1, 1):
                hx = cx + side * (fw + W(6))
                d.polygon([
                    (hx - W(9), W(150)), (hx + W(9), W(150)),
                    (hx + W(12), W(215)), (hx - W(12), W(215)),
                ], fill=hair_c)
            d = _overlay(img, lambda ld: _flow_shade(ld))
            d = _overlay(img, lambda ld: _fringe(ld, fullness=0.9))
        elif hair_style == "long":
            # Long hair falling past the shoulders at the sides
            for side in (-1, 1):
                hx = cx + side * (fw + W(8))
                d.polygon([
                    (hx - W(11), W(150)), (hx + W(10), W(150)),
                    (hx + W(14), W(245)), (hx - W(15), W(245)),
                ], fill=hair_c)
                d = _overlay(img, lambda ld, _hx=hx: _hair_strand_tex(
                    ld, _hx - W(9), _hx + W(8), W(158), W(238), 16))
            d = _overlay(img, lambda ld: _fringe(ld, fullness=1.0, jagged=W(6)))
        elif hair_style == "ponytail":
            d = _overlay(img, lambda ld: _fringe(ld, fullness=0.85))
            side = rng.choice((-1, 1))
            hx = cx + side * (fw + W(14))
            # Tail hanging behind
            d.polygon([
                (hx - W(9), W(148)), (hx + W(9), W(148)),
                (hx + W(12), W(250)), (hx - W(12), W(250)),
            ], fill=hair_c)
            # Tie band
            d.ellipse([hx - W(10), W(150), hx + W(10), W(160)], fill=(30, 30, 34))
            d = _overlay(img, lambda ld, _hx=hx: _hair_strand_tex(
                ld, _hx - W(7), _hx + W(7), W(163), W(245), 12))
        elif hair_style == "man_bun":
            d = _overlay(img, lambda ld: _fringe(ld, fullness=0.8))
            side = rng.choice((-1, 1))
            bx, by = cx + side * (fw + W(20)), W(135)
            d.ellipse([bx - W(14), by - W(14), bx + W(14), by + W(14)], fill=hair_c)
            d.ellipse([bx - W(14), by - W(14), bx - W(2), by - W(2)],
                      fill=(255, 255, 255, 40))
            d.ellipse([bx - W(15), by - W(4), bx + W(15), by + W(6)], fill=(30, 30, 34))
        elif hair_style == "mohawk":
            # Strip visible at the helmet's front edge
            d.polygon([
                (cx - W(11), W(86)), (cx + W(11), W(86)),
                (cx + W(13), W(112)), (cx - W(13), W(112)),
            ], fill=hair_c)
            def _mohawk_tex(ld):
                for i in range(6):
                    sx = cx - W(10) + i * W(4)
                    ld.line([(sx, W(88)), (sx, W(110))], fill=(0, 0, 0, 60), width=W(2))
                    ld.line([(sx, W(88)), (sx + W(2), W(82))], fill=(*hair_c, 255), width=W(3))
            d = _overlay(img, _mohawk_tex)
        elif hair_style == "curly":
            for i in range(8):
                side = -1 if i % 2 == 0 else 1
                hx = cx + side * (fw * 0.94)
                hy = W(132) + (i // 2) * W(17)
                d.ellipse([hx - W(9), hy - W(9), hx + W(9), hy + W(9)], fill=hair_c)
            d = _overlay(img, lambda ld: _fringe(ld, fullness=0.9, jagged=W(8)))

    # ================= HELMET =================
    helm_top, helm_bot = W(12), W(105)
    helm_w = fw + W(18)

    d.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
               180, 360, fill=helmet_c)

    def _helmet_shade(ld):
        ld.ellipse([cx - helm_w + W(15), helm_top + W(8),
                    cx - W(20), helm_top + W(55)],
                   fill=(255, 255, 255, 85))
        ld.ellipse([cx + W(10), helm_top + W(12),
                    cx + helm_w - W(30), helm_top + W(40)],
                   fill=(255, 255, 255, 40))
        ld.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
                    260, 360, fill=(0, 0, 0, 65))
        ld.rectangle([cx - helm_w, helm_bot - W(12), cx + helm_w, helm_bot],
                     fill=(0, 0, 0, 50))
    _hs = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _hsd = ImageDraw.Draw(_hs, "RGBA")
    _helmet_shade(_hsd)
    _hs = _hs.filter(ImageFilter.GaussianBlur(W(12)))
    _hm = Image.new("L", (S, S), 0)
    _hmd = ImageDraw.Draw(_hm)
    _hmd.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
                  180, 360, fill=255)
    _hs.putalpha(_hm)
    img.alpha_composite(_hs)
    d = ImageDraw.Draw(img, "RGBA")

    d.arc([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
          180, 360, fill=(15, 14, 13, 255), width=W(3))

    def _vents(ld):
        for side in (-1, 1):
            vx = cx + side * helm_w * 0.52
            for i in range(4):
                vy = W(38) + i * W(13)
                ld.ellipse([vx - W(5), vy - W(4), vx + W(5), vy + W(4)],
                           fill=(0, 0, 0, 120))
                ld.ellipse([vx - W(5), vy - W(4), vx + W(2), vy],
                           fill=(255, 255, 255, 30))
    d = _overlay(img, _vents)

    if sum(helmet_c) > 100:
        d.polygon([
            (cx - W(6), helm_top + W(4)), (cx + W(6), helm_top + W(4)),
            (cx + W(5), W(68)), (cx - W(5), W(68))
        ], fill=(240, 240, 240, 255))

    for side in (-1, 1):
        lx = cx + side * (helm_w - W(4))
        d.rounded_rectangle([lx - W(7), W(82), lx + W(7), W(112)],
                            radius=W(4), fill=_shade(helmet_c, -45))

    # ================= VISOR =================
    if visor:
        visor_top, visor_bot = W(128), W(172)
        visor_w = fw * 0.92

        def _visor(ld):
            ld.rounded_rectangle(
                [cx - visor_w, visor_top, cx + visor_w, visor_bot],
                radius=W(14), fill=(150, 175, 200, 35))
            ld.rounded_rectangle(
                [cx - visor_w + W(6), visor_top + W(3),
                 cx + visor_w - W(6), visor_top + W(10)],
                radius=W(5), fill=(200, 220, 240, 70))
            ld.polygon([
                (cx - visor_w + W(18), visor_top + W(6)),
                (cx - visor_w + W(44), visor_top + W(6)),
                (cx - visor_w + W(24), visor_bot - W(6)),
                (cx - visor_w - W(2), visor_bot - W(6)),
            ], fill=(190, 210, 235, 45))
        d = _overlay(img, _visor)
        for side in (-1, 1):
            mx = cx + side * visor_w
            d.ellipse([mx - W(6), visor_top - W(4), mx + W(6), visor_top + W(8)],
                      fill=(25, 25, 28, 255))

    # ================= NECK -> JERSEY BLEND =================
    # Soft shadow where the neck meets the collar (hides the hard edge)
    def _neck_blend(ld):
        ld.ellipse([cx - W(42), shoulder_top - W(16),
                    cx + W(42), shoulder_top + W(16)],
                   fill=(0, 0, 0, 60))
        # Chin shadow falling on the upper chest
        ld.ellipse([cx - W(28), shoulder_top - W(4),
                    cx + W(28), shoulder_top + W(20)],
                   fill=(0, 0, 0, 35))
    d = _blurred_overlay(img, _neck_blend, W(8))

    # ================= AGE DETAIL =================
    if wrinkle > 0 or youthful:
        def _age(ld):
            if youthful:
                return  # smooth young skin; fullness handled in structure shading
            # Crow's feet
            for side in (-1, 1):
                ex = cx + side * eye_spacing
                n = 2 if wrinkle > 0.4 else 1
                for i in range(n):
                    ld.line([(ex + side * (eye_w + W(3)), eye_y - W(3) + i * W(7)),
                             (ex + side * (eye_w + W(10)), eye_y - W(1) + i * W(7))],
                            fill=(0, 0, 0, int(55 * wrinkle)), width=W(2))
            # Forehead lines
            if wrinkle > 0.35:
                lines = 3 if wrinkle > 0.7 else 2
                for i in range(lines):
                    ly = W(78) + i * W(14)
                    ld.arc([cx - W(55), ly - W(8), cx + W(55), ly + W(8)],
                           205, 335, fill=(0, 0, 0, int(50 * wrinkle)), width=W(3))
            # Deeper nasolabial with age
            if wrinkle > 0.6:
                for side in (-1, 1):
                    ld.arc([cx + side * W(32) - W(14), W(190),
                            cx + side * W(32) + W(14), W(228)],
                           300 if side < 0 else 240, 60 if side < 0 else 120,
                           fill=(0, 0, 0, int(60 * wrinkle)), width=W(3))
            # Neck lines for veterans
            if wrinkle > 0.7:
                for i in range(2):
                    ny = W(232) + i * W(9)
                    ld.arc([cx - W(30), ny - W(6), cx + W(30), ny + W(6)],
                           25, 155, fill=(0, 0, 0, int(45 * wrinkle)), width=W(2))
        d = _blurred_overlay(img, _age, W(3))

    # Downscale
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
