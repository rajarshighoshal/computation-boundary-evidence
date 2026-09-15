# Fable extractor build spec (2026-09-11)

Third read-only consultation. Full buildable specification for the scientific-meaning extractor. Design principle: every new thing is an object in scientific-objects.json with a new kind, or a link with a new relation — the enrichment schema needs zero changes; loci are annotatable because they have IDs; the LLM still cannot create structure.

## 0. Coverage architecture (the top-level design statement)

The extractor is **two-tier by construction**:

- **Universal tier (floor):** the `/proc` observer + LD_PRELOAD shims operate below the language at the OS process/native-symbol boundary. Every scientific language — Fortran, MATLAB, Octave, R, C, C++, Python, Julia, Haskell, and MPI/threaded programs in any of them — is observed as processes with threads, CPU time, memory growth, file I/O patterns, malloc behavior, communication traffic, exit codes and artifacts. This tier never goes blind; it guarantees the method applies to the full breadth of scientific computing, compiled and parallel included.
- **Deep tier (graded depth):** the relation layer (repeated-call alignment → invariance/sensitivity/distinctness loci) currently operates at the Python frame level via sys.monitoring. Static source-span binding (tree-sitter frontends) exists for C/C++/Fortran/MATLAB/Cython; the long tail (Octave/R/Julia/Haskell) is process-level only until a grammar is wired.

Capability matrix (stated in the paper as-is): Python = full depth; C/C++/Fortran/MATLAB = process+tools + static spans, process-level relation evidence; long tail = universal tier only. Intra-binary call-level relations in compiled cores (perf/callgrind class) are declared future work — this is a paper-worthy limitation, not a hidden failure.

The HPC-flavored contribution claim follows directly: no LLM4SE repair representation offers language-agnostic reach through process-level observation, and the graded-depth fallback (deep where instruments exist, universal everywhere) is the honest scientific position.

## 1. Representation schema (extends the graph)

Three new object kinds (IDs via existing `_id(prefix, *parts)`):

- `state_quantity` — id `_id("st_", producer_transition_id, slot)`. Fields: symbol (return/argname/script_local_name/file:relpath), path/scope of producer, source_entry_ids (may be []), source_span, properties: dimensions/scale_to_si (existing), shape/dtype, fingerprint {t, exact, equiv, multiset, rev, struct, bytes, truncated}, stats {n, min, max, n_nan, n_inf, sum} | null, persistence transient|returned_to_script|written_to_file. Roles: observed_output | observed_input | script_observable | file_state.
- `transition_instance` — id `_id("tr_", relpath, qualname, ordinal)`. properties: func_key [relpath, qualname, co_firstlineno], ordinal, call_path, parent_transition_id, inputs {argname: st_id, self: st_id}, outputs {return: st_id}, exception, duration_ns, pid, tid, process_kind python_frame|child_process.
- `constraint_locus` — id `_id("cl_", constraint_type, func_key, rule_id)`. properties: constraint_type invariance|sensitivity|distinctness|containment|continuity|finiteness|completion; status violated|holds|undetermined; rule_id R1..R9; predicate_source script_declared|generic|process_observable; locus_transitions; static_candidates (R9 only); evidence {pairs: [{a,b,input_relation,output_relation,delta_param}], measures {...}, process {exit_code, expected_artifacts, missing_artifacts, stall}}; provenance {trace_run sha, script, image, baseline_tree, pythonhashseed, tracer_version}.

New link relations: observed_instance_of, consumes_state, produces_state, flows_into (value provenance via exact fingerprint), locus_of, evidence_for, script_compares, static_candidate_of.

Graph top-level: `dynamic` {trace_status, observer_summary, instances, pairs, loci}; coverage gains executed_signature_entries/total_signature_entries.

## 2. Modules

- `trace_runtime.py` — Python-frame workflow tracer. CPython sys.monitoring (PEP 669, low overhead) preferred over setprofile; PYTHONHASHSEED=0 set by wrapper (recorded; never seed numpy/random — nondeterminism is detected, R7). Filter frames to repo source. Call/return fingerprinting incl. self.__dict__ depth-1. Script observables = script module globals at exit. Script-declared predicates parsed from reproduce script AST (equality/inequality/bounds/closeness forms) and evaluated on script-frame line events only. Caps: ≤64 instances per func_key fingerprinted; 64 MiB per value; --seconds bound via existing timeout wrapper; partial JSONL valid. Output: trace.jsonl, script_predicates.json, observer.jsonl, run.json.
- `fingerprint.py` — canonical fingerprints: ndarray (shape,dtype,bytes sha) / equiv scale-free rounded / multiset sorted / rev reversed-axis0 / struct shape+dtype; dict key-agnostic multiset; scalars repr; objects via __dict__ depth≤2; opaque otherwise. struct = structural-isomorphism candidate (ints/float placeholders).
- `proc_observer.py` — pure-Python /proc sampler thread (200 ms): process tree (ppid map), per-pid VmRSS/VmHWM/Threads, per-tid utime/stime/comm, per-fd pos tracking; summary: max_rss, rss_slope, hot_threads (≥20% CPU), io_pattern sequential|random|mixed, stall detection (compute_stall/idle_hang), expected artifacts from script AST literals, missing_artifacts.
- `shims/` — precompiled x86_64 LD_PRELOAD: scitrace_malloc.c (~80 lines, dlsym RTLD_NEXT, __thread counters, destructor writes $SCITRACE_OUT/malloc.<pid>.<exe>.json, gated by SCITRACE_EXE basename); scitrace_mpi.c conditional (only if ldd of traced exe lists libmpi; void*-handle wrappers calling PMPI_*; log rank/count/tag). Build once with gcc -O2 -shared -fPIC in a glibc 2.31 container; attach via env only, task repo untouched; shim_status recorded; if not loadable continue.
- `dynamic_binding.py` — joins: (relpath, qualname) → static signature entries; arg/return → existing parameter/return objects; child process → native source tree (binary_to_tree level, coarse, labeled); accessed files → file_state quantities.
- `relations.py` — group instances by func_key; pairs n≤8; input_relation identical|equivalent|param_delta(name,va,vb)|reversed|relabeled|isomorphic_candidate|different; output_relation identical|equivalent|relabeled|reversed|different. declared_equivalent from script equality predicates (primary mechanism for 001); declared_distinct from != predicates. First-divergence descent for relabeled/reversed/declared_equivalent inputs with different outputs: deepest aligned child with related inputs and different output whose children all agree.

## 3. Loci rules (predeclared; only these create constraint_locus objects)

- R1 param_delta ∧ output identical → sensitivity violated; locus = deepest child consuming the delta value.
- R2 declared_equivalent|relabeled|reversed ∧ output different → invariance violated; first-divergence descent.
- R3 related inputs ∧ outputs agree → invariance holds (kept, ranked below violations).
- R4 different inputs ∧ identical outputs (≥2 pairs or declared_distinct) → distinctness violated (collapse).
- R5 finite inputs → produced state with nan/inf → finiteness violated.
- R6 script bounds predicate violated → containment violated; provenance chain via flows_into, top-3.
- R6′ closeness/equality on adjacent slices/periods violated → continuity violated (jump measured).
- R7 identical inputs ∧ different outputs → nondeterministic; suppresses R1–R4 for that func_key.
- R8 child process: exit≠0 | missing artifacts | wall timeout → completion violated; observer stall labels.
- R9 R8 fired ∧ static native entries → static_candidates: comparisons of length/distance/sqrt-derived quantity vs bare-float named constant (*PRECISION*|*EPS*|*TOL* ranked first); labeled heuristic.

Enrichment priority: constraint_locus 0, transition_instance 1, state_quantity 2 (in _OBJECT_KIND_PRIORITY). enrich_objects.md gains one paragraph: annotation on a cl_ ID means scientific requirement realized / not physical requirement / why required or legitimately broken. Schema untouched.

## 4. Offline eval protocol (five dev tasks)

Predeclare configs/loci-eval-v1.json before running (tasks, reproduce path, patch path, caps, rules). Fix-touched set F from verified-passing patches (001: best-known 1/3 patch, disclose prior exposure). Metrics: hit (level function|file|process), precision = |violated loci ∩ F| / |violated loci|, flip (apply patch in container, re-trace: violated → holds/disappears, no new same-type on F).

Expected: 009 R1 function-hit + flip yes; 001 R2 hit on ≥1 of the three signature functions, flip n/a (informative negative); 091 R6 hit + flip yes; 114 R6′ partial (file-level likely, function-level uncertain — scalar provenance excluded) flip likely; 058 R8 process-level certain + R9 heuristic 1/N, flip yes at process level.

Stop rules: H+4 — if 009 does not yield R1 on buggy tree and its disappearance on patched tree, stop the relation layer, ship honest framing. End of day 1 — fewer than 2 of {009,001,091} with function/file-level hit → drop shims polish, move to paper. Rule changes after seeing outcomes = new eval version, never pooled.

## 5. Repair handoff + pilot

Guide: constraint findings first (observations, not intent), ≤15-line executed-workflow block, ≤12 object annotations (loci neighbourhood), coverage. Keep graph-pointer discipline and file handoff. prompts/repair.md: one hedge + "Start by inspecting the source spans of the listed constraint findings; they describe what the current code does under the public reproducer, not what it should do."

Pilot (only if end-of-day-1 clears): configs/deepseek-five-loci-v1.json; tasks 091/058/009/114/001; counterbalanced order; 1 attempt/arm; DeepSeek-flash both arms; flexible budget; official verifier primary; secondary = guide utilization (tool calls touching locus spans; cl_ IDs cited), tokens; no retries; no pooling; disclose development exposure and 001 hidden exposure; counts only, no inference language.

## 6. Report (4 pages)

Title: Executable constraint structure for scientific bug localization: observing invariance, sensitivity and containment in public reproducers.
p1 problem/RQ (RQ1 offline primary: does executing the public reproducer under a task-agnostic tracer with predeclared rules place fix-touched functions among flagged loci? RQ2 secondary pilot) + contribution (code-owned state/transition/constraint records with execution evidence; traceability; testing-derived evidence from the task's own reproducer; offline localization + flip results + two negative findings).
p2 method: figure + ~8-line schema + compressed rule table + one real 009 locus record.
p3 results: per-task table (instances, pairs, loci, hit level, precision, flip, overhead) + pilot table if run.
p4 threats/limitations: single-execution evidence describes behavior not intent; relation layer needs repeated instances; scalar provenance excluded; compiled cores process-level only (function binding heuristic); overhead/caps truncation; reproducer quality; dev exposure incl. 001; n=5; no locked cohort. Future work: locked ≥8-task cohort, ≥2 attempts/arm, MPI shim, metamorphic replay, sampling-based native stacks. Disclose LLM tooling.

## 7. Riskiest assumption + first-4-hours validation

Assumption: reproducers exercise repo functions in repeated instances whose related inputs are visible at call boundaries (arg or self.__dict__). Validate in the pinned 009 image: (i) overhead ≤3× untraced; (ii) build_projection_wall instances captured with gain visible in args or self; (iii) returns byte-identical on buggy tree and differ after git apply of the verified patch. If (iii) fails, stop rule applies immediately.

## Build-stack directive (researcher, 2026-09-11)

The extractor implementation language is free. Do not rebuild observation primitives: use existing tools — CPython 3.12 sys.monitoring (PEP 669) for Python tracing; precompiled static strace (musl) if available and our C shims for native observation; image-native gdb/nm/objdump if present; C only where it is the natural tool (shims, proc sampler). Target: glue existing observation primitives into the representation pipeline; analysis stages stay Python (they integrate with the existing graph pipeline).
