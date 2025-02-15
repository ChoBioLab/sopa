from pathlib import Path
import shutil
import yaml
from datetime import datetime
import csv
from typing import Dict
from .utils import logger, flatten_dict
from .config import DEFAULT_CONFIG_FIELDS, SCRATCH_BASE


def read_yaml_config(config_file: Path) -> dict:
    """Read and parse YAML config file, flattening all fields."""
    try:
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
            if config is None:
                return DEFAULT_CONFIG_FIELDS

            flat_config = flatten_dict(config)
            all_fields = DEFAULT_CONFIG_FIELDS.copy()

            for k, v in flat_config.items():
                if k in all_fields:
                    all_fields[k] = str(v) if v is not None else ''

            return all_fields

    except yaml.YAMLError as e:
        logger.error(f"Error parsing config file: {e}")
        return DEFAULT_CONFIG_FIELDS
    except Exception as e:
        logger.error(f"Unexpected error reading config file: {e}")
        return DEFAULT_CONFIG_FIELDS


def create_params_log(
    sample_name: str,
    data_path: str,
    config_file: Path,
    conda_env: str,
    run_dir: Path,
    proj_dir: str
) -> Path:
    """Create a parameter log CSV file."""
    config_params = read_yaml_config(config_file)

    params = {
        'sample_name': sample_name,
        'proj_dir': proj_dir,
        'generation_timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'run_completion_timestamp': '',
        'data_path': data_path,
        'config_file': str(config_file),
        'conda_env': conda_env,
        'run_dir': str(run_dir)
    }

    for k, v in config_params.items():
        params[k] = str(v) if v is not None else ''

    ordered_columns = [
        'sample_name',
        'proj_dir',
        'generation_timestamp',
        'run_completion_timestamp'
    ] + [k for k in params.keys() if k not in {
        'sample_name', 'proj_dir', 'generation_timestamp', 'run_completion_timestamp'
    }]

    params_file = run_dir / 'params_log.csv'
    with open(params_file, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=ordered_columns)
        writer.writeheader()
        writer.writerow(params)

    return params_file


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
