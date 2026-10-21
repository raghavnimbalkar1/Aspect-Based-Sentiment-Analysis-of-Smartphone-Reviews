"""Stream complete exports without applying dashboard pagination limits."""

import csv
import io
import json
from collections.abc import Iterable, Iterator

from smartphone_absa.taxonomy import TAXONOMY_VERSION


def json_reviews(items: Iterable[dict], metadata: dict) -> Iterator[str]:
    yield json.dumps(metadata)[:-1] + ', "reviews": ['
    separator = ""
    for item in items:
        yield separator + json.dumps(item)
        separator = ","
    yield "]}"


def csv_reviews(items: Iterable[dict], model: str) -> Iterator[str]:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer)

    def row(values):
        buffer.seek(0)
        buffer.truncate()
        writer.writerow(
            [
                "'" + value
                if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@"))
                else value
                for value in values
            ]
        )
        return buffer.getvalue()

    yield row(
        [
            "review_id",
            "product",
            "date",
            "text",
            "category",
            "sentiment",
            "model_id",
            "taxonomy_version",
            "brand",
        ]
    )
    for item in items:
        aspects = item["analysis"]["aspects"] if item["analysis"] else []
        for aspect in aspects or [{"category": "", "sentiment": ""}]:
            yield row(
                [
                    item["id"],
                    item["product_name"],
                    item["date"],
                    item["text"],
                    aspect["category"],
                    aspect["sentiment"],
                    model,
                    TAXONOMY_VERSION,
                    item.get("brand", "Unknown"),
                ]
            )
