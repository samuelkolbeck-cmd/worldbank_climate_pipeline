-- Cloudflare D1 Database Schema for FinSAC Climate Dashboard

DROP TABLE IF EXISTS country_data;
DROP TABLE IF EXISTS indicators;
DROP TABLE IF EXISTS submissions_log;
DROP TABLE IF EXISTS country_scores;
DROP TABLE IF EXISTS countries;

CREATE TABLE indicators (
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

CREATE TABLE country_data (
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
    region_id TEXT,
    nace_node_id TEXT,
    currency TEXT,
    fx_rate_to_eur REAL,
    fx_rate_date TEXT,
    physical_risk REAL,
    transition_risk REAL,
    financial_vulnerability REAL,
    ccr_score REAL,
    ranking_position INTEGER,
    FOREIGN KEY (indicator_id) REFERENCES indicators(id),
    UNIQUE(country_code, indicator_id, year, round_id, region_id, nace_node_id)
);

CREATE TABLE submissions_log (
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

CREATE INDEX idx_cd_country ON country_data(country_code);
CREATE INDEX idx_cd_year ON country_data(year);
CREATE INDEX idx_cd_indicator ON country_data(indicator_id);
CREATE INDEX idx_cd_region ON country_data(region_id);
CREATE INDEX idx_cd_nace ON country_data(nace_node_id);
CREATE INDEX idx_cd_ccr ON country_data(ccr_score);
