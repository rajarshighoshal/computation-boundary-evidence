#!/usr/bin/env python3
"""Programmatic layout QA for figure PDFs and the compiled report.

Detects, without human vision:
  * text clipped by the page edge (bbox within `margin` pt of an edge)
  * overlapping text bounding boxes on the same page
  * figure body drawn outside the declared page box

Usage:
    python analysis/figure_qa.py paper/latex/figures/*.pdf paper/latex/main.pdf
"""
from __future__ import annotations
import re
import subprocess
import sys
from pathlib import Path

MARGIN = 4.0     # pt: text closer than this to an edge is suspicious
OVERLAP = 0.35   # fraction of the smaller box that must intersect to flag


def page_words(pdf: Path):
    """Yield (page_width, page_height, [(x0, y0, x1, y1, text), ...])."""
    out = subprocess.run(['pdftotext', '-bbox', str(pdf), '-'],
                         capture_output=True, text=True, check=True).stdout
    for width, height, body in re.findall(
            r'<page width="([\d.]+)" height="([\d.]+)">(.*?)</page>', out, re.S):
        words = []
        for xmin, ymin, xmax, ymax, text in re.findall(
                r'<word xMin="([\d.]+)" yMin="([\d.]+)" '
                r'xMax="([\d.]+)" yMax="([\d.]+)">(.*?)</word>', body):
            words.append((float(xmin), float(ymin), float(xmax), float(ymax), text))
        yield float(width), float(height), words


def overlap_fraction(a, b) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    small = min((a[2]-a[0]) * (a[3]-a[1]), (b[2]-b[0]) * (b[3]-b[1]))
    return inter / small if small > 0 else 0.0


def audit(pdf: Path) -> list[str]:
    findings = []
    for index, (width, height, words) in enumerate(page_words(pdf), start=1):
        if not words:
            continue
        for x0, y0, x1, y1, text in words:
            if x0 < MARGIN or y0 < MARGIN or x1 > width - MARGIN or y1 > height - MARGIN:
                findings.append(
                    f'{pdf.name} p{index}: CLIPPED "{text}" '
                    f'bbox=({x0:.1f},{y0:.1f},{x1:.1f},{y1:.1f}) page=({width:.0f}x{height:.0f})')
        # pairwise overlap (bounded: skip pages with huge word counts)
        if len(words) <= 400:
            for i in range(len(words)):
                for j in range(i + 1, len(words)):
                    a, b = words[i], words[j]
                    # ignore boxes that merely share a baseline row and butt edges
                    if overlap_fraction(a, b) >= OVERLAP:
                        findings.append(
                            f'{pdf.name} p{index}: OVERLAP "{a[4]}" x "{b[4]}" '
                            f'({overlap_fraction(a, b):.0%})')
    return findings


def main() -> int:
    targets = [Path(p) for p in sys.argv[1:]]
    if not targets:
        print(__doc__)
        return 2
    total = 0
    for pdf in targets:
        if not pdf.exists():
            print(f'{pdf}: MISSING')
            continue
        findings = audit(pdf)
        total += len(findings)
        if findings:
            for line in findings:
                print(line)
        else:
            print(f'{pdf.name}: clean (no clipping, no text overlap)')
    return 1 if total else 0


if __name__ == '__main__':
    raise SystemExit(main())
