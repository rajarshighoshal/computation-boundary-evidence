# Reproduction Guide

This guide provides step-by-step instructions to verify the static evidence extractor, execute repair trials, and reproduce the evaluation results on SWE-bench Science.

---

## 1. System Requirements

- **Operating System:** macOS (Apple Silicon / Intel) or Linux (x86_64 / aarch64)
- **Python:** 3.12+
- **Package Manager:** [uv](https://docs.astral.sh/uv/)
- **Container Engine:** Docker Desktop or Docker Engine (8 CPUs, 16\,GiB RAM allocated)
- **API Key:** `DEEPSEEK_API_KEY` (required for model repair trials; not required for static extraction)

---

## 2. Environment Setup

Clone the repository and install all dependencies using the pinned lockfile:

```bash
git clone https://github.com/rajarshighoshal/computation-boundary-evidence.git
cd computation-boundary-evidence

# Install dependencies in isolated virtualenv
uv sync --python 3.12 --locked --extra test --extra runner

# Verify test suite
uv run --no-sync pytest -q
```

---

## 3. Materializing Benchmark Task Environments

SWE-bench Science task environments are pulled and built via Docker. To restore specific task source repositories from the official release (commit `42e7e97`):

```bash
# Restore sample development tasks
uv run --no-sync python scripts/restore_release.py --workspace . --task-id 001,002,058

# For restricted-license tasks, add the opt-in flag:
uv run --no-sync python scripts/restore_release.py --workspace . --task-id 001 --allow-restricted-licenses
```

---

## 4. Static Evidence Extractor (Zero Model Invocations)

The extraction pipeline runs entirely offline using Tree-sitter and native parsers. To execute extraction across the 30 development tasks:

```bash
SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . \
  --config configs/extractor-validation-30.json \
  --output runs/extractor-validation-30 \
  --execute --extract-only
```

To view the generated extraction summary report:

```bash
uv run --no-sync python scripts/extractor_report.py runs/extractor-validation-30
```

Extracted evidence packets and dependency graphs are stored under `runs/extractor-validation-30/jobs/*/agent/science/`.

---

## 5. Running a Paired Repair Trial

To run a single paired repair attempt (Baseline vs. CBE under identical seed, prompt, and container conditions):

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"

SCICONSORT_RESTRICTED_OPTIN=1 uv run --no-sync scicontext pilot \
  --workspace . \
  --config configs/development-e2e-check.json \
  --output runs/development-e2e-check-v5 \
  --execute
```

Each arm runs in an isolated Docker container with an 1800\,s wall-clock timeout. After the repair phase terminates, the official SWE-bench Science verifier evaluates the generated git patch in a clean container against private test assertions.

Results and verifier rewards (`reward.json`) are logged under `runs/development-e2e-check-v5/jobs/*/verifier/`.

---

## 6. Running the Full Evaluation (Locked-89, $k{=}3$)

To execute the locked evaluation benchmark across all 89 held-out tasks with 3 repeated runs:

```bash
export DEEPSEEK_API_KEY="your-deepseek-api-key"

# Executes the evaluation workload across tasks and replicates
bash scripts/run_locked89_k3.sh
```

---

## 7. Task Partition Reference

Task partitions are defined in `configs/interactive-science.split.json`:

- **Development Tasks (30):**  
  `001`, `002`, `004`, `005`, `006`, `008`, `009`, `010`, `014`, `016`, `019`, `024`, `025`, `027`, `028`, `045`, `051`, `058`, `061`, `070`, `073`, `076`, `077`, `078`, `080`, `091`, `099`, `104`, `114`, `119`.

- **Locked Evaluation Tasks (89):**  
  `003`, `007`, `011`, `012`, `013`, `015`, `017`, `018`, `020`, `021`, `022`, `023`, `026`, `029`, `030`, `031`, `032`, `033`, `034`, `035`, `036`, `037`, `038`, `039`, `040`, `041`, `042`, `043`, `044`, `046`, `047`, `048`, `049`, `050`, `052`, `053`, `054`, `055`, `056`, `057`, `059`, `060`, `062`, `063`, `064`, `065`, `066`, `067`, `068`, `069`, `071`, `072`, `074`, `075`, `079`, `081`, `082`, `083`, `084`, `085`, `086`, `087`, `088`, `089`, `090`, `092`, `093`, `094`, `095`, `096`, `097`, `098`, `100`, `101`, `102`, `103`, `105`, `106`, `107`, `108`, `109`, `110`, `111`, `112`, `113`, `115`, `116`, `117`, `118`.
