import logging
from pathlib import Path
from typing import List, Dict
import yaml


def setup_logging() -> logging.Logger:
    """Configure and return logger instance."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    return logging.getLogger(__name__)


logger = setup_logging()


def flatten_dict(d: dict, parent_key: str = '', sep: str = '_') -> dict:
    """Flatten a nested dictionary, joining keys with separator."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def validate_path(path: Path, path_type: str = "directory") -> bool:
    """Validate if a path exists and is of the correct type."""
    logger.info(f"Validating path: {path} (type: {path_type})")
    if path_type == "directory":
        result = path.is_dir()
    else:
        result = path.is_file()
    logger.info(f"Path validation {'succeeded' if result else 'failed'}")
    return result


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
