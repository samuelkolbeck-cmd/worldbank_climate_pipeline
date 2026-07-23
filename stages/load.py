"""stages/load.py — Write processed rows to SQLite."""

from typing import List
from models import ProcessedDataRow, CountrySubmission
from database import Database
import yaml


def load_indicators(db: Database, indicators_path: str):
    """Seed the indicators reference table from indicators.yaml."""
    with open(indicators_path) as f:
        data = yaml.safe_load(f)

    for ind_id, ind in data.get('indicators', {}).items():
        db.upsert_indicator({
            'id': ind_id,
            'name': ind.get('name', ind_id),
            'module': ind.get('module'),
            'tier': ind.get('tier'),
            'data_type': ind.get('data_type'),
            'unit': ind.get('unit'),
            'source_type': ind.get('source_type'),
            'valid_range': ind.get('valid_range', [None, None]),
        })


def load(
    processed_rows: List[ProcessedDataRow],
    db: Database,
    submission: CountrySubmission,
    error_count: int = 0,
    warning_count: int = 0,
):
    """
    Write all processed rows to SQLite and log the submission.
    Uses INSERT OR IGNORE so reruns are safe.
    """
    for row in processed_rows:
        db.insert_country_data({
            'country_iso3':           row.country_code,
            'indicator_id':           row.indicator_id,
            'year':                   row.year,
            'value':                  row.value,
            'unit':                   row.unit,
            'source':                 row.source,
            'is_estimated':           row.is_estimated,
            'submission_date':        row.submission_date.isoformat(),
            'round_id':               row.round_id,
            'region_id':              row.region_id,
            'nace_node_id':           row.nace_node_id,
            'currency':               row.currency,
            'fx_rate_to_eur':         row.fx_rate_to_eur,
            'fx_rate_date':           row.fx_rate_date,
            'physical_risk':          row.physical_risk,
            'transition_risk':        row.transition_risk,
            'financial_vulnerability': row.financial_vulnerability,
            'ccr_score':              row.ccr_score,
            'ranking_position':       row.ranking_position,
        })
    db.conn.commit()

    meta = submission.metadata
    db.log_submission({
        'country_iso3':      meta.country_code,
        'analyst_name':      meta.analyst_name,
        'submission_date':   meta.submission_date.isoformat(),
        'round_id':          meta.round_id,
        'national_records':  len(submission.national_data),
        'regional_records':  len(submission.regional_data),
        'sectoral_records':  len(submission.sectoral_data),
        'validation_status': 'passed',
        'error_count':       error_count,
        'warning_count':     warning_count,
        'notes':             meta.notes,
    })
