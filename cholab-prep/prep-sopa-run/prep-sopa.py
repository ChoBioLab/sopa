#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

from src import (
    DEFAULT_EMAIL,
    DEFAULT_CONDA_ENV,
    DEFAULT_SOPA_SOURCE,
    DEFAULT_QUEUE,
    BASE_DATA_PATH,
    PROJ_BASE_PATH,
    MAX_JOB_RAM,
    setup_logging,
    validate_path,
    get_sample_directories,
    parse_sample_name,
    copy_workflow_to_scratch,
    setup_transcript_directories,
    create_timestamped_run_dir,
    create_lsf_script,
    create_params_log
)


def main() -> None:
    logger = setup_logging()
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
    parser.add_argument(
        '--max-ram', default=MAX_JOB_RAM,
        help=f'Maximum combined RAM to not exceed by all processes (default: {MAX_JOB_RAM})'
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

        # Create workflow in scratch
        scratch_workflow_path = copy_workflow_to_scratch(
            sopa_source_path,
            sample_name
        )
        workflow_path = scratch_workflow_path / "workflow"

        # Create run directory
        run_dir = create_timestamped_run_dir(
            args.project_dir,
            sample_name,
            PROJ_BASE_PATH
        )

        # Create params log
        params_file = create_params_log(
            sample_name=sample_name,
            data_path=str(sample_dir.absolute()),
            config_file=config_file,
            conda_env=args.conda_env,
            run_dir=run_dir,
            proj_dir=args.project_dir
        )

        # Create LSF script
        lsf_file = scripts_dir / f"submit_{sample_name}.lsf"
        create_lsf_script(
            sample_name=sample_name,
            data_path=str(sample_dir.absolute()),
            conda_env=args.conda_env,
            email=args.email,
            config_file=str(config_file.absolute()),
            sopa_workflow=str(workflow_path),
            lsf_file=str(lsf_file),
            queue=args.queue,
            proj_dir=args.project_dir,
            run_dir=run_dir,
            params_file=params_file,
            max_ram=args.max_ram
        )

    logger.info("LSF script generation completed successfully")


if __name__ == '__main__':
    main()
