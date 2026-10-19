# Local CPU measurement

Measured on 19 October 2026 on the available MacBook Air M2, 8 GB RAM, using CPU inference. The machine/application checks and the accuracy study serve different purposes. This measurement describes responsiveness; it has no gold labels or accuracy scores.

| Model | Initialization | First request | Warm median | Warm p95 | Warm mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| Rules + VADER | <1 ms | 6.5 ms | 1.1 ms | 2.4 ms | 1.2 ms |
| Transferred DeBERTa | 4.73 s | 2.31 s | 64.3 ms | 214.1 ms | 86.0 ms |

The [full JSON record](data/m2-cpu-latency.json) includes dependency/OS versions, source hash, sampled review IDs/text hashes/lengths, model revision, every warm timing and the selection policy. No original review text or weights are committed with the report.

The sample comprises 16 English source reviews between 40 and 1,200 characters, selected by deterministic SHA-256 ordering with seed 42. Twelve include explicit aspect cues; four exercise the adapter's path with no detected candidate. Each model receives the same reviews, three times, sequentially in one fresh process: 48 warm requests per model. A separate first request uses a sampled review with explicit cues so that it exercises neural inference. Initialization includes integrity checks and lazy model/dependency imports. The first inference is excluded from the warm distribution.

These numbers exclude HTTP, browser rendering, database I/O and concurrent users. Repeated inputs, short reviews, the explicit-candidate gate, thermal state and background activity affect timing. Reviews without detected cues do not invoke the transformer. The sample is too small for a capacity claim; p95 is a descriptive percentile over these 48 requests. No MPS/Colab results are asserted.

To repeat from the repository root after setup, model installation and data preparation:

```sh
.venv/bin/absa benchmark data/processed/reviews.jsonl \
  --model rules-v1 --model deberta-absa-10c9dff3 \
  --samples 16 --repeats 3 \
  --output artifacts/benchmarks/m2-cpu-new-run.json
```

Choose a new output filename; existing runs are preserved. Run while the application has no heavy background job. `--samples` accepts 1–100 and `--repeats` 1–10. The command rejects insufficient eligible inputs or unavailable/duplicate model IDs. Benchmark files deliberately use a separate directory/schema, so the dashboard cannot mistake latency for a model accuracy report.
