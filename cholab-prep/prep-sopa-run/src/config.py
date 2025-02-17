import os

# Default settings
DEFAULT_EMAIL = "christopher.tastad@mssm.edu"
DEFAULT_CONDA_ENV = "/sc/arion/projects/untreatedIBD/ctastad/conda/envs/snakemake"
DEFAULT_SOPA_SOURCE = "/sc/arion/projects/untreatedIBD/cache/tools/sopa"
DEFAULT_QUEUE = "premium"
BASE_DATA_PATH = "/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/oba-outputs"
SCRATCH_BASE = f"/sc/arion/scratch/{os.environ.get('USER')}"
PROJ_BASE_PATH = "/sc/arion/projects/untreatedIBD/cache/nfs-data-registries/xenium-registry/sopa"
MAX_JOB_RAM = "4000000"

# Default config fields
DEFAULT_CONFIG_FIELDS = {
    'read_technology': '',
    'patchify_patch_width_pixel': '',
    'patchify_patch_overlap_pixel': '',
    'patchify_patch_width_microns': '',
    'patchify_patch_overlap_microns': '',
    'segmentation_cellpose_diameter': '',
    'segmentation_cellpose_channels': '',
    'segmentation_cellpose_flow_threshold': '',
    'segmentation_cellpose_cellprob_threshold': '',
    'segmentation_cellpose_model_type': '',
    'segmentation_cellpose_min_area': '',
    'segmentation_cellpose_clip_limit': '',
    'segmentation_cellpose_gaussian_sigma': '',
    'segmentation_baysor_min_area': '',
    'segmentation_baysor_cell_key': '',
    'segmentation_baysor_unassigned_value': '',
    'segmentation_baysor_config_data_exclude_genes': '',
    'segmentation_baysor_config_data_force_2d': '',
    'segmentation_baysor_config_data_min_molecules_per_cell': '',
    'segmentation_baysor_config_data_gene': '',
    'segmentation_baysor_config_data_min_molecules_per_gene': '',
    'segmentation_baysor_config_data_min_molecules_per_segment': '',
    'segmentation_baysor_config_data_confidence_nn_id': '',
    'segmentation_baysor_config_data_x': '',
    'segmentation_baysor_config_data_y': '',
    'segmentation_baysor_config_data_z': '',
    'segmentation_baysor_config_segmentation_scale': '',
    'segmentation_baysor_config_segmentation_scale_std': '',
    'segmentation_baysor_config_segmentation_prior_segmentation_confidence': '',
    'segmentation_baysor_config_segmentation_estimate_scale_from_centers': '',
    'segmentation_baysor_config_segmentation_n_clusters': '',
    'segmentation_baysor_config_segmentation_iters': '',
    'segmentation_baysor_config_segmentation_n_cells_init': '',
    'segmentation_baysor_config_segmentation_nuclei_genes': '',
    'segmentation_baysor_config_segmentation_cyto_genes': '',
    'aggregate_average_intensities': '',
    'aggregate_min_intensity_ratio': '',
    'aggregate_expand_radius_ratio': '',
    'aggregate_gene_column': '',
    'aggregate_min_transcripts': '',
    'annotation_method': '',
    'annotation_args_sc_reference_path': '',
    'annotation_args_cell_type_key': '',
    'annotation_args_reference_preprocessing': '',
    'annotation_args_marker_cell_dict': '',
    'explorer_gene_column': '',
    'explorer_ram_threshold_gb': '',
    'explorer_pixel_size': '',
    'executables_baysor': ''
}
