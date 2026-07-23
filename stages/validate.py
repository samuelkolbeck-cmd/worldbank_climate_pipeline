"""stages/validate.py — Validate a CountrySubmission against config rules."""

from typing import Dict, List
import yaml

from models import CountrySubmission, ValidationResult


def _load_yaml(path: str) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


def validate(
    submission: CountrySubmission,
    rules_path: str,
    indicators_path: str,
) -> ValidationResult:
    """
    Validate submission.  Returns ValidationResult with errors / warnings.
    Errors are fatal; warnings are logged but pipeline continues.
    """
    result = ValidationResult(submission=submission)

    try:
        indicators = _load_yaml(indicators_path).get('indicators', {})

        meta = submission.metadata

        # --- Metadata checks ---
        if not meta.country_code:
            result.add_error('country_code_required', 'country_code is missing')

        if not (1990 <= meta.data_as_of_year <= 2030):
            result.add_error(
                'year_range',
                f"data_as_of_year {meta.data_as_of_year} out of range [1990-2030]",
            )

        # --- National data ---
        seen_national: set = set()
        for idx, row in enumerate(submission.national_data, 2):
            key = (row.indicator_id, row.year)
            if key in seen_national:
                result.add_error(
                    'duplicate_national',
                    f"Duplicate national row: {row.indicator_id} year {row.year}",
                    row=idx,
                )
            seen_national.add(key)

            if row.indicator_id not in indicators:
                result.add_warning(
                    'unknown_indicator',
                    f"Unknown indicator: {row.indicator_id}",
                    indicator_id=row.indicator_id, row=idx,
                )
            else:
                ind = indicators[row.indicator_id]
                _check_range(result, row.value, ind, row.indicator_id, idx)

        # --- Regional data ---
        seen_regional: set = set()
        for idx, row in enumerate(submission.regional_data, 2):
            key = (row.indicator_id, row.region_id, row.year)
            if key in seen_regional:
                result.add_error(
                    'duplicate_regional',
                    f"Duplicate regional row: {row.indicator_id} "
                    f"region {row.region_id} year {row.year}",
                    row=idx,
                )
            seen_regional.add(key)

        # --- Sectoral data ---
        seen_sectoral: set = set()
        for idx, row in enumerate(submission.sectoral_data, 2):
            key = (row.indicator_id, row.nace_node_id, row.year)
            if key in seen_sectoral:
                result.add_error(
                    'duplicate_sectoral',
                    f"Duplicate sectoral row: {row.indicator_id} "
                    f"NACE {row.nace_node_id} year {row.year}",
                    row=idx,
                )
            seen_sectoral.add(key)

        # --- Coverage check ---
        if submission.record_count == 0:
            result.add_error('no_records', 'Submission contains zero data rows')
        elif submission.record_count < 5:
            result.add_warning(
                'few_records',
                f"Only {submission.record_count} records — expected more",
            )

    except Exception as exc:
        result.add_error('validation_exception', f"Unexpected error: {exc}")

    return result


def _check_range(result: ValidationResult, value: float,
                 indicator: dict, ind_id: str, row_idx: int):
    """Warn if value is outside the indicator's valid_range."""
    valid_range = indicator.get('valid_range')
    if valid_range and len(valid_range) == 2:
        lo, hi = valid_range
        if lo is not None and hi is not None:
            if not (lo <= value <= hi):
                result.add_warning(
                    'out_of_range',
                    f"Value {value} outside range [{lo}, {hi}]",
                    indicator_id=ind_id, row=row_idx,
                )
