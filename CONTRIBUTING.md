# Contributing

Use a branch named for its purpose, such as `feat/review-analysis-workspace` or `fix/import-validation`. Keep commits focused and use an imperative summary with a conventional prefix: `feat`, `fix`, `test`, `docs`, `build`, or `ci`.

Run the checks documented in the README before pushing. Open a pull request against `main` with the problem, the resulting behaviour, validation performed, and any remaining limitations. Do not force-push shared branches or commit generated application data.

Database changes belong in numbered migrations. Add a migration instead of changing the meaning of an existing deployed migration. Exercise upgrades against a temporary database, and keep the user's local database outside version control.

Data and model changes must record source versions, checksums, label mappings, split manifests, and experiment configuration. Test partitions must not be used to choose model settings or annotation rules.

Use the author's configured Git identity. Commit messages should describe the change without automatic contributor trailers.
