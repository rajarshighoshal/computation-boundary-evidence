"""How the prepared representation is built, and what the agent sees.

Panel A  the four preparation stages and the three query endpoints
Panel B  verbatim payload shapes: a science_find response and one recorded
         boundary contract from the held-out task 103, plus the baseline
         equivalent for the same call.

Tool descriptions are read from src/scicontext/science_tools.py and the contract
from runs/deepseek-locked89-k1-v2 (the same receipt a verifier scored), so the
figure cannot drift from the shipped code.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.transforms as transforms
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))

CLAIM = (
    "Preparation makes structure queryable to the repair agent, and the payloads it answers with are recorded ones."
)
from plotting import REPO, RC, save, scene  # noqa: E402
from theme import INK, INK_SOFT, LIGHT_BLUE, LIGHT_GRAY, LIGHT_TEAL, RUST, TEAL  # noqa: E402

TOOLS = REPO / "src" / "scicontext" / "science_tools.py"
TASK103_STATE = Path(
    "runs/deepseek-locked89-k1-v2/jobs/task-103-science/task_103__c7n8YcK/agent-host/science/state.json"
)
MONO = 6.2


def tool_descriptions() -> dict[str, str]:
    text = TOOLS.read_text()
    found: dict[str, str] = {}
    for name in ("science_find", "science_inspect", "science_note"):
        match = re.search(rf'tool\("{name}",\s*"([^"]+)"', text)
        if match is None:
            raise SystemExit(f"tool description for {name} not found in {TOOLS}")
        found[name] = match.group(1)
    return found


def external_contract() -> dict[str, Any]:
    payload = json.loads((REPO / TASK103_STATE).read_text())
    stack: list[Any] = [payload]
    best: dict[str, Any] | None = None
    while stack:
        item = stack.pop()
        if isinstance(item, dict):
            boundary = item.get("boundary")
            if (isinstance(boundary, dict) and boundary.get("kind") == "external"
                    and isinstance(item.get("code"), str) and item.get("callee")
                    and item["callee"] in item["code"] and boundary.get("provider")):
                candidate = {"callee": item["callee"], "code": item["code"],
                             "line": item.get("line"), "path": item.get("path") or "shell.py",
                             "boundary": boundary}
                if best is None or len(candidate["code"]) < len(best["code"]):
                    best = candidate
            stack.extend(item.values())
        elif isinstance(item, list):
            stack.extend(item)
    if best is None:
        raise SystemExit(f"no external boundary contract found in {TASK103_STATE}")
    return best


def box(ax: Any, x: float, y: float, w: float, h: float, title: str, lines: list[str],
        *, face: str, edge: str, title_size: float = 7.0, line_size: float = 6.2) -> None:
    """Card with a title and text lines, spaced in points so it holds at any figure size.

    The card must be tall enough for its content; a short card is a hard error rather than a
    silent overflow into the border.
    """
    axes_height_in = ax.get_position().height * ax.figure.get_size_inches()[1]
    needed_pt = title_size * 1.75 + len(lines) * line_size * 1.55 + 6.0
    if h * axes_height_in * 72.0 < needed_pt:
        raise SystemExit(
            f"card '{title}' needs {needed_pt / 72.0 / axes_height_in:.3f} axes height, has {h:.3f}")
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.010,rounding_size=0.02",
                                facecolor=face, edgecolor=edge, linewidth=0.7, zorder=2))
    top = y + h - 0.022
    ax.text(x + 0.015, top, title, fontsize=title_size, fontweight="bold", color=INK,
            va="top", ha="left", zorder=3)
    for index, line in enumerate(lines):
        shifted = transforms.offset_copy(ax.transAxes, fig=ax.figure,
                                         x=0, y=-(title_size * 1.75 + index * line_size * 1.55),
                                         units="points")
        ax.text(x + 0.015, top, line, fontsize=line_size, color=INK_SOFT, va="top", ha="left",
                zorder=3, transform=shifted)


def arrow(ax: Any, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=6, linewidth=0.8,
                                 color=INK_SOFT, shrinkA=0, shrinkB=0, zorder=1))


def main() -> None:
    tools = tool_descriptions()
    contract = external_contract()
    boundary = contract["boundary"]

    with plt.rc_context(RC):
        fig = plt.figure(figsize=(5.5, 2.35))
        flow = fig.add_axes((0.005, 0.02, 0.385, 0.86))
        quote = fig.add_axes((0.415, 0.02, 0.575, 0.86))
        for ax in (flow, quote):
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.axis("off")

        scene(flow, "A", "Preparation and query path", y=0.965)
        box(flow, 0.01, 0.690, 0.98, 0.258, "static extraction: parsers only, no model call",
            ["parsers rank files and resolve imports;",
             "Tree-sitter and Joern supply structure"],
            face=LIGHT_BLUE, edge="#2468A0", line_size=6.0)
        arrow(flow, (0.50, 0.685), (0.50, 0.663))
        box(flow, 0.01, 0.345, 0.98, 0.280, "queryable store, filled once per task",
            ["computations and result anchors; conditions;",
             "definitions; call boundaries with providers"],
            face=LIGHT_TEAL, edge=TEAL, line_size=6.0)
        arrow(flow, (0.50, 0.340), (0.50, 0.318))
        box(flow, 0.01, 0.115, 0.98, 0.190, "endpoints beside the ordinary shell tools",
            ["science_find / inspect / note"],
            face=LIGHT_GRAY, edge=INK_SOFT, line_size=6.0)
        flow.text(0.0, 0.045,
                  "Prepared once per task, queried on demand, same budget as the baseline arm.",
                  fontsize=6.2, color=INK_SOFT, ha="left", va="center", style="italic")

        scene(quote, "B", "Recorded payloads", y=0.90)
        quote.add_patch(FancyBboxPatch((0.012, 0.455), 0.976, 0.430,
                                       boxstyle="round,pad=0.010,rounding_size=0.02",
                                       facecolor=LIGHT_TEAL, edgecolor=TEAL, linewidth=0.7))
        quote.text(0.030, 0.845,
                   f'boundary record, task 103, {contract["path"]}:{contract["line"]}',
                   fontsize=6.4, fontweight="bold", color=INK, va="top")
        quote.text(0.030, 0.792,
                   f'{{"callee": "{contract["callee"]}", "code": "{contract["code"]}",\n'
                   f' "boundary": {{"kind": "{boundary["kind"]}",\n'
                   f'              "provider": "{boundary["provider"]}",\n'
                   f'              "assume": "{boundary["assume"]}",\n'
                   f'              "repair_scope": "{boundary["repair_scope"]}"}}}}',
                   fontsize=MONO, color=INK_SOFT, va="top", family="monospace", linespacing=1.35)

        quote.add_patch(FancyBboxPatch((0.012, 0.175), 0.976, 0.250,
                                       boxstyle="round,pad=0.010,rounding_size=0.02",
                                       facecolor=LIGHT_GRAY, edgecolor=INK_SOFT, linewidth=0.7))
        quote.text(0.030, 0.390, "search response: targets first, no verdict", fontsize=6.4,
                   fontweight="bold", color=INK, va="top")
        quote.text(0.030, 0.337,
                   '{"status": "ok", "matches": [{"target": ...,\n'
                   '  "excerpt": ..., "kind": "scientific_node"}],\n'
                   ' "scope": "Lexical discovery, not a verdict."}',
                   fontsize=MONO, color=INK_SOFT, va="top", family="monospace", linespacing=1.35)

        quote.add_patch(FancyBboxPatch((0.012, 0.020), 0.976, 0.130,
                                       boxstyle="round,pad=0.010,rounding_size=0.02",
                                       facecolor="white", edgecolor=RUST, linewidth=0.7))
        quote.text(0.030, 0.115, "the same call without the store", fontsize=6.4,
                   fontweight="bold", color=RUST, va="top")
        quote.text(0.030, 0.070,
                   'grep -rn "radians" .    # provider inferred by hand',
                   fontsize=MONO, color=INK_SOFT, va="top", family="monospace", linespacing=1.35)

        save(fig, "fig_grounding_flow", claim=CLAIM)


if __name__ == "__main__":
    main()
