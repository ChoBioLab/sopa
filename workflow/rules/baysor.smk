rule patch_segmentation_baysor:
    input:
        paths.smk_patches_file_transcripts,
    output:
        paths.smk_transcripts_temp_dir / "{index}" / "segmentation_counts.loom",
    conda:
        "sopa206"
    params:
        baysor_config = args["segmentation"]["baysor"].as_cli(keys=["config"]),
        sdata_path = paths.sdata_path,
        baysor_path = "~/.julia/bin/baysor",
    threads: 8
    resources:
        cpus_per_task=8,
    shell:
        """
        export JULIA_NUM_THREADS={resources.cpus_per_task} # parallelize within each patch for Baysor >= v0.7

        # Use the explicit Baysor path
        export PATH=~/.julia/bin:$PATH

        # Check if Baysor is available
        if ! command -v baysor &> /dev/null; then
            echo "Baysor not found in PATH or at {params.baysor_path}"
            exit 1
        fi

        sopa segmentation baysor {params.sdata_path} --patch-index {wildcards.index} {params.baysor_config}
        """

rule resolve_baysor:
    input:
        files = get_input_resolve("transcripts", "baysor"),
    output:
        touch(paths.segmentation_done("baysor")),
        touch(paths.smk_table),
    conda:
        "sopa206"
    params:
        resolve = args.resolve_transcripts(),
        sdata_path = paths.sdata_path,
        smk_transcripts_temp_dir = paths.smk_transcripts_temp_dir,
    shell:
        """
        sopa resolve baysor {params.sdata_path} {params.resolve}

        rm -r {params.smk_transcripts_temp_dir}    # cleanup large baysor files
        """
