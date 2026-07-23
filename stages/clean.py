"""stages/clean.py — Standardise and convert data rows."""

from typing import List
from models import (
    CountrySubmission, ProcessedDataRow,
    DataRow, RegionalDataRow, SectoralDataRow,
)


def clean(submission: CountrySubmission) -> List[ProcessedDataRow]:
    """
    Convert all raw data rows (national / regional / sectoral) into
    ProcessedDataRow objects ready for merge and enrich stages.

    Applies:
    - Null value handling (default 0.0)
    - Unit string normalisation
    - Copies currency / FX info through unchanged
      (actual unit conversion can be wired in here when needed)
    """
    processed: List[ProcessedDataRow] = []
    meta = submission.metadata

    for row in submission.national_data:
        processed.append(ProcessedDataRow(
            country_code=meta.country_code,
            indicator_id=row.indicator_id,
            year=row.year,
            value=_safe_float(row.value),
            source=row.source,
            submission_date=meta.submission_date,
            round_id=meta.round_id,
            unit=row.unit or "",
            is_estimated=row.is_estimated,
            region_id=None,
            nace_node_id=None,
            currency=row.currency,
            fx_rate_to_eur=row.fx_rate_to_eur,
            fx_rate_date=row.fx_rate_date,
        ))

    for row in submission.regional_data:
        processed.append(ProcessedDataRow(
            country_code=meta.country_code,
            indicator_id=row.indicator_id,
            year=row.year,
            value=_safe_float(row.value),
            source=row.source,
            submission_date=meta.submission_date,
            round_id=meta.round_id,
            unit=row.unit or "",
            is_estimated=row.is_estimated,
            region_id=row.region_id,
            nace_node_id=None,
            currency=row.currency,
            fx_rate_to_eur=row.fx_rate_to_eur,
            fx_rate_date=row.fx_rate_date,
        ))

    for row in submission.sectoral_data:
        processed.append(ProcessedDataRow(
            country_code=meta.country_code,
            indicator_id=row.indicator_id,
            year=row.year,
            value=_safe_float(row.value),
            source=row.source,
            submission_date=meta.submission_date,
            round_id=meta.round_id,
            unit=row.unit or "",
            is_estimated=row.is_estimated,
            region_id=None,
            nace_node_id=row.nace_node_id,
            currency=row.currency,
            fx_rate_to_eur=row.fx_rate_to_eur,
            fx_rate_date=row.fx_rate_date,
        ))

    return processed


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
