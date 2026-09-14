# Scientific context for scientific-code repair

This project tests whether a compact, evidence-grounded scientific task model helps an otherwise
unchanged coding agent repair SWE-bench Science tasks under a matched total allowance.

The current implementation is **scientific interpretation 2.0**. Code supplies computations,
quantity identities, dependencies and conditions. One read-only LLM call explains their scientific
purpose, quantity roles and conventions with source citations. Code joins those interpretations
to its recorded relationships and delivers a short guide plus scientific-model.json.

Implementation and offline delivery checks are complete for this revision. **Automatic scientific
interpretation quality and repair improvement have not yet been evaluated for 2.0.** Historical
runs do not evaluate this method. See [the method](docs/METHOD.md),
[the input/output contract](docs/OBJECT_ENRICHMENT.md), and the current [ledger](WORK_LOG.md).

## Pipeline

Public task/code/docs → existing source and Joern analysis → shared computation/entity/source
index → one source-cited scientific interpretation → connected model and guide → ordinary repair.

The representation retains source/analyzer namespaces and unknown bindings. It does not infer
scientific equivalence from similar names, treat observations as physical requirements, or allow
the interpreter to invent program edges. Existing API rules are not being expanded into a physics
catalogue. No compiler-IR pipeline or additional repair-agent framework is introduced.

The actual repair prompt contains the guide once. The connected model, code graph, public-source
records and selected analyzer evidence remain durable files under /opt/scicontext/context/.
Missing scientific context is recorded as failed delivery; it does not silently launch an
unassisted repair labelled as science.

## Install and verify

Python 3.12 and uv are required. Docker with linux/amd64 support is required for benchmark runs.
Joern/fortls are optional analysis capabilities whose availability and omissions are recorded.

```bash
uv sync --python 3.12 --locked --extra test --extra runner
uv run --no-sync pytest -q
```

Inspect public source without executing candidate code or calling a model:

```bash
uv run --no-sync scicontext scientific-objects \
  --root /path/to/public/task --context-root /path/to/context \
  --output /tmp/scientific-objects.json --llm-input /tmp/scientific-reading-input.json
```

The context directory contains task_statement.md. This standalone command uses the source
extractor; Joern augmentation is part of the full agent preparation path.

Join a saved interpretation using the same offline assembly helper:

```bash
uv run --no-sync scicontext assemble-objects \
  --graph /tmp/scientific-objects.json --context-input /tmp/scientific-reading-input.json \
  --annotations /path/to/model-response.json --output /tmp/scientific-bundle.json
```

Unit/integration checks cover source citations, scoped identity, unknown inputs/outputs,
condition preservation, both provider output paths, actual file collection and prompt delivery.
The [five-input compatibility receipt](results/connected-science-review-2026-09-14.json) includes
a manually authored cube-reader interpretation fixture. It tests joining/rendering, not automatic
scientific understanding. The [selected-export receipt](results/selected-export-review-2026-09-14.json)
covers two real CPGs and Python/C++/JavaScript fixtures.

## Experiments

Use an explicit configuration, predeclared task IDs and a fresh output directory. Dry-run scheduling
does not call a model:

```bash
uv run --no-sync scicontext pilot --config /path/to/approved-config.json \
  --extract-only --output /path/to/new-run
```

Adding --execute launches the configured workflow and requires approval of tasks, attempts and
budget. Current configuration files include historical experiments; do not assume a filename
denotes the latest evaluated method. The original five development tasks are
091, 058, 009, 114 and 001. They are not an untouched evaluation set.

Codex uses the standard subscription-authenticated CLI route; DeepSeek uses its configured API
route. One scientific interpretation call is used, without probe/refinement loops. Host code,
guest helpers and prompts are frozen together. Extraction, transfer and cleanup count against
the science arm's total allowance. Model, effort, source revision, images, prompts and task
selection belong in each run's receipts.

Keep credentials outside Git, images and public artifacts. Standard Codex container authentication
is not isolation from hostile candidate code. Do not mount personal home directories or the Docker
socket into task containers.

## Results and records

```bash
uv run --no-sync scicontext summarize /path/to/run/jobs --output /path/to/summary
uv run --no-sync python scripts/report_scientific_reading.py \
  --run-root /path/to/extraction-run --json-output /path/to/results.json \
  --markdown-output /path/to/results.md
```

Preserve trajectories, patches, verifier outputs, failed attempts, source evidence and exact task
IDs. Do not pool method revisions or reinterpret broken delivery as a clean test of the research
hypothesis. Verifier success is the eventual primary repair outcome; tokens, time and failure
mechanisms are also required.

Source code is in src/scicontext/, tests in tests/, prompts/configs in their named directories,
and compact receipts in results/. Large raw artifacts stay under ignored runs/, data/ and .cache/.
WORK_LOG.md is the only live milestone ledger. Historical designs/results remain in Git and
docs/archive/; [AI disclosure](docs/AI_DISCLOSURE.md) must accompany the final research submission.
