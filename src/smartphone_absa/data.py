"""Deterministic source audit and bounded preparation without copying reviewer identities."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

from smartphone_absa.domain import Review
from smartphone_absa.text import detect_language, text_hash

SOURCE = "grikomsn/amazon-cell-phones-reviews@2"
FILES = {
    "20191226-items.csv": "043c1d6d5126cc294991ce6e0cb855699af912d571b786af8f967ce251aded45",
    "20191226-reviews.csv": "ad03353b68bea3a1ba7f1ab1efd10bb212baa7c045dd7e548e53e8132ca97ba3",
}


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_date(value: str) -> str | None:
    if not value.strip():
        return None
    for pattern in ("%Y-%m-%d", "%B %d, %Y", "%b %d, %Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(value.strip(), pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError(f"unsupported review date: {value[:40]}")


def make_review(row: dict[str, str], product: dict[str, str], source: str = SOURCE) -> Review:
    text = row.get("body", row.get("text", ""))
    if not text or not text.strip():
        raise ValueError("empty review text")
    rating_value = row.get("rating", "").strip()
    rating = float(rating_value) if rating_value else None
    if rating is not None and not 1 <= rating <= 5:
        raise ValueError("rating must be between 1 and 5")
    verified_value = row.get("verified", "").strip().lower()
    if verified_value not in ("", "true", "false", "1", "0", "yes", "no"):
        raise ValueError("verified must be true or false")
    group = text_hash(text)
    product_id = product["asin"]
    review_id = hashlib.sha256(f"{source}\0{product_id}\0{group}".encode()).hexdigest()[:24]
    return Review(
        id=review_id,
        product_id=product_id,
        product_name=product["model"],
        brand=product.get("brand", "Unknown"),
        condition=product.get("condition", "unspecified"),
        text=text,
        title=row.get("title", ""),
        rating=rating,
        date=parse_date(row.get("date", "")),
        verified=None if not verified_value else verified_value in ("true", "1", "yes"),
        language=detect_language(text),
        duplicate_group=group,
        source=source,
    )


def audit_source(directory: Path, verify: bool = True) -> dict[str, Any]:
    files = {}
    for name, expected in FILES.items():
        path = directory / name
        actual = file_hash(path)
        if verify and actual != expected:
            raise ValueError(
                f"Source checksum mismatch: {name}. Do not continue with unknown data."
            )
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            files[name] = {
                "sha256": actual,
                "bytes": path.stat().st_size,
                "rows": len(rows),
                "columns": reader.fieldnames,
            }
    with (directory / "20191226-items.csv").open(encoding="utf-8-sig", newline="") as handle:
        products = {row["asin"]: row for row in csv.DictReader(handle)}
    counts: Counter[str] = Counter()
    empty = missing_product = duplicates = 0
    seen = set()
    dates = []
    with (directory / "20191226-reviews.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            counts[row["asin"]] += 1
            missing_product += row["asin"] not in products
            body = row.get("body", "")
            empty += not body.strip()
            key = (row["asin"], text_hash(body))
            duplicates += key in seen
            seen.add(key)
            if row["date"]:
                dates.append(parse_date(row["date"]))
    return {
        "source": SOURCE,
        "verified_checksums": verify,
        "files": files,
        "review_rows_with_missing_product": missing_product,
        "empty_review_rows": empty,
        "duplicate_product_text_rows": duplicates,
        "date_from": min(dates) if dates else None,
        "date_to": max(dates) if dates else None,
        "products_with_reviews": len(counts),
        "limitations": [
            "Raw data includes feature phones and renewed listings.",
            "Star ratings are not aspect labels.",
            "Duplicate detection here is exact after case/whitespace normalisation.",
        ],
    }


def prepare_source(
    directory: Path,
    selection: Path,
    output: Path,
    per_product: int = 400,
) -> dict[str, Any]:
    if not 1 <= per_product <= 5000:
        raise ValueError("per_product must be between 1 and 5000")
    audit = audit_source(directory)
    config = json.loads(selection.read_text())
    products = {item["asin"]: item for item in config["products"]}
    candidates: dict[str, list[Review]] = defaultdict(list)
    rejected: Counter[str] = Counter()
    seen = set()
    with (directory / "20191226-reviews.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["asin"] not in products:
                rejected["listing_outside_selection"] += 1
                continue
            try:
                review = make_review(row, products[row["asin"]])
            except ValueError:
                rejected["invalid_row"] += 1
                continue
            if review.language not in ("en", "unknown"):
                rejected["non_english"] += 1
                continue
            if review.id in seen:
                rejected["duplicate_product_text"] += 1
                continue
            seen.add(review.id)
            candidates[review.product_id].append(review)
    selected = []
    for product_id in sorted(candidates):
        # Hash ordering is deterministic and avoids the source's chronological ordering.
        rows = sorted(candidates[product_id], key=lambda review: review.id)
        selected.extend(rows[:per_product])
        rejected["per_product_cap"] += max(0, len(rows) - per_product)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for review in selected:
            handle.write(review.model_dump_json() + "\n")
    manifest = {
        "source": SOURCE,
        "prepared_on": date.today().isoformat(),
        "source_audit": audit,
        "selection_sha256": file_hash(selection),
        "output_sha256": file_hash(output),
        "accepted": len(selected),
        "rejected": dict(rejected),
        "per_product_limit": per_product,
        "language_policy": "English accepted; short/undetermined text retained as unknown.",
        "duplicate_policy": (
            "One normalised body per listing; global text hash retained for splits."
        ),
        "language_counts": dict(Counter(row.language for row in selected)),
        "products": [
            {**product, "accepted": sum(r.product_id == asin for r in selected)}
            for asin, product in products.items()
        ],
    }
    output.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


def read_reviews(path: Path) -> list[Review]:
    with path.open(encoding="utf-8") as handle:
        return [Review.model_validate_json(line) for line in handle if line.strip()]
