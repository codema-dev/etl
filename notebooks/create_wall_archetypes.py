from pathlib import Path

import pandas as pd

data_dir = Path("../data")

df = pd.DataFrame(pd.read_parquet(data_dir / "dublin_ber_public.parquet"))
distance_to_cc = "distance_to_city_centre_in_km"
dwelling_type = "dwelling_type"
period_built = "period_built"
wall = "FirstWallType_Description"
rename = "ModeWallDescription"

mode_wall_types = (
    df.groupby([distance_to_cc, dwelling_type, period_built])[wall]
    .agg(pd.Series.mode)
    .rename(rename)
)

mode_wall_types.to_csv(data_dir / "mode_wall_bands.csv")
