# Smartphone Review Analysis

A local workspace for aspect-based sentiment analysis of smartphone reviews. The project covers data preparation, annotation, baseline and transformer experiments, and a dashboard for investigating the evidence behind feature-level sentiment.

The implementation follows the approved [research proposal](RESEARCH_PLAN.md). See the [delivery phases](docs/DELIVERY.md) for progress and acceptance criteria.

## Delivery

1. Data audit, annotation format, grouped splits, and reproducible baseline.
2. Local API, persistent analysis jobs, and dashboard.
3. Supervised model comparison and local transformer inference.
4. Final evaluation, verification, and submission packaging.

Review-level ratings are metadata. They are never substituted for aspect sentiment labels. Real model measurements will be published only after evaluation on independently checked annotations.

## Development workflow

Use focused feature branches and pull requests. Raw datasets, local databases, trained checkpoints, credentials, and generated exports stay out of Git. See [contribution guidance](CONTRIBUTING.md).
