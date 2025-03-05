import ast
from pathlib import Path
from typing import Optional

import typer

from .utils import SDATA_HELPER

app_annotate = typer.Typer()


@app_annotate.command()
def fluorescence(
    sdata_path: str = typer.Argument(help=SDATA_HELPER),
    marker_cell_dict: str = typer.Option(callback=ast.literal_eval),
    cell_type_key: str = typer.Option("cell_type", help="Key added in `adata.obs` corresponding to the cell type"),
):
    """Simple annotation based on fluorescence, where each provided channel corresponds to one cell type.

    For each cell, one z-score statistic is computed and the population with the highest z-score is attributed.
    """
    from sopa._constants import SopaKeys
    from sopa.io.standardize import read_zarr_standardized
    from sopa.utils import higher_z_score

    sdata = read_zarr_standardized(sdata_path)

    assert SopaKeys.TABLE in sdata.tables, f"No '{SopaKeys.TABLE}' found in sdata.tables"

    higher_z_score(sdata.tables[SopaKeys.TABLE], marker_cell_dict, cell_type_key)

    if sdata.is_backed():
        sdata.delete_element_from_disk(SopaKeys.TABLE)
        sdata.write_element(SopaKeys.TABLE)


@app_annotate.command()
def tangram(
    sdata_path: str = typer.Argument(help=SDATA_HELPER),
    sc_reference_path: str = typer.Option(help="Path to the scRNAseq annotated reference, as a `.h5ad` file"),
    cell_type_key: str = typer.Option(help="Key of `adata_ref.obs` containing the cell-types"),
    reference_preprocessing: str = typer.Option(
        None,
        help="Preprocessing method applied to the reference. Either None (raw counts), or `normalized` (sc.pp.normalize_total) or `log1p` (sc.pp.normalize_total and sc.pp.log1p)",
    ),
    bag_size: int = typer.Option(
        10_000,
        help="Number of cells in each bag of the spatial table. Low values will decrease the memory usage",
    ),
    max_obs_reference: int = typer.Option(
        10_000,
        help="Maximum samples to be considered in the reference for tangram. Low values will decrease the memory usage",
    ),
    threshold: float = typer.Option(
        0.5,
        help="Threshold for filtering low probability annotations",
    ),
    save_maps: bool = typer.Option(
        False,
        help="Save Tangram training data to disk",
    ),
):
    """Tangram segmentation (i.e., uses an annotated scRNAseq reference to transfer cell-types)"""
    import logging

    import anndata

    from sopa._constants import SopaKeys
    from sopa.io.standardize import read_zarr_standardized
    from sopa.utils import tangram_annotate

    log = logging.getLogger(__name__)

    sdata = read_zarr_standardized(sdata_path)
    adata_sc = anndata.io.read_h5ad(sc_reference_path)

    # Set output directory if save_maps is True
    output_dir = None
    if save_maps:
        output_dir = Path(sdata_path).with_suffix(".explorer")
        log.info(f"Will save training data to {output_dir}")
        output_dir.mkdir(parents=True, exist_ok=True)

    tangram_annotate(
        sdata,
        adata_sc,
        cell_type_key,
        reference_preprocessing=reference_preprocessing,
        bag_size=bag_size,
        max_obs_reference=max_obs_reference,
        threshold=threshold,
        output_dir=output_dir,
    )
    if sdata.is_backed():
        sdata.delete_element_from_disk(SopaKeys.TABLE)
        sdata.write_element(SopaKeys.TABLE, overwrite=True)
