# AI-assisted validation diagnostic

Measured on 19 October 2026. **These are agreement scores against an AI-assisted reference, not independent human-evaluated smartphone accuracy.** No test evaluation was performed.

The frozen validation sample contains 35 sentences / 350 category states. One sentence retains the user's human labels; 34 were labelled by direct AI sentence reading before checkpoint/baseline predictions were consulted. Notes preserve ambiguous interpretations and taxonomy gaps. The reference has 21 present aspect–sentiment tuples: 11 positive, 6 negative and 4 neutral; 329 states are absent. No mixed example exists in this validation sample.

| Model | Tuple micro-F1 | Presence F1 |
| --- | ---: | ---: |
| Always absent | 0.000 | 0.000 |
| Rules + VADER (`rules-v1`) | 0.267 | 0.533 |
| Transferred DeBERTa (`deberta-absa-10c9dff3`) | 0.323 | 0.516 |
| Local TF-IDF (`tfidf-db3871146fbb`) | 0.091 | 0.091 |

The TF-IDF classifier was fitted on the frozen 199 training sentences: 1 human-labelled sentence and 198 teacher-pseudo-labelled sentences. Human training decisions took precedence over matching pseudo labels. Vocabulary fitting used training text only. It is an actual locally trained artifact, separate from the third-party transferred checkpoint and from synthetic development fixtures.

The available reference is small and heavily dominated by absent states; some categories have no examples. An always-absent predictor reaches 94% category-state accuracy while detecting no aspect tuples, which is why that accuracy is not the headline metric. TF-IDF performs poorly against this limited reference; broader accuracy has not been established. The transferred model's higher diagnostic F1 is provisional, with missed aspects and sentiment errors visible in the report. No model or label changes were made in response to these scores.

The [machine-readable summary](data/ai-validation-diagnostic.json) contains precision/recall/F1 counts, category support, confusion matrices, reference origins and source/artifact hashes. Full input snapshots, prediction files and weights remain local under ignored `artifacts`. In the app, open **Model evaluation**, inspect the `compare-a4414bffb3b8` report, and filter its individual errors. Every diagnostic row and detail identifies AI-assisted validation.

The 69 frozen test sentences remain unchanged and unevaluated. Independent human test annotation and one final evaluation of fixed model configurations are still needed for a human-evaluated result. A larger independently labelled validation sample would be needed for stronger model-selection evidence. Smartphone transformer fine-tuning has not been performed.
