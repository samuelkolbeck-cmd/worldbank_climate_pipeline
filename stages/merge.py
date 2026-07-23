"""stages/merge.py — Deduplication and revision handling."""

from typing import List
from models import ProcessedDataRow
from database import Database


def merge(processed_rows: List[ProcessedDataRow], db: Database) -> List[ProcessedDataRow]:
    """
    Check for existing records in the current batch.
    (Cross-batch deduplication is safely handled by SQLite's INSERT OR IGNORE).
    """
    # round_id is already set from submission metadata (e.g. "2026-H1")
    # We just verify there is no exact duplicate (same round_id + same keys).
    # If there IS a match with the same round_id we skip (idempotent rerun).
    # This keeps the pipeline safe to run multiple times.

    deduped: List[ProcessedDataRow] = []
    seen: set = set()

    for row in processed_rows:
        key = (
            row.country_code,
            row.indicator_id,
            row.year,
            row.round_id,
            row.region_id,
            row.nace_node_id,
        )
        if key in seen:
            continue  # exact in-memory duplicate within this batch
        seen.add(key)
        deduped.append(row)

    return deduped
