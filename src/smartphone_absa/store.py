"""Local persistence with explicit migrations and versioned analysis records."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from smartphone_absa.baseline import MODEL_ID
from smartphone_absa.domain import Analysis, Review
from smartphone_absa.taxonomy import CATEGORIES, TAXONOMY_VERSION


@dataclass(frozen=True)
class Filters:
    product: str = ""
    category: str = ""
    sentiment: str = ""
    q: str = ""


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        self.migrate()

    @contextmanager
    def connection(self):
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        try:
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> None:
        with self.connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations "
                "(version TEXT PRIMARY KEY, checksum TEXT NOT NULL)"
            )
            for migration in sorted((Path(__file__).parent / "migrations").glob("*.sql")):
                sql = migration.read_text()
                checksum = hashlib.sha256(sql.encode()).hexdigest()
                existing = connection.execute(
                    "SELECT checksum FROM schema_migrations WHERE version=?", (migration.name,)
                ).fetchone()
                if existing:
                    if existing["checksum"] != checksum:
                        raise RuntimeError(f"Applied migration changed: {migration.name}")
                    continue
                # Source-controlled migration names/checksums contain no user data.
                connection.executescript(
                    "BEGIN IMMEDIATE;\n"
                    + sql
                    + "\nINSERT INTO schema_migrations VALUES ('"
                    + migration.name
                    + "','"
                    + checksum
                    + "');\nCOMMIT;"
                )

    def import_reviews(self, name: str, reviews: list[Review], manifest: dict) -> dict:
        if not reviews:
            raise ValueError("No valid reviews to import")
        fingerprint = hashlib.sha256(
            "\n".join(sorted(row.model_dump_json() for row in reviews)).encode()
        ).hexdigest()
        dataset_id = fingerprint[:24]
        with self.connection() as connection:
            existing = connection.execute(
                "SELECT * FROM datasets WHERE fingerprint=?", (fingerprint,)
            ).fetchone()
            if existing:
                return {**dict(existing), "duplicate": True}
            rejected = manifest.get("rejected", {})
            rejected_count = sum(rejected.values()) if isinstance(rejected, dict) else rejected
            connection.execute(
                "INSERT INTO datasets "
                "(id,name,source,fingerprint,accepted,rejected,manifest_json) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    dataset_id,
                    name,
                    manifest.get("source", "csv-upload"),
                    fingerprint,
                    len(reviews),
                    rejected_count,
                    json.dumps(manifest),
                ),
            )
            connection.executemany(
                "INSERT INTO reviews VALUES (?,?,?,?,?,?,?,?,?,?)",
                [
                    (
                        dataset_id,
                        row.id,
                        row.product_id,
                        row.product_name,
                        row.brand,
                        row.condition,
                        row.text,
                        row.date,
                        row.language,
                        row.model_dump_json(),
                    )
                    for row in reviews
                ],
            )
        return {
            "id": dataset_id,
            "name": name,
            "accepted": len(reviews),
            "rejected": rejected_count,
            "duplicate": False,
        }

    def datasets(self) -> list[dict]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT d.id,d.name,d.source,d.imported_at,d.accepted,d.rejected,
                    (SELECT COUNT(*) FROM analyses a WHERE a.dataset_id=d.id
                     AND a.model_id=? AND a.taxonomy_version=?) AS analysed
                FROM datasets d ORDER BY d.imported_at DESC
            """,
                (MODEL_ID, TAXONOMY_VERSION),
            ).fetchall()
            return [dict(row) for row in rows]

    def dataset(self, dataset_id: str) -> dict | None:
        with self.connection() as connection:
            row = connection.execute("SELECT * FROM datasets WHERE id=?", (dataset_id,)).fetchone()
            if row:
                result = dict(row)
                result["manifest"] = json.loads(result.pop("manifest_json"))
                return result
        return None

    def products(self, dataset_id: str) -> list[dict]:
        with self.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    """
                SELECT product_id AS id,product_name AS name,brand,condition,COUNT(*) AS reviews
                FROM reviews WHERE dataset_id=? GROUP BY product_id ORDER BY product_name
            """,
                    (dataset_id,),
                ).fetchall()
            ]

    def pending_reviews(self, dataset_id: str) -> list[Review]:
        with self.connection() as connection:
            rows = connection.execute(
                """
                SELECT r.payload_json FROM reviews r LEFT JOIN analyses a ON
                  a.dataset_id=r.dataset_id AND a.review_id=r.id
                  AND a.model_id=? AND a.taxonomy_version=?
                WHERE r.dataset_id=? AND a.id IS NULL ORDER BY r.id
            """,
                (MODEL_ID, TAXONOMY_VERSION, dataset_id),
            ).fetchall()
            return [Review.model_validate_json(row[0]) for row in rows]

    def save_analysis(self, dataset_id: str, review_id: str, analysis: Analysis) -> None:
        with self.connection() as connection:
            row = connection.execute(
                """
                INSERT INTO analyses
                (dataset_id,review_id,model_id,taxonomy_version,supported,result_json)
                VALUES (?,?,?,?,?,?) ON CONFLICT(dataset_id,review_id,model_id,taxonomy_version)
                DO UPDATE SET result_json=excluded.result_json,supported=excluded.supported
                RETURNING id
            """,
                (
                    dataset_id,
                    review_id,
                    analysis.model_id,
                    analysis.taxonomy_version,
                    int(analysis.supported),
                    analysis.model_dump_json(),
                ),
            ).fetchone()
            connection.execute("DELETE FROM aspects WHERE analysis_id=?", (row[0],))
            connection.executemany(
                "INSERT INTO aspects VALUES (?,?,?)",
                [(row[0], aspect.category, aspect.sentiment) for aspect in analysis.aspects],
            )

    @staticmethod
    def _where(dataset_id: str, filters: Filters) -> tuple[str, list]:
        sql = "r.dataset_id=?"
        values: list = [dataset_id]
        if filters.product:
            sql += " AND r.product_id=?"
            values.append(filters.product)
        if filters.q:
            # instr implements literal substring search, so '%' and '_' are not wildcards.
            sql += " AND instr(lower(r.text),lower(?))>0"
            values.append(filters.q)
        if filters.category or filters.sentiment:
            sql += " AND EXISTS (SELECT 1 FROM aspects af WHERE af.analysis_id=a.id"
            if filters.category:
                sql += " AND af.category=?"
                values.append(filters.category)
            if filters.sentiment:
                sql += " AND af.sentiment=?"
                values.append(filters.sentiment)
            sql += ")"
        return sql, values

    @staticmethod
    def _join() -> str:
        return (
            " FROM reviews r LEFT JOIN analyses a ON a.dataset_id=r.dataset_id "
            "AND a.review_id=r.id AND a.model_id=? AND a.taxonomy_version=? "
        )

    def reviews(
        self, dataset_id: str, filters: Filters, page: int = 1, page_size: int = 20
    ) -> dict:
        where, values = self._where(dataset_id, filters)
        bindings = [MODEL_ID, TAXONOMY_VERSION, *values]
        with self.connection() as connection:
            total = connection.execute(
                "SELECT COUNT(*)" + self._join() + "WHERE " + where, bindings
            ).fetchone()[0]
            rows = connection.execute(
                "SELECT r.payload_json,a.result_json"
                + self._join()
                + "WHERE "
                + where
                + " ORDER BY r.date DESC,r.id LIMIT ? OFFSET ?",
                [*bindings, page_size, (page - 1) * page_size],
            ).fetchall()
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "items": [
                    {
                        **json.loads(row["payload_json"]),
                        "analysis": json.loads(row["result_json"]) if row["result_json"] else None,
                    }
                    for row in rows
                ],
            }

    def overview(self, dataset_id: str, filters: Filters | None = None) -> dict:
        filters = filters or Filters()
        where, values = self._where(dataset_id, filters)
        bindings = [MODEL_ID, TAXONOMY_VERSION, *values]
        with self.connection() as connection:
            stats = dict(
                connection.execute(
                    """
                SELECT COUNT(*) AS reviews,COUNT(a.id) AS analysed,
                COALESCE(SUM(a.supported),0) AS supported,
                COUNT(DISTINCT r.product_id) AS products,
                MIN(r.date) AS date_from,MAX(r.date) AS date_to
            """
                    + self._join()
                    + "WHERE "
                    + where,
                    bindings,
                ).fetchone()
            )
            rows = connection.execute(
                "SELECT x.category,x.sentiment,COUNT(*) AS count"
                + self._join()
                + " JOIN aspects x ON x.analysis_id=a.id WHERE "
                + where
                + " GROUP BY x.category,x.sentiment",
                bindings,
            ).fetchall()
            by_category = {
                category.id: {
                    "category": category.id,
                    "name": category.name,
                    "positive": 0,
                    "negative": 0,
                    "neutral": 0,
                    "mixed": 0,
                }
                for category in CATEGORIES
            }
            for row in rows:
                by_category[row["category"]][row["sentiment"]] = row["count"]
            aspects = []
            for entry in by_category.values():
                total = sum(entry[state] for state in ("positive", "negative", "neutral", "mixed"))
                aspects.append(
                    {
                        **entry,
                        "mentions": total,
                        "net_sentiment": round(
                            100 * (entry["positive"] - entry["negative"]) / total, 1
                        )
                        if total
                        else None,
                        "mention_rate": total / stats["supported"] if stats["supported"] else 0,
                        "limited_evidence": total < 20,
                    }
                )
            sentiment_totals = {
                state: sum(entry[state] for entry in aspects)
                for state in ("positive", "negative", "neutral", "mixed")
            }
            languages = [
                dict(row)
                for row in connection.execute(
                    "SELECT r.language,COUNT(*) AS count"
                    + self._join()
                    + "WHERE "
                    + where
                    + " GROUP BY r.language",
                    bindings,
                ).fetchall()
            ]
            return {
                **stats,
                "pending": stats["reviews"] - stats["analysed"],
                "unsupported": stats["analysed"] - stats["supported"],
                "aspects": aspects,
                "sentiment_totals": sentiment_totals,
                "languages": languages,
                "model_id": MODEL_ID,
                "taxonomy_version": TAXONOMY_VERSION,
            }

    def create_job(self, dataset_id: str) -> tuple[dict, bool]:
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM jobs WHERE dataset_id=? AND model_id=? "
                "AND taxonomy_version=? AND status IN ('queued','running')",
                (dataset_id, MODEL_ID, TAXONOMY_VERSION),
            ).fetchone()
            if existing:
                return dict(existing), False
            total = connection.execute(
                """
                SELECT COUNT(*) FROM reviews r LEFT JOIN analyses a ON
                  a.dataset_id=r.dataset_id AND a.review_id=r.id AND a.model_id=?
                  AND a.taxonomy_version=? WHERE r.dataset_id=? AND a.id IS NULL
            """,
                (MODEL_ID, TAXONOMY_VERSION, dataset_id),
            ).fetchone()[0]
            job_id = uuid.uuid4().hex
            connection.execute(
                "INSERT INTO jobs "
                "(id,dataset_id,model_id,taxonomy_version,status,total) VALUES (?,?,?,?,?,?)",
                (
                    job_id,
                    dataset_id,
                    MODEL_ID,
                    TAXONOMY_VERSION,
                    "queued" if total else "completed",
                    total,
                ),
            )
            row = connection.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
            return dict(row), total > 0

    def jobs(self, dataset_id: str) -> list[dict]:
        with self.connection() as connection:
            return [
                dict(row)
                for row in connection.execute(
                    "SELECT * FROM jobs WHERE dataset_id=? ORDER BY created_at DESC LIMIT 10",
                    (dataset_id,),
                ).fetchall()
            ]

    def update_job(
        self, job_id: str, status: str, processed: int, failed: int, error: str | None = None
    ) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET status=?,processed=?,failed=?,error=?,"
                "updated_at=strftime('%Y-%m-%dT%H:%M:%fZ','now') WHERE id=?",
                (status, processed, failed, error, job_id),
            )

    def interrupt_jobs(self) -> None:
        with self.connection() as connection:
            connection.execute(
                "UPDATE jobs SET status='interrupted',"
                "error='Application stopped; completed results are preserved.' "
                "WHERE status IN ('queued','running')"
            )
