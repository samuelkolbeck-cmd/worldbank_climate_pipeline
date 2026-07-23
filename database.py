"""
database.py — SQLite schema and queries for the climate pipeline.

The schema here mirrors the Cloudflare D1 schema in d1_schema.sql exactly,
so that export_d1.py can generate a compatible seed file.
"""

import sqlite3
from pathlib import Path
from datetime import datetime


class Database:
    def __init__(self, db_path: str = "data/dashboard.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        """Create tables if they don't exist."""
        cursor = self.conn.cursor()

        cursor.executescript("""
            CREATE TABLE IF NOT EXISTS indicators (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                module TEXT,
                tier TEXT,
                data_type TEXT,
                unit TEXT,
                source_type TEXT,
                valid_range_min REAL,
                valid_range_max REAL
            );

            CREATE TABLE IF NOT EXISTS country_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code TEXT NOT NULL,
                indicator_id TEXT NOT NULL,
                year INTEGER NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                source TEXT,
                is_estimated INTEGER DEFAULT 0,
                submission_date DATETIME NOT NULL,
                round_id TEXT NOT NULL,
                -- geographic granularity (NULL = national)
                region_id TEXT,
                nace_node_id TEXT,
                -- currency
                currency TEXT,
                fx_rate_to_eur REAL,
                fx_rate_date TEXT,
                -- Layer 5 scores (national level only)
                physical_risk REAL,
                transition_risk REAL,
                financial_vulnerability REAL,
                ccr_score REAL,
                ranking_position INTEGER,
                UNIQUE(country_code, indicator_id, year, round_id, region_id, nace_node_id)
            );

            CREATE TABLE IF NOT EXISTS submissions_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                country_code TEXT NOT NULL,
                analyst_name TEXT,
                submission_date DATETIME NOT NULL,
                round_id TEXT NOT NULL,
                national_records INTEGER DEFAULT 0,
                regional_records INTEGER DEFAULT 0,
                sectoral_records INTEGER DEFAULT 0,
                validation_status TEXT,
                error_count INTEGER DEFAULT 0,
                warning_count INTEGER DEFAULT 0,
                notes TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_cd_country ON country_data(country_code);
            CREATE INDEX IF NOT EXISTS idx_cd_year ON country_data(year);
            CREATE INDEX IF NOT EXISTS idx_cd_indicator ON country_data(indicator_id);
            CREATE INDEX IF NOT EXISTS idx_cd_region ON country_data(region_id);
            CREATE INDEX IF NOT EXISTS idx_cd_nace ON country_data(nace_node_id);
            CREATE INDEX IF NOT EXISTS idx_cd_ccr ON country_data(ccr_score);
        """)
        self.conn.commit()

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------

    def upsert_indicator(self, indicator: dict):
        """Insert or replace indicator definition."""
        self.conn.execute("""
            INSERT OR REPLACE INTO indicators
            (id, name, module, tier, data_type, unit, source_type,
             valid_range_min, valid_range_max)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            indicator['id'],
            indicator['name'],
            indicator.get('module'),
            indicator.get('tier'),
            indicator.get('data_type'),
            indicator.get('unit'),
            indicator.get('source_type'),
            indicator.get('valid_range', [None, None])[0],
            indicator.get('valid_range', [None, None])[1],
        ))
        self.conn.commit()

    # ------------------------------------------------------------------
    # Country data
    # ------------------------------------------------------------------

    def insert_country_data(self, row: dict):
        """Insert a processed data row (ignore duplicates)."""
        self.conn.execute("""
            INSERT OR IGNORE INTO country_data
            (country_code, indicator_id, year, value, unit, source,
             is_estimated, submission_date, round_id,
             region_id, nace_node_id,
             currency, fx_rate_to_eur, fx_rate_date,
             physical_risk, transition_risk, financial_vulnerability,
             ccr_score, ranking_position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            row['country_code'],
            row['indicator_id'],
            row['year'],
            row['value'],
            row.get('unit'),
            row.get('source'),
            1 if row.get('is_estimated') else 0,
            row['submission_date'],
            row['round_id'],
            row.get('region_id'),
            row.get('nace_node_id'),
            row.get('currency'),
            row.get('fx_rate_to_eur'),
            row.get('fx_rate_date'),
            row.get('physical_risk'),
            row.get('transition_risk'),
            row.get('financial_vulnerability'),
            row.get('ccr_score'),
            row.get('ranking_position'),
        ))
        self.conn.commit()

    def get_latest_round(self, country_code: str, indicator_id: str,
                         year: int, region_id=None, nace_node_id=None) -> str:
        """Return the latest round_id string for a record, or empty string."""
        cursor = self.conn.execute("""
            SELECT round_id FROM country_data
            WHERE country_code = ?
              AND indicator_id = ?
              AND year = ?
              AND (region_id IS ? OR region_id = ?)
              AND (nace_node_id IS ? OR nace_node_id = ?)
            ORDER BY round_id DESC
            LIMIT 1
        """, (country_code, indicator_id, year,
              region_id, region_id,
              nace_node_id, nace_node_id))
        result = cursor.fetchone()
        return result['round_id'] if result else ""

    # ------------------------------------------------------------------
    # Submissions log
    # ------------------------------------------------------------------

    def log_submission(self, log: dict):
        """Write a submission audit entry."""
        self.conn.execute("""
            INSERT INTO submissions_log
            (country_code, analyst_name, submission_date, round_id,
             national_records, regional_records, sectoral_records,
             validation_status, error_count, warning_count, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            log['country_code'],
            log.get('analyst_name'),
            log['submission_date'],
            log['round_id'],
            log.get('national_records', 0),
            log.get('regional_records', 0),
            log.get('sectoral_records', 0),
            log.get('validation_status', 'passed'),
            log.get('error_count', 0),
            log.get('warning_count', 0),
            log.get('notes'),
        ))
        self.conn.commit()

    def close(self):
        self.conn.close()
