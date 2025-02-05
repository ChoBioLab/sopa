# SOPA Pipeline Setup Guide

This guide explains how to set up and run the SOPA (Spatial Omics Processing and Analysis) pipeline on the Minerva HPC cluster.

## Prerequisites

1. Access to Minerva HPC cluster with valid credentials
2. Filtered transcripts must be prepared before running this pipeline
3. Write access to the following paths:
   - `/sc/arion/projects/untreatedIBD/cache/tools/sopa`
   - `/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry`

## Environment Setup

### 1. Set up prep-sopa Environment
```bash
# Create conda environment for prep-sopa
cd /sc/arion/projects/untreatedIBD/cache/tools/sopa/workflow/config/cholab-config/prep-sopa-run
conda env create -f environment.yml
conda activate prep-sopa
pip install -r requirements.txt
```

### 2. Set up SOPA Pipeline Environment
```bash
# Create main SOPA conda environment
cd /sc/arion/projects/untreatedIBD/cache/tools/sopa/workflow/config/cholab-config
conda env create -f environment.yml
conda activate sopa
pip install -r requirements.txt
```

## Directory Structure

The SOPA configuration and setup tools are located at:
```/sc/arion/projects/untreatedIBD/cache/tools/sopa/workflow/config/cholab-config```

The setup tool repo needs to be on the cholab-config branch to work correctly

## Setup Steps

1. **Prepare Your Data**
   - Ensure your Xenium data is in the correct location in an oba-outputs dir
   - Verify that filtered transcripts are available in the `qv20-filtered-transcripts` directory

2. **Configuration Setup**
   - Copy the example config: `example_xenium-multichannel-config.yaml`
   - Modify parameters according to your needs
   - Place the config file in your run directory (e.g., `/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/oba-outputs/CHO-001/`)

3. **Generate LSF Scripts**
   Activate the prep-sopa environment and run:

   ```bash
   conda activate prep-sopa

   python /sc/arion/projects/untreatedIBD/cache/tools/sopa/workflow/config/cholab-config/prep-sopa-run/main.py \
     --id <panel_id>/<run_id> \
     --config-name <your_config.yaml> \
     --project-dir <project_directory>
   ```

   Required arguments:
   - `--id`: Panel/Run ID (e.g., TUQ97N/CHO-001)
   - `--config-name`: Name of SOPA config file (e.g., cellpose-baysor.yaml)
   - `--project-dir`: Project directory name for output organization

   Optional arguments:
   - `--sopa-source`: Path to SOPA workflow directory
   - `--conda-env`: Path to SOPA conda environment
   - `--email`: Email for job notifications
   - `--queue`: LSF queue name

4. **Submit Jobs**
   - LSF scripts will be generated in the `lsf_scripts` directory
   - Submit jobs using:
     ```bash
     cd oba-outputs/<run_id>/lsf_scripts
     bsub < submit_<sample_name>.lsf
     ```

## Output Structure

All pipeline outputs will be stored in:
`/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/sopa/<project_dir>`

The pipeline creates:
1. A timestamped run directory under your project directory
2. Explorer and Zarr directories for results
3. Parameter logs and configuration backups
4. Standard output and error logs

## Troubleshooting

1. If jobs fail, check:
   - Error logs are under the working dir in scratch
     - master log is in `workflow/.snakemake/log` (e.g. /sc/arion/scratch/tastac01/sopa_50006A-TUQ97N-EA/workflow/.snakemake/log)
     - individual job logs are in `workflow/logs` (e.g. /sc/arion/scratch/tastac01/sopa_50006A-TUQ97N-EA/workflow/logs)
   - LSF error files (*.stderr)
   - Available disk space in scratch directory

2. Common issues:
   - Missing or incorrect transcript files
   - Insufficient permissions
   - Resource limitations
   - Conda environment activation failures
   - Missing dependencies in environment setup

## Environment Management Tips

- Keep environments separate (prep-sopa vs. main SOPA)
- Update environments if new dependencies are added:
  ```bash
  conda env update -f environment.yml
  pip install -r requirements.txt
  ```
- If environment becomes corrupted:
  ```bash
  conda remove --name <env_name> --all
  conda env create -f environment.yml
  ```

## Notes

- The pipeline automatically handles transcript file management
- Results are stored in both scratch and project directories
- Default runtime is set to 24 hours
- Jobs use 8 cores and 8GB memory by default
- Configuration files must be placed in the specific run directory
