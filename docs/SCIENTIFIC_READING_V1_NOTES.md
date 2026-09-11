# Scientific-reading findings

These are development extraction checks, not repair experiments. The generated
[execution/cost report](SCIENTIFIC_READING_V1.md) and
[independent token audit](../results/scientific-reading-v1-token-audit.json) record the outcomes.
The evaluated implementation is `2aafb20`; the method was not changed between calls.

## What the reading recovered

- **SHTOOLS:** distinguishes the geocentric north-west-up tensor frame from the spherical vector
  frame; identifies the documented positive potential Hessian despite the negative-gradient
  magnetic-field convention; explains why zero trace does not establish complete tensor equivalence.
  These reviewed claims match the public tensor/vector manuals and study description.
- **Osprey:** identifies the different OFF versus SUM references supplied to macromolecule
  calibration, without inventing a universal conversion factor. It also identifies a repeated
  millisecond-to-second conversion across the quantification interface. Both reviewed claims match
  the public implementation; they are more specific than generic API explanations.
- **MACS:** distinguishes half-open genomic boundaries, absolute stored summits versus output
  offsets, and the quantitative peak-score field from significance/enrichment placeholders. The
  reviewed coordinate and positive-support score/tie descriptions match PeakIO and the closure
  helper. These are workflow-specific conventions, not universal biological requirements.

This is a targeted source review, not validation of every annotation. None of these observations
establishes that the representation improves repair or that a second LLM pass is necessary.

## What failed in the intended design

The graph does not adequately connect these interpretations to the relevant implementation bodies.
Osprey annotates reproduction objects, not its fitting/quantification functions. SHTOOLS annotates
fixture values and declaration-only synthesis interfaces, while the synthesis bodies are absent.
MACS includes PeakIO interfaces but misses the BedGraph refinement implementation. Relevant source
citations in the annotations are therefore often textual links supplied by the reader, not
code-derived computational relationships.

Saved packets explain the gap: language-balanced selection admits utility, GUI and support-library
files, and the global entry allowance is consumed before key scientific routines are indexed.
Cross-language/dynamic dispatch from the public reproduction is also not followed sufficiently.
Having access to the full workspace did not make the selected graph task-complete.

The next justified change is task-directed source/operation selection. More API rules or another
verification layer would not address this failure. No extractor change or further model attempt
was made after observing these outputs. A subsequent comparison needs a separately approved run.

## Evidence locations

Raw outputs, packets and graphs: `runs/scientific-reading-v1/jobs/`.
Cited public files copied from the same pinned environment images:
`runs/scientific-reading-v1/public-review/`.

- SHTOOLS: `051/source/src/fdoc/makemaggradgriddh.md`,
  `051/source/src/fdoc/makemaggriddh.md`, `051/paper.md`.
- Osprey: `025/source/fit/osp_fitMEGA.m`, `025/source/fit/osp_fitHERMES.m`,
  `025/source/libraries/FID-A/fitTools/fitModels/Osprey/osp_addDiffMMPeaks.m`,
  `025/source/quantify/OspreyQuantify.m`.
- MACS: `016/source/MACS3/Signal/BedGraph.py`, `016/source/MACS3/IO/PeakIO.py`.

Codex performed implementation and artifact analysis; read-only AI reviewers checked selected
SHTOOLS/Osprey claims against public sources. This review is AI-assisted, not independent expert
ground truth. Rajarshi has not yet approved a scientific interpretation or efficacy claim.
