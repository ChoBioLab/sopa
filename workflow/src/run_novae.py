#!/usr/bin/env python
# workflow/src/run_novae.py

import sys
import os
import novae
import spatialdata as sd
from spatialdata import SpatialData
import anndata as ad
import numpy as np
import pandas as pd
import tempfile
import shutil

def main():
    # Parse command line arguments
    if len(sys.argv) != 6:
        print("Usage: python run_novae.py <sdata_path> <model> <radius> <zero_shot> <num_workers>")
        sys.exit(1)

    sdata_path = sys.argv[1]
    model_name = sys.argv[2]
    radius = float(sys.argv[3])
    zero_shot = sys.argv[4].lower() == 'true'
    num_workers = int(sys.argv[5])

    # Define the table key constant
    TABLE_KEY = 'table'

    print(f"Processing {sdata_path}")
    print(f"Model: {model_name}, Radius: {radius}, Zero-shot: {zero_shot}, Workers: {num_workers}")

    # Read the SpatialData object
    sdata = sd.read_zarr(sdata_path)
    adata = sdata[TABLE_KEY]

    # Run Novae on the AnnData object
    model = novae.Novae.from_pretrained(model_name)

    # Compute spatial neighbors
    novae.utils.spatial_neighbors(adata, radius=radius)

    # Compute representations
    model.compute_representations(adata, zero_shot=zero_shot, accelerator='cuda', num_workers=num_workers)

    # Assign domains at different levels
    model.assign_domains(adata, level=5)
    model.assign_domains(adata, level=10)
    model.assign_domains(adata, level=15)

    # Fix serialization issue with Novae columns
    novae_columns = [col for col in adata.obs.columns if 'novae' in col]
    print(f"Preparing {len(novae_columns)} Novae columns for serialization")

    for col in novae_columns:
        if col in adata.obs.columns and adata.obs[col].isna().any():
            print(f'Fixing NaN values in column "{col}"')

            # For categorical columns
            if pd.api.types.is_categorical_dtype(adata.obs[col]):
                # Add empty string to categories if not present
                if '' not in adata.obs[col].cat.categories:
                    adata.obs[col] = adata.obs[col].cat.add_categories([''])
                # Replace NaN with empty string for serialization
                adata.obs[col] = adata.obs[col].fillna('')
            else:
                # For non-categorical columns, convert to string and replace NaN with empty string
                adata.obs[col] = adata.obs[col].astype(str).replace('nan', '')

    # Update the table in the SpatialData object
    sdata[TABLE_KEY] = adata

    # Use a direct approach for updating just the table
    if sdata.is_backed():
        print("Writing backed SpatialData...")
        sdata.delete_element_from_disk(TABLE_KEY)
        sdata.write_element(TABLE_KEY, overwrite=True)
    else:
        print("Writing non-backed SpatialData...")
        # Fallback to a temporary directory approach if not backed
        temp_dir = tempfile.mkdtemp()
        try:
            # Write to temporary location
            sdata.write(temp_dir)

            # Copy only the table directory
            src_table_dir = os.path.join(temp_dir, 'tables', 'table')
            dst_table_dir = os.path.join(sdata_path, 'tables', 'table')

            # Remove the destination directory if it exists
            if os.path.exists(dst_table_dir):
                shutil.rmtree(dst_table_dir)

            # Copy the new table directory to the destination
            shutil.copytree(src_table_dir, dst_table_dir)
        finally:
            # Clean up the temporary directory
            shutil.rmtree(temp_dir)

    print('Successfully updated the table with Novae domains')

if __name__ == "__main__":
    main()
