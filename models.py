"""
models.py — Data models for the FinSAC country submission pipeline

Dataclasses flowing through each stage of the ETL pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Literal, Dict, Tuple
from enum import Enum
import re


# ============================================================
# ENUMS
# ============================================================

class Tier(Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"


class DataType(Enum):
    FLOAT = "float"
    INTEGER = "int"
    PERCENTAGE = "percentage"
    CATEGORICAL = "categorical"


class SourceType(Enum):
    AUTO = "auto"
    COUNTRY = "country"
    MANUAL = "manual"
    DROPPED = "dropped"


class RiskType(Enum):
    PHYSICAL = "Physical"
    TRANSITION = "Transition"
    FINANCIAL = "Financial"
    CROSS_CUTTING = "Cross-cutting"


class Module(Enum):
    CLIMATE_DATA = "Climate Data"
    REAL_ECONOMY = "Real Economy"
    CORE_FINANCIAL_HEALTH = "Core Financial Health"
    CLIMATE_FINANCE = "Climate Finance"
    REGIONAL_SECTORAL = "Regional & Sectoral"


class QualityFlag(Enum):
    VERIFIED = "verified"
    ESTIMATED = "estimated"
    PRELIMINARY = "preliminary"


class SubmissionStatus(Enum):
    RECEIVED = "received"
    VALIDATING = "validating"
    VALIDATED = "validated"
    MERGED = "merged"
    ENRICHED = "enriched"
    PUBLISHED = "published"
    FAILED = "failed"


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"


# ============================================================
# SUBMISSION MODELS
# ============================================================

@dataclass
class CountryMetadata:
    """
    Metadata from the 01_Submission_Metadata sheet.
    """
    country_code: str        # ISO3 (e.g. "BGR")
    round_id: str            # e.g. "2026-H1"
    data_as_of_year: int
    submission_date: datetime
    analyst_name: str
    analyst_email: str
    notes: Optional[str] = None

    def __post_init__(self):
        assert 1990 <= self.data_as_of_year <= 2030, \
            f"Invalid year: {self.data_as_of_year}"
        assert len(self.country_code) == 3, \
            f"Invalid ISO3 code: {self.country_code}"
        if not re.match(r'^\d{4}-(H[1-2]|Q[1-4])$', self.round_id):
            raise ValueError(
                f"Invalid round_id format: {self.round_id} "
                f"(expected YYYY-H1/H2 or YYYY-Q1-Q4)"
            )


@dataclass
class DataRow:
    """National-level data row (Sheet 06_Data_National)."""
    country_code: str
    year: int
    indicator_id: str
    value: float
    unit: str
    currency: Optional[str] = None
    fx_rate_to_eur: Optional[float] = None
    fx_rate_date: Optional[str] = None
    source: str = ""
    is_estimated: bool = False

    def __post_init__(self):
        assert 1990 <= self.year <= 2030, f"Invalid year: {self.year}"


@dataclass
class RegionalDataRow:
    """Regional-level data row (Sheet 07_Data_Regional)."""
    country_code: str
    region_id: str
    year: int
    indicator_id: str
    value: float
    unit: str
    currency: Optional[str] = None
    fx_rate_to_eur: Optional[float] = None
    fx_rate_date: Optional[str] = None
    source: str = ""
    is_estimated: bool = False

    def __post_init__(self):
        assert 1990 <= self.year <= 2030, f"Invalid year: {self.year}"


@dataclass
class SectoralDataRow:
    """Sectoral-level data row (Sheet 08_Data_Sectoral)."""
    country_code: str
    nace_node_id: str
    year: int
    indicator_id: str
    value: float
    unit: str
    currency: Optional[str] = None
    fx_rate_to_eur: Optional[float] = None
    fx_rate_date: Optional[str] = None
    source: str = ""
    is_estimated: bool = False

    def __post_init__(self):
        assert 1990 <= self.year <= 2030, f"Invalid year: {self.year}"


@dataclass
class CountrySubmission:
    """
    Complete parsed submission from a FinSAC _MP Excel file.
    Supports national, regional, and sectoral data granularities.
    """
    metadata: CountryMetadata
    national_data: List[DataRow] = field(default_factory=list)
    regional_data: List[RegionalDataRow] = field(default_factory=list)
    sectoral_data: List[SectoralDataRow] = field(default_factory=list)
    submission_file: Optional[str] = None

    @property
    def record_count(self) -> int:
        return len(self.national_data) + len(self.regional_data) + len(self.sectoral_data)

    def all_data_rows(self) -> List:
        return self.national_data + self.regional_data + self.sectoral_data


# ============================================================
# VALIDATION MODELS
# ============================================================

@dataclass
class ValidationError:
    """A validation issue (error or warning) found during processing."""
    severity: Severity
    stage: str
    rule_id: Optional[str] = None
    indicator_id: Optional[str] = None
    row: Optional[int] = None
    column: Optional[str] = None
    message: str = ""

    # Alias so pipeline.py can use err.error_type
    @property
    def error_type(self) -> str:
        return self.rule_id or "unknown"

    def __str__(self) -> str:
        loc = ""
        if self.row:
            loc += f"row {self.row}"
        if self.column:
            loc += f" col {self.column}"
        if loc:
            loc = f" ({loc})"
        return f"[{self.stage.upper()}] {self.severity.value.upper()}{loc}: {self.message}"


@dataclass
class ValidationResult:
    """Result of validation process for a single submission."""
    submission: CountrySubmission
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationError] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def add_error(self, rule_id: str, message: str, **kwargs):
        self.errors.append(ValidationError(
            severity=Severity.ERROR,
            stage=kwargs.pop('stage', 'validate'),
            rule_id=rule_id,
            message=message,
            **kwargs
        ))

    def add_warning(self, rule_id: str, message: str, **kwargs):
        self.warnings.append(ValidationError(
            severity=Severity.WARNING,
            stage=kwargs.pop('stage', 'validate'),
            rule_id=rule_id,
            message=message,
            **kwargs
        ))


# ============================================================
# PROCESSED DATA MODELS
# ============================================================

@dataclass
class ProcessedDataRow:
    """
    A single data row after all transformation stages.
    Ready to load into SQLite and seed into D1.
    Supports all three granularities (national / regional / sectoral).
    """
    country_code: str
    indicator_id: str
    year: int
    value: float
    source: str
    submission_date: datetime
    round_id: str       # e.g. "2026-H1"
    unit: str
    is_estimated: bool = False

    # Geographic granularity (None = national)
    region_id: Optional[str] = None
    nace_node_id: Optional[str] = None

    # Currency info
    currency: Optional[str] = None
    fx_rate_to_eur: Optional[float] = None
    fx_rate_date: Optional[str] = None

    # Layer 5 scores (populated in Enrich stage — national level only)
    physical_risk: Optional[float] = None
    transition_risk: Optional[float] = None
    financial_vulnerability: Optional[float] = None
    ccr_score: Optional[float] = None
    ranking_position: Optional[int] = None


# ============================================================
# LAYER 5 SCORE MODELS
# ============================================================

@dataclass
class CCRScore:
    """Composite Climate Credit Risk Score."""
    country_code: str
    year: int
    physical_risk: float
    transition_risk: float
    financial_vulnerability: float
    ccr_score: float
    ranking_position: Optional[int] = None

    @classmethod
    def from_components(
        cls,
        country_code: str,
        year: int,
        physical_risk: float,
        transition_risk: float,
        financial_vulnerability: float,
        physical_weight: float = 0.35,
        transition_weight: float = 0.40,
        financial_weight: float = 0.25,
    ) -> "CCRScore":
        ccr = (
            physical_risk * physical_weight +
            transition_risk * transition_weight +
            financial_vulnerability * financial_weight
        )
        return cls(
            country_code=country_code,
            year=year,
            physical_risk=physical_risk,
            transition_risk=transition_risk,
            financial_vulnerability=financial_vulnerability,
            ccr_score=round(ccr, 3),
        )


# ============================================================
# REPORTING MODELS
# ============================================================

@dataclass
class PipelineMetrics:
    """Metrics from a full pipeline run (used by batch_run.py)."""
    countries_received: int
    countries_succeeded: int
    countries_failed: int
    total_records_processed: int
    total_errors: int
    total_warnings: int
    runtime_seconds: float

    @property
    def success_rate(self) -> float:
        if self.countries_received == 0:
            return 0.0
        return (self.countries_succeeded / self.countries_received) * 100
