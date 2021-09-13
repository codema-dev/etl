import json
from pathlib import Path
from typing import Any

import fs
from fs.tools import copy_file_data
import numpy as np
import pandas as pd

from rcbm import fab


def get_data(filepath: str) -> Path:
    return Path(__name__).parent / filepath


def create_folder_structure(data_dirpath: Path) -> None:
    data_dirpath.mkdir(exist_ok=True)
    external_dir = data_dirpath / "external"
    external_dir.mkdir(exist_ok=True)
    interim_dir = data_dirpath / "interim"
    interim_dir.mkdir(exist_ok=True)
    processed_dir = data_dirpath / "processed"
    processed_dir.mkdir(exist_ok=True)


def fetch_s3_file(bucket: str, filename: str, savedir: Path) -> None:
    savepath = savedir / filename
    if not savepath.exists():
        s3fs = fs.open_fs(bucket)
        with s3fs.open(filename, "rb") as remote_file:
            with open(savedir / filename, "wb") as local_file:
                copy_file_data(remote_file, local_file)


def estimate_cost_of_fabric_retrofits(
    is_selected: pd.Series,
    cost: float,
    areas: pd.Series,
) -> pd.Series:
    return pd.Series([cost] * is_selected * areas, dtype="int64")


def calculate_fabric_heat_loss_w_per_k(buildings: pd.DataFrame) -> pd.Series:
    return fab.calculate_fabric_heat_loss(
        roof_area=buildings["roof_area"],
        roof_uvalue=buildings["roof_uvalue"],
        wall_area=buildings["wall_area"],
        wall_uvalue=buildings["wall_uvalue"],
        floor_area=buildings["floor_area"],
        floor_uvalue=buildings["floor_uvalue"],
        window_area=buildings["window_area"],
        window_uvalue=buildings["window_uvalue"],
        door_area=buildings["door_area"],
        door_uvalue=buildings["door_uvalue"],
        thermal_bridging_factor=0.05,
    )


def get_ber_rating(energy_values: pd.Series) -> pd.Series:
    return (
        pd.cut(
            energy_values,
            [
                -np.inf,
                25,
                50,
                75,
                100,
                125,
                150,
                175,
                200,
                225,
                260,
                300,
                340,
                380,
                450,
                np.inf,
            ],
            labels=[
                "A1",
                "A2",
                "A3",
                "B1",
                "B2",
                "B3",
                "C1",
                "C2",
                "C3",
                "D1",
                "D2",
                "E1",
                "E2",
                "F",
                "G",
            ],
        )
        .rename("energy_rating")
        .astype("string")
    )  # streamlit & altair don't recognise category


def load_defaults(product: Any) -> None:
    defaults = {
        "wall": {
            "uvalue": {"target": 0.35, "threshold": 1},
            "cost": {"lower": 50, "upper": 300},
            "typical_area": 70,
        },
        "roof": {
            "uvalue": {"target": 0.25, "threshold": 1},
            "cost": {"lower": 5, "upper": 30},
            "typical_area": 50,
        },
        "window": {
            "uvalue": {"target": 1.4, "threshold": 2},
            "cost": {"lower": 30, "upper": 150},
            "typical_area": 16,
        },
    }
    with open(product, "w") as f:
        json.dump(defaults, f)


def replace_uvalues_with_target_uvalues(upstream: Any, product: Any) -> None:

    with open(upstream["load_defaults"], "r") as f:
        defaults = json.load(f)
    pre_retrofit = pd.read_parquet(upstream["download_buildings"])

    post_retrofit_columns = [
        "small_area",
        "dwelling_type",
        "year_of_construction",
        "period_built",
        "archetype",
        "door_area",
        "floor_area",
        "roof_area",
        "small_area",
        "wall_area",
        "window_area",
        "floor_uvalue",
        "door_uvalue",
    ]
    post_retrofit = pre_retrofit[post_retrofit_columns].copy()

    for component, properties in defaults.items():
        uvalue_column = component + "_uvalue"
        is_retrofitted_column = component + "_is_retrofitted"
        uvalues = pre_retrofit[uvalue_column].copy()
        where_uvalue_is_viable = (
            (uvalues > properties["uvalue"]["threshold"])
            & (pre_retrofit["heat_loss_parameter"] > 2)
            & (pre_retrofit["period_built"] != "PRE19")
        )
        uvalues.loc[where_uvalue_is_viable] = properties["uvalue"]["target"]
        post_retrofit[uvalue_column] = uvalues
        post_retrofit[is_retrofitted_column] = where_uvalue_is_viable

    post_retrofit.to_csv(product)
