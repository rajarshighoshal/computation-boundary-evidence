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
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from plotting import REPO, RC, save, scene  # noqa: E402
from theme import INK, INK_SOFT, LIGHT_BLUE, LIGHT_GRAY, LIGHT_TEAL, RUST, TEAL  # noqa: E402

TOOLS = REPO / "src" / "scicontext" / "science_tools.py"
TASK103_STATE = Path(
    "runs/deepseek-locked89-k1-v2/jobs/task-103-science/task_103__c7n8YcK/agent-host/science/state.json"
)
MONO = 5.8


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
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.010,rounding_size=0.02",
                                facecolor=face, edgecolor=edge, linewidth=0.7, zorder=2))
    ax.text(x + 0.015, y + h - 0.028, title, fontsize=title_size, fontweight="bold", color=INK,
            va="top", ha="left", zorder=3)
    for index, line in enumerate(lines):
        ax.text(x + 0.015, y + h - 0.078 - index * 0.041, line, fontsize=line_size,
                color=INK_SOFT, va="top", ha="left", zorder=3)


def arrow(ax: Any, start: tuple[float, float], end: tuple[float, float]) -> None:
    ax.add_patch(FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=6, linewidth=0.8,
                                 color=INK_SOFT, shrinkA=0, shrinkB=0, zorder=1))


def main() -> None:
    tools = tool_descriptions()
    contract = external_contract()
    boundary = contract["boundary"]

    with plt.rc_context(RC):
        fig = plt.figure(figsize=(7.0, 3.0))
        flow = fig.add_axes((0.005, 0.015, 0.465, 0.88))
        quote = fig.add_axes((0.492, 0.015, 0.503, 0.88))
        for ax in (flow, quote):
            ax.set_xlim(0, 1)
            ax.set_ylim(0, 1)
            ax.set_xticks([])
            ax.set_yticks([])
            ax.axis("off")

        scene(flow, "A", "Preparation, then queries", y=0.95)
        box(flow, 0.01, 0.795, 0.98, 0.155, "task snapshot (no model call)",
            ["issue text, repository tree at the pinned commit,",
             "reproducer command, ranked source-file budget"],
            face=LIGHT_GRAY, edge=INK_SOFT)
        arrow(flow, (0.50, 0.790), (0.50, 0.760))
        box(flow, 0.01, 0.505, 0.98, 0.250, "static extraction (parsers only)",
            ["Tree-sitter for Python, Joern code property graphs for",
             "C/C++/Fortran/Cython; import and dynamic-binding resolution;",
             "findings, conditions and documented definitions captured",
             "with source spans. Nothing is executed here."],
            face=LIGHT_BLUE, edge="#2468A0")
        arrow(flow, (0.50, 0.500), (0.50, 0.470))
        box(flow, 0.01, 0.235, 0.98, 0.230, "queryable evidence store",
            ["computations: name, path, result anchor, expressions",
             "conditions and findings; documented public definitions",
             "call boundaries: internal | external provider | unknown"],
            face=LIGHT_TEAL, edge=TEAL)
        arrow(flow, (0.50, 0.230), (0.50, 0.200))
        box(flow, 0.01, 0.020, 0.98, 0.175, "agent endpoints (same budget as baseline)",
            ["science_find - " + tools["science_find"],
             "science_inspect - relationships, definitions, source, contracts",
             "science_note - optional record; never gates repair"],
            face=LIGHT_GRAY, edge=INK_SOFT)

        scene(quote, "B", "Payloads the agent sees", y=0.95)
        quote.add_patch(FancyBboxPatch((0.012, 0.585), 0.976, 0.315,
                                       boxstyle="round,pad=0.010,rounding_size=0.02",
                                       facecolor=LIGHT_TEAL, edgecolor=TEAL, linewidth=0.7))
        quote.text(0.03, 0.880,
                   f'one recorded boundary contract: task 103, {contract["path"]}:{contract["line"]}',
                   fontsize=6.6, fontweight="bold", color=INK, va="top")
        quote.text(0.03, 0.830,
                   f'{{"callee": "{contract["callee"]}", "code": "{contract["code"]}",\n'
                   f' "boundary": {{"kind": "{boundary["kind"]}", "provider": "{boundary["provider"]}",\n'
                   f'              "assume": "{boundary["assume"]}",\n'
                   f'              "repair_scope": "{boundary["repair_scope"]}"}}}}',
                   fontsize=MONO, color=INK_SOFT, va="top", family="monospace", linespacing=1.40)

        quote.add_patch(FancyBboxPatch((0.012, 0.300), 0.976, 0.260,
                                       boxstyle="round,pad=0.010,rounding_size=0.02",
                                       facecolor=LIGHT_GRAY, edgecolor=INK_SOFT, linewidth=0.7))
        quote.text(0.03, 0.535, "science_find response shape (keys verbatim)", fontsize=6.6,
                   fontweight="bold", color=INK, va="top")
        quote.text(0.03, 0.488,
                   '{"status": "ok", "matches": [{"target": ...,\n'
                   ' "excerpt": ..., "kind": "scientific_node"}],\n'
                   ' "total_matches": N, "next_offset": ...,\n'
                   ' "scope": "Lexical discovery, not a verdict."}',
                   fontsize=MONO, color=INK_SOFT, va="top", family="monospace", linespacing=1.40)

        quote.add_patch(FancyBboxPatch((0.012, 0.020), 0.976, 0.250,
                                       boxstyle="round,pad=0.010,rounding_size=0.02",
                                       facecolor="white", edgecolor=RUST, linewidth=0.7))
        quote.text(0.03, 0.245, "the same call in the baseline arm", fontsize=6.6,
                   fontweight="bold", color=RUST, va="top")
        quote.text(0.03, 0.198,
                   'grep -rn "radians" .      # provider, contract and repair\n'
                   '                          # scope are rebuilt by reading the\n'
                   '                          # file and its imports; nothing is\n'
                   '                          # marked assumed-correct',
                   fontsize=MONO, color=INK_SOFT, va="top", family="monospace", linespacing=1.40)

        save(fig, "fig_grounding_flow")


if __name__ == "__main__":
    main()
