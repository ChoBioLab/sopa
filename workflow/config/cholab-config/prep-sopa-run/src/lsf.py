from pathlib import Path
import os
from datetime import datetime
from .utils import logger


def create_timestamped_run_dir(proj_dir: str, sample_name: str, base_path: str) -> Path:
    """Create a timestamped run directory for the sample."""
    timestamp = datetime.now().strftime("%Y-%m-%d-%H%M")
    run_dir_name = f"{sample_name}_{timestamp}"

    proj_path = Path(base_path) / proj_dir
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
    proj_dir: str,
    run_dir: Path,
    params_file: Path,
    max_ram: int
) -> None:
    """Generate LSF submission script for a single sample."""
    logger.info(f"Generating LSF script for sample: {sample_name}")

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
MAX_JOB_RAM={max_ram}

################################################################################

export http_proxy=http://172.28.7.1:3128
export https_proxy=http://172.28.7.1:3128
export all_proxy=http://172.28.7.1:3128
export no_proxy=localhost,*.chimera.hpc.mssm.edu,172.28.0.0/16

source /hpc/packages/minerva-centos7/anaconda3/2018.12/etc/profile.d/conda.sh
conda init bash
conda activate $CONDA_ENV

# Redirect stdout and stderr using exec
exec 1> "$RUN_OUT_DIR/output_{sample_name}.stdout"
exec 2> "$RUN_OUT_DIR/error_{sample_name}.stderr"

cd $SOPA_WORKFLOW

snakemake \\
  --config data_path=$DATA_PATH \\
  --configfile=$SOPA_CONFIG_FILE \\
  --use-conda \\
  --profile lsf \\
  --resources mem_mb=$MAX_JOB_RAM

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
awk -v timestamp="$TIMESTAMP" -F, 'BEGIN{{OFS=","}} NR==1{{print $0}}NR==2{{$NF=timestamp;print}}' "$PARAMS_LOG" > "$PARAMS_LOG.tmp"
mv "$PARAMS_LOG.tmp" "$PARAMS_LOG"

echo "Housekeeping completed. Output files moved to: $RUN_OUT_DIR"
"""

    logger.info(f"Writing LSF script to: {lsf_file}")
    with open(lsf_file, 'w') as f:
        f.write(script_content)

    logger.info("Setting script permissions")
    os.chmod(lsf_file, 0o755)
