# Workflow-localized scientific reading: findings

This approved development check kept model, effort, prompt, task selection and allowances matched
to v1. The method source is `a27cc93`; `084718b` adds only the approved control record/configuration.
No method changes occurred between calls. See the generated [before/after comparison](SCIENTIFIC_READING_V1_V2.md),
[execution/cost report](SCIENTIFIC_READING_V2.md), and [token audit](../results/scientific-reading-v2-token-audit.json).

## What changed in the context

| Task | Before | After |
| --- | --- | --- |
| SHTOOLS | Tensor meaning attached to header declarations and fixture arrays. | Meaning attached to the actual magnetic synthesis interfaces and parameters; a real pole-zero assignment receives a qualified scientific interpretation. |
| Osprey | Normalization and timing explanations attached to generated-driver objects. | Largely the same scientific insights attach to fitting/quantification interfaces, the target basis parameter and selected calibration assignments. |
| MACS | Interval and score interpretation concentrated on reproduction and PeakIO objects. | Meaning also attaches to the actual sparse-track/refinement interfaces, signal/candidate parameters, evidence accumulator and interval-intersection statement. |

These are substantive interpretations, not merely function-name paraphrases. The clearest body-level
examples are MACS's interval intersection and SHTOOLS's pole assignment. The MACS annotation distinguishes
positive half-open overlap from adjacency and interprets the middle-coordinate selection as clipping,
not interpolation. The SHTOOLS annotation distinguishes a source assignment of zero from a claim
that the physical Hessian must vanish at the pole.

## Source review and limitations

- SHTOOLS's frame/sign and reference-versus-observation-radius explanations match its public source
  and manuals. Two component annotations have imprecise line ranges: the cited file supports their
  formulas nearby, but not at exactly the stated lines. These annotations were not silently corrected.
- Osprey's OFF/SUM reference distinction and repeated timing conversion are supported. However,
  the scaling and timing-factor chains remain absent from the graph. The explanations use additional
  source reading while anchoring to interfaces/selected assignments. V2 also omits v1's useful caveat
  that the public reproduction substitutes fitting routines; “fits a Lorentzian” describes repository
  code, not demonstrated nonlinear fitting in the reproduction.
- MACS's coordinate, positive-support score, tie and placeholder-field descriptions match the public
  code. Some relationships are source-reference candidates rather than established argument/return
  flow. The interpretation does not demonstrate correct behavior for every valid interval arrangement.
- The overall handoff is still verbose: useful scientific text can appear after substantial generic
  structure. Readable annotations do not establish an efficiently readable whole repair prompt.

The criteria are therefore supported for improved implementation anchoring and the reviewed
scientific content, with remaining traceability/readability limitations. This is a usable research
prototype checkpoint, not comprehensive scientific reconstruction, state-of-the-art performance,
or evidence of improved repair. These tasks informed the revision and are not held-out evidence.

## Next scientific step

The next useful experiment is a bounded, matched repair comparison—not expanding the API catalogue
or waiting for complete reconstruction. No repair or further model attempts are authorized by this
check. Runtime dispatch remains unproved where the graph labels only a candidate source link.

Raw artifacts are in `runs/scientific-reading-v2/`; public sources are the same pinned originals
used in v1 (`.cache/public-workspaces/` and `runs/scientific-reading-v1/public-review/`). Review was
AI-assisted and targeted, not independent expert ground truth or exhaustive annotation validation.
