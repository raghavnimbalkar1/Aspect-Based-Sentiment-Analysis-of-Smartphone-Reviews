export UV_CACHE_DIR := $(CURDIR)/.cache/uv

.PHONY: setup data seed build run check dev-api dev-ui pilot model-setup annotation-open doctor verify-release verify-release-neural demo-check

QA_RUN_DIR ?= artifacts/release-qa/$(shell date +%Y%m%d-%H%M%S)

setup:
	uv sync --frozen --group dev
	npm --prefix frontend ci

data:
	uv run --frozen python scripts/download_data.py
	uv run --frozen absa prepare data/raw/grikomsn-v2

seed:
	uv run --frozen absa load data/processed/reviews.jsonl --analyse

build:
	npm --prefix frontend run build

run:
	.venv/bin/absa serve

doctor:
	.venv/bin/absa doctor --verify-models

verify-release:
	.venv/bin/python scripts/verify_release.py --output $(QA_RUN_DIR)

verify-release-neural:
	.venv/bin/python scripts/verify_release.py --output $(QA_RUN_DIR) --neural

demo-check:
	.venv/bin/python scripts/check_live_demo.py

check:
	.venv/bin/ruff check src tests scripts
	.venv/bin/pytest
	npm --prefix frontend run format:check
	npm --prefix frontend test
	npm --prefix frontend run build

dev-api:
	uv run --frozen uvicorn smartphone_absa.api:create_app --factory --reload --host 127.0.0.1 --port 8000

dev-ui:
	npm --prefix frontend run dev

pilot:
	uv run --frozen absa annotation-tasks data/processed/reviews.jsonl --output data/annotations/pilot.csv --sentences 100

model-setup:
	uv sync --frozen --extra training --group dev
	HF_HUB_DISABLE_XET=1 .venv/bin/absa download-model

annotation-open:
	.venv/bin/absa annotation-import data/annotations/pilot.csv --manifest data/annotations/pilot.manifest.json --name "Smartphone annotation pilot"
