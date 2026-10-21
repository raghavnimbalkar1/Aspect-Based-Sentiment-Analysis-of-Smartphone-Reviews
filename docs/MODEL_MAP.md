# Which model does what?

The application has **three method families**. It also retains earlier versions and two TF-IDF training profiles. Those versions are not six separately trained neural networks.

| Method | Role | Aspect detection | Sentiment | Training performed here |
| --- | --- | --- | --- | --- |
| DeBERTa with smartphone context | Recommended live-review demo | Smartphone expressions, local context and scope guards | Published DeBERTa sentence/aspect classifier | No transformer fine-tuning |
| Rules + VADER | Comparison baseline and precomputed corpus views | Feature expressions | VADER plus category rules | None |
| TF-IDF + logistic regression | Locally trained research comparison | Per-category classifiers | Flat five-state classification, or presence followed by sentiment | Fit on the recorded 199 training sentences |

## The live demo

The dashboard starts on **Analyse a review**. When the checkpoint is installed, it selects **DeBERTa · smartphone context**. Type an English review and select **Analyse review**. The app performs new inference. It does not search the review database for an answer, train a model or fetch a saved demonstration output.

The current adapter is version 3, with an ID starting `deberta-live-v3`.

1. `text.py` preserves sentence boundaries and original character offsets.
2. `models/live.py` identifies candidates and local contexts. `models/aspects_live.json` extends the existing versioned smartphone vocabulary.
3. `models/inference.py` tokenizes each context together with an aspect target and runs DeBERTa.
4. `models/live.py` keeps each opinion's verbatim clause and offsets. It resolves a limited omitted feature reference within a sentence, and combines opposing opinions into mixed only in the review summary.
5. `components/SentenceBreakdown.tsx` displays sentences in reading order and their separate feature opinions. `views/Analyse.tsx` adds the summary and trace. **How this result was produced** exposes the feature cue, classifier context and decision, including supplied references.

One sentence can contain several opinions. For example, “The battery lasts two days, and the display is bright” remains one source sentence with two feature rows. Two full sentences appear in two cards. Positive and negative camera clauses keep their separate labels even when the review-level camera summary is mixed.

Source-code and vocabulary hashes form part of the live model ID. Release 1.2.0 uses `deberta-live-v3-10c9dff3-f342bce5`. It changes candidate/context handling, without retraining or replacing checkpoint weights. Historical verification records retain their recorded IDs.

“I love this phone” can receive a **general phone opinion**. That is separate from the ten aspects and remains visible when another sentence describes a feature. The app does not invent praise for battery or camera. Retail-only text can correctly return no phone aspect.

Version 1.2.0 handles “camera is slow to focus” as camera context, carries a shared predicate into “so is the display,” and retains conditional negative fragments such as “not outdoors.” These are limited context rules, not general language understanding. **Download analysis JSON** preserves the actual input and inference trace for inspection.

The input stays in the current browser tab across model changes, navigation and refresh. Live model selection is separate from the corpus selector. Changing the live model does not replace saved corpus predictions.

## The neural weights

The checkpoint is `yangheng/deberta-v3-base-absa-v1.1`, pinned to revision `10c9dff335a44073e1352360c3a7bc54dc58eb01`. The app downloads allowlisted configuration, tokenizer and safetensors files, verifies hashes and loads them locally.

The checkpoint predicts **negative, neutral or positive** for a context/aspect pair. The application supplies candidates and creates absent/mixed behaviour around those predictions. Vocabulary patterns select categories, not prewritten sentiment answers.

The original transfer adapter, domain adapter v2 and live adapter v3 share one set of weights and one loaded backbone. Earlier variants remain available to reproduce recorded experiments. Version 3 adds live-review handling and a decision trace.

## The teacher model and trained classifiers

“Teacher” means the model generating **pseudo labels**, not the course instructor.

The original DeBERTa adapter generated labels for 198 training sentences. One sentence retains human training labels. Those 199 sentences supplied the recorded TF-IDF runs:

- **Flat:** one classifier per aspect predicts absent, positive, negative, neutral or mixed.
- **Two-stage:** predict presence first, then sentiment for a present example.

DeBERTa does not consult those labels when answering a live input. TF-IDF classifiers do not inherit DeBERTa's weights. Their training targets inherit some of its decisions and errors.

## Data and results

| Material | Actual use |
| --- | --- |
| 67,986 source reviews and 720 listings | Source for the bounded historical smartphone corpus |
| 4,346 selected reviews across 12 listings | Analytics and annotation sampling |
| 199 training sentences | Fit the recorded TF-IDF classifiers |
| 35 validation sentences | Development diagnostics, including 34 AI-assisted sentence reviews |
| 69 unlabelled test sentences | Reserved for independent human annotation and final evaluation |
| Written live-review examples | Demo regressions outside the frozen study |

**0.750 tuple F1 belongs to domain adapter v2 on the inspected AI-assisted development reference.** It is not independent accuracy or a measured score for the live adapter. Passing written demo examples is not a scientific accuracy estimate.

A precise viva description:

> We built a local ABSA application. Its main demo combines smartphone aspect/context rules with a pretrained DeBERTa sentiment classifier. We also implemented a VADER baseline and trained two TF-IDF/logistic-regression profiles using mostly pseudo-labelled training sentences. We have not fine-tuned the transformer on our smartphone corpus.

See [demo and code-change preparation](DEMO_PREPARATION.md), [research results](RESULTS.md) and [checkpoint attribution](MODELING.md).
