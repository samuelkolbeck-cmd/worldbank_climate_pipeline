"""pipeline.py — Orchestrates the 6-stage ETL for a single Excel file."""

import logging
from pathlib import Path

from stages.ingest   import ingest
from stages.validate import validate
from stages.clean    import clean
from stages.merge    import merge
from stages.enrich   import enrich
from stages.load     import load, load_indicators
from database        import Database
from utils           import setup_logger


class ETLPipeline:

    def __init__(
        self,
        config_dir: str = "config",
        output_db:  str = "data/dashboard.db",
    ):
        self.config_dir = config_dir
        self.output_db  = output_db
        self.logger     = setup_logger(__name__)
        self.db         = Database(output_db)

    def run(self, excel_path: str) -> bool:
        """
        Run the full 6-stage pipeline for one Excel submission.

        Stages:
          1. Ingest   — parse Excel (national + regional + sectoral sheets)
          2. Validate — check rules, known indicators, duplicate rows
          3. Clean    — standardise, null-handle, normalise units
          4. Merge    — deduplicate within batch
          5. Enrich   — calculate Layer 5 scores (national level)
          6. Load     — write to SQLite

        Returns True on success, False on failure.
        """
        self.logger.info("=" * 70)
        self.logger.info(f"Processing: {excel_path}")

        try:
            # ── Stage 1: Ingest ──────────────────────────────────────────
            self.logger.info("Stage 1: Ingest")
            submission, ingest_errors = ingest(excel_path)

            for err in ingest_errors:
                lvl = err.get('severity', 'warning')
                msg = f"  [{err.get('sheet', 'ingest')}] {err.get('message')}"
                (self.logger.error if lvl == 'error' else self.logger.warning)(msg)

            if submission is None:
                self.logger.error("  ✗ Ingest failed — no submission returned")
                return False

            self.logger.info(
                f"  ✓ {submission.metadata.country_code}  "
                f"national={len(submission.national_data)}  "
                f"regional={len(submission.regional_data)}  "
                f"sectoral={len(submission.sectoral_data)}"
            )

            # ── Stage 2: Validate ────────────────────────────────────────
            self.logger.info("Stage 2: Validate")
            result = validate(
                submission,
                f"{self.config_dir}/validation_rules.yaml",
                f"{self.config_dir}/indicators.yaml",
            )

            for err in result.errors:
                self.logger.error(f"  ERROR  — {err.error_type}: {err.message}")
            for warn in result.warnings:
                self.logger.warning(f"  WARN   — {warn.error_type}: {warn.message}")

            if result.errors:
                self.logger.error(
                    f"  ✗ Validation failed ({len(result.errors)} errors)"
                )
                return False

            self.logger.info(
                f"  ✓ Passed  ({len(result.warnings)} warnings)"
            )

            # ── Stage 3: Clean ───────────────────────────────────────────
            self.logger.info("Stage 3: Clean")
            cleaned = clean(submission)
            self.logger.info(f"  ✓ {len(cleaned)} rows cleaned")

            # ── Stage 4: Merge ───────────────────────────────────────────
            self.logger.info("Stage 4: Merge")
            merged = merge(cleaned, self.db)
            self.logger.info(f"  ✓ {len(merged)} rows after deduplication")

            # ── Stage 5: Enrich ──────────────────────────────────────────
            self.logger.info("Stage 5: Enrich (Layer 5 scores)")
            enriched = enrich(merged)
            scored = sum(1 for r in enriched if r.ccr_score is not None)
            self.logger.info(f"  ✓ {scored} national rows scored")

            # ── Stage 6: Load ────────────────────────────────────────────
            self.logger.info("Stage 6: Load")
            try:
                load_indicators(self.db, f"{self.config_dir}/indicators.yaml")
            except Exception as exc:
                self.logger.warning(f"  Could not seed indicators table: {exc}")

            load(
                enriched, self.db, submission,
                error_count=len(result.errors),
                warning_count=len(result.warnings),
            )
            self.logger.info(f"  ✓ {len(enriched)} rows written to database")

            self.logger.info(
                f"Pipeline complete: {submission.metadata.country_code} ✓"
            )
            return True

        except Exception as exc:
            self.logger.error(f"Pipeline exception: {exc}", exc_info=True)
            return False

        finally:
            self.db.close()
