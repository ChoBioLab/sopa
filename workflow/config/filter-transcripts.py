#!/usr/bin/env python3

from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
import logging
import shutil
from concurrent.futures import ThreadPoolExecutor
from typing import List
import argparse
import subprocess
import sys

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_validation(filtered_dir: Path) -> bool:
    """Run validation script on processed directory."""
    validation_script = Path(__file__).parent / "validate-transcripts.py"

    if not validation_script.exists():
        logger.error(f"Validation script not found: {validation_script}")
        return False

    logger.info(f"Running validation on: {filtered_dir}")
    try:
        # Call validation script with the filtered directory as an argument
        result = subprocess.run(
            [
                sys.executable,
                str(validation_script),
                "--filtered-dir", str(filtered_dir)
            ],
            capture_output=True,
            text=True
        )

        if result.returncode != 0:
            logger.error(f"Validation failed for {filtered_dir}")
            logger.error(f"Validation output:\n{result.stderr}")
            return False

        logger.info(f"Validation output:\n{result.stdout}")
        return True

    except Exception as e:
        logger.error(f"Error running validation: {str(e)}")
        return False


def filter_and_save_csv(source_path: Path, target_path: Path, dry_run: bool = False) -> None:
    """Filter and save CSV data with QV >= 20."""
    if dry_run:
        logger.info(f"[DRY RUN] Would process CSV file: {source_path}")
        return
    logger.info(f"Processing CSV file: {source_path}")
    df = pd.read_csv(source_path)
    filtered_df = df[df['qv'] >= 20]
    filtered_df.to_csv(target_path / "transcripts.csv.gz", index=False, compression='gzip')


def filter_and_save_parquet(source_path: Path, target_path: Path, dry_run: bool = False) -> None:
    """Filter and save Parquet data with QV >= 20."""
    if dry_run:
        logger.info(f"[DRY RUN] Would process Parquet file: {source_path}")
        return
    logger.info(f"Processing Parquet file: {source_path}")
    table = pq.read_table(source_path)
    df = table.to_pandas()
    filtered_df = df[df['qv'] >= 20]
    filtered_df.to_parquet(target_path / "transcripts.parquet", index=False)


def process_run_directory(run_dir: Path, dry_run: bool = False) -> None:
    """Process a single run directory if not already processed."""
    filtered_dir = run_dir / "qv20-filtered-transcripts"

    # Skip if already processed
    if filtered_dir.exists():
        logger.info(f"Would skip already processed run: {run_dir}")
        return

    try:
        # Create filtered directory
        if not dry_run:
            filtered_dir.mkdir(exist_ok=True)
        else:
            logger.info(f"[DRY RUN] Would create directory: {filtered_dir}")

        # Process CSV
        csv_path = run_dir / "transcripts.csv.gz"
        if csv_path.exists():
            filter_and_save_csv(csv_path, filtered_dir, dry_run)

        # Process Parquet
        parquet_path = run_dir / "transcripts.parquet"
        if parquet_path.exists():
            filter_and_save_parquet(parquet_path, filtered_dir, dry_run)

        if dry_run:
            logger.info(f"[DRY RUN] Would process: {run_dir}")
        else:
            logger.info(f"Successfully processed: {run_dir}")

            # Run validation after processing
            if not run_validation(filtered_dir):
                logger.error(f"Validation failed for {run_dir}")
                # Optionally, clean up if validation fails
                if not dry_run and filtered_dir.exists():
                    logger.warning(f"Cleaning up failed directory: {filtered_dir}")
                    shutil.rmtree(filtered_dir)

    except Exception as e:
        logger.error(f"Error processing {run_dir}: {str(e)}")
        # Clean up if there was an error and not in dry run mode
        if not dry_run and filtered_dir.exists():
            shutil.rmtree(filtered_dir)
        raise


def find_run_directories(base_path: Path) -> List[Path]:
    """Find all run directories containing transcript data."""
    run_dirs = []
    for panel_dir in base_path.glob("*"):
        if not panel_dir.is_dir():
            continue
        for run_id_dir in panel_dir.glob("*"):
            if not run_id_dir.is_dir():
                continue
            for output_dir in run_id_dir.glob("output-*"):
                if not output_dir.is_dir():
                    continue
                # Verify this is a valid run directory by checking for transcript files
                if (output_dir / "transcripts.csv.gz").exists() or \
                   (output_dir / "transcripts.parquet").exists():
                    run_dirs.append(output_dir)
    return run_dirs


def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description='Filter Xenium transcript data by QV scores'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform a dry run without making any changes'
    )
    parser.add_argument(
        '--base-path',
        type=str,
        default="/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/outputs",
        help='Base directory containing Xenium runs'
    )
    parser.add_argument(
        '--skip-validation',
        action='store_true',
        help='Skip validation after processing'
    )
    args = parser.parse_args()

    base_path = Path(args.base_path)

    # Find all run directories
    run_dirs = find_run_directories(base_path)
    logger.info(f"Found {len(run_dirs)} run directories to process")

    if args.dry_run:
        logger.info("=== DRY RUN MODE ===")
        logger.info("The following directories would be processed:")
        for run_dir in run_dirs:
            if not (run_dir / "qv20-filtered-transcripts").exists():
                logger.info(f"  - {run_dir}")

    # Process runs in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(
            lambda x: process_run_directory(x, args.dry_run),
            run_dirs
        ))


if __name__ == "__main__":
    main()
