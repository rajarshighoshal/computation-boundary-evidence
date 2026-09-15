# Fable core-extractor design consultation (2026-09-11)

Second read-only consultation. Evidence: WORK_LOG.md, prior review docs, the five instruction.md files, the actual reproduce.py/workflow bodies for all five tasks, and the verified-passing patches for 091/058/009/114.

## The decisive observation

The five public reproduce scripts are not smoke tests — each is a scientific-property check on computed quantities, and each names the property in code:

| Task | What reproduce.py asserts | Coupling involved |
|---|---|---|
| 001 autochem | rotor signature identical over 4 presentations of one TS (identity, relabelings, reverse) + negative control | invariance under permutation/reversal |
| 009 DESC | projection_a != projection_b and != scaled mode | parameter sensitivity, mode distinctness |
| 114 PyPSA | energy series continuous across the period boundary | state continuity at a boundary condition |
| 091 pymatgen | fractional coords in [0,1) | frame consistency between two quantities |
| 058 OpenMC | transport completes with a statepoint | finiteness; C++ scale-dependent absolute tolerance |

So the genuine scientific content that exists in these repos, independent of domain vocabulary, is: which computed quantities must be invariant/equivariant/sensitive/continuous/contained/finite under which transformations of their inputs, and where that requirement is realized or broken. A call graph does not know this; execution does.

## What code can establish vs what needs the LLM

Code can (with evidence): quantity identity/flow via workflow tracing with fingerprints; relations between repeated call instances (identical / relabeled / param_delta / reversed inputs; identical / equivalent / different outputs); predicates on workflow observables (finiteness, containment, boundary jump, non-degenerate response); unit-conversion edges from physical constants.

LLM only: which invariances are physically required vs legitimately broken; paper-to-symbol mapping beyond numeric coincidences; anything in compiled cores not exposed to Python (058's lattice.cpp).

## Recommendation: Option 1 — differential workflow trace

Representation: quantity-flow graph from one execution of the public reproduce script + a relation layer over repeated call instances yielding invariance-break / insensitivity / collapse loci with execution evidence.

Mechanism: trace the public reproduce script in the pinned image (sys.setprofile on source/ frames); canonical fingerprints (shape, dtype, byte hash); align call instances by call path; relabeling detection via key-agnostic canonical forms.

Why it is scientific, not relabeling: outputs like "build_projection_wall returns byte-identical arrays for projection_gain in {0.15, 0.55}" are facts about the computed physics that no static structure carries. Option 1 authors NO new tests — it observes the public workflow; the LLM only annotates locus IDs. This is the clean separation from the rejected LLM-authored probes.

Failure modes: single-call workflows (091/114/058) yield no relation layer — only predicates; 058's locus is in C++ behind a subprocess; fingerprint cost needs caps; stochastic codes need fixed seeds.

Offline falsifiable check on the five dev tasks: (a) flagged loci contain functions touched by the verified-passing patches (expected hits 009/001/091, partial 114, declared miss 058); (b) precision = flagged / traced; (c) apply the passing patch and re-trace — the workflow-level property must flip.

Alternatives: Option 2 predeclared metamorphic replay (scale/translate/permute/reverse catalogue) — only if Option 1 lands on day 1. Option 3 static dimensional/tolerance lattice (bohr_to_angstrom edge; length-vs-constant comparison in lattice.cpp) — cheapest, labeled heuristic, only deterministic route into 058.

## Stop rule

If by end of day 1 the tracer produces a non-empty relation layer on fewer than two tasks (009 and 001 are the ones that must work), stop and ship the honest framing: workflow localization + anchored annotation + the two negative findings, with the execution-derived relation layer as designed-and-specified future work.

## Paper scope (5 days)

Days 1-2: Option 1 + offline check. Day 3: paper (contribution: code-owned quantity-flow representation with execution-derived relation layer; anchored enrichment contract; offline localization/flip results; two negative findings). Day 4: clean reproduction. Day 5: submit. Future work: locked >=8-task unrestricted cohort, >=2 attempts/arm, same model, treatment = Option 1 loci.
