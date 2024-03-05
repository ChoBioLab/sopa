from __future__ import annotations

import logging
from typing import Callable

import numpy as np
import tqdm
from multiscale_spatial_image import MultiscaleSpatialImage
from spatial_image import SpatialImage
from spatialdata import SpatialData, bounding_box_query
from spatialdata.models import Image2DModel
from spatialdata.transformations import Scale

from sopa._constants import SopaKeys
from sopa._sdata import get_intrinsic_cs, get_key
from sopa.segmentation import Patches2D

log = logging.getLogger(__name__)


def _get_best_level_for_downsample(
    level_downsamples: list[float], downsample: float, epsilon: float = 0.01
) -> int:
    """Return the best level for a given downsampling factor"""
    if downsample <= 1.0:
        return 0
    for level, ds in enumerate(level_downsamples):
        if ds > downsample + epsilon:
            return level - 1
    return len(level_downsamples) - 1


def _get_extraction_parameters(
    tiff_metadata: dict,
    patch_width: int,
    level: int | None,
    magnification: int | None,
) -> tuple[int, int, int, bool]:
    """
    Given the metadata for the slide, a target magnification and a patch width,
    it returns the best scale to get it from (level), a resize factor (resize_factor)
    and the corresponding patch size at scale0 (patch_width)
    """
    if level is None and magnification is None:
        log.warn("Both level and magnification arguments are None. Using level=0 by default.")
        level = 0

    if magnification is None:
        return level, 1, patch_width, True

    if tiff_metadata["properties"].get("tiffslide.objective-power"):
        objective_power = int(tiff_metadata["properties"].get("tiffslide.objective-power"))
        downsample = objective_power / magnification

    elif tiff_metadata["properties"].get("tiffslide.mpp-x"):
        mppx = float(tiff_metadata["properties"].get("tiffslide.mpp-x"))

        mpp_objective = min([80, 40, 20, 10, 5], key=lambda obj: abs(10 / obj - mppx))
        downsample = mpp_objective / magnification
    else:
        return None, None, None, False

    level = _get_best_level_for_downsample(tiff_metadata["level_downsamples"], downsample)
    resize_factor = tiff_metadata["level_downsamples"][level] / downsample
    patch_width = int(patch_width * downsample)

    return level, resize_factor, patch_width, True


def _torch_patch(
    image: MultiscaleSpatialImage | SpatialImage,
    box: tuple[int, int, int, int],
    level: int,
    coordinate_system: str,
    resize_factor: float,
) -> np.ndarray:
    """Extract a numpy patch from the MultiscaleSpatialImage given a bounding box"""
    import cv2
    import torch

    image_patch = bounding_box_query(
        image, ("y", "x"), box[:2][::-1], box[2:][::-1], coordinate_system
    )

    if isinstance(image, MultiscaleSpatialImage):
        patch = np.array(next(iter(image_patch[f"scale{level}"].values())).transpose("y", "x", "c"))
    else:
        patch = image_patch.transpose("y", "x", "c").compute().data

    if resize_factor != 1:
        dim = (int(patch.shape[0] * resize_factor), int(patch.shape[1] * resize_factor))
        patch = cv2.resize(patch, dim)

    patch = patch.transpose(2, 0, 1)
    return torch.tensor(patch / 255.0, dtype=torch.float32)


def embed_batch(model_name: str, device: str) -> tuple[Callable, int]:
    import torch

    import sopa.embedding.models as models

    assert hasattr(
        models, model_name
    ), f"'{model_name}' is not a valid model name under `sopa.embedding.models`. Valid names are: {', '.join(models.__all__)}"

    model: torch.nn.Module = getattr(models, model_name)()
    model.eval().to(device)

    def _(patches: torch.Tensor):
        """Uses the model to gets the patches outputs.

        patches has a shape (B * Y * X * 3) and the output is of shape (B * output_dim)"""
        if len(patches.shape) == 3:
            patches = patches.unsqueeze(0)

        with torch.no_grad():
            embedding = model(patches.to(device)).squeeze()
            return embedding.cpu()

    return _, model.output_dim


def embed_wsi_patches(
    sdata: SpatialData,
    model_name: str,
    patch_width: int,
    level: int | None = 0,
    magnification: int | None = None,
    image_key: str | None = None,
    batch_size: int = 32,
    device: str = "cpu",
) -> SpatialImage | bool:
    """Create an image made of patch embeddings of a WSI image.

    !!! info
        The image will be saved into the `SpatialData` object with the key `sopa_{model_name}` (see the argument below).

    Args:
        sdata: A `SpatialData` object
        model_name: Name of the computer vision model to be used. One of `Resnet50Features`, `HistoSSLFeatures`, or `DINOv2Features`.
        patch_width: Width of the patches for which the embeddings will be computed.
        level: Image level on which the embedding is performed. Either `level` or `magnification` should be provided.
        magnification: The target magnification on which the embedding is performed. If `magnification` is provided, the `level` argument will be automatically computed.
        image_key: Optional image key of the WSI image, unecessary if there is only one image.
        batch_size: Mini-batch size used during inference.
        device: Device used for the computer vision model.

    Returns:
        If the embedding was successful, returns the `SpatialImage` of shape `(C,Y,X)` containing the embedding, else `False`
    """
    import torch

    image_key = get_key(sdata, "images", image_key)
    image = sdata.images[image_key]

    tiff_metadata = image.attrs.get("metadata", {})
    coordinate_system = get_intrinsic_cs(sdata, image)

    embedder, output_dim = embed_batch(model_name=model_name, device=device)

    level, resize_factor, patch_width, success = _get_extraction_parameters(
        tiff_metadata, patch_width, level, magnification
    )
    if not success:
        log.error(f"Error retrieving the mpp for {image_key}, skipping tile embedding.")
        return False

    patches = Patches2D(sdata, image_key, patch_width, 0)
    embedding_image = np.zeros((output_dim, *patches.shape), dtype=np.float32)

    log.info(f"Computing {len(patches)} embeddings at level {level}")

    for i in tqdm.tqdm(range(0, len(patches), batch_size)):
        batch = torch.stack(
            [
                _torch_patch(image, box, level, coordinate_system, resize_factor)
                for box in patches.bboxes[i : i + batch_size]
            ]
        )

        loc_x, loc_y = patches.ilocs[i : i + len(batch)].T
        embedding_image[:, loc_y, loc_x] = embedder(batch).T

    embedding_image = SpatialImage(embedding_image, dims=("c", "y", "x"))
    embedding_image = Image2DModel.parse(
        embedding_image,
        transformations={coordinate_system: Scale([patch_width, patch_width], axes=("x", "y"))},
    )
    embedding_image.coords["y"] = patch_width * embedding_image.coords["y"]
    embedding_image.coords["x"] = patch_width * embedding_image.coords["x"]

    embedding_key = f"sopa_{model_name}"
    sdata.add_image(embedding_key, embedding_image)

    log.info(f"WSI embeddings saved as an image in sdata['{embedding_key}']")

    patches.write(shapes_key=SopaKeys.EMBEDDINGS_PATCHES_KEY)

    return sdata[embedding_key]
