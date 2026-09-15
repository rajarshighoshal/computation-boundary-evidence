# Specialist extraction models for scientific-code repair

There is no verified winner over DeepSeek V4.1 Flash for extracting the scientific meaning needed
by this project. Small specialists can contribute useful, source-linked facts, but the reviewed
evidence does not establish a replacement for general scientific interpretation. GLiNER2.5 is the
most practical *auxiliary candidate to test*, not an established quality improvement.

## What must be extracted

The target is a compact task model connecting implemented quantities and computations to their
scientific roles, conventions, conditions and intended behaviour. Three different capabilities
must be distinguished:

- Retrieving a relevant document or passage.
- Extracting a documented fact, such as a symbol's definition or a quantity's unit.
- Establishing that this fact applies to a particular code quantity, invocation or output frame.

The last capability is not supplied merely by entity recognition or text similarity. A structural
graph must already identify the code quantities and their relationships; text-extraction candidates
then need evidence-backed correspondence to those identities. Natural-language multilingual support
does not provide Python/C++/Fortran/MATLAB program analysis.

## Comparison

| Candidate | What it actually supplies | Availability and fit | Principal failure condition |
|---|---|---|---|
| **GLiNER2.5** | Schema-conditioned entity spans, records and relations. | Public 74M/194M/287M checkpoints; Apache-2.0. The 194M English model is a practical candidate for proposed definition/unit/condition records. Those scientific labels are an application schema, not validated scientific capabilities. [Model card](https://huggingface.co/fastino/gliner2.5-base-v1) | Wrong relation or omitted qualifier; no automatic correspondence to code identities. |
| **TaDDEx / SymDef** | Targeted mathematical-symbol-to-definition extraction. | A genuinely specialized scientific-definition model based on RoBERTa-large. Needs identified target symbols; its definition task excludes equations, assigned values and descriptions of how a symbol is computed. [Paper](https://arxiv.org/html/2305.14660v1) | Scientific meaning is implicit, crosses sentences, or depends on a computation rather than an explicit definition. |
| **NuExtract3** | Generative JSON extraction from text/images using a template; also document conversion. | Public Apache-2.0, Qwen3.5-4B-based model; Hub metadata reports approximately 5B total parameters. It is a specialized generative language/vision model, not a non-LLM alternative. [Model card](https://huggingface.co/numind/NuExtract3) | Plausible but incorrect fields or interpretations; much heavier than an encoder; no demonstrated scientific code-alignment capability. |
| **GLiREL** | Requested relations between supplied entity spans. | Public 467M model; checkpoint license CC BY-NC-SA 4.0. Requires entity extraction and careful span conversion. Its extra component is not automatically justified when GLiNER2.5 already offers relations. [Repository](https://github.com/jackboyla/GLiREL), [checkpoint](https://huggingface.co/jackboyla/glirel-large-v0) | Incorrect/missing entity endpoints; relation label does not preserve scientific scope or conditions. |
| **SKEMA text reading / Odin** | Existing linguistic rules extract scientific variables, descriptions, values and related mentions. | Closely relevant reusable extraction logic, but a Scala/Processors/Odin component, not a small pretrained scientific-understanding model. [Pinned component README](https://github.com/ml4ai/skema/blob/fe8f41f704e8802a6d1d30cc7107062d338489b0/skema/text_reading/scala/README.md) | Uncovered wording; broad application can generate many false positives; extraction still needs code correspondence. |
| **SciBERT + DyGIE++ / PURE / SciREX** | Trained scholarly entity/relation systems, often with fixed task/method/material labels. | SciBERT alone is an encoder. Task-specific systems have public code, but legacy dependencies and schemas poorly matched to arbitrary units, conditions and program quantities. [SciBERT](https://github.com/allenai/scibert), [DyGIE++](https://github.com/dwadden/dygiepp), [PURE](https://github.com/princeton-nlp/PURE), [SciREX](https://github.com/allenai/SciREX) | The desired scientific relation is outside the trained label set; changing it requires adaptation and suitable labels. |
| **SPECTER2** | Scholarly document/query embeddings for similarity, retrieval and related tasks. | Useful retrieval research, not a source of variable definitions or scientific relationships. It does not emit the desired task graph. [Official model card](https://huggingface.co/allenai/specter2) | Mistaking document similarity for shared scientific identity or an applicable requirement. |

## What the comparisons against LLMs actually establish

**GLiNER2 is not GLiNER2.5.** The 2025 paper evaluates the older 205M model. On CrossNER's Science
entity-recognition category it reports F1 0.547 versus GPT-4o's 0.518; overall CrossNER F1 is 0.590
versus 0.599. Hierarchical extraction was not evaluated. This is neither a DeepSeek comparison nor
a test of scientific requirements, mathematical relationships or code alignment. The inspected
2.5 release does not supply equivalent direct evidence for this project's task. [GLiNER2 paper,
Sections 3.1–3.3](https://arxiv.org/html/2507.18546v1)

**TaDDEx demonstrates a narrow specialist advantage.** Its definition-label F1 is 73.56 versus
37.22 for few-shot `text-davinci-003`. Its headline macro F1 includes the outside/non-definition
label and should not be read as end-to-end scientific understanding. The trained specialist uses
known/masked symbol targets; the comparator is GPT-3-era, not a current frontier model. The result
does not establish transfer from the selected ML papers to scientific repositories. [TaDDEx,
Table 3 and Sections 5–6](https://arxiv.org/html/2305.14660v1)

**The closest variable-extraction study supports complementarity, not specialist supremacy.**
SciVar reports 22 pandemic-modelling papers and 556 excerpts already containing annotations.
These are not arbitrary scientific passages. Token-level F1 is 0.437 for rules, 0.600 for
GPT-4o-mini and 0.640 for that model with rule-extracted candidates. With full articles, the rule
system's reported F1 falls to 0.172. These are literature-extraction results, not repair results;
gains are not universal across models/metrics. Its GitHub README says 20 papers, so the release
would need reconciliation before reuse. [SciVar paper](https://arxiv.org/html/2411.14569v1),
[released dataset](https://github.com/mitdbg/scivar)

**GLiREL's strong relation scores have additional conditions.** Its reported wins over GPT-4o on
Wiki-ZSL/FewRel involve supplied entities and training on each dataset's non-held-out relations.
They are not an off-the-shelf scientific-document or scientific-code test. [GLiREL paper,
Sections 4–5](https://arxiv.org/html/2501.03172v1)

**NuExtract3 has relevant vendor evidence, but not the required comparison.** Its model card reports
results on an internal collection of roughly 600 diverse documents, with structured-output scoring
and small-model baselines. That does not establish better scientific interpretation than DeepSeek
V4.1 Flash. [NuExtract3 benchmark description](https://huggingface.co/numind/NuExtract3)

## Practical costs and integration limits

The following effort ranges are planning estimates, not measured setup times. They cover a thin
adapter and a smoke check, not scientific evaluation or full integration. Local weights avoid
per-token API billing, but runtime, memory and engineering effort remain costs.

| Route | Near-term effort estimate | Verified constraints |
|---|---|---|
| GLiNER2.5 | Roughly 1–2 engineering hours if installation works. | Base weights about 774 MB; Python >=3.10, CPU/CUDA/MPS documented. Use `AutoExtractor`, not the incompatible legacy loader shown in an autogenerated snippet. [Files](https://huggingface.co/fastino/gliner2.5-base-v1/tree/main), [loading instructions](https://huggingface.co/fastino/gliner2.5-base-v1) |
| NuExtract3 | Several hours; more runtime/memory integration risk. | Official quantized/MLX variants exist; actual Mac performance is unmeasured. [Model collection](https://huggingface.co/collections/numind/nuextract3) |
| GLiREL | Another roughly 1–2 hours for entity/token-span handling. | Approximately 1.87 GB checkpoint; configured length 512, including labels. [Files](https://huggingface.co/jackboyla/glirel-large-v0/tree/main), [configuration](https://huggingface.co/jackboyla/glirel-large-v0/blob/main/glirel_config.json) |
| TaDDEx | Not a quick ready-checkpoint integration. | Public instructions require training; no ready trained checkpoint or clear repository redistribution license was verified. README estimates 3–5 training hours, apart from setup; the paper used an RTX A6000. [Repository](https://github.com/minnesotanlp/taddex), [paper Appendix D](https://arxiv.org/html/2305.14660v1) |
| SKEMA/Odin | High/uncertain; could consume much of the available day. | Scala 2.12.17, Processors release-candidate dependencies and domain-model artifacts; installation notes reference Java 8 and older macOS. Runtime compatibility has not been tested. [Pinned build](https://github.com/ml4ai/skema/blob/fe8f41f704e8802a6d1d30cc7107062d338489b0/skema/text_reading/scala/build.sbt) |
| Legacy SciBERT IE systems | Do not schedule as a dependency of the immediate milestone. | DyGIE++ maintainers explicitly flag broken installation after AllenNLP archival; other systems also document old environments. This is a repository-reproduction issue, not proof that their underlying encoders cannot run today. [DyGIE++ installation notice](https://github.com/dwadden/dygiepp) |

GLiNER2.5's base configuration has a finite 4096-token encoded window. Long-document utilities do
not create relations across separate chunks automatically. Its joint-IE API can constrain endpoint
types, but that does not establish scientific entailment or document-wide identity. [Configuration](https://huggingface.co/fastino/gliner2.5-base-v1/blob/main/config.json),
[long-context documentation](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/12-long_context.md),
[joint extraction](https://github.com/fastino-ai/GLiNER2/blob/main/tutorial/15-joint_ie.md)

AutoMATES and SKEMA remain important architectural precedents for connecting text, equations and
software. They are not evidence that a complete universal semantic extractor can simply be loaded:
AutoMATES explicitly labels its motivating richly connected example as hand-crafted and
aspirational. [AutoMATES project](https://ml4ai.github.io/automates/)

## Decision for this project

Keep DeepSeek Flash as the quality baseline. Do not replace it merely because a smaller model is
specialized or can emit structured output. The hypothesis worth checking is narrower: a specialist
could provide additional explicit, source-linked facts that improve the repair agent's use of the
prepared code graph.

GLiNER2.5 is the first practical auxiliary candidate; TaDDEx is the closest targeted-definition
research reference; NuExtract3 is an alternative if a dedicated generative document extractor is
desired. None has been selected for implementation. No candidate was downloaded, installed or run
for this comparison; availability checks and published scores are not local benchmark results.

The useful interface would preserve source spans for proposed symbol-definition, quantity-unit and
convention/condition records. Code-derived identities supply candidate connections to program
quantities. Ambiguous alignments stay alternatives, and conditions remain attached to the facts
they qualify. A naming match is not enough to assert a scientific identity.

A later controlled extraction comparison should use the same passages and output fields for the
specialist, DeepSeek and their combination. Include explicit definitions, multi-symbol definitions,
negation/conditions, repeated names with different meanings, and passages with no relevant fact.
Measure precision, recall, qualifier retention, code-link correctness, latency and total resource
cost separately. Those checks can decide whether the specialist adds value; published NER scores
cannot answer the repair research question.

Source versions: public repositories/model cards inspected on 14 September 2026; SKEMA at
fe8f41f704e8802a6d1d30cc7107062d338489b0; TaDDEx 2305.14660v1, SciVar 2411.14569v1,
GLiNER2 2507.18546v1 and GLiREL 2501.03172v1. No direct DeepSeek V4.1 Flash comparison was found
in the inspected evidence. Comparative recommendations above are explicitly engineering judgments.
