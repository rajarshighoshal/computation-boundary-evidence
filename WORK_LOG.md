# Current work

## User's clarified target
Preparation must construct a connected, task-relevant graph before the first repair-model call:
public workflow -> implementation computations -> quantities/dependencies/conditions, with public
scientific documentation and data/interface evidence attached. A file inventory or disconnected
outputs collected into JSON do not satisfy this. Use existing multilingual analyzers; persist the
graph and expose compact connected queries that can expand it. Scientific meaning must explain
the computation, conventions, required change and behaviour to preserve. A specialist semantic
model was discussed but has not been selected, implemented or validated.

## Current scope
- [verified] Independent read-only review throughbfb70ee: preparation andgraph-IDsearch genuinely
  work;009has20nodes/59edges,17nodeswithparsedcomputations;563tests pass. Remaining blockers:
  failedCMake in058becomesR6script-declaredcontainment;defaultnodeinspectmarksunshownsourceIDsread;
  on-demandC++backendrequestisnested,soJoernisnotinvokedandgraphisnotexpanded;preparedpayloads
  canmixold/freshsourceafteredits;totalconstructionfailurecancontinueasindex-onlyscience.
  058packetcontains203C++entriesbutrepresentationselectiondropsall;all20graphnodeslacksourceIDs.
  Cuttracecallsarenotallretainedasboundaryrefs(009:13outgoingcutpairs,9withouttargetreferences);
  internaledgesconsume5-boundarycap. Scope normalizationalso mergesleft::Solver::step/right::Solver::step
  inonefile. No fixes/modelcalls/Dockerchanges. Do not launchpaidcomparisonfromthisreview.
- [verified] Prepared connected graph implemented on the existing extraction machinery (9b01692,
  d9e6e4c): preparation runs trace -> packet -> merge-dynamic before any model call, then filters
  the merged graph to one node per observed function or finding site with real dependency edges,
  boundary references and every violated locus. find returns node IDs; inspect '#graph' lists
  nodes; node inspect registers citable entity/source IDs; record_model joins the same prepared
  representation. Nodes without a parsed region compile their public location on demand. 563
  tests pass, including fixture tests that prepare, query and record a model with no model call.
- [verified] Prompt pass: prompts/scientific_repair.md rewritten graph-first and short; unused
  prompts/repair.md removed.
- [verified] No-model container preflights (extraction-only, zero model calls): public 009
  (configs/graph-preflight-009.json, runs/graph-preflight-009) prepared_graph 20 nodes / 59
  edges / 6 findings, and the exported store answers '#graph', find, node inspect and
  record_model; public 058 C++ (configs/graph-preflight-058.json, runs/graph-preflight-058)
  prepared_graph 20 nodes / 1 finding anchored to R6 candidate paths, with call evidence absent
  because the trace only observes the Python driver.
- [verified] Specialist comparison at docs/SPECIALIST_EXTRACTOR_COMPARISON.md; GLiNER2.5 is an
  auxiliary candidate, not a demonstrated improvement over DeepSeek V4.1 Flash.
- [verified] Stop the index-first pilot at the user's request. No further trials or paid calls.
- [verified] Review fixes in 1194944: runner/build failures are no longer labelled scientific
  violations (R6 only for the reproducer's own failed check; runner_failure/post_fix_success are
  recorded as reproduction status); node inspection shows the sources and entity/quantity
  references it registers, pages them, and refuses citations to unseen content; cut calls stay as
  boundary references; on-demand node compilation persists compiled evidence on the node and
  hoists the analyzer request so Joern actually runs and the graph expands; packet-selected
  sources are admitted into the reading selection so the 058 graph grounds 19/20 nodes (was
  0/20); namespace scopes keep their block offsets; prepared evidence whose file changed on disk
  is refused at record_model; prepare refuses index-only science. 572 tests pass.
- [verified] No-model container preflights on 1194944 (extraction-only, zero model calls, stores
  exported): 009 prepared_graph 20 nodes / 59 edges / 6 findings, reproduction classified
  scientific_failure (projection_control_response_collapsed), 18/20 nodes grounded; 058 OpenMC
  prepared_graph 20 nodes / 5 edges / 0 findings with reproduction runner_failure (CMake
  configuration), 20/20 nodes grounded, 57 compiled computations and 9 citable computation IDs
  (was 1 computation / 0 grounded nodes). Exported stores answer '#graph', find, node inspect
  (showing exactly the registered sources), and record_model with file-level version checks.
- [next] Review graph content on 091/114/001 and (with approval) relaunch the frozen five-task
  paired pilot; no method edits during live trials.

Final check: inspect the saved connected implementation/dependency graph before any model call,
then verify queries return and expand that same representation. This is not itself evidence of
scientific correctness or improved repair.

## Verified checkpoint and preserved evidence
Current code is bfb70ee. Latest graph evidence: runs/graph-preflight-009 (receipt + exported
store). The stopped pilot used d1e21ff (index-first, no prepared graph); its 091 science 0/3 vs
baseline 3/3 and the interrupted 058/009 attempts remain preserved there. 551 tests passed before
that pilot; 563 now, including the prepared-graph paths. Prior no-model integration receipts:
runs/interactive-container-check/receipt.json and runs/interactive-backend-check/integration-receipt.json.

## Boundaries
One writer; independent reviewers read-only. Preserve historical runs and unrelated files. No
automatic rewrite, new model selection, paid experiment or report/submission pivot. Rajarshi owns
scientific decisions. Keep changes small; do not substitute index/search/planning gates for the
requested representation. Frozen 30/89 split remains in configs/interactive-science.split.json;
license gates and prior exposure metadata remain. Forty rolling slots are the eventual target, not
validated 40-heavy-task capacity on this laptop (Docker 8 CPUs/~9GiB). No cloud rental/full-test
launch authorization.
