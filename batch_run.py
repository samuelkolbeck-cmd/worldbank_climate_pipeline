"""
batch_run.py — Process all Excel submissions in a folder.

Usage:
  python batch_run.py                              # uses defaults
  python batch_run.py --input-folder submissions/
  python batch_run.py --input-folder submissions/ --output-db data/dashboard.db

GitHub Actions runs this script automatically when Excel files are pushed.
"""

import argparse
import sys
import time
from pathlib import Path

from pipeline import ETLPipeline
from utils import setup_logger


def main():
    parser = argparse.ArgumentParser(
        description="Batch-process all FinSAC Excel submissions into SQLite"
    )
    parser.add_argument(
        '--input-folder', default='submissions',
        help='Folder containing *.xlsx files (default: submissions/)'
    )
    parser.add_argument(
        '--output-db', default='data/dashboard.db',
        help='Output SQLite database (default: data/dashboard.db)'
    )
    parser.add_argument(
        '--config-dir', default='config',
        help='Config directory with YAML files (default: config/)'
    )
    args = parser.parse_args()

    logger = setup_logger('batch_run')

    # Collect Excel files
    folder = Path(args.input_folder)
    if not folder.exists():
        logger.error(f"Input folder not found: {folder}")
        sys.exit(1)

    excel_files = sorted(folder.glob('*.xlsx'))
    if not excel_files:
        logger.warning(f"No .xlsx files found in {folder}")
        sys.exit(0)

    logger.info(f"Found {len(excel_files)} Excel file(s) in '{folder}'")
    logger.info("=" * 70)

    # Process each file
    results = []  # list of (filename, success, duration_s)
    t_start_all = time.time()

    for excel_path in excel_files:
        logger.info(f"\nProcessing: {excel_path.name}")
        t_start = time.time()

        pipeline = ETLPipeline(
            config_dir=args.config_dir,
            output_db=args.output_db,
        )
        success = pipeline.run(str(excel_path))
        duration = round(time.time() - t_start, 2)

        results.append((excel_path.name, success, duration))

    total_time = round(time.time() - t_start_all, 2)

    # Summary report
    successes = [r for r in results if r[1]]
    failures  = [r for r in results if not r[1]]

    logger.info("\n" + "=" * 70)
    logger.info("BATCH SUMMARY")
    logger.info("=" * 70)
    for name, ok, dur in results:
        icon = "✅" if ok else "❌"
        logger.info(f"  {icon}  {name:<40} ({dur}s)")

    logger.info("-" * 70)
    logger.info(
        f"  Succeeded: {len(successes)} / {len(results)}   |   "
        f"Failed: {len(failures)}   |   Total time: {total_time}s"
    )

    if failures:
        logger.error("\nFailed files:")
        for name, _, _ in failures:
            logger.error(f"  - {name}")
        sys.exit(1)  # non-zero exit so GitHub Actions marks the job as failed

    logger.info(f"\nDatabase saved to: {args.output_db}")
    sys.exit(0)


if __name__ == '__main__':
    main()
