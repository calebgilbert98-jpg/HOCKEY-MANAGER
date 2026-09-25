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
_CACHE_TAG = "v4"  # bump when the art style changes so old cached faces refresh
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
    """NHL 2010/2014-style realistic portrait.

    Realistic proportions, subtle shading (no cartoon outlines), skin texture,
    natural eyes. All alpha blending via _overlay().
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
    hair_style = rng.choice(HAIR_STYLES)
    visor = rng.random() < 0.65
    beard_style = rng.choices(
        ["clean", "stubble", "beard", "goatee"],
        weights=[0.40, 0.30, 0.20, 0.10]
    )[0]
    if age > 30 and beard_style == "clean" and rng.random() < 0.4:
        beard_style = rng.choice(["stubble", "beard"])
    mouth_style = rng.choice(["neutral", "smile", "smirk"])

    # Higher res for realism detail
    S = size * 3
    k = S / 384.0
    W = lambda v: max(1, int(v * k))

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img, "RGBA")
    cx = S / 2

    from PIL import ImageFilter as _IF

    # Realistic face proportions (longer, narrower than cartoon)
    if face_shape == "oval":
        fw, fh_top, fh_bot, jaw_w = W(88), W(58), W(258), W(68)
    elif face_shape == "round":
        fw, fh_top, fh_bot, jaw_w = W(94), W(62), W(250), W(78)
    elif face_shape == "square":
        fw, fh_top, fh_bot, jaw_w = W(86), W(60), W(254), W(80)
    else:  # oblong
        fw, fh_top, fh_bot, jaw_w = W(80), W(56), W(264), W(62)
    face_top, face_bot = fh_top, fh_bot

    # Feature positions (realistic ratios)
    eye_y = W(148)          # eyes at vertical midpoint
    eye_spacing = fw * 0.52
    nose_bot = W(200)
    mouth_y = W(228)

    # ================= JERSEY =================
    shoulder_top = W(262)
    d.polygon([
        (cx - W(140), S), (cx + W(140), S),
        (cx + W(90), shoulder_top), (cx - W(90), shoulder_top)
    ], fill=jersey_c)

    def _jersey_shade(ld):
        # Soft gradient shading on shoulders
        for i in range(5):
            inset = W(10 + i * 14)
            alpha = 35 - i * 6
            ld.polygon([
                (cx - W(140) + inset, S), (cx - W(90) + inset * 0.6, shoulder_top),
                (cx - W(90) + inset * 0.6 + W(6), shoulder_top), (cx - W(140) + inset + W(6), S)
            ], fill=(0, 0, 0, alpha))
            ld.polygon([
                (cx + W(140) - inset, S), (cx + W(90) - inset * 0.6, shoulder_top),
                (cx + W(90) - inset * 0.6 - W(6), shoulder_top), (cx + W(140) - inset - W(6), S)
            ], fill=(0, 0, 0, alpha))
        # Center highlight
        ld.polygon([
            (cx - W(30), S), (cx + W(30), S),
            (cx + W(20), shoulder_top), (cx - W(20), shoulder_top)
        ], fill=(255, 255, 255, 18))
    _js = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _jsd = ImageDraw.Draw(_js, "RGBA")
    _jersey_shade(_jsd)
    _js = _js.filter(_IF.GaussianBlur(W(8)))
    img.alpha_composite(_js)
    d = ImageDraw.Draw(img, "RGBA")

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
    # Neck muscle shading
    def _neck_shade(ld):
        ld.rectangle([cx - neck_w, W(215), cx - neck_w + W(10), shoulder_top],
                     fill=(0, 0, 0, 30))
        ld.rectangle([cx + neck_w - W(10), W(215), cx + neck_w, shoulder_top],
                     fill=(0, 0, 0, 30))
        ld.rectangle([cx - W(10), W(215), cx + W(10), shoulder_top],
                     fill=(255, 255, 255, 15))
    d = _overlay(img, _neck_shade)

    # ================= FACE BASE =================
    # Draw face with subtle vertical gradient (forehead lighter)
    d.ellipse([cx - fw, face_top, cx + fw, face_bot], fill=skin_base)
    if face_shape == "square":
        d.rectangle([cx - jaw_w, W(175), cx - fw + W(10), W(235)], fill=skin_base)
        d.rectangle([cx + fw - W(10), W(175), cx + jaw_w, W(235)], fill=skin_base)

    # Skin texture (subtle noise for pores)
    def _skin_tex(ld):
        for _ in range(400):
            bx = rng.uniform(cx - fw + W(8), cx + fw - W(8))
            by = rng.uniform(face_top + W(15), face_bot - W(10))
            # Within face ellipse
            if ((bx - cx) / fw) ** 2 + ((by - W(158)) / W(100)) ** 2 < 0.92:
                v = rng.randint(-12, 12)
                ld.point((int(bx), int(by)), fill=(v, v, v, 18))
    d = _overlay(img, _skin_tex)

    # Facial structure shading (the key to realism)
    def _face_structure(ld):
        # Forehead - light from above
        ld.ellipse([cx - fw * 0.65, face_top + W(6), cx + fw * 0.65, W(105)],
                   fill=(255, 255, 255, 28))
        # Brow ridge shadow
        ld.ellipse([cx - fw * 0.7, W(125), cx + fw * 0.7, W(142)],
                   fill=(0, 0, 0, 22))
        # Cheekbones - highlight on top, shadow below
        for side in (-1, 1):
            chx = cx + side * fw * 0.52
            ld.ellipse([chx - W(22), W(160), chx + W(22), W(182)],
                       fill=(255, 255, 255, 20))
            ld.ellipse([chx - W(20), W(184), chx + W(20), W(205)],
                       fill=(0, 0, 0, 28))
        # Nasolabial folds (smile lines)
        for side in (-1, 1):
            ld.arc([cx + side * W(28) - W(14), W(185),
                    cx + side * W(28) + W(14), W(220)],
                   300 if side < 0 else 240, 60 if side < 0 else 120,
                   fill=(0, 0, 0, 35), width=W(3))
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
    _fs = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _fsd = ImageDraw.Draw(_fs, "RGBA")
    _face_structure(_fsd)
    _fs = _fs.filter(_IF.GaussianBlur(W(10)))
    img.alpha_composite(_fs)
    d = ImageDraw.Draw(img, "RGBA")

    # ================= EARS (subtle) =================
    for side in (-1, 1):
        ex = cx + side * (fw - W(2))
        d.ellipse([ex - W(10), W(148), ex + W(10), W(180)], fill=_shade(skin_base, -5))
    def _ear_detail(ld):
        for side in (-1, 1):
            ex = cx + side * (fw - W(2))
            ld.ellipse([ex - W(5), W(156), ex + W(5), W(172)], fill=(0, 0, 0, 45))
    d = _overlay(img, _ear_detail)

    # ================= EYES (realistic, smaller) =================
    # NHL 2010 eyes are much smaller and more natural than cartoon
    eye_w, eye_h = W(17), W(10)

    for side in (-1, 1):
        ex = cx + side * eye_spacing

        # Eye white (almond shape via polygon)
        d.polygon([
            (ex - eye_w, eye_y),
            (ex - eye_w * 0.6, eye_y - eye_h),
            (ex + eye_w * 0.6, eye_y - eye_h),
            (ex + eye_w, eye_y),
            (ex + eye_w * 0.6, eye_y + eye_h * 0.7),
            (ex - eye_w * 0.6, eye_y + eye_h * 0.7),
        ], fill=(232, 226, 214))

        # Iris (realistic size - fills most of eye opening)
        iris_r = W(8)
        d.ellipse([ex - iris_r, eye_y - iris_r, ex + iris_r, eye_y + iris_r], fill=iris_c)
        # Iris radial detail
        def _iris_detail(ld, _ex=ex, _ey=eye_y, _r=iris_r):
            for a in range(0, 360, 30):
                import math
                x1 = _ex + math.cos(math.radians(a)) * _r * 0.3
                y1 = _ey + math.sin(math.radians(a)) * _r * 0.3
                x2 = _ex + math.cos(math.radians(a)) * _r * 0.85
                y2 = _ey + math.sin(math.radians(a)) * _r * 0.85
                ld.line([(x1, y1), (x2, y2)], fill=(0, 0, 0, 50), width=W(2))
            # Limbal ring (dark outer ring)
            ld.ellipse([_ex - _r, _ey - _r, _ex + _r, _ey + _r],
                       outline=(20, 15, 12, 200), width=W(2))
        d = _overlay(img, _iris_detail)

        # Pupil
        pup_r = W(4)
        d.ellipse([ex - pup_r, eye_y - pup_r, ex + pup_r, eye_y + pup_r], fill=(12, 10, 10))

        # Catchlight (small, realistic)
        d.ellipse([ex - W(4), eye_y - W(5), ex - W(1), eye_y - W(2)],
                  fill=(255, 255, 255, 255))

    def _eye_final(ld):
        for side in (-1, 1):
            ex = cx + side * eye_spacing
            # Upper eyelid (thick, defines eye)
            ld.arc([ex - eye_w - W(3), eye_y - eye_h - W(6),
                    ex + eye_w + W(3), eye_y + eye_h],
                   200, 340, fill=(30, 22, 18, 255), width=W(4))
            # Lower lid (thin)
            ld.arc([ex - eye_w, eye_y - eye_h, ex + eye_w, eye_y + eye_h + W(4)],
                   20, 160, fill=(30, 22, 18, 140), width=W(2))
            # Inner corner shadow
            ld.ellipse([ex - side * eye_w - W(4), eye_y - W(4),
                        ex - side * eye_w + W(4), eye_y + W(4)],
                       fill=(0, 0, 0, 50))
    d = _overlay(img, _eye_final)

    # Eyebrows (realistic - follow brow bone)
    brow_c = _shade(_blend(hair_c, (50, 44, 40), 0.65), -15)
    for side in (-1, 1):
        ex = cx + side * eye_spacing
        by = eye_y - W(28)
        # Brow shape: thick inner, tapering outer, slight arch
        d.polygon([
            (ex - W(20), by + W(6)),
            (ex - W(14), by - W(2)),
            (ex + W(2), by - W(4)),
            (ex + W(16), by),
            (ex + W(20), by + W(5)),
            (ex + W(14), by + W(8)),
            (ex - W(2), by + W(6)),
            (ex - W(16), by + W(8)),
        ], fill=brow_c)

    # ================= NOSE (realistic) =================
    # Bridge
    def _nose_bridge(ld):
        ld.polygon([
            (cx - W(7), W(150)), (cx + W(7), W(150)),
            (cx + W(10), nose_bot - W(12)), (cx - W(10), nose_bot - W(12))
        ], fill=(255, 255, 255, 25))
        ld.polygon([
            (cx - W(10), W(155)), (cx - W(7), W(150)),
            (cx - W(10), nose_bot - W(12)), (cx - W(13), nose_bot - W(8))
        ], fill=(0, 0, 0, 30))
    d = _overlay(img, _nose_bridge)

    # Tip and nostrils (more defined)
    d.ellipse([cx - W(14), nose_bot - W(16), cx + W(14), nose_bot + W(4)],
              fill=_shade(skin_base, -6))
    def _nostrils(ld):
        for side in (-1, 1):
            nx = cx + side * W(9)
            # Nostril (almond shaped, angled)
            ld.ellipse([nx - W(5), nose_bot - W(8), nx + W(5), nose_bot - W(1)],
                       fill=(45, 30, 25, 255))
            # Nose wing shadow
            ld.ellipse([nx + side * W(4) - W(4), nose_bot - W(12),
                        nx + side * W(4) + W(4), nose_bot - W(2)],
                       fill=(0, 0, 0, 40))
    d = _overlay(img, _nostrils)

    # ================= MOUTH (realistic lips) =================
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
    ], fill=_shade(_blend(skin_base, (150, 90, 85), 0.35), -18))

    # Lower lip (fuller, lighter)
    d.ellipse([cx - W(16), mouth_y - W(1), cx + W(16), mouth_y + W(10)],
              fill=_shade(_blend(skin_base, (150, 90, 85), 0.35), -8))

    # Mouth line
    if mouth_style == "smile":
        d.arc([cx - W(18), mouth_y - W(8), cx + W(18), mouth_y + W(10)],
              25, 155, fill=(60, 35, 30, 255), width=W(3))
    elif mouth_style == "smirk":
        d.arc([cx - W(18), mouth_y - W(6), cx + W(18), mouth_y + W(8)],
              30, 150, fill=(60, 35, 30, 255), width=W(3))
    else:
        d.line([cx - W(14), mouth_y + W(1), cx + W(14), mouth_y + W(1)],
               fill=(60, 35, 30, 255), width=W(3))

    # Lower lip highlight
    def _lip_hi(ld):
        ld.ellipse([cx - W(10), mouth_y + W(3), cx + W(10), mouth_y + W(7)],
                   fill=(255, 255, 255, 45))
    d = _overlay(img, _lip_hi)

    # ================= FACIAL HAIR =================
    beard_c = _shade(_blend(hair_c, (65, 58, 52), 0.4), -10)
    if beard_style == "beard":
        bw = jaw_w - W(8)
        d.pieslice([cx - bw, W(190), cx + bw, face_bot + W(8)], 18, 162, fill=beard_c)
        def _beard_tex(ld):
            for _ in range(80):
                bx = rng.uniform(cx - bw + W(6), cx + bw - W(6))
                by = rng.uniform(W(200), face_bot - W(4))
                if ((bx - cx) / bw) ** 2 + ((by - W(218)) / W(32)) ** 2 < 1:
                    if abs(bx - cx) < W(18) and abs(by - mouth_y) < W(10):
                        continue
                    v = rng.randint(-30, 20)
                    ld.point((int(bx), int(by)),
                             fill=(v, v, v, 60))
        d = _overlay(img, _beard_tex)
    elif beard_style == "goatee":
        # Chin patch (below lower lip, on chin - not a circle)
        d.polygon([
            (cx - W(16), mouth_y + W(12)),
            (cx + W(16), mouth_y + W(12)),
            (cx + W(12), mouth_y + W(32)),
            (cx - W(12), mouth_y + W(32)),
        ], fill=beard_c)
        # Mustache (thin, above lip)
        d.polygon([
            (cx - W(18), mouth_y - W(8)),
            (cx - W(8), mouth_y - W(11)),
            (cx, mouth_y - W(9)),
            (cx + W(8), mouth_y - W(11)),
            (cx + W(18), mouth_y - W(8)),
            (cx + W(14), mouth_y - W(4)),
            (cx, mouth_y - W(5)),
            (cx - W(14), mouth_y - W(4)),
        ], fill=beard_c)
    elif beard_style == "stubble":
        def _stubble(ld):
            stubble_c = _blend(hair_c, (85, 78, 72), 0.6)
            ld.pieslice([cx - jaw_w + W(8), W(188), cx + jaw_w - W(8), face_bot - W(4)],
                        15, 165, fill=(*stubble_c, 45))
        _stubl = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        _stld = ImageDraw.Draw(_stubl, "RGBA")
        _stubble(_stld)
        _stubl = _stubl.filter(_IF.GaussianBlur(W(5)))
        img.alpha_composite(_stubl)
        d = ImageDraw.Draw(img, "RGBA")

    # ================= HAIR =================
    if hair_style == "flow":
        # Hair tucked behind jaw, visible below helmet at back
        for side in (-1, 1):
            # Draw behind the face (already drawn, so draw then cover center)
            hx = cx + side * (fw + W(6))
            d.polygon([
                (hx - W(10), W(140)),
                (hx + W(10), W(140)),
                (hx + W(14), W(215)),
                (hx - W(14), W(215)),
            ], fill=hair_c)
        def _flow_shade(ld):
            for side in (-1, 1):
                hx = cx + side * (fw + W(6))
                for i in range(3):
                    lx = hx - W(6) + i * W(6)
                    ld.line([(lx, W(150)), (lx, W(205))],
                            fill=(0, 0, 0, 45), width=W(3))
        d = _overlay(img, _flow_shade)
    elif hair_style == "curly":
        for i in range(10):
            side = -1 if i % 2 == 0 else 1
            hx = cx + side * (fw * 0.92)
            hy = W(115) + (i // 2) * W(16)
            d.ellipse([hx - W(10), hy - W(10), hx + W(10), hy + W(10)], fill=hair_c)

    # ================= HELMET (realistic) =================
    helm_top, helm_bot = W(12), W(105)
    helm_w = fw + W(18)

    # Helmet shell (more realistic dome shape)
    d.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
               180, 360, fill=helmet_c)

    # Realistic helmet shading (multiple light sources)
    _hs = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    _hsd = ImageDraw.Draw(_hs, "RGBA")
    # Main highlight (top-left, large soft)
    _hsd.ellipse([cx - helm_w + W(15), helm_top + W(8),
                  cx - W(20), helm_top + W(55)],
                 fill=(255, 255, 255, 85))
    # Secondary highlight (top-right, smaller)
    _hsd.ellipse([cx + W(10), helm_top + W(12),
                  cx + helm_w - W(30), helm_top + W(40)],
                 fill=(255, 255, 255, 40))
    # Shadow (bottom-right)
    _hsd.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
                  260, 360, fill=(0, 0, 0, 65))
    # Front edge shadow
    _hsd.rectangle([cx - helm_w, helm_bot - W(12), cx + helm_w, helm_bot],
                   fill=(0, 0, 0, 50))
    _hs = _hs.filter(_IF.GaussianBlur(W(12)))
    _hm = Image.new("L", (S, S), 0)
    _hmd = ImageDraw.Draw(_hm)
    _hmd.pieslice([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
                  180, 360, fill=255)
    _hs.putalpha(_hm)
    img.alpha_composite(_hs)
    d = ImageDraw.Draw(img, "RGBA")

    # Helmet edge (thin, realistic)
    d.arc([cx - helm_w, helm_top, cx + helm_w, helm_bot * 2 - helm_top],
          180, 360, fill=(15, 14, 13, 255), width=W(3))

    # Vents (realistic - recessed)
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

    # Center stripe
    if sum(helmet_c) > 100:
        d.polygon([
            (cx - W(6), helm_top + W(4)), (cx + W(6), helm_top + W(4)),
            (cx + W(5), W(68)), (cx - W(5), W(68))
        ], fill=(240, 240, 240, 255))

    # Ear loops (J-clips)
    for side in (-1, 1):
        lx = cx + side * (helm_w - W(4))
        d.rounded_rectangle([lx - W(7), W(82), lx + W(7), W(112)],
                            radius=W(4), fill=_shade(helmet_c, -45))

    # ================= VISOR =================
    if visor:
        visor_top, visor_bot = W(128), W(172)
        visor_w = fw * 0.92
        def _visor(ld):
            # Clear visor - very transparent
            ld.rounded_rectangle(
                [cx - visor_w, visor_top, cx + visor_w, visor_bot],
                radius=W(14), fill=(150, 175, 200, 35))
            # Edge reflection (top)
            ld.rounded_rectangle(
                [cx - visor_w + W(6), visor_top + W(3),
                 cx + visor_w - W(6), visor_top + W(10)],
                radius=W(5), fill=(200, 220, 240, 70))
            # Diagonal shine
            ld.polygon([
                (cx - visor_w + W(18), visor_top + W(6)),
                (cx - visor_w + W(44), visor_top + W(6)),
                (cx - visor_w + W(24), visor_bot - W(6)),
                (cx - visor_w - W(2), visor_bot - W(6)),
            ], fill=(190, 210, 235, 45))
        d = _overlay(img, _visor)
        # Visor mounts (small, at sides)
        for side in (-1, 1):
            mx = cx + side * visor_w
            d.ellipse([mx - W(6), visor_top - W(4), mx + W(6), visor_top + W(8)],
                      fill=(25, 25, 28, 255))

    # ================= AGE =================
    if age >= 28:
        def _age(ld):
            # Crow's feet
            for side in (-1, 1):
                ex = cx + side * eye_spacing
                n = 2 if age >= 32 else 1
                for i in range(n):
                    ld.line([(ex + side * (eye_w + W(3)), eye_y - W(3) + i * W(7)),
                             (ex + side * (eye_w + W(10)), eye_y - W(1) + i * W(7))],
                            fill=(0, 0, 0, 50), width=W(2))
            # Forehead lines
            if age >= 32:
                for i in range(2):
                    ly = W(78) + i * W(14)
                    ld.arc([cx - W(55), ly - W(8), cx + W(55), ly + W(8)],
                           205, 335, fill=(0, 0, 0, 40), width=W(3))
            # Nasolabial deeper with age
            if age >= 35:
                for side in (-1, 1):
                    ld.arc([cx + side * W(32) - W(14), W(190),
                            cx + side * W(32) + W(14), W(228)],
                           300 if side < 0 else 240, 60 if side < 0 else 120,
                           fill=(0, 0, 0, 50), width=W(3))
        _ag = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        _agd = ImageDraw.Draw(_ag, "RGBA")
        _age(_agd)
        _ag = _ag.filter(_IF.GaussianBlur(W(3)))
        img.alpha_composite(_ag)
        d = ImageDraw.Draw(img, "RGBA")

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
