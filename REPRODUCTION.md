# Reproduction

## Requirements

- macOS or Linux, Python 3.12, [uv](https://docs.astral.sh/uv/), Docker (8 CPUs, 16 GiB RAM)
- `DEEPSEEK_API_KEY` for repair trials (not needed for static extraction)

## Setup

```bash
git clone https://github.com/rajarshighoshal/computation-boundary-evidence.git
cd computation-boundary-evidence
uv sync --python 3.12 --locked --extra test --extra runner
uv run --no-sync pytest -q
```

## Restore task environments

```bash
uv run --no-sync python scripts/restore_release.py --workspace . --task-id 001,002,058
# Restricted-license tasks need --allow-restricted-licenses
```

Official SWE-bench Science release, commit `42e7e97`.

## Run the extractor (no API key)

```bash
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . --config configs/extractor-validation-30.json \
  --output runs/extractor-validation-30 --execute --extract-only

uv run --no-sync python scripts/extractor_report.py runs/extractor-validation-30
```

## Run a paired trial

```bash
export DEEPSEEK_API_KEY="your-key"
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . --config configs/development-e2e-check.json \
  --output runs/development-e2e-check-v5 --execute
```

## Run the locked-89 evaluation (k=3)

```bash
export DEEPSEEK_API_KEY="your-key"
bash scripts/run_locked89_k3.sh
```

## Reproduce the reported numbers

Everything the paper reports recomputes from the exports committed under `paper/latex/data/`. No API key, no Docker, and no repair trial is involved.

```bash
uv run --no-sync python paper/latex/scripts/analyze_results.py
uv run --no-sync python paper/latex/scripts/analyze_visual_results.py
uv run --no-sync python paper/latex/scripts/make_figures.py
cd paper/latex && pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
```

`analyze_results.py` writes `paper/latex/generated/numbers.tex` (every macro the text quotes), `main_table.tex`, and `results.json`. `analyze_visual_results.py` writes the public/private gate counts and the exact-versus-partial table. `make_figures.py` redraws the discipline and trial figures.

Rebuilding those exports from scratch needs the run tree (14 GB, not shipped):

```bash
uv run --no-sync python paper/latex/scripts/extract_records.py --repo .
uv run --no-sync python paper/latex/scripts/extract_visual_records.py --repo .
```

`extract_records.py` reads each trial's `run.json`, `verifier/reward.json`, and `agent-host/repair-session.json`. Twelve attempt slots whose primary run produced no verifier verdict are filled from `runs/rerun-missing-k3-v1`; every row names the run that produced it in its `run` column. The run tree itself is reconstructed by `bash scripts/run_locked89_k3.sh` plus the gap-fill config `configs/rerun-missing-k3.json`.

## Task partition

Defined in `configs/interactive-science.split.json`.

**Development (30):** 001 002 004 005 006 008 009 010 014 016 019 024 025 027 028 045 051 058 061 070 073 076 077 078 080 091 099 104 114 119

**Locked (89):** 003 007 011 012 013 015 017 018 020 021 022 023 026 029 030 031 032 033 034 035 036 037 038 039 040 041 042 043 044 046 047 048 049 050 052 053 054 055 056 057 059 060 062 063 064 065 066 067 068 069 071 072 074 075 079 081 082 083 084 085 086 087 088 089 090 092 093 094 095 096 097 098 100 101 102 103 105 106 107 108 109 110 111 112 113 115 116 117 118
