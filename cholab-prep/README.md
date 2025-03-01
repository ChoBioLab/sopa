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
cd /sc/arion/projects/untreatedIBD/cache/tools/sopa/cholab-config/prep-sopa-run
conda env create -f environment.yml
```

### 2. Set up SOPA and Snakemake Environments
```bash
# Create main SOPA conda environment
conda create --name sopa2 python=3.10
conda activate sopa2
pip install 'sopa[cellpose,baysor,tangram,wsi]'
conda deactivate

# Create Snakemake conda environment
conda create -c conda-forge -c bioconda -n snakemake snakemake
```

### 3. Set up Baysor executable
```bash
# Pull compiled Baysor v0.7.1
wget https://github.com/kharchenkolab/Baysor/releases/download/v0.7.1/baysor-x86_x64-linux-v0.7.1_build.zip
unzip baysor-x86_x64-linux-v0.7.1_build.zip

# Push to Julia config path so Baysor bin found at ~/.julia/bin/baysor
mkdir ~/.julia
cp -r bin/baysor/* ~/.julia
```

## Directory Structure

The SOPA configuration and setup tools are located at:
```/sc/arion/projects/untreatedIBD/cache/tools/sopa/cholab-config```

## Setup Steps

1. **Prepare Your Data**
   - Ensure your Xenium data is in the correct location in an oba-outputs dir
   - Verify that filtered transcripts are available in the `qv20-filtered-transcripts` directory

2. **Configuration Setup**
   - Copy the example config: `example_xenium-multichannel-config.yaml`
   - Modify parameters according to your needs
   - Place the config file in your xenium run directory (e.g., `/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/oba-outputs/CHO-001/`)

3. **Generate LSF Scripts**
   Activate the prep-sopa environment and run:

   ```bash
   conda activate prep-sopa

   python /sc/arion/projects/untreatedIBD/cache/tools/sopa/cholab-config/prep-sopa-run/main.py \
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
   - `--max_ram`: Max RAM across all processes

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
     - individual job logs are in `workflow/.snakemake/lsf_logs` (e.g. /sc/arion/scratch/tastac01/sopa_50006A-TUQ97N-EA/workflow/.snakemake/lsf_logs)
   - LSF error files (*.stderr)

2. Common issues:
   - Missing or incorrect transcript files
   - Insufficient permissions
   - Resource limitations
   - Conda environment activation failures
   - Missing dependencies in environment setup

## Notes

- The pipeline automatically handles transcript file management
- Results are stored in both scratch and project directories
- Default runtime is set to 24 hours
- Configuration files must be placed in the specific run directory
