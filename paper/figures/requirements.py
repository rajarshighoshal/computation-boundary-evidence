"""Figure requirements, enforced in code.

The report has a fixed geometry: a 6.5in text block, four content pages, one references page.
The figures are authored blind (no vision in the authoring loop), so every aesthetic rule that
can be measured is checked here instead of being eyeballed.

R1  design width is 5.5in or 6.5in. The report includes each figure at \\linewidth (6.5in), so the
    5.5in class is upscaled 1.18x and the 6.5in class is placed at native size; never downscaled.
R2  design height <= 3.1in: multi-row charts need the canvas, and three figures must still fit the
    four-page budget at 6.5in width.
R3  no text smaller than 6.0pt at design size, which renders at 7.1pt or larger.
R4  at most two panels per figure, or three when each panel is at least 1.7in wide.
R5  at most 58 text artists (a labelled row chart: 15 rows x id + value) and 3.5-45% ink.
R6  no text leaves the canvas and no two text artists overlap (checked by plotting.save).
R7  each figure declares the single claim it supports; its caption must open with that claim.
R8  colour semantics are fixed across the paper: BLUE = baseline arm, TEAL = CBE gain,
    RUST = CBE loss, neutral grey = parity/other.
R9  figures read frozen receipts only; plotting code may not contain result literals.
"""

from __future__ import annotations

from typing import Any

FIGURE_WIDTHS_IN = (5.5, 6.5)   # 5.5in is upscaled 1.18x at \linewidth; 6.5in is native
FIGURE_WIDTH_IN = 5.5
MAX_HEIGHT_IN = 3.1
MIN_FONT_PT = 6.0
MAX_PANELS = 3
MIN_PANEL_WIDTH_IN = 1.7
MAX_TEXT_ARTISTS = 58
INK_MIN, INK_MAX = 0.035, 0.45

ALLOWED_COLOURS = {
    "#2468a0",  # BLUE    baseline arm
    "#408f83",  # TEAL    CBE gain
    "#b5523a",  # RUST    CBE loss
    "#171717",  # INK     text
    "#555555",  # INK_SOFT text
    "#6e6e6e",  # GRAY    neutral
    "#d9d9d9",  # GRID
    "#eaf4fa",  # LIGHT_BLUE
    "#eaf6f4",  # LIGHT_TEAL
    "#f3f3f3",  # LIGHT_GRAY
    "#c36547",  # ORANGE
    "#c9ced3",  # TIE     neutral tie line
    "#9cc3de",  # light blue bar tint
    "#b9bec4",  # muted bar tint
}


def check(fig: Any, name: str, claim: str) -> list[str]:
    """Return the list of requirement violations for one rendered figure."""
    import matplotlib.text as mtext
    import numpy

    problems: list[str] = []
    width, height = fig.get_size_inches()

    if not any(abs(width - allowed) < 1e-6 for allowed in FIGURE_WIDTHS_IN):
        problems.append(f"R1 width {width:.2f}in not in {FIGURE_WIDTHS_IN}")
    if height > MAX_HEIGHT_IN + 1e-6:
        problems.append(f"R2 height {height:.2f}in > {MAX_HEIGHT_IN}in")

    texts = [t for t in fig.findobj(mtext.Text) if t.get_visible() and t.get_text().strip()]
    if len(texts) > MAX_TEXT_ARTISTS:
        problems.append(f"R5 {len(texts)} text artists > {MAX_TEXT_ARTISTS}")
    for text in texts:
        size = text.get_fontsize()
        if size < MIN_FONT_PT:
            problems.append(f"R3 '{text.get_text()[:24]}' at {size:.1f}pt < {MIN_FONT_PT}pt")

    panels = [ax for ax in fig.axes if ax.get_visible()]
    panel_widths = [ax.get_position().width * width for ax in panels]
    if len(panels) > MAX_PANELS:
        problems.append(f"R4 {len(panels)} panels > {MAX_PANELS}")
    for index, panel_width in enumerate(panel_widths):
        if len(panels) > 2 and panel_width < MIN_PANEL_WIDTH_IN:
            problems.append(f"R4 panel {index} is {panel_width:.2f}in wide")

    for artist in fig.findobj():
        colour = None
        getter = getattr(artist, "get_color", None) or getattr(artist, "get_facecolor", None)
        if getter is None:
            continue
        try:
            colour = getter()
        except Exception:  # noqa: BLE001 - property probes on assorted artists
            continue
        if isinstance(colour, str) and colour.startswith("#") and colour.lower() not in ALLOWED_COLOURS:
            problems.append(f"R8 colour {colour} outside the semantic palette")

    fig.canvas.draw()
    buffer = numpy.asarray(fig.canvas.buffer_rgba())[:, :, :3]
    ink = float((buffer.min(axis=2) < 200).mean())
    if not INK_MIN <= ink <= INK_MAX:
        problems.append(f"R5 ink {ink:.0%} outside [{INK_MIN:.0%}, {INK_MAX:.0%}]")

    if not claim.strip():
        problems.append("R7 missing claim")
    return problems


__all__ = ["check", "FIGURE_WIDTH_IN"]
