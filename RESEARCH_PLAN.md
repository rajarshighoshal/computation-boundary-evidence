# Scientific understanding as context for repair

## Objective and hypothesis

Build a hybrid representation that helps a repair agent understand the scientific computation:
what its objects mean, how code and interfaces realise that meaning, and which assumptions and
conventions matter. The hypothesis is that making this working model explicit improves scientific
bug repair under a matched overall budget. The target is SWE-bench Science as a whole; small samples
are development checks, not a substitute for the eventual benchmark evaluation.

## Method

1. Code extracts source-backed computational objects, operations, interfaces and dependencies.
   Documented scientific APIs add supported roles, unit metadata and contract discrepancies.
   Unrecognised custom computation remains visible with unknown scientific semantics.
2. A scientific-reading LLM receives this representation together with the public task, scientific
   passages and relevant code/interface excerpts. It connects domain meaning to the actual objects.
3. The LLM returns only anchored meanings, conventions and assumptions. Code joins these onto
   existing object IDs without replacing structural facts or turning hypotheses into repair rules.
4. A fresh repair session receives the scientific working model and the original task/code.
   The benchmark's official verifier evaluates the patch independently.

Probes can support later investigation, but are not the representation or the required output.
See `docs/OBJECT_ENRICHMENT.md` for the current interface and `docs/METHOD.md` for mechanisms and limits.

## Current implementation and remaining work

The Python path has code-first extraction, conservative wrapper-body links, unit analysis using
Pint, source-context input, anchored enrichment and an existing-runner integration. Native parser
frontends now feed source/interface/expression evidence into the same representation; their
scientific semantics remain unknown until interpreted. Offline fixtures and model doubles test
mechanisms; they do not establish autonomous scientific interpretation.

Approved live extraction-only checks now exist for SHTOOLS, Osprey and MACS; see
`docs/SCIENTIFIC_READING_V1.md` and `_NOTES.md`. They recovered substantive documented scientific
meaning, but the graph often missed the corresponding implementation bodies. Next is task-directed
source/operation selection, followed by a separately approved check. Do not expand the
API rule catalogue merely to make demonstrations look complete. Unsupported structure and missing
scientific definitions must remain explicit. Having a parser for a language is not whole-repository
coverage, and neither parser coverage nor annotation validity establishes scientific understanding.

## Evaluation

- Ordinary Codex versus the same model/harness receiving the hybrid scientific representation.
- Same public task access, model effort, tools and total allowance. Record extraction overhead.
- Retain the existing Astra/medium, total1800s/extraction360s settings unless Rajarshi changes them.
  New runs still need explicit task/attempt/budget approval; subscription route, no API billing fallback.
- Freeze the evaluation selection and language/license handling before observing outcomes.
  Full-benchmark execution remains the target; restricted-license tasks need explicit opt-in.
- Primary measure: official repair success. Also report paired outcomes, time, input/cached/output/
  reasoning tokens, missing costs, scientific-interpretation errors and representation coverage.
- API recognition rate is a diagnostic, not a scientific-quality score. Passing local tests or
  constructing a valid graph does not demonstrate useful understanding.
- Keep all failed/interrupted runs. Earlier development comparisons are separate and must not be
  presented as results of this new method. No unsupported significance or component-causality claims.

## Working boundary

One–two-day implementation window is the current planning assumption, not a promise that a full
benchmark run finishes in that time. Prioritise scientific meaning and its code connection over
new infrastructure. Root writes in the main checkout; reviewers remain read-only until Rajarshi
requests a handoff. Current work and its final check live only in `WORK_LOG.md`.

Submission requirements and authoritative sources remain in `AGENTS.md` and the assignment PDF.
