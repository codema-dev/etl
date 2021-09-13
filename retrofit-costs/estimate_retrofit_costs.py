# %%
from collections import defaultdict
from pathlib import Path

import pandas as pd

import tasks

# %% tags=["parameters"]
DATA_DIR = Path("data")
ber_filepath = Path(
    "data/external/dublin_census_2016_filled_with_ber_public_14_05_2021.parquet"
)

# %%
bers = pd.read_parquet(ber_filepath)

# %%
# where target uvalues are taken from gov.ie 2021 Technical Guidance Document Table 5
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


# %%
total_floor_area = (
    bers["ground_floor_area"]
    + bers["first_floor_area"]
    + bers["second_floor_area"]
    + bers["third_floor_area"]
)

# %%
post_retrofit_columns = [
    "door_area",
    "floor_area",
    "roof_area",
    "small_area",
    "wall_area",
    "window_area",
    "floor_uvalue",
    "door_uvalue",
]

# %%
pre_retrofit = bers
post_retrofit = bers[post_retrofit_columns].copy()

# %%
dict_of_costs = defaultdict(list)
for component, properties in defaults.items():
    uvalue_column_name = component + "_uvalue"
    uvalues = pre_retrofit[uvalue_column_name].copy()
    where_uvalue_is_viable = (
        (uvalues > properties["uvalue"]["threshold"])
        & (pre_retrofit["heat_loss_parameter"] > 2)
        & (pre_retrofit["period_built"] != "PRE19")
    )
    uvalues.loc[where_uvalue_is_viable] = properties["uvalue"]["target"]
    post_retrofit[uvalue_column_name] = uvalues

    area_column_name = component + "_area"
    areas = pre_retrofit[area_column_name].copy()
    dict_of_costs[component + "_cost_lower"] = pd.Series(
        [properties["cost"]["lower"]] * where_uvalue_is_viable * areas, dtype="int64"
    )
    dict_of_costs[component + "_cost_upper"] = pd.Series(
        [properties["cost"]["upper"]] * where_uvalue_is_viable * areas, dtype="int64"
    )

    retrofit_flag_column_name = component + "_is_retrofitted"
    dict_of_costs[retrofit_flag_column_name] = where_uvalue_is_viable

retrofit_costs = pd.DataFrame(dict_of_costs)

# %%
retrofit_costs["small_area"] = pre_retrofit["small_area"]

# %%
small_area_total = retrofit_costs.groupby("small_area").sum()

# %%
small_area_total.to_csv(Path(DATA_DIR) / "processed" / "small_area_retrofit_cost.csv")

# %%
