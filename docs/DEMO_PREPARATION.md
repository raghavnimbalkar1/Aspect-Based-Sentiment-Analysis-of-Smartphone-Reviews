# Dashboard demo and code-change preparation

Read [the model map](MODEL_MAP.md) first. It separates live inference, pseudo-label generation and locally trained classifiers.

## Before the session

From the project directory:

```sh
make build
make doctor
make demo-check
make run
```

If optional neural dependencies or checkpoint files are missing, run `make model-setup` first. Initial downloads need internet. Installed inference uses local files. Run one server per database.

Open **http://localhost:8000**. Confirm **DeBERTa · smartphone context** on **Analyse a review**. Run one review before the session to load the checkpoint. The first neural request can take several seconds.

`make demo-check` runs written development examples through the actual model and writes a new report under `artifacts/demo-check`. A failed check prints its input identifier and output. These checks are not independent accuracy measurements.

## Demo sequence

1. Type the instructor's English smartphone review.
2. Select **Analyse review**. Read the sentence cards and individual feature opinions, then explain the combined review summary.
3. Open **How this result was produced** to show the actual candidate, context and decision.
   Use **Download analysis JSON** to keep that input and its exact output for later debugging.
4. Optionally compare with **Rules + VADER** on the same text. The main model appears first.
5. Open **Models explained** for the training, checkpoint and data questions.
6. Show **Overview** and **Review explorer** afterward for corpus analytics.

Live and corpus selectors are separate. A live request does not process all 4,346 reviews or save training labels. Its text remains in the current browser tab across navigation and refresh.

| Situation | Explanation |
| --- | --- |
| Camera positive, battery negative | Different features receive different opinions. |
| Positive and negative evidence for one feature | That aspect aggregates to mixed. |
| Feature mentioned without judgement | Neutral is valid. |
| General praise without a feature | General phone opinion stays separate from aspect predictions. |
| Seller/shipping text without a phone feature | No aspect result can be correct. |
| Incorrect output | Inspect candidate selection, context and polarity separately. |

Do not promise every unfamiliar sentence will be correct. Sarcasm, references across sentences and product comparisons remain difficult. Softmax values and written-demo pass rates are not accuracy percentages.

## Code path to know

| Stage | File | What to explain |
| --- | --- | --- |
| Input/request | `frontend/src/views/Analyse.tsx` | Text, selected model, comparison and stale-request cancellation |
| HTTP route | `src/smartphone_absa/api.py` | Validation and registry dispatch |
| Model selection | `src/smartphone_absa/models/registry.py` | Identity, availability and shared backbone |
| Live policy | `src/smartphone_absa/models/live.py` | Candidate context, actual predictions, aggregation and trace |
| Extra vocabulary | `src/smartphone_absa/models/aspects_live.json` | Expressions for existing categories |
| Inherited vocabulary | `src/smartphone_absa/models/aspects_v2.json` | Earlier smartphone policy retained for reproducibility |
| Neural forward pass | `src/smartphone_absa/models/inference.py` | Sentence/aspect tokenization, batches and softmax |
| Definitions | `src/smartphone_absa/taxonomy.py` | Categories, states and mixed aggregation |
| Local training | `experiments.py` and `models/classical.py` | Training-only features, logistic regression and artifacts |
| Saved records | `store.py` and `migrations/` | Reviews, model-specific results, jobs and annotations |

If the trace has no candidate, inspect vocabulary and scope. If the candidate is right but its context is wrong, inspect clause splitting. If both are right but polarity is wrong, inspect the checkpoint decision. Adding a keyword alone does not retrain sentiment. If JSON is correct but the screen is wrong, inspect the React rendering.

## Common code-change exercises

### Recognise a synonym

For “recognise snapshots as camera mentions,” append this pattern to the existing `camera` array inside `additional_cues` in `models/aspects_live.json`. Keep the existing focus patterns:

```json
"\\bsnapshots?\\b"
```

JSON needs double backslashes to encode regex backslashes. This selects a camera candidate without deciding its polarity.

Restart the backend with `Ctrl+C`, then `make run`. Refresh the browser to fetch the new model ID. JSON edits require a restart; do not assume the Python reloader watches them. Test both “The snapshots are excellent” and “The snapshots are awful.”

```sh
.venv/bin/pytest tests/test_live_analysis.py
make demo-check
```

The live ID hashes its policy and configuration. Edits therefore produce a different ID rather than silently overwriting earlier results.

### Change a dashboard label, colour or layout

Edit the relevant React component or `frontend/src/styles.css`. Sentiment colours are also mapped in `frontend/src/api.ts`. Keep stored category/sentiment identifiers stable when changing display text.

Run `make build` and refresh. The backend serves that built frontend. No model training is required.

### Change the VADER threshold

Find `RuleBaseline._state` in `baseline.py`: positive at `+0.05` or higher, negative at `-0.05` or lower after domain rules.

This changes **Rules + VADER**, not DeBERTa. Assign a new baseline model ID before preserving results from altered behaviour, then update dependent routing/tests. Do not quietly alter `rules-v1` and claim old results still describe it. For an explanation exercise, locate the comparisons and describe their effect before editing.

### Add a new category

This changes taxonomy and annotation contracts:

1. Add the category definition and a new taxonomy version.
2. Add candidate handling and a sentiment target. The live adapter inherits its category loop and targets from the versioned smartphone configuration.
3. Add the frontend name and verify annotation controls, outputs and exports.
4. Create compatible labels and check report/confusion-matrix dimensions.
5. Retrain TF-IDF artifacts if they should support the new category.
6. Preserve earlier models/reports under their original taxonomy. A database migration is needed only if the storage schema changes.

This is broader than adding a synonym. Explain the required changes before attempting it during a demonstration.

### Change mixed aggregation

Find `aggregate_sentiments` in `taxonomy.py`. Positive and negative evidence for the **same category** becomes mixed. Positive camera and negative battery remain separate aspect outputs.

This function is shared. Update affected identities, add behavioural tests and rerun checks before claiming replacement results.

### Train on new labels

Prepare a frozen annotation study, complete labels and export them. **Model evaluation** supports flat and two-stage TF-IDF training. Vocabulary/classifiers fit training text only. Validation assesses choices. Final test inference requires complete human labels and an explicit command.

Review text alone does not supply aspect labels. Transformer fine-tuning is a separate extension, not a dropdown option implemented in this project.

## Short answers to practise

**Why ABSA?** A review can praise camera and criticise battery. ABSA preserves that distinction.

**What did we implement?** Data preparation, smartphone candidate/context policy, baseline, evidence/aggregation, TF-IDF training, storage, annotation/evaluation tools and dashboard.

**Did we train DeBERTa?** No. We use a pinned pretrained checkpoint. We trained the TF-IDF profiles.

**What is TF-IDF?** A numerical representation weighting terms by their frequency and prevalence in the training collection. Logistic regression learns category decisions.

**What does the teacher model do?** The original DeBERTa adapter generates pseudo labels for most training sentences. It does not independently verify them.

**Must a live input exist in the dataset?** No. It runs as new inference.

**Does 0.750 F1 mean 75% accuracy?** No. It is tuple F1 for domain adapter v2 on an inspected, mostly AI-assisted development reference.

**Where is the final test score?** Pending independent human annotation of 69 sentences.

**Does inference need internet?** Installed inference is local. Initial dependency, source-data and checkpoint downloads need internet.
