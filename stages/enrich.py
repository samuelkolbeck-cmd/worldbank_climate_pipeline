"""
stages/enrich.py — Calculate Layer 5 scores for national-level rows.

Scores are only meaningful at the national (country) level.
Regional and sectoral rows pass through unchanged.

Layer 5 scoring:
  Physical Risk         = AVG(flood, drought, wildfire, landslide, vulnerability)
  Transition Risk       = weighted_avg(GHG×0.4, energy×0.3, coal×0.2, renewables×0.1)
                          → min-max normalised across all countries in the batch
  Financial Vulnerability = weighted_avg(debt×0.3, fiscal×0.2, CA×0.2, FX×0.2, doll×0.1)
                          → min-max normalised across all countries in the batch
  CCR Score             = 0.35×Physical + 0.40×Transition + 0.25×Financial
"""

from typing import List, Dict, Optional, Tuple
from models import ProcessedDataRow

# ---------------------------------------------------------------------------
# Indicator IDs used in scoring (from indicators.yaml)
# ---------------------------------------------------------------------------
PHYSICAL_COMPONENTS = [
    'i_002',   # Flood risk
    'i_003',   # Drought risk
    'i_004',   # Wildfire risk
    'i_005',   # Landslide risk
    'i_006',   # Vulnerability index
]

TRANSITION_COMPONENTS: Dict[str, float] = {
    'i_011': 0.40,   # GHG emissions
    'i_012': 0.30,   # Energy intensity
    'i_013': 0.20,   # Coal share
    'i_014': 0.10,   # Renewables share
}

FINANCIAL_COMPONENTS: Dict[str, float] = {
    'i_021': 0.30,   # Government debt / GDP
    'i_022': 0.20,   # Fiscal balance
    'i_023': 0.20,   # Current account
    'i_024': 0.20,   # FX reserves
    'i_025': 0.10,   # Dollarisation
}

CCR_WEIGHTS = {'physical': 0.35, 'transition': 0.40, 'financial': 0.25}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def enrich(processed_rows: List[ProcessedDataRow]) -> List[ProcessedDataRow]:
    """
    Populate physical_risk, transition_risk, financial_vulnerability,
    and ccr_score on national-level rows.

    Regional and sectoral rows are returned unchanged (scores = None).
    """
    # Build lookup: (country_code, indicator_id, year) → value
    # Only from national rows (region_id IS None and nace_node_id IS None)
    data: Dict[Tuple, float] = {}
    for row in processed_rows:
        if row.region_id is None and row.nace_node_id is None:
            data[(row.country_code, row.indicator_id, row.year)] = row.value

    countries = list({row.country_code for row in processed_rows})

    # Pre-compute raw transition / financial values for min-max normalisation
    transition_raw  = _compute_weighted_raws(data, countries, TRANSITION_COMPONENTS)
    financial_raw   = _compute_weighted_raws(data, countries, FINANCIAL_COMPONENTS)

    for row in processed_rows:
        if row.region_id is not None or row.nace_node_id is not None:
            continue  # skip sub-national rows

        cc, year = row.country_code, row.year

        row.physical_risk = _physical(cc, year, data)
        row.transition_risk = _normalise(
            transition_raw.get((cc, year)), transition_raw
        )
        row.financial_vulnerability = _normalise(
            financial_raw.get((cc, year)), financial_raw
        )

        if (row.physical_risk is not None
                and row.transition_risk is not None
                and row.financial_vulnerability is not None):
            row.ccr_score = round(
                CCR_WEIGHTS['physical']    * row.physical_risk +
                CCR_WEIGHTS['transition']  * row.transition_risk +
                CCR_WEIGHTS['financial']   * row.financial_vulnerability,
                3,
            )

    return processed_rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _physical(country: str, year: int, data: Dict) -> Optional[float]:
    vals = [
        data[(country, ind, year)]
        for ind in PHYSICAL_COMPONENTS
        if (country, ind, year) in data
    ]
    return round(sum(vals) / len(vals), 3) if vals else None


def _compute_weighted_raws(
    data: Dict,
    countries: List[str],
    components: Dict[str, float],
) -> Dict[Tuple, float]:
    """
    For each (country, year) pair compute the weighted average of
    the component indicators. Returns {(country, year): raw_value}.
    """
    years = list({k[2] for k in data})
    result = {}
    for country in countries:
        for year in years:
            wsum = 0.0
            wtot = 0.0
            for ind_id, weight in components.items():
                key = (country, ind_id, year)
                if key in data:
                    wsum += data[key] * weight
                    wtot += weight
            if wtot > 0:
                result[(country, year)] = wsum / wtot
    return result


def _normalise(
    raw: Optional[float],
    all_raws: Dict[Tuple, float],
) -> Optional[float]:
    if raw is None:
        return None
    vals = list(all_raws.values())
    if not vals:
        return None
    lo, hi = min(vals), max(vals)
    if hi == lo:
        return 0.5
    return round(min(1.0, max(0.0, (raw - lo) / (hi - lo))), 3)
