"""Measure the rendered PDF instead of guessing: margins, whitespace bands, text density.

Visual QA of a compiled paper without eyes. Renders each page at a fixed DPI, builds a
per-row ink profile, and reports the numbers that decide whether a page looks tight,
loose, or broken:

- content margins (left/right/top/bottom) per page
- interior whitespace bands taller than a threshold (float-packing holes)
- ink fraction per page (a page that is 12% ink is dense; 4% is airy)
- rendered text sizes from word bounding boxes (catches shrunken figure labels)

Usage: PYTHONPATH=. .venv/bin/python analysis/audit_pdf_layout.py paper/latex/report.pdf
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
DPI = 100
POINTS_PER_INCH = 72.0
GAP_INCHES = 0.45          # interior band this tall with no ink is a hole
DARK = 200                 # PGM value below this counts as ink


def render_pages(pdf: Path, workdir: Path) -> list[Path]:
    subprocess.run(
        ["pdftoppm", "-gray", "-r", str(DPI), "-png", str(pdf), str(workdir / "page")],
        check=True, capture_output=True,
    )
    return sorted(workdir.glob("page-*.png"))


def read_gray_png(path: Path) -> tuple[int, int, bytes, int]:
    """Decode a grayscale PNG without third-party libraries."""
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise SystemExit(f"{path} is not a PNG")
    pos = 8
    width = height = 0
    raw = b""
    while pos < len(data):
        length = int.from_bytes(data[pos:pos + 4], "big")
        chunk = data[pos + 4:pos + 8]
        payload = data[pos + 8:pos + 8 + length]
        if chunk == b"IHDR":
            width = int.from_bytes(payload[0:4], "big")
            height = int.from_bytes(payload[4:8], "big")
            bit_depth, colour_type = payload[8], payload[9]
            if bit_depth != 8 or colour_type not in (0, 2, 4, 6):
                raise SystemExit(f"unsupported PNG format ({bit_depth}bpc, type {colour_type})")
            channels = {0: 1, 2: 3, 4: 2, 6: 3}[colour_type]
        elif chunk == b"IDAT":
            raw += payload
        elif chunk == b"IEND":
            break
        pos += 12 + length
    import zlib
    stream = zlib.decompress(raw)
    stride = width * channels
    rows: list[bytes] = []
    previous = bytearray(stride)
    offset = 0
    for _ in range(height):
        filter_type = stream[offset]
        line = bytearray(stream[offset + 1:offset + 1 + stride])
        offset += 1 + stride
        if filter_type == 1:
            for i in range(channels, stride):
                line[i] = (line[i] + line[i - channels]) & 0xFF
        elif filter_type == 2:
            for i in range(stride):
                line[i] = (line[i] + previous[i]) & 0xFF
        elif filter_type == 3:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                line[i] = (line[i] + ((left + previous[i]) >> 1)) & 0xFF
        elif filter_type == 4:
            for i in range(stride):
                left = line[i - channels] if i >= channels else 0
                up = previous[i]
                up_left = previous[i - channels] if i >= channels else 0
                p = left + up - up_left
                pa, pb, pc = abs(p - left), abs(p - up), abs(p - up_left)
                predictor = left if (pa <= pb and pa <= pc) else (up if pb <= pc else up_left)
                line[i] = (line[i] + predictor) & 0xFF
        rows.append(bytes(line))
        previous = line
    return width, height, b"".join(rows), channels


def page_metrics(path: Path) -> dict[str, Any]:
    width, height, pixels, channels = read_gray_png(path)
    if channels != 1:  # keep the row profile cheap on colour renders
        pixels = pixels[::channels]
    row_ink = []
    col_ink = [0] * width
    for y in range(height):
        row = pixels[y * width:(y + 1) * width]
        count = 0
        for x, value in enumerate(row):
            if value < DARK:
                count += 1
                col_ink[x] += 1
        row_ink.append(count)

    def first_last(values: list[int]) -> tuple[int, int, int]:
        idx = [i for i, value in enumerate(values) if value > 0]
        if not idx:
            return 0, 0, len(values)
        return idx[0], len(values) - 1 - idx[-1], idx[-1] - idx[0] + 1

    top_blank, bottom_blank, content_height = first_last(row_ink)
    left_blank, right_blank, _content_width = first_last(col_ink)

    gap_limit = int(GAP_INCHES * DPI)
    gaps = []
    run_start = None
    for y, ink in enumerate(row_ink):
        if ink == 0:
            run_start = y if run_start is None else run_start
        else:
            if run_start is not None and y - run_start >= gap_limit:
                gaps.append(((run_start + y) / 2 / DPI, (y - run_start) / DPI))
            run_start = None

    interior_ink = sum(row_ink[top_blank:height - bottom_blank])
    return {
        "left_in": left_blank / DPI,
        "right_in": right_blank / DPI,
        "top_in": top_blank / DPI,
        "bottom_in": bottom_blank / DPI,
        "ink_pct": 100.0 * interior_ink / (content_height * width) if content_height else 0.0,
        "holes": sorted(gaps, key=lambda item: -item[1])[:3],
    }


def text_sizes(pdf: Path) -> dict[str, float]:
    out = subprocess.run(["pdftotext", "-bbox", str(pdf), "-"],
                         check=True, capture_output=True, text=True).stdout
    heights: list[float] = []
    import re
    for match in re.finditer(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">', out):
        x_min, y_min, x_max, y_max = (float(value) for value in match.groups())
        del x_min, x_max
        height = y_max - y_min
        if 2.0 < height < 40.0:
            heights.append(height)
    heights.sort()
    if not heights:
        return {}
    return {
        "min": heights[0],
        "p05": heights[int(0.05 * len(heights))],
        "p25": heights[int(0.25 * len(heights))],
        "median": heights[len(heights) // 2],
        "p90": heights[int(0.90 * len(heights))],
    }


def main() -> int:
    pdf = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "paper" / "latex" / "report.pdf"
    if not pdf.is_file():
        print(f"missing {pdf}", file=sys.stderr)
        return 1
    pages = int(subprocess.run(["pdfinfo", str(pdf)], check=True, capture_output=True, text=True)
                .stdout.split("Pages:")[1].split()[0])
    print(f"{pdf} — {pages} pages")
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        rendered = render_pages(pdf, workdir)
        print(f"\n{'page':>4} {'left':>6} {'right':>6} {'top':>6} {'bottom':>7} {'ink%':>6}  "
              f"largest interior gap")
        for index, path in enumerate(rendered, start=1):
            metrics = page_metrics(path)
            holes = metrics["holes"]
            hole_text = ", ".join(
                f"{float(size):.2f}in @ {float(position):.1f}in" for position, size in holes) or "none"
            print(f"{index:>4} {metrics['left_in']:>5.2f}\" {metrics['right_in']:>5.2f}\" "
                  f"{metrics['top_in']:>5.2f}\" {metrics['bottom_in']:>6.2f}\" "
                  f"{metrics['ink_pct']:>5.1f}  {hole_text}")

    sizes = text_sizes(pdf)
    print("\nrendered word heights (points):",
          "  ".join(f"{key} {value:.1f}" for key, value in sizes.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
