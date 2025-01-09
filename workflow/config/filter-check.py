import pandas as pd
import pyarrow.parquet as pq
import gzip
from pathlib import Path
from typing import Tuple, Dict
import numpy as np
import logging
from datetime import datetime
import sys

def setup_logger(log_dir: Path) -> logging.Logger:
    """Setup logger with both file and console handlers."""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger('validation_logger')
    logger.setLevel(logging.INFO)
    logger.handlers = []

    file_formatter = logging.Formatter(
        '%(asctime)s | %(levelname)-8s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_formatter = logging.Formatter('%(message)s')

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    file_handler = logging.FileHandler(
        log_dir / f'validation_log_{timestamp}.txt',
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(file_formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(console_formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

def analyze_csv_in_chunks(file_path: Path, logger: logging.Logger, chunk_size: int = 1_000_000) -> Dict:
    """Analyze CSV file in chunks to avoid memory issues."""
    metrics = {
        'total_rows': 0,
        'qv_ge_20': 0,
        'min_qv': float('inf'),
        'max_qv': float('-inf'),
        'columns': None
    }

    logger.info(f"Analyzing CSV in chunks of {chunk_size:,} rows")

    try:
        with gzip.open(file_path, 'rt') as f:
            for chunk_num, chunk in enumerate(pd.read_csv(f, chunksize=chunk_size)):
                chunk_rows = len(chunk)
                metrics['total_rows'] += chunk_rows

                if 'qv' in chunk.columns:
                    metrics['qv_ge_20'] += len(chunk[chunk['qv'] >= 20])
                    metrics['min_qv'] = min(metrics['min_qv'], chunk['qv'].min())
                    metrics['max_qv'] = max(metrics['max_qv'], chunk['qv'].max())

                if metrics['columns'] is None:
                    metrics['columns'] = set(chunk.columns)

                if (chunk_num + 1) % 10 == 0:
                    logger.info(f"Processed {metrics['total_rows']:,} rows...")

    except Exception as e:
        logger.error(f"Error processing CSV: {str(e)}")
        raise

    return metrics

def analyze_parquet(file_path: Path, logger: logging.Logger) -> Dict:
    """Analyze Parquet file using PyArrow for memory efficiency."""
    metrics = {
        'total_rows': 0,
        'qv_ge_20': 0,
        'min_qv': float('inf'),
        'max_qv': float('-inf'),
        'columns': None
    }

    try:
        parquet_file = pq.ParquetFile(file_path)
        metrics['total_rows'] = parquet_file.metadata.num_rows
        metrics['columns'] = set(parquet_file.schema.names)

        # Process in batches using row groups
        for row_group in range(parquet_file.num_row_groups):
            table = parquet_file.read_row_group(row_group)
            if 'qv' in table.column_names:
                qv_array = table.column('qv').to_numpy()
                metrics['qv_ge_20'] += np.sum(qv_array >= 20)
                metrics['min_qv'] = min(metrics['min_qv'], np.min(qv_array))
                metrics['max_qv'] = max(metrics['max_qv'], np.max(qv_array))

            if (row_group + 1) % 10 == 0:
                logger.info(f"Processed {(row_group + 1):,} row groups...")

    except Exception as e:
        logger.error(f"Error processing Parquet: {str(e)}")
        raise

    return metrics

def validate_filtered_transcripts(filtered_dir: Path, logger: logging.Logger) -> Dict:
    """Validate transcript files."""
    parent_dir = filtered_dir.parent

    files = {
        'original_csv': parent_dir / "transcripts.csv.gz",
        'filtered_csv': filtered_dir / "transcripts.csv.gz",
        'original_parquet': parent_dir / "transcripts.parquet",
        'filtered_parquet': filtered_dir / "transcripts.parquet"
    }

    metrics = {'file_sizes': {}, 'analysis': {}}

    # Get file sizes
    for file_type, file_path in files.items():
        if file_path.exists():
            metrics['file_sizes'][file_type] = file_path.stat().st_size / 1024 / 1024  # MB
            logger.info(f"\n{file_type} size: {metrics['file_sizes'][file_type]:.2f} MB")
        else:
            logger.warning(f"{file_type} not found: {file_path}")

    # Analyze each file
    for file_type, file_path in files.items():
        if not file_path.exists():
            continue

        logger.info(f"\nAnalyzing {file_type}...")

        try:
            if file_type.endswith('csv'):
                metrics['analysis'][file_type] = analyze_csv_in_chunks(file_path, logger)
            else:
                metrics['analysis'][file_type] = analyze_parquet(file_path, logger)

            logger.info(f"Analysis complete for {file_type}:")
            logger.info(f"  Total rows: {metrics['analysis'][file_type]['total_rows']:,}")
            logger.info(f"  Rows with QV >= 20: {metrics['analysis'][file_type]['qv_ge_20']:,}")
            logger.info(f"  QV range: {metrics['analysis'][file_type]['min_qv']:.2f} - {metrics['analysis'][file_type]['max_qv']:.2f}")

        except Exception as e:
            logger.error(f"Error analyzing {file_type}: {str(e)}")
            continue

    # Validate filtering
    logger.info("\nValidating filtering...")
    for fmt in ['csv', 'parquet']:
        orig_key = f'original_{fmt}'
        filt_key = f'filtered_{fmt}'

        if orig_key in metrics['analysis'] and filt_key in metrics['analysis']:
            orig_metrics = metrics['analysis'][orig_key]
            filt_metrics = metrics['analysis'][filt_key]

            logger.info(f"\n{fmt.upper()} format validation:")
            logger.info(f"  Original rows: {orig_metrics['total_rows']:,}")
            logger.info(f"  Expected filtered rows: {orig_metrics['qv_ge_20']:,}")
            logger.info(f"  Actual filtered rows: {filt_metrics['total_rows']:,}")
            logger.info(f"  Matches expected: {orig_metrics['qv_ge_20'] == filt_metrics['total_rows']}")
            logger.info(f"  All QV >= 20: {filt_metrics['min_qv'] >= 20}")

            size_ratio = metrics['file_sizes'][filt_key] / metrics['file_sizes'][orig_key]
            logger.info(f"  Size ratio (filtered/original): {size_ratio:.2f}x")

    return metrics

def main():
    """Main function to run the validation."""
    filtered_dir = Path("/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/outputs/TUQ97N/CHO-001/output-XETG00189__0010663__50452C-TUQ97N-EA__20240126__205019/qv20-filtered-transcripts")

    log_dir = filtered_dir / "validation_logs"
    logger = setup_logger(log_dir)

    logger.info("Starting validation process")
    logger.info(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Filtered directory: {filtered_dir}")
    logger.info(f"Original directory: {filtered_dir.parent}")

    try:
        metrics = validate_filtered_transcripts(filtered_dir, logger)
        logger.info("\nValidation process completed successfully")

    except Exception as e:
        logger.error(f"\nValidation process failed: {str(e)}")
        raise

if __name__ == "__main__":
    main()

