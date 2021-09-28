from pathlib import Path
from typing import Any
from typing import Dict
from typing import List

import geopandas as gpd
import pandas as pd


def _check_gni_data_is_uploaded(filepath: str) -> None:
    message = "Please upload GNI CAD Network data (Tx and Dx) to data/raw/"
    assert Path(filepath).exists(), message


def save_gni_data_to_parquet(product: Any, filepaths: List[str]) -> None:
    _check_gni_data_is_uploaded(filepaths[0])
    lines = pd.concat([gpd.read_file(f, crs="EPSG:2157") for f in filepaths])
    lines.to_parquet(product)


def extract_lines_in_small_area_boundaries(
    product: Any,
    upstream: Any,
) -> None:
    lines = gpd.read_parquet(upstream["save_gni_data_to_parquet"])
    dublin_small_area_boundaries = gpd.read_file(
        str(upstream["download_dublin_small_area_boundaries"])
    )

    lines_in_boundaries = gpd.overlay(
        lines,
        dublin_small_area_boundaries[["small_area", "geometry"]],
        "intersection",
    )

    lines_in_boundaries.to_file(str(product), driver="GPKG")
