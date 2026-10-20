# Model refinement protocol — 20 October 2026

The existing 35-sentence diagnostic reference has already been inspected. It contains 1 human and 34 AI-assisted sentences, so improvements measured on it are development agreement, not independent human accuracy. The 69 test sentences remain locked and will not be read for model design, labelled, inferred or evaluated in this increment.

The first comparison missed 13 of 21 reference mentions with the transferred adapter and 20 with flat TF-IDF. Error inspection exposed incomplete domain vocabulary and shared-predicate coordination losing opinion context. The training collection also has only 5–15 non-absent examples per category. Changes below are fixed before the new comparison; reference labels and taxonomy definitions stay unchanged.

## Candidates

1. **Domain adapter v2.** Reuse the pinned DeBERTa weights. Add a versioned smartphone cue/target configuration covering the existing category definitions: operating speed, display resolution, physical controls/durability, named software and network/SIM compatibility. Preserve shared opinion predicates in coordinated noun phrases. Separate independent clauses, guard retail speed and distinguish volume controls from sound quality. No rule will directly assign a sentiment label; the paired transformer remains the sentiment classifier. Keep `deberta-absa-10c9dff3` unchanged under its existing ID and register the new adapter separately.
2. **Hierarchical TF-IDF.** Keep the same frozen training sentences and human-over-pseudo-label precedence. Fit word uni/bigrams plus character 3–5-grams on training text only. Each category gets a balanced binary presence classifier; its sentiment classifier uses only present training examples. Use logistic regression `C=1`, seed 42, and the default binary decision boundary. No hyperparameter or probability threshold search on diagnostic labels. Preserve the flat classifier and its artifact.

Before the first new comparison, the feature configuration is fixed at 25,000 word features and 25,000 `char_wb` features, equal feature weights, Unicode accent stripping, sublinear term frequency and per-vectorizer L2 normalization. Categories with no present training examples emit absent; a single observed sentiment uses a constant classifier. Domain adapter targets and vocabulary are stored in `src/smartphone_absa/models/aspects_v2.json`; its ID includes a hash of that configuration and the adapter policy source. Both neural adapters share the same loaded backbone and inference lock.

## Checks and reporting

- Test coordination, negation, distinct opinions, charging-versus-speed, retail text, hardware controls, language rejection and original evidence offsets with isolated behavioural fixtures. These fixtures are not a benchmark and will not be included in accuracy claims.
- Compare all candidates with the original rules, transferred adapter and flat TF-IDF on the same unchanged diagnostic reference. Save full predictions, configuration/label hashes, reference origins and per-category support. Retain failed or superseded experiments rather than reporting only a preferred run.
- Measure CPU latency separately using the established deterministic sample. Reuse one shared neural backbone in the registry so comparing adapters does not duplicate weights in the 8 GB workspace.
- Do not change reference annotations to agree with predictions. Record any implementation corrections and additional development comparisons. Keep final human test evaluation separate after model configurations are fixed.

The checkpoint's [pinned model card](https://huggingface.co/yangheng/deberta-v3-base-absa-v1.1/blob/10c9dff335a44073e1352360c3a7bc54dc58eb01/README.md) supports sentence/aspect pair inference. The revised alias targets and scope rules are our application adapter, not smartphone fine-tuning of that checkpoint. The classical estimators follow the installed scikit-learn implementation and [its logistic-regression documentation](https://scikit-learn.org/stable/modules/linear_model.html#logistic-regression).
