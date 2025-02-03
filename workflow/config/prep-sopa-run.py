#!/usr/bin/env python3

import os
import argparse
import logging
from pathlib import Path
import sys
from typing import List, Optional
import shutil
import glob
from datetime import datetime
import yaml
import csv

# Default settings
DEFAULT_EMAIL = "christopher.tastad@mssm.edu"
DEFAULT_CONDA_ENV = "/sc/arion/projects/untreatedIBD/ctastad/conda/envs/sopa"
DEFAULT_SOPA_SOURCE = "/sc/arion/projects/untreatedIBD/cache/tools/sopa"
DEFAULT_QUEUE = "premium"
BASE_DATA_PATH = "/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/outputs"
SCRATCH_BASE = f"/sc/arion/scratch/{os.environ.get('USER')}"
PROJ_BASE_PATH = "/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/sopa"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def read_yaml_config(config_file: Path) -> dict:
    """Read and parse YAML config file."""
    with open(config_file, 'r') as f:
        try:
            config = yaml.safe_load(f)
            # Filter out commented fields (those starting with '_')
            return {k: v for k, v in config.items() if not k.startswith('_')}
        except yaml.YAMLError as e:
            logger.error(f"Error parsing config file: {e}")
            return {}


def create_params_log(
    sample_name: str,
    data_path: str,
    config_file: Path,
    conda_env: str,
    run_dir: Path
) -> Path:
    """Create a parameter log CSV file."""
    # Read config parameters
    config_params = read_yaml_config(config_file)

    # Create params dictionary
    params = {
        'sample_name': sample_name,
        'data_path': data_path,
        'config_file': str(config_file),
        'conda_env': conda_env,
        'run_dir': str(run_dir),
        'generation_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'run_completion_timestamp': ''  # Will be filled after run completion
    }

    # Add config parameters
    for k, v in config_params.items():
        params[f'config_{k}'] = str(v)

    # Create params log file
    params_file = run_dir / 'params_log.csv'
    with open(params_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=params.keys())
        writer.writeheader()
        writer.writerow(params)

    return params_file


def validate_path(path: Path, path_type: str = "directory") -> bool:
    """Validate if a path exists and is of the correct type."""
    logger.info(f"Validating path: {path} (type: {path_type})")
    if path_type == "directory":
        result = path.is_dir()
    else:
        result = path.is_file()
    logger.info(f"Path validation {'succeeded' if result else 'failed'}")
    return result


def get_sample_directories(source_data_dir: Path) -> List[Path]:
    """Get all valid sample directories from the source data directory."""
    logger.info(f"Scanning for sample directories in: {source_data_dir}")
    sample_dirs = [
        d for d in source_data_dir.iterdir()
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


def setup_transcript_directories(data_path: Path) -> None:
    """Set up and organize transcript directories and files."""
    logger.info(f"Setting up transcript directories in: {data_path}")

    # Create original-transcripts directory if it doesn't exist
    original_transcripts_dir = data_path / "original-transcripts"
    original_transcripts_dir.mkdir(exist_ok=True)

    # Check if original-transcripts already contains transcript files
    existing_transcripts = list(original_transcripts_dir.glob("transcripts.*"))
    if existing_transcripts:
        logger.info("Found existing transcript files in original-transcripts. Checking filtered transcripts...")

        # Ensure data_path transcripts match qv20-filtered-transcripts
        filtered_dir = data_path / "qv20-filtered-transcripts"
        if filtered_dir.exists():
            # Remove existing transcripts.* from data_path
            for transcript_file in data_path.glob("transcripts.*"):
                if transcript_file.is_file():
                    logger.info(f"Removing existing {transcript_file.name} from data_path")
                    transcript_file.unlink()

            # Copy fresh transcripts from qv20-filtered-transcripts
            for transcript_file in filtered_dir.glob("transcripts.*"):
                if transcript_file.is_file():
                    target_path = data_path / transcript_file.name
                    logger.info(f"Copying {transcript_file.name} from qv20-filtered-transcripts to data_path")
                    shutil.copy2(str(transcript_file), str(target_path))
        else:
            logger.warning("qv20-filtered-transcripts directory not found")
        return

    # If no existing transcripts in original-transcripts, proceed with normal setup
    # Move all transcripts.* files from data_path to original-transcripts
    for transcript_file in data_path.glob("transcripts.*"):
        if transcript_file.is_file():
            target_path = original_transcripts_dir / transcript_file.name
            if not target_path.exists():
                logger.info(f"Moving {transcript_file.name} to original-transcripts")
                shutil.move(str(transcript_file), str(target_path))

    # Copy transcripts.* from qv20-filtered-transcripts to data_path
    filtered_dir = data_path / "qv20-filtered-transcripts"
    if filtered_dir.exists():
        for transcript_file in filtered_dir.glob("transcripts.*"):
            if transcript_file.is_file():
                target_path = data_path / transcript_file.name
                if not target_path.exists():
                    logger.info(f"Copying {transcript_file.name} from qv20-filtered-transcripts to data_path")
                    shutil.copy2(str(transcript_file), str(target_path))
    else:
        logger.warning("qv20-filtered-transcripts directory not found")


def create_timestamped_run_dir(proj_dir: str, sample_name: str) -> Path:
    """Create a timestamped run directory for the sample."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M")
    run_dir_name = f"{sample_name}_{timestamp}"

    proj_path = Path(PROJ_BASE_PATH) / proj_dir
    run_dir = proj_path / run_dir_name

    logger.info(f"Creating run directory: {run_dir}")
    run_dir.mkdir(parents=True, exist_ok=True)

    return run_dir


def create_lsf_script(
    sample_name: str,
    data_path: str,
    conda_env: str,
    email: str,
    config_file: str,
    sopa_workflow: str,
    lsf_file: str,
    queue: str,
    proj_dir: str
) -> None:
    """Generate LSF submission script for a single sample."""
    logger.info(f"Generating LSF script for sample: {sample_name}")

    # Create the timestamped run directory path
    run_dir = create_timestamped_run_dir(proj_dir, sample_name)

    # Create params log
    params_file = create_params_log(
        sample_name=sample_name,
        data_path=data_path,
        config_file=Path(config_file),
        conda_env=conda_env,
        run_dir=run_dir
    )

    script_content = f"""#BSUB -J sopa-{sample_name}
#BSUB -P acc_untreatedIBD
#BSUB -W 24:00
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
RUN_OUT_DIR={run_dir}
PARAMS_LOG={params_file}

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
  --resources mem_mb=5000000

# Restore original transcript files
echo "Restoring original transcript files..."
cp $DATA_PATH/original-transcripts/transcripts.* $DATA_PATH/

# Post-run housekeeping
echo "Performing post-run housekeeping..."
mkdir -p $RUN_OUT_DIR

# Move explorer and zarr directories
mv $DATA_PATH.explorer $RUN_OUT_DIR/
mv $DATA_PATH.zarr $RUN_OUT_DIR/

# Copy config file and LSF script
cp $SOPA_CONFIG_FILE $RUN_OUT_DIR/
cp {lsf_file} $RUN_OUT_DIR/

# Update params log with completion timestamp
echo "Updating params log with completion timestamp..."
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
# Create temp file and swap to avoid any potential race conditions
awk -v timestamp="$TIMESTAMP" -F, 'NR==1{{print $0}}NR==2{{$NF=timestamp;print}}' "$PARAMS_LOG" > "$PARAMS_LOG.tmp"
mv "$PARAMS_LOG.tmp" "$PARAMS_LOG"

echo "Housekeeping completed. Output files moved to: $RUN_OUT_DIR"
"""

    logger.info(f"Writing LSF script to: {lsf_file}")
    with open(lsf_file, 'w') as f:
        f.write(script_content)

    logger.info("Setting script permissions")
    os.chmod(lsf_file, 0o755)


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
        '--project-dir', required=True,
        help='[REQUIRED] Project directory name for output organization'
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

    # Construct the full source data directory path
    source_data_dir = Path(BASE_DATA_PATH) / args.id
    logger.info(f"Validating source data directory: {source_data_dir}")
    if not validate_path(source_data_dir):
        logger.error(f"Source data directory {source_data_dir} does not exist")
        sys.exit(1)

    # Validate source workflow directory
    logger.info(f"Validating SOPA source directory: {args.sopa_source}")
    sopa_source_path = Path(args.sopa_source)
    if not validate_path(sopa_source_path):
        logger.error(f"Source workflow directory {sopa_source_path} does not exist")
        sys.exit(1)

    # Validate config file
    logger.info(f"Validating config file: {args.config_name}")
    config_file = source_data_dir / args.config_name
    if not validate_path(config_file, "file"):
        logger.error(f"Config file {config_file} not found in source data directory")
        sys.exit(1)

    # Find all potential sample directories
    sample_dirs = get_sample_directories(source_data_dir)
    if not sample_dirs:
        logger.error(f"No sample directories (output-*) found in {source_data_dir}")
        sys.exit(1)

    # Create scripts directory
    scripts_dir = source_data_dir / 'lsf_scripts'
    logger.info(f"Creating scripts directory: {scripts_dir}")
    scripts_dir.mkdir(exist_ok=True)

    # Generate LSF script for each sample
    logger.info(f"Processing {len(sample_dirs)} samples")
    for sample_dir in sample_dirs:
        # Set up transcript directories for each sample
        setup_transcript_directories(sample_dir)

        sample_name = parse_sample_name(sample_dir.name)
        logger.info(f"Processing sample: {sample_name}")

        scratch_workflow_path = os.path.join(copy_workflow_to_scratch(
            sopa_source_path,
            sample_name
        ), "workflow")

        lsf_file = scripts_dir / f"submit_{sample_name}.lsf"
        create_lsf_script(
            sample_name=sample_name,
            data_path=str(sample_dir.absolute()),
            conda_env=args.conda_env,
            email=args.email,
            config_file=str(config_file.absolute()),
            sopa_workflow=str(scratch_workflow_path),
            lsf_file=str(lsf_file),
            queue=args.queue,
            proj_dir=args.project_dir
        )

    logger.info("LSF script generation completed successfully")


if __name__ == '__main__':
    main()
