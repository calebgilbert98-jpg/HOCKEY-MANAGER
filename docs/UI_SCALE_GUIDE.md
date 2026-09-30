# UI Text Scaling Guide

How font scaling works in Puck Dynasty, and the rules for keeping text
uncut at every window size and tier.

## The 5 tiers

`ui_scale.py` owns everything. Tiers (multiplier on every base size):

| Tier        | Factor |
|-------------|--------|
| Compact     | 0.85   |
| Small       | 0.925  |
| Default     | 1.00   |
| Large       | 1.12   |
| Extra Large | 1.25   |

Legacy setting values (`"Small"`, `"Medium"`, `"Medium (Current)"`,
`"Large"`) auto-migrate to the nearest new tier — old `settings.json`
files keep working.

## The live font registry — use it for all new text

Never hard-code `font=(FAMILY, size)` tuples in new code. Use:

```python
import ui_scale
lbl = tk.Label(parent, text="...", font=ui_scale.font("DejaVu Sans", 10, "bold"))
```

`ui_scale.font()` returns a registered `tkinter.font.Font` object.
`set_tier()` resizes every registered font **in place** — all open
windows update instantly, no restart, no reopen. Base sizes are rounded
to whole points.

`ui_scale.on_scale_change(callback)` fires after every tier switch —
use it for layout reflows (repacking, rewrapping), not for font sizes.

## Auto-fit (windowed mode scaling)

Settings → Interface → Window Behavior → **"Auto-fit text size to
window size"** (persisted as `ui_preferences.auto_fit_ui`).

When on, a debounced `<Configure>` on the app root derives
`auto_factor = clamp(min(w/1600, h/900), 0.8, 1.2)` and multiplies it
with the tier. Narrow window + Extra Large → effective 1.0 instead of
overflowing; 4K monitor → text grows up to 1.2x. This is what keeps the
lines editor fitting at small window sizes: the header needs ~1200px at
raw XL, so auto-fit shrinks the effective tier instead of clipping.

`bind_auto_fit(root)` is called once at startup in `main.py`.
`ui_scale.scaled(px)` scales a pixel value by the effective factor;
`ui_scale.card_size(w, h)` scales popup-card geometry (used by
`popup_system.show_card` so Large/XL tiers don't clip card content).

## Rules for new windows (so text never gets cut off)

1. **Route every font through `ui_scale.font()`** (or the window-local
   `_font()` helper where one exists, e.g. `CleanEditLinesWindow`,
   `pbp_visual_sim._vfont`). Raw tuples don't scale and will look
   wrong next to scaled text.
2. **Long hint/status labels must wrap.** Bind `wraplength` to the
   *window* width (not the label's own container — that's circular when
   overflowing). See the lines-editor footer `_wrap_hint`.
3. **Chip/button rows must reflow.** If a row of fixed chips can exceed
   the window at XL, repack N-across vs 2×2 on `<Configure>` (see
   `CleanEditLinesWindow._layout_chips`). Guard with a width-change
   check to avoid repack loops.
4. **Popup cards:** `show_card` scales geometry automatically; don't
   hard-code card sizes that assume 1.0 text.
5. **ttk widgets:** raw `ttk.Label` picks up the OS theme background
   (white in our dark UI). Use `tk.Label` with explicit colors or the
   existing `_caption()` helper in settings windows.

## Cutoff audit

`~/workspace/.lines_new/clip_audit.py` builds the lines editor and a
popup card at 1280x720 / 1366x768 / 1920x1080 × Compact / Default /
Extra Large and flags any label/button whose requested width exceeds
its allocated width. Run it after touching shared UI code; zero
product-code issues is the bar.
