# Computation and Boundary Evidence for Scientific Software Repair

[![Benchmark](https://img.shields.io/badge/Benchmark-SWE--bench%20Science-orange.svg)](https://github.com/OpenMOSS/SWE-bench-Science)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

Static extraction of computation graphs, conditions, and library boundaries from scientific repositories. The repair agent queries this evidence during bug repair instead of reconstructing it from grep and file reads.

**Author:** Rajarshi Ghoshal (`rajarshi.ghoshal1@gmail.com`)
**Report:** 4 pages + references, submitted to TU Graz (Institute of Software Engineering and AI).

---

## What it does

CBE traces the public reproducer, extracts expressions, conditions, definitions, and call boundaries with Tree-sitter and Joern, and exposes three query endpoints (`find`, `inspect`, `note`) alongside the agent's normal shell tools. No model calls during preparation. Median extraction: 73 s of an 1800 s budget.

The baseline gets the same model, budget, tools, and containers — minus the evidence store.

---

## Results (89 locked tasks, k=3, 522 verified attempts)

Both arms solve 60 attempts (22.9% vs. 23.1%). The confidence interval spans zero: paired bootstrap Δ = +0.75 pp, 95% CI [−3.4, +4.9] pp.

Discipline-level outcomes diverge:
- Mechanics +22.2 pp (task 103, pyNastran: CBE exposes ply iteration + matrix accumulation)
- Materials +9.7 pp, Astronomy +12.4 pp
- Biomedical engineering −16.7 pp (task 022, nilearn: agent reads projection maths instead of preserving the atlas-label interface)
- Biology −9.5 pp
- Chemistry, physics, mathematics: 0.0 pp across 31 tasks

CBE uses 13.7% fewer output tokens (10.36M vs. 12.01M), 4.8% more input tokens, and 70 s more work time per attempt.

About a fifth of tasks flip outcome between identical runs.

---

## Method

```
reproduce.py → trace observer → static extractor → evidence store → agent queries
                                (Tree-sitter, Joern)       (find, inspect, note)
```

- Preparation is offline. No model calls.
- Both arms: DeepSeek V4.1 Flash, temperature 0, 1800 s, 8 CPUs, 16 GiB RAM.
- Verifier runs in a clean container. Private tests never visible during repair.

---

## Repository

```
src/scicontext/          CBE implementation (evidence, parsers, graph, tools, agent)
configs/                 Frozen task split + evaluation configs
scripts/                 Runners and analysis
tests/                   715 tests
pyproject.toml, uv.lock  Pinned dependencies
REPRODUCTION.md          How to run everything
```

---

## Quick start

```bash
git clone https://github.com/rajarshighoshal/computation-boundary-evidence.git
cd computation-boundary-evidence
uv sync --python 3.12 --locked --extra test --extra runner
uv run --no-sync pytest -q
```

Run the extractor (no API key needed):

```bash
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . --config configs/extractor-validation-30.json \
  --output runs/extractor-validation-30 --execute --extract-only
```

Run a paired repair trial:

```bash
export DEEPSEEK_API_KEY="your-key"
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . --config configs/development-e2e-check.json \
  --output runs/development-e2e-check-v5 --execute
```

Full reproduction details: [REPRODUCTION.md](REPRODUCTION.md).

---

## Task IDs

Frozen split in `configs/interactive-science.split.json`. Official SWE-bench Science release, commit `42e7e97`.

**Development (30):** 001 002 004 005 006 008 009 010 014 016 019 024 025 027 028 045 051 058 061 070 073 076 077 078 080 091 099 104 114 119

**Locked evaluation (89):** 003 007 011 012 013 015 017 018 020 021 022 023 026 029 030 031 032 033 034 035 036 037 038 039 040 041 042 043 044 046 047 048 049 050 052 053 054 055 056 057 059 060 062 063 064 065 066 067 068 069 071 072 074 075 079 081 082 083 084 085 086 087 088 089 090 092 093 094 095 096 097 098 100 101 102 103 105 106 107 108 109 110 111 112 113 115 116 117 118

---

## AI disclosure

Rajarshi Ghoshal designed and directed the study. Oh My Pi and ChatGPT assisted with harness code, tests, figures, and prose. DeepSeek V4.1 Flash was the sole repair model. All trajectories, diffs, and verifier receipts are preserved.
