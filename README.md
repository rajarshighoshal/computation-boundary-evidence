# Computation and Boundary Evidence for Scientific Software Repair

[![Benchmark](https://img.shields.io/badge/Benchmark-SWE--bench%20Science-orange.svg)](https://github.com/OpenMOSS/SWE-bench-Science)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)

This repository contains the complete implementation, evaluation artifacts, and research report for the PhD applicant research task at the **Institute of Software Engineering and Artificial Intelligence, Graz University of Technology (TU Graz)**.

**Author:** Rajarshi Ghoshal (`rajarshi.ghoshal1@gmail.com`)  
**Research Report:** *"Computation and Boundary Evidence for Scientific Software Repair"* (4 content pages + 1 references page, submitted via email to TU Graz).

---

## Research Question

> *Does a compact, queryable representation of scientific code and its public definitions help an autonomous repair agent form an accurate task model and repair software under the same total allowance as ordinary repair?*

Standard coding agents navigate repositories as raw text, relying on speculative `grep` searches and file reads. In scientific software, where correctness depends on mathematical pipelines, numerical constraints, and library interfaces, flat text search often misses the governing calculation or boundaries.

**Computation and Boundary Evidence (CBE)** statically indexes expressions, conditional guards, and external library interfaces, providing a targeted query interface (`find`, `inspect`, `note`) that the agent queries during repair under matched models and budgets.

---

## Core Findings

We conducted a replicated evaluation across **89 held-out SWE-bench Science tasks** with $k{=}3$ repeated seeds (522 verified Docker attempts), paired against an identical baseline (same model, tools, budget, and containers):

1. **Aggregate Parity:** Both arms solve exactly 60 attempts across the evaluation set (22.9% baseline vs. 23.1% CBE; paired bootstrap $\Delta = +0.75$\,pp, 95% CI $[-3.4, +4.9]$\,pp; two-sided sign test $p = 1.00$).
2. **Sharp Discipline Split:** Aggregate parity conceals opposing domain effects:
   - **Mechanics:** $+22.2$\,pp (driven by task 103, `pyNastran`, where CBE exposes both ply iteration and matrix accumulation).
   - **Materials Science:** $+9.7$\,pp across 15 tasks.
   - **Astronomy:** $+12.4$\,pp across 5 tasks.
   - **Biomedical Engineering:** $-16.7$\,pp across 10 tasks (in task 022, `nilearn`, the agent anchored on coordinate projection mathematics instead of preserving the atlas-label interface contract).
   - **Biology:** $-9.5$\,pp across 6 tasks.
   - **Chemistry, Physics, Mathematics:** $0.0$\,pp difference across 31 tasks.
3. **Token Efficiency:** CBE generates **13.7% fewer output tokens** (10.36M vs. 12.01M tokens). Direct graph queries eliminate speculative exploratory script writing.
4. **Outcome Stochasticity:** Approximately 18–20% of tasks yield mixed verdicts across identical seeds, bounding single-run benchmark resolution: differences smaller than $\sim$5\,pp fall within stochastic noise.

**Core Insight:** *When the defect is a computation, structure finds it. When an ordinary bug sits under scientific prose, structure distracts.*

---

## Method Overview

```
[ Public reproduce.py ]
         │
         ▼
[ Dynamic Trace Observer ] ──► Identifies active source files
         │
         ▼
[ Static Multi-Language Extractor ]
   ├── Tree-sitter (Python AST: expressions, returns, condition chains)
   ├── Joern CPG (C / C++ / Fortran / Cython semantic boundaries)
   └── Public docstring & interface parser
         │
         ▼
[ Evidence Store ] ──► Indexed computation graphs & boundary signatures
         │
         ▼
[ Repair Agent Interface ]
   ├── find(query)    : Search symbols, docstrings, and expressions
   ├── inspect(target): Retrieve computation scopes, dependencies, boundaries
   └── note(text)     : Scratchpad for working hypotheses (non-gating)
```

- **Zero model calls during preparation:** Static extraction runs entirely offline in a median of 73\,s (out of the 1800\,s trial budget).
- **Matched baseline:** Both arms use DeepSeek V4.1 Flash, temperature 0, 1800\,s timeout, 8 CPUs, 16\,GiB RAM, identical prompt templates, and standard shell tools.
- **Strict isolation:** Verifier runs in a clean, separate container after repair completes. Private test suites are never visible during repair.

---

## Repository Structure

```
.
├── src/
│   └── scicontext/          # Core CBE implementation
│       ├── evidence.py      # Evidence packet schema & extraction
│       ├── language_frontends.py # Tree-sitter & native AST parsers
│       ├── scientific_graph.py   # Computation graph construction
│       ├── science_tools.py # find, inspect, note query endpoints
│       └── deepseek_agent.py# Repair loop & tool dispatch
├── configs/                 # Task splits, pilot configs, and model parameters
│   └── interactive-science.split.json # 30 dev / 89 locked task partition
├── scripts/                 # Execution, evaluation, and reproduction runners
│   ├── run_locked89_k3.sh   # Replicate locked-89 evaluation (k=3)
│   └── compare_dev_runs.py  # Receipt aggregation and statistics
├── tests/                   # Test suite (680+ tests)
├── pyproject.toml           # Project metadata and dependencies
├── uv.lock                  # Pinned dependency lockfile
├── README.md                # This document
└── REPRODUCTION.md          # Step-by-step reproduction instructions
```

---

## Quick Start & Reproduction

Detailed, step-by-step reproduction guidelines are in [REPRODUCTION.md](REPRODUCTION.md).

### 1. Environment Setup

Requirements: macOS or Linux, Python 3.12, [uv](https://docs.astral.sh/uv/), and Docker Desktop (8 CPUs, 16\,GiB RAM allocated).

```bash
# Clone the repository
git clone https://github.com/rajarshighoshal/computation-boundary-evidence.git
cd computation-boundary-evidence

# Install pinned dependencies
uv sync --python 3.12 --locked --extra test --extra runner

# Run test suite (680+ tests)
uv run --no-sync pytest -q
```

### 3. Run the Static Extractor (Zero Model Calls)

Verify that the evidence extraction pipeline operates correctly on the development split without issuing model calls:

```bash
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . \
  --config configs/extractor-validation-30.json \
  --output runs/extractor-validation-30 \
  --execute --extract-only
```

### 4. Paired Repair Trial

Execute a single paired trial (Task 009) comparing baseline and CBE under identical conditions:

```bash
export DEEPSEEK_API_KEY="your-api-key"
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . \
  --config configs/development-e2e-check.json \
  --output runs/development-e2e-check-v5 \
  --execute
```

---

## Evaluated Tasks (SWE-bench Science)

The dataset is partitioned into a **frozen split** (`configs/interactive-science.split.json`):

### Development Split (30 tasks)
Used during system development and sanity checking:
`001`, `002`, `004`, `005`, `006`, `008`, `009`, `010`, `014`, `016`, `019`, `024`, `025`, `027`, `028`, `045`, `051`, `058`, `061`, `070`, `073`, `076`, `077`, `078`, `080`, `091`, `099`, `104`, `114`, `119`.

### Locked Evaluation Split (89 tasks)
Evaluated with $k{=}3$ replicates (522 verified attempts) under frozen code:
`003`, `007`, `011`, `012`, `013`, `015`, `017`, `018`, `020`, `021`, `022`, `023`, `026`, `029`, `030`, `031`, `032`, `033`, `034`, `035`, `036`, `037`, `038`, `039`, `040`, `041`, `042`, `043`, `044`, `046`, `047`, `048`, `049`, `050`, `052`, `053`, `054`, `055`, `056`, `057`, `059`, `060`, `062`, `063`, `064`, `065`, `066`, `067`, `068`, `069`, `071`, `072`, `074`, `075`, `079`, `081`, `082`, `083`, `084`, `085`, `086`, `087`, `088`, `089`, `090`, `092`, `093`, `094`, `095`, `096`, `097`, `098`, `100`, `101`, `102`, `103`, `105`, `106`, `107`, `108`, `109`, `110`, `111`, `112`, `113`, `115`, `116`, `117`, `118`.

All task IDs correspond to the official SWE-bench Science release (commit `42e7e97`).

---

## AI & Tool Disclosure

In compliance with the TU Graz task guidelines:
- **Study Conceptualization & Architecture:** Conceived, designed, and directed by Rajarshi Ghoshal.
- **AI Coding Assistants:** Oh My Pi and ChatGPT (GPT-5.6 Sol Pro) assisted with harness scaffolding, test development, matplotlib figure styling, and prose editing.
- **Repair Model:** DeepSeek V4.1 Flash (`deepseek-chat`) served as the sole experimental model evaluated across both baseline and CBE arms.
- **Provenance:** All execution trajectories, prompt templates, tool call transcripts, diffs, and container logs are preserved in trial receipts.

---

## Citation & Contact

If you find this work relevant, please cite the accompanying report:

```bibtex
@article{ghoshal2026cbe,
  author    = {Rajarshi Ghoshal},
  title     = {Computation and Boundary Evidence for Scientific Software Repair},
  journal   = {PhD Research Task Report, Graz University of Technology},
  year      = {2026}
}
```

For questions regarding this submission, contact:
**Rajarshi Ghoshal** — `rajarshi.ghoshal1@gmail.com`
