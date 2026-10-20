# Project reference guide

[Download the PowerPoint](Smartphone_ABSA_Reference_Guide.pptx) · [Read the text companion](STUDY_GUIDE.md)

This 52-slide guide explains the implemented application and the recorded experiments in release 1.0.0. It is intended for individual reading and reference. Open the **Notes** pane in PowerPoint for the detailed explanation and source references on each slide. The text companion includes the same explanations if you prefer reading or searching in a browser.

| Slides | Contents |
| --- | --- |
| 3–7 | The ABSA problem, ten aspects and five annotation states |
| 8–14 | Source files, selection, exclusions, language coverage and label origins |
| 15–29 | Processing pipeline, stack, API, SQLite, jobs and all five model variants |
| 30–36 | Actual application screenshots and the six workspaces |
| 37–43 | Tuple metrics, diagnostic results, remaining errors, latency and software checks |
| 44–48 | Local commands, source layout, limitations, glossary and references |
| 49–52 | All selected listings, field definitions, API lookup and evaluation commands |

The tables, charts and explanatory text are editable PowerPoint objects. Screenshots show the running local application. Charts use the committed aggregate records rather than live external data. The project source references identify application commit `8e4d312f208d021e9b5e729435197ecf21bbfb9a`; the guide and subsequent documentation commits do not change those recorded experiments.

The results chapter distinguishes software verification from scientific evaluation. The 35 validation sentences include 34 AI-assisted reviews, and the revised models used inspected validation errors. The reported 0.750 tuple F1 is development agreement. The 69 test sentences remain unlabelled and unevaluated, so independent human test accuracy is still pending.

The PowerPoint includes the explanations in its Notes, so it can be shared as one file. The companion links to screenshots stored in the repository.
