from __future__ import annotations

import csv
import io
from collections import Counter

from smartphone_absa.data import make_review
from smartphone_absa.text import text_hash

MAX_UPLOAD_BYTES = 16 * 1024 * 1024
MAX_ROWS = 10000


def parse_csv(content: bytes) -> tuple[list[str], list[dict]]:
    if len(content) > MAX_UPLOAD_BYTES:
        raise ValueError("CSV exceeds the 16 MB limit")
    try:
        decoded = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("Save this CSV using UTF-8 encoding") from exc
    if "\x00" in decoded:
        raise ValueError("CSV contains invalid null bytes")
    reader = csv.DictReader(io.StringIO(decoded, newline=""), strict=True)
    try:
        columns = reader.fieldnames
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV header: {exc}") from exc
    if not columns or len(set(columns)) != len(columns) or any(not c.strip() for c in columns):
        raise ValueError("CSV needs a header with unique, nonempty column names")
    rows = []
    try:
        for row in reader:
            if len(rows) >= MAX_ROWS:
                raise ValueError("CSV exceeds the 10,000-review limit; split it into smaller files")
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"CSV row {reader.line_num} has a different number of columns")
            rows.append(row)
    except csv.Error as exc:
        raise ValueError(f"Malformed CSV: {exc}") from exc
    if not rows:
        raise ValueError("CSV contains no data rows")
    return columns, rows


def prepare_upload(content: bytes, mapping: dict[str, str]) -> tuple[list, dict]:
    columns, rows = parse_csv(content)
    if not mapping.get("text") or mapping["text"] not in columns:
        raise ValueError("Choose a text column that exists in this CSV")
    if any(column and column not in columns for column in mapping.values()):
        raise ValueError("A mapped column does not exist in this CSV")
    reviews = []
    seen = set()
    rejected: Counter[str] = Counter()
    examples = []
    for number, row in enumerate(rows, start=2):
        mapped = {key: row.get(column, "") if column else "" for key, column in mapping.items()}
        product_name = mapped.get("product", "").strip() or "Uploaded reviews"
        product = {
            "asin": text_hash(product_name)[:16],
            "model": product_name,
            "brand": mapped.get("brand", "").strip() or "Unknown",
        }
        try:
            review = make_review({**mapped, "body": mapped["text"]}, product, source="csv-upload")
        except ValueError as exc:
            rejected["invalid_row"] += 1
            if len(examples) < 10:
                examples.append({"row": number, "reason": str(exc).split("\n")[0][:180]})
            continue
        if review.id in seen:
            rejected["duplicate_product_text"] += 1
            continue
        seen.add(review.id)
        reviews.append(review)
    if not reviews:
        raise ValueError("No valid reviews remain after checking text, ratings, and dates")
    return reviews, {
        "source": "csv-upload",
        "input_rows": len(rows),
        "accepted": len(reviews),
        "rejected": dict(rejected),
        "rejection_examples": examples,
        "column_mapping": mapping,
        "scope": "User-supplied products; smartphone relevance is not verified.",
    }
