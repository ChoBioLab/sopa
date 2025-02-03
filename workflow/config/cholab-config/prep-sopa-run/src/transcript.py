from pathlib import Path
import shutil
from .utils import logger


def setup_transcript_directories(data_path: Path) -> None:
    """Set up and organize transcript directories and files."""
    logger.info(f"Setting up transcript directories in: {data_path}")

    original_transcripts_dir = data_path / "original-transcripts"
    original_transcripts_dir.mkdir(exist_ok=True)

    existing_transcripts = list(original_transcripts_dir.glob("transcripts.*"))
    if existing_transcripts:
        logger.info("Found existing transcript files in original-transcripts. Checking filtered transcripts...")

        filtered_dir = data_path / "qv20-filtered-transcripts"
        if filtered_dir.exists():
            for transcript_file in data_path.glob("transcripts.*"):
                if transcript_file.is_file():
                    logger.info(f"Removing existing {transcript_file.name} from data_path")
                    transcript_file.unlink()

            for transcript_file in filtered_dir.glob("transcripts.*"):
                if transcript_file.is_file():
                    target_path = data_path / transcript_file.name
                    logger.info(f"Copying {transcript_file.name} from qv20-filtered-transcripts to data_path")
                    shutil.copy2(str(transcript_file), str(target_path))
        else:
            logger.warning("qv20-filtered-transcripts directory not found")
        return

    for transcript_file in data_path.glob("transcripts.*"):
        if transcript_file.is_file():
            target_path = original_transcripts_dir / transcript_file.name
            if not target_path.exists():
                logger.info(f"Moving {transcript_file.name} to original-transcripts")
                shutil.move(str(transcript_file), str(target_path))

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
