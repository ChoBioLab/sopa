#!/usr/bin/env python3

import os
import argparse
import logging
from pathlib import Path
import sys
from typing import List, Optional
import shutil
import pandas as pd
import pyarrow.parquet as pq
import zarr
import numpy as np

# Default settings
DEFAULT_EMAIL = "christopher.tastad@mssm.edu"
DEFAULT_CONDA_ENV = "/sc/arion/projects/untreatedIBD/ctastad/conda/envs/sopa"
DEFAULT_SOPA_SOURCE = "/sc/arion/projects/untreatedIBD/cache/tools/sopa"
DEFAULT_QUEUE = "premium"
BASE_DATA_PATH = "/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/outputs"
SCRATCH_BASE = f"/sc/arion/scratch/{os.environ.get('USER')}"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def validate_path(path: Path, path_type: str = "directory") -> bool:
    """Validate if a path exists and is of the correct type."""
    logger.info(f"Validating path: {path} (type: {path_type})")
    if path_type == "directory":
        result = path.is_dir()
    else:
        result = path.is_file()
    logger.info(f"Path validation {'succeeded' if result else 'failed'}")
    return result


def get_sample_directories(run_dir: Path) -> List[Path]:
    """Get all valid sample directories from the run directory."""
    logger.info(f"Scanning for sample directories in: {run_dir}")
    sample_dirs = [
        d for d in run_dir.iterdir()
        if d.is_dir()
        and d.name.startswith('output-')
        and d.name != 'lsf_scripts'
    ]
    logger.info(f"Found {len(sample_dirs)} sample directories")
    return sample_dirs


def parse_sample_name(directory_name: str) -> str:
    """Extract sample ID from the directory name."""
    logger.debug(f"Parsing sample name from directory: {directory_name}")
    try:
        parts = directory_name.replace('output-', '').split('__')
        sample_name = parts[2]
        logger.debug(f"Extracted sample name: {sample_name}")
        return sample_name
    except (IndexError, AttributeError):
        logger.error(f"Invalid directory name format: {directory_name}")
        return directory_name


def copy_workflow_to_scratch(workflow_path: Path, sample_name: str) -> Path:
    """Copy workflow directory to scratch with sample-specific name."""
    logger.info(f"Setting up scratch directory for sample: {sample_name}")
    scratch_dir = Path(SCRATCH_BASE)
    if not scratch_dir.exists():
        logger.info(f"Creating scratch base directory: {scratch_dir}")
        scratch_dir.mkdir(parents=True, exist_ok=True)

    target_dir = scratch_dir / f"sopa_{sample_name}"

    if target_dir.exists():
        logger.info(f"Removing existing scratch directory: {target_dir}")
        shutil.rmtree(target_dir)

    logger.info(f"Copying workflow from {workflow_path} to {target_dir}")
    shutil.copytree(workflow_path, target_dir)
    logger.info("Workflow copy completed successfully")

    return target_dir


def backup_original_files(data_path: Path) -> Path:
    """Create backup of original transcript files."""
    logger.info("Creating backup of original transcript files")
    backup_dir = data_path / "original_transcripts"
    backup_dir.mkdir(exist_ok=True)

    for file_name in ["transcripts.csv.gz", "transcripts.parquet", "transcripts.zarr.zip"]:
        src = data_path / file_name
        if src.exists():
            logger.info(f"Backing up {file_name}")
            shutil.copy2(src, backup_dir / file_name)

    return backup_dir


def filter_and_save_csv(data_path: Path) -> None:
    """Filter and save CSV data."""
    logger.info("Processing CSV file")
    csv_path = data_path / "transcripts.csv.gz"
    df = pd.read_csv(csv_path)
    filtered_df = df[df['qv'] >= 20]
    filtered_df.to_csv(csv_path, index=False, compression='gzip')


def filter_and_save_parquet(data_path: Path) -> None:
    """Filter and save Parquet data."""
    logger.info("Processing Parquet file")
    parquet_path = data_path / "transcripts.parquet"
    table = pq.read_table(parquet_path)
    df = table.to_pandas()
    filtered_df = df[df['qv'] >= 20]
    filtered_df.to_parquet(parquet_path, index=False)


def process_transcript_files(sample_dir: Path) -> None:
    """Process all transcript files with qv filtering."""
    logger.info(f"Processing transcript files in {sample_dir}")

    # Backup original files
    backup_dir = backup_original_files(sample_dir)

    try:
        # Process each file type
        filter_and_save_csv(sample_dir)
        filter_and_save_parquet(sample_dir)
        #filter_and_save_zarr(sample_dir)

        logger.info("Successfully filtered all transcript files")
    except Exception as e:
        logger.error(f"Error during filtering: {str(e)}")
        # Restore from backup
        logger.info("Restoring from backup")
        for file_name in ["transcripts.csv.gz", "transcripts.parquet", "transcripts.zarr.zip"]:
            src = backup_dir / file_name
            if src.exists():
                shutil.copy2(src, sample_dir / file_name)
        raise


def create_lsf_script(
    sample_name: str,
    data_path: str,
    conda_env: str,
    email: str,
    config_file: str,
    sopa_workflow: str,
    output_file: str,
    queue: str
) -> None:
    """Generate LSF submission script for a single sample."""
    logger.info(f"Generating LSF script for sample: {sample_name}")

    script_content = f"""#BSUB -J sopa-{sample_name}
#BSUB -P acc_untreatedIBD
#BSUB -W 48:00
#BSUB -q {queue}
#BSUB -n 8
#BSUB -R span[hosts=1]
#BSUB -R rusage[mem=8G]
#BSUB -u {email}
#BSUB -o output_{sample_name}_%J.stdout
#BSUB -eo error_{sample_name}_%J.stderr
#BSUB -L /bin/bash

# Generated LSF submission script
SOPA_WORKFLOW={sopa_workflow}
DATA_PATH={data_path}
SOPA_CONFIG_FILE={config_file}
CONDA_ENV={conda_env}

################################################################################

export http_proxy=http://172.28.7.1:3128
export https_proxy=http://172.28.7.1:3128
export all_proxy=http://172.28.7.1:3128
export no_proxy=localhost,*.chimera.hpc.mssm.edu,172.28.0.0/16

source /hpc/packages/minerva-centos7/anaconda3/2018.12/etc/profile.d/conda.sh
conda init bash
conda activate $CONDA_ENV

cd $SOPA_WORKFLOW 

snakemake \\
  --config data_path=$DATA_PATH \\
  --configfile=$SOPA_CONFIG_FILE \\
  --use-conda \\
  --profile lsf \\
  --resources mem_mb=15000000
"""

    logger.info(f"Writing LSF script to: {output_file}")
    with open(output_file, 'w') as f:
        f.write(script_content)

    logger.info("Setting script permissions")
    os.chmod(output_file, 0o755)


def main() -> None:
    logger.info("Starting SOPA LSF script generation")

    parser = argparse.ArgumentParser(
        description='Generate LSF submission scripts for SOPA pipeline'
    )
    parser.add_argument(
        '--id', required=True,
        help='[REQUIRED] Panel/Run ID (e.g., TUQ97N/CHO-001). Path to minerva-hosted xenium nfs assumed.'
    )
    parser.add_argument(
        '--config-name', required=True,
        help='[REQUIRED] Name of sopa config present in run dir (eg cellpose-baysor.yaml)'
    )
    parser.add_argument(
        '--sopa-source', default=DEFAULT_SOPA_SOURCE,
        help=f'Path to source SOPA workflow directory to copy from (default: {DEFAULT_SOPA_SOURCE})'
    )
    parser.add_argument(
        '--conda-env', default=DEFAULT_CONDA_ENV,
        help=f'Path to sopa conda environment (default: {DEFAULT_CONDA_ENV})'
    )
    parser.add_argument(
        '--email', default=DEFAULT_EMAIL,
        help=f'Email address for job notifications (default: {DEFAULT_EMAIL})'
    )
    parser.add_argument(
        '--queue', default=DEFAULT_QUEUE,
        help=f'LSF queue name (default: {DEFAULT_QUEUE})'
    )

    args = parser.parse_args()
    logger.info(f"Processing run ID: {args.id}")

    # Construct the full run directory path
    run_dir = Path(BASE_DATA_PATH) / args.id
    logger.info(f"Validating run directory: {run_dir}")
    if not validate_path(run_dir):
        logger.error(f"Run directory {run_dir} does not exist")
        sys.exit(1)

    # Validate source workflow directory
    logger.info(f"Validating SOPA source directory: {args.sopa_source}")
    sopa_source_path = Path(args.sopa_source)
    if not validate_path(sopa_source_path):
        logger.error(f"Source workflow directory {sopa_source_path} does not exist")
        sys.exit(1)

    # Validate config file
    logger.info(f"Validating config file: {args.config_name}")
    config_file = run_dir / args.config_name
    if not validate_path(config_file, "file"):
        logger.error(f"Config file {config_file} not found in run directory")
        sys.exit(1)

    # Find all potential sample directories
    sample_dirs = get_sample_directories(run_dir)
    if not sample_dirs:
        logger.error(f"No sample directories (output-*) found in {run_dir}")
        sys.exit(1)

    # Create scripts directory
    scripts_dir = run_dir / 'lsf_scripts'
    logger.info(f"Creating scripts directory: {scripts_dir}")
    scripts_dir.mkdir(exist_ok=True)

    # Generate LSF script for each sample
    logger.info(f"Processing {len(sample_dirs)} samples")
    for sample_dir in sample_dirs:
        sample_name = parse_sample_name(sample_dir.name)
        logger.info(f"Processing sample: {sample_name}")

        # Add the new filtering step
        process_transcript_files(sample_dir)

        scratch_workflow_path = os.path.join(copy_workflow_to_scratch(
            sopa_source_path,
            sample_name
        ), "workflow")

        output_file = scripts_dir / f"submit_{sample_name}.lsf"
        create_lsf_script(
            sample_name=sample_name,
            data_path=str(sample_dir.absolute()),
            conda_env=args.conda_env,
            email=args.email,
            config_file=str(config_file.absolute()),
            sopa_workflow=str(scratch_workflow_path),
            output_file=str(output_file),
            queue=args.queue
        )

    logger.info("LSF script generation completed successfully")


if __name__ == '__main__':
    main()

