"""QA: team-color text/background pairs meet WCAG AA (4.5:1).

Covers every place team colors meet text: standings Team column, team
listbox, CTk accent buttons/nav pills (+hover), launcher buttons,
PillBadge on the accent whisper, visualizer team text on dark, and the
dataclass pairs backing the themed ttk styles. 32 teams x 8 pairs.
"""
import sys
sys.path.insert(0, ".")

from team_identity_system import (
    nhl_identity, accent_for_team, text_color_for_team,
    ensure_text_contrast, contrast_ratio)

PASS, FAIL = [], []

def check(n, c, d=""):
    (PASS if c else FAIL).append(n)
    print(("  ok  " if c else "  FAIL") + f" {n}" +
          (f" -- {d}" if d and not c else ""))

DARK = "#0e0e11"

def mix(a, b, t):
    ah, bh = a.lstrip("#"), b.lstrip("#")
    ar, ag, ab = (int(ah[i:i + 2], 16) for i in (0, 2, 4))
    br, bg_, bb = (int(bh[i:i + 2], 16) for i in (0, 2, 4))
    return "#%02x%02x%02x" % (round(ar + (br - ar) * t),
                              round(ag + (bg_ - ag) * t),
                              round(ab + (bb - ab) * t))

n_pairs = 0
for name in sorted(nhl_identity.team_colors):
    c = nhl_identity.team_colors[name]
    bg, hover, fg = accent_for_team(name)
    whisper = mix(bg, DARK, 0.85)  # same recipe as AppColors.ACCENT_BG
    pairs = {
        "fg on accent": (fg, bg),
        "fg on hover": (fg, hover),
        "team text on dark": (text_color_for_team(name), DARK),
        "accent-on-dark on whisper": (ensure_text_contrast(bg, whisper),
                                      whisper),
        "dataclass primary": (c.text_on_primary, c.primary),
        "dataclass secondary": (c.text_on_secondary, c.secondary),
        "white on whisper": ("#ffffff", whisper),
        "default accent text": ("#0e0e11", "#00ceb8"),
    }
    for label, (f_, b_) in pairs.items():
        n_pairs += 1
        r = contrast_ratio(f_, b_)
        if r < 4.5:
            FAIL.append(f"{name} {label}")
            print(f"  FAIL {name} -- {label}: fg={f_} bg={b_} {r:.2f}:1")

check(f"all {n_pairs} team-color text pairs meet WCAG AA 4.5:1",
      not FAIL, f"{len(FAIL)} failing" if FAIL else "")

# Spot checks: the previously-worst offenders are now readable AND
# still in the team hue family.
stl = text_color_for_team("St. Louis Blues")
check("St. Louis visualizer text readable (was 1.61:1)",
      contrast_ratio(stl, DARK) >= 4.5, f"{contrast_ratio(stl, DARK):.2f}")
uta_bg, _, uta_fg = accent_for_team("Utah Hockey Club")
check("Utah accent text readable (was 2.33:1)",
      contrast_ratio(uta_fg, uta_bg) >= 4.5,
      f"{contrast_ratio(uta_fg, uta_bg):.2f}")
check("Utah still wears green", uta_bg.lower() == "#69be28", uta_bg)
phi_bg, _, phi_fg = accent_for_team("Philadelphia Flyers")
check("Philadelphia accent text readable (was 3.55:1)",
      contrast_ratio(phi_fg, phi_bg) >= 4.5,
      f"{contrast_ratio(phi_fg, phi_bg):.2f}")

# Passing teams are untouched: e.g. Pittsburgh keeps gold accent/white... no,
# black->gold secondary with black text; Detroit keeps red/white.
det_bg, _, det_fg = accent_for_team("Detroit Red Wings")
check("Detroit unchanged (red/white)",
      det_bg.lower() == "#ce1126" and det_fg.lower() == "#ffffff",
      f"{det_bg}/{det_fg}")
pit_bg, _, pit_fg = accent_for_team("Pittsburgh Penguins")
check("Pittsburgh unchanged (gold/black)",
      pit_bg.lower() == "#fcb514" and pit_fg.lower() == "#000000",
      f"{pit_bg}/{pit_fg}")

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
sys.exit(1 if FAIL else 0)
