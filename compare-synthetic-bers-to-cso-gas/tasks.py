from typing import Any

import geopandas as gpd
import numpy as np
import pandas as pd


def create_dublin_postcode_residential_gas_consumption(
    upstream: Any, product: Any
) -> None:
    county = pd.read_csv(
        upstream["download_county_residential_networked_gas_consumption"], index_col=0
    )
    postal_district = pd.read_csv(
        upstream[
            "download_dublin_postal_district_residential_networked_gas_consumption"
        ],
        index_col=0,
    )
    dublin = pd.concat([county.loc[["Dublin County"], :], postal_district])
    dublin.to_csv(product)


def create_dublin_postcode_residential_gas_meters(upstream: Any, product: Any) -> None:
    county = pd.read_csv(
        upstream["download_county_residential_networked_gas_meters"], index_col=0
    )
    postal_district = pd.read_csv(
        upstream["download_dublin_postal_district_residential_networked_gas_meters"],
        index_col=0,
    )
    dublin = pd.concat([county.loc[["Dublin County"], :], postal_district])
    dublin.to_csv(product)


def _standardise_postcode_ber_names(bers: pd.DataFrame) -> pd.DataFrame:
    # to the same format as CSO Gas
    return pd.concat(
        [
            pd.Series(bers.index)
            .replace({"CO. DUBLIN": "Dublin County"})
            .str.title()
            .str.replace(
                r"^(Dublin )(\dW?)$",
                lambda m: m.group(1) + "0" + m.group(2),
                regex=True,
            ),
            bers.reset_index(drop=True),
        ],
        axis=1,
    ).set_index("countyname")


def amalgamate_synthetic_ber_gas_consumption_to_postcodes(
    upstream: Any, product: Any
) -> None:
    bers = pd.read_parquet(upstream["download_synthetic_bers"])
    gas_bers = bers.query("main_sh_boiler_fuel == 'Mains Gas'")
    gas_consumption = (
        gas_bers["main_sh_demand"]
        + np.where(
            gas_bers["main_hw_boiler_fuel"] == "Mains Gas",
            gas_bers["main_hw_demand"],
            0,
        )
        + np.where(
            gas_bers["suppl_sh_boiler_fuel"] == "Mains Gas",
            gas_bers["suppl_sh_demand"],
            0,
        )
    )
    postcode_gas_consumption = (
        pd.concat([gas_bers["countyname"], gas_consumption], axis=1)
        .groupby("countyname")
        .sum()
        .squeeze()
        .divide(1e6)
        .round()
        .rename("ber_gas_consumption")
    )
    postcode_gas_consumption_standardised = _standardise_postcode_ber_names(
        postcode_gas_consumption
    )
    postcode_gas_consumption_standardised.to_csv(product)


def amalgamate_synthetic_ber_gas_meters_to_postcodes(
    upstream: Any, product: Any
) -> None:
    bers = pd.read_parquet(upstream["download_synthetic_bers"])
    gas_bers = bers.query("main_sh_boiler_fuel == 'Mains Gas'")
    postcode_gas_meters = gas_bers.groupby("countyname").size().rename("ber_gas_meters")
    postcode_gas_meters_standardised = _standardise_postcode_ber_names(
        postcode_gas_meters
    )
    postcode_gas_meters_standardised.to_csv(product)


def amalgamate_census_2016_gas_meters_to_postcodes(upstream: Any, product: Any) -> None:
    census = pd.read_csv(upstream["download_census_2016"])
    census_small_areas = census["GEOGID"].str[7:].rename("small_area")
    census_gas_meters = pd.concat(
        [census_small_areas, census["T6_5_NGCH"].rename("census_gas_meters")], axis=1
    )
    dublin_small_area_boundaries = gpd.read_file(
        str(upstream["download_dublin_small_area_boundaries"])
    ).loc[:, ["small_area", "countyname"]]
    postcode_gas_meters = (
        census_gas_meters.merge(dublin_small_area_boundaries)
        .drop(columns="small_area")
        .groupby("countyname")
        .sum()
    )
    postcode_gas_meters_standardised = _standardise_postcode_ber_names(
        postcode_gas_meters
    )
    postcode_gas_meters_standardised.to_csv(product)
