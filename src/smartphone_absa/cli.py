from __future__ import annotations

import argparse
import json
from pathlib import Path

from smartphone_absa.annotations import export_tasks
from smartphone_absa.data import audit_source, prepare_source, read_reviews
from smartphone_absa.experiments import evaluate_models, train_tfidf
from smartphone_absa.models.checkpoints import TRANSFER_ID, download_checkpoint
from smartphone_absa.models.registry import ModelRegistry


def main() -> None:
    parser = argparse.ArgumentParser(prog="absa")
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit", help="Verify source checksums and inspect all raw rows")
    audit.add_argument("directory", type=Path)
    audit.add_argument("--output", type=Path)
    prepare = sub.add_parser("prepare", help="Build the bounded English smartphone corpus")
    prepare.add_argument("directory", type=Path)
    prepare.add_argument("--selection", type=Path, default=Path("config/products.json"))
    prepare.add_argument("--output", type=Path, default=Path("data/processed/reviews.jsonl"))
    prepare.add_argument("--per-product", type=int, default=400)
    annotate = sub.add_parser(
        "annotation-tasks", help="Export blind labels and a frozen split manifest"
    )
    annotate.add_argument("input", type=Path)
    annotate.add_argument("--output", type=Path, required=True)
    annotate.add_argument("--sentences", type=int, default=100)
    annotate.add_argument(
        "--full", action="store_true", help="Include validation/test; default is train-only"
    )
    task_import = sub.add_parser(
        "annotation-import", help="Open frozen blank tasks in the dashboard"
    )
    task_import.add_argument("input", type=Path)
    task_import.add_argument("--manifest", type=Path, required=True)
    task_import.add_argument("--name", default="Annotation pilot")
    task_import.add_argument("--database", type=Path, default=Path("data/workspace.sqlite3"))
    train = sub.add_parser(
        "train-tfidf", help="Train/evaluate only on adjudicated human annotations"
    )
    train.add_argument("annotations", type=Path)
    train.add_argument("--manifest", type=Path, required=True)
    train.add_argument("--output", type=Path, required=True)
    train.add_argument(
        "--final-test", action="store_true", help="Explicitly evaluate the locked test set"
    )
    evaluate = sub.add_parser("evaluate-models", help="Compare installed models on human labels")
    evaluate.add_argument("annotations", type=Path)
    evaluate.add_argument("--manifest", type=Path, required=True)
    evaluate.add_argument("--output", type=Path, required=True)
    evaluate.add_argument("--model", action="append", required=True)
    evaluate.add_argument("--final-test", action="store_true")
    analyse = sub.add_parser("analyse", help="Analyse English text with the rule baseline")
    analyse.add_argument("text")
    analyse.add_argument("--model", default="rules-v1")
    sub.add_parser("download-model", help="Download the pinned public ABSA checkpoint")
    load = sub.add_parser("load", help="Import a prepared corpus into the local workspace")
    load.add_argument("input", type=Path)
    load.add_argument("--name", default="Smartphone reviews · research corpus")
    load.add_argument("--database", type=Path, default=Path("data/workspace.sqlite3"))
    load.add_argument("--model", default="rules-v1")
    load.add_argument("--analyse", action="store_true", help="Run the rule baseline after import")
    sub.add_parser("serve", help="Start the local API and built dashboard on port 8000")
    args = parser.parse_args()
    try:
        if args.command == "download-model":
            result = download_checkpoint(Path("artifacts/models") / TRANSFER_ID)
        elif args.command == "audit":
            result = audit_source(args.directory)
            if args.output:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, indent=2) + "\n")
        elif args.command == "prepare":
            result = prepare_source(args.directory, args.selection, args.output, args.per_product)
        elif args.command == "annotation-tasks":
            result = export_tasks(
                read_reviews(args.input), args.output, args.sentences, pilot=not args.full
            )
        elif args.command == "annotation-import":
            from smartphone_absa.store import Store
            from smartphone_absa.workbench import AnnotationWorkbench

            result = AnnotationWorkbench(Store(args.database)).import_tasks(
                args.input, args.manifest, args.name
            )
        elif args.command == "train-tfidf":
            result = train_tfidf(args.annotations, args.manifest, args.output, args.final_test)
        elif args.command == "evaluate-models":
            result = evaluate_models(
                args.annotations,
                args.manifest,
                args.output,
                args.model,
                ModelRegistry(Path("artifacts")),
                args.final_test,
            )
        elif args.command == "load":
            from smartphone_absa.jobs import run_job
            from smartphone_absa.store import Store

            store = Store(args.database)
            manifest_file = args.input.with_suffix(".manifest.json")
            manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {}
            result = store.import_reviews(args.name, read_reviews(args.input), manifest)
            if args.analyse:
                job, created = store.create_job(result["id"], args.model)
                if created:
                    run_job(store, job, ModelRegistry(Path("artifacts")).get(args.model))
                result["job"] = store.jobs(result["id"], args.model)[0]
        elif args.command == "serve":
            from smartphone_absa.api import serve

            serve()
            return
        else:
            result = (
                ModelRegistry(Path("artifacts"))
                .get(args.model)
                .analyse(args.text)
                .model_dump(mode="json")
            )
        print(json.dumps(result, indent=2))
    except (ValueError, FileNotFoundError, KeyError) as exc:
        parser.exit(2, f"Error: {exc}\n")


if __name__ == "__main__":
    main()
