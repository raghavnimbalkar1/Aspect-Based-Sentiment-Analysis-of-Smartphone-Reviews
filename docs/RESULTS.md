# Model development results

Measured on 19–20 October 2026. **These are agreement scores against an AI-assisted reference, not independent human-evaluated smartphone accuracy.** The revised models were designed after inspecting this reference's errors, making their results development comparisons. No test evaluation was performed.

The frozen validation sample contains 35 sentences / 350 category states. One sentence retains the user's human labels; 34 were labelled by direct AI sentence reading before checkpoint/baseline predictions were consulted. Notes preserve ambiguous interpretations and taxonomy gaps. The reference has 21 present aspect–sentiment tuples: 11 positive, 6 negative and 4 neutral; 329 states are absent. No mixed example exists in this validation sample.

## Same-reference comparison

The 20 October comparison reproduces every original model's metrics exactly, using unchanged label and manifest hashes. It adds two candidates without replacing the original artifacts.

| Model | Tuple micro-F1 | Presence F1 |
| --- | ---: | ---: |
| Always absent | 0.000 | 0.000 |
| Rules + VADER (`rules-v1`) | 0.267 | 0.533 |
| Transferred DeBERTa (`deberta-absa-10c9dff3`) | 0.323 | 0.516 |
| Local TF-IDF (`tfidf-db3871146fbb`) | 0.091 | 0.091 |
| Domain adapter v2 (`deberta-domain-v2-10c9dff3-b377506c`) | 0.750 | 0.950 |
| Two-stage TF-IDF (`tfidf-4e97a73e6f8a`) | 0.240 | 0.320 |

The TF-IDF classifier was fitted on the frozen 199 training sentences: 1 human-labelled sentence and 198 teacher-pseudo-labelled sentences. Human training decisions took precedence over matching pseudo labels. Vocabulary fitting used training text only. It is an actual locally trained artifact, separate from the third-party transferred checkpoint and from synthetic development fixtures.

The available reference is small and heavily dominated by absent states; some categories have no examples. An always-absent predictor reaches 94% category-state accuracy while detecting no aspect tuples, which is why that accuracy is not the headline metric. Both TF-IDF methods remain weak with sparse pseudo-labelled training data. The domain adapter's diagnostic improvement is provisional: these examples informed its design, and the labels are mostly AI-assisted.

## What changed

The [refinement protocol](MODEL_IMPROVEMENT_PLAN.md) was fixed before the new comparison. The domain adapter expands vocabulary within the existing ten categories, preserves shared predicates such as coordinated aspect nouns, and distinguishes charging/retail speed from phone performance and physical volume controls from audio. Sentiment still comes from the same pinned DeBERTa weights. This is an application adapter, not smartphone fine-tuning. Its model ID hashes the cue configuration and policy source; the original neural ID retains its original behaviour.

The two-stage classifier uses training-only word and character features. Each category first predicts presence, then classifies sentiment using present training examples. It uses the same 199 training sentences and the same human-over-assisted precedence as flat TF-IDF. Feature budgets, regularization and decision rules were fixed without a threshold or hyperparameter search on the diagnostic labels.

This is the first new development comparison; no alternative model settings were evaluated and discarded. Behavioural fixtures were corrected before corpus inference, including a charging-speed guard. The new neural adapter still has **2 missed mentions and 4 wrong sentiments**; two-stage TF-IDF has **17 missed mentions and 1 wrong sentiment**. Neither emits an extra category on this sample. Wrong sentiments count as both a tuple false positive and a tuple false negative. No reference label was changed to improve a score.

The original [diagnostic record](data/ai-validation-diagnostic.json) is retained. The new [full aggregate record](data/model-refinement-diagnostic.json) includes every candidate's metrics, category support, confusion matrices, error counts, configuration and source/artifact hashes. Full input snapshots, prediction files and weights remain local under ignored `artifacts`. In **Model evaluation**, inspect `compare-refinement-20261020-01` and filter its errors. The UI identifies both AI-assisted reference labels and the development comparison. The classical training report is `train-hierarchical-20261020-01`.

The [CPU measurement](PERFORMANCE.md) uses the established 16-review sample, with no review overlap with the locked test partition. Median direct inference is about 61 ms for domain adapter v2; latency does not establish accuracy.

The 69 frozen test sentences remain unchanged and unevaluated. Independent human test annotation and one final evaluation of fixed model configurations are still needed for a human-evaluated result. A larger independently labelled validation sample would be needed for stronger model-selection evidence. Smartphone transformer fine-tuning has not been performed.
