from collections import defaultdict
import json
from typing import Any
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd


def convert_benchmark_uses_to_json(upstream: Any, product: Any) -> None:
    uses_grouped_by_category = defaultdict()
    with ZipFile(upstream["download_benchmark_uses"]) as zf:
        for filename in zf.namelist():
            name = filename.split("/")[-1].replace(".txt", "")
            with zf.open(filename, "r") as f:
                uses_grouped_by_category[name] = [
                    line.rstrip().decode("utf-8") for line in f
                ]
    benchmark_uses = {i: k for k, v in uses_grouped_by_category.items() for i in v}
    with open(product, "w") as f:
        json.dump(benchmark_uses, f)


def weather_adjust_benchmarks(upstream: Any, product: Any) -> None:

    benchmarks = pd.read_csv(upstream["download_benchmarks"])

    # 5y average for Dublin Airport from 2015 to 2020
    dublin_degree_days = 2175
    tm46_degree_days = 2021
    degree_day_factor = dublin_degree_days / tm46_degree_days

    weather_dependent_electricity = (
        benchmarks["Typical electricity [kWh/m²y]"]
        * benchmarks["% electricity pro-rated to degree days"]
        * degree_day_factor
    )
    weather_independent_electricity = benchmarks["Typical electricity [kWh/m²y]"] * (
        1 - benchmarks["% electricity pro-rated to degree days"]
    )
    electricity = weather_dependent_electricity + weather_independent_electricity

    # ASSUMPTION: space heat is the only electrical heat
    electricity_heat = (
        weather_dependent_electricity * benchmarks["% suitable for DH or HP"]
    )

    weather_dependent_fossil_fuel = (
        benchmarks["Typical fossil fuel [kWh/m²y]"]
        * benchmarks["% fossil fuel pro-rated to degree days"]
        * degree_day_factor
    )
    weather_independent_fossil_fuel = benchmarks["Typical fossil fuel [kWh/m²y]"] * (
        1 - benchmarks["% fossil fuel pro-rated to degree days"]
    )
    fossil_fuel = weather_dependent_fossil_fuel + weather_independent_fossil_fuel

    # ASSUMPTION: fossil fuel is only used for space heat & hot water
    fossil_fuel_heat = fossil_fuel * benchmarks["% suitable for DH or HP"]

    industrial_low_temperature_heat = (
        benchmarks["Industrial space heat [kWh/m²y]"] * degree_day_factor
        + benchmarks["Industrial process energy [kWh/m²y]"]
        * benchmarks["% suitable for DH or HP"]
    )
    industrial_high_temperature_heat = benchmarks[
        "Industrial process energy [kWh/m²y]"
    ] * (1 - benchmarks["% suitable for DH or HP"])

    normalised_benchmarks = pd.DataFrame(
        {
            "Benchmark": benchmarks["Benchmark"],
            "typical_area_m2": benchmarks["Typical Area [m²]"],
            "area_upper_bound_m2": benchmarks["Area Upper Bound [m²]"],
            "typical_electricity_kwh_per_m2y": electricity,
            "typical_fossil_fuel_kwh_per_m2y": fossil_fuel,
            "typical_building_energy_kwh_per_m2y": benchmarks[
                "Industrial building total [kWh/m²y]"
            ],
            "typical_process_energy_kwh_per_m2y": benchmarks[
                "Industrial process energy [kWh/m²y]"
            ],
            "typical_electricity_heat_kwh_per_m2y": electricity_heat,
            "typical_fossil_fuel_heat_kwh_per_m2y": fossil_fuel_heat,
            "typical_industrial_low_temperature_heat_kwh_per_m2y": industrial_low_temperature_heat,
            "typical_industrial_high_temperature_heat_kwh_per_m2y": industrial_high_temperature_heat,
        }
    )

    normalised_benchmarks.to_csv(product)


def replace_unexpectedly_large_floor_areas_with_typical_values(
    upstream: Any, product: Any
) -> None:
    buildings = pd.read_csv(upstream["download_buildings"])
    benchmarks = pd.read_csv(upstream["weather_adjust_benchmarks"], index_col=0)
    with open(upstream["convert_benchmark_uses_to_json"], "r") as f:
        benchmark_uses = json.load(f)

    buildings["Benchmark"] = (
        buildings["Use1"].map(benchmark_uses).rename("Benchmark").fillna("Unknown")
    )
    buildings_with_benchmarks = buildings.merge(benchmarks)

    bounded_area_m2 = buildings_with_benchmarks["Total_SQM"].rename("bounded_area_m2")
    typical_area = buildings_with_benchmarks["typical_area_m2"]

    greater_than_zero_floor_area = buildings_with_benchmarks["Total_SQM"] > 0
    greater_than_typical_benchmark_upper_bound = (
        buildings_with_benchmarks["Total_SQM"]
        > buildings_with_benchmarks["area_upper_bound_m2"]
    )
    valid_benchmark = ~buildings_with_benchmarks["Benchmark"].isin(["Unknown", "None"])
    area_is_greater_than_expected = (
        greater_than_zero_floor_area
        & greater_than_typical_benchmark_upper_bound
        & valid_benchmark
    )
    bounded_area_m2.loc[area_is_greater_than_expected] = typical_area.loc[
        area_is_greater_than_expected
    ]

    propertyno_bounded_area_map = pd.concat(
        [buildings["PropertyNo"], bounded_area_m2], axis=1
    )

    propertyno_bounded_area_map.to_csv(product, index=False)


def save_unknown_benchmark_uses(upstream: Any, product: Any) -> None:
    buildings = pd.read_csv(upstream["download_buildings"])
    benchmarks = pd.read_csv(upstream["weather_adjust_benchmarks"], index_col=0)
    with open(upstream["convert_benchmark_uses_to_json"], "r") as f:
        benchmark_uses = json.load(f)

    buildings["Benchmark"] = (
        buildings["Use1"].map(benchmark_uses).rename("Benchmark").fillna("Unknown")
    )
    buildings_with_benchmarks = buildings.merge(benchmarks)

    benchmark_is_unknown = buildings_with_benchmarks["Benchmark"] == "Unknown"
    unknown_benchmark_uses = pd.Series(
        buildings_with_benchmarks.loc[benchmark_is_unknown, "Use1"].unique(),
        name="Use1",
    )
    unknown_benchmark_uses.to_csv(product, index=False)


def apply_energy_benchmarks_to_floor_areas(
    upstream: Any, product: Any, boiler_efficiency: float
) -> None:

    buildings = pd.read_csv(upstream["download_buildings"])
    benchmarks = pd.read_csv(upstream["weather_adjust_benchmarks"], index_col=0)
    with open(upstream["convert_benchmark_uses_to_json"], "r") as f:
        benchmark_uses = json.load(f)

    buildings["Benchmark"] = (
        buildings["Use1"].map(benchmark_uses).rename("Benchmark").fillna("Unknown")
    )
    buildings_with_benchmarks = buildings.merge(benchmarks)

    # Replace invalid floor areas with typical values
    bounded_area_m2 = buildings_with_benchmarks["Total_SQM"].rename("bounded_area_m2")
    greater_than_zero_floor_area = buildings_with_benchmarks["Total_SQM"] > 0
    greater_than_typical_benchmark_upper_bound = (
        buildings_with_benchmarks["Total_SQM"]
        > buildings_with_benchmarks["area_upper_bound_m2"]
    )
    valid_benchmark = ~buildings_with_benchmarks["Benchmark"].isin(["Unknown", "None"])
    area_is_greater_than_expected = (
        greater_than_zero_floor_area
        & greater_than_typical_benchmark_upper_bound
        & valid_benchmark
    )
    bounded_area_m2.loc[area_is_greater_than_expected] = buildings_with_benchmarks[
        "typical_area_m2"
    ].loc[area_is_greater_than_expected]
    buildings_with_benchmarks["bounded_area_m2"] = bounded_area_m2

    # Apply Benchmarks
    kwh_to_mwh = 1e-3
    buildings_with_benchmarks["electricity_demand_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks["typical_electricity_kwh_per_m2y"].fillna(0)
        * kwh_to_mwh
    ).fillna(0)
    buildings_with_benchmarks["fossil_fuel_demand_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks["typical_fossil_fuel_kwh_per_m2y"].fillna(0)
        * kwh_to_mwh
        * boiler_efficiency
    ).fillna(0)

    buildings_with_benchmarks["building_energy_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks["typical_building_energy_kwh_per_m2y"].fillna(0)
        * kwh_to_mwh
    )
    buildings_with_benchmarks["process_energy_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks["typical_process_energy_kwh_per_m2y"].fillna(0)
        * kwh_to_mwh
    )

    buildings_with_benchmarks["electricity_heat_demand_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks["typical_electricity_heat_kwh_per_m2y"].fillna(0)
        * kwh_to_mwh
        * boiler_efficiency
    ).fillna(0)
    buildings_with_benchmarks["fossil_fuel_heat_demand_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks["typical_fossil_fuel_heat_kwh_per_m2y"].fillna(0)
        * kwh_to_mwh
        * boiler_efficiency
    ).fillna(0)
    buildings_with_benchmarks["industrial_low_temperature_heat_demand_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks[
            "typical_industrial_low_temperature_heat_kwh_per_m2y"
        ].fillna(0)
        * kwh_to_mwh
    )
    buildings_with_benchmarks["industrial_high_temperature_heat_demand_mwh_per_y"] = (
        bounded_area_m2.fillna(0)
        * buildings_with_benchmarks[
            "typical_industrial_high_temperature_heat_kwh_per_m2y"
        ].fillna(0)
        * kwh_to_mwh
    )

    buildings_with_benchmarks.to_csv(product)


def link_valuation_office_to_boundaries(upstream: Any, product: Any) -> None:
    valuation_office = pd.read_csv(upstream["apply_energy_benchmarks_to_floor_areas"])
    small_area_boundaries = gpd.read_file(
        str(upstream["download_small_area_boundaries"])
    )

    valuation_office_geo = gpd.GeoDataFrame(
        valuation_office,
        geometry=gpd.points_from_xy(
            x=valuation_office["X_ITM"], y=valuation_office["Y_ITM"], crs="EPSG:2157"
        ),
    )
    valuation_office_in_small_areas = gpd.sjoin(
        valuation_office_geo,
        small_area_boundaries,
        op="within",
    ).drop(columns="geometry")
    valuation_office_in_small_areas.to_csv(product)


def save_building_columns(
    upstream: Any, product: Any, columns: str, filter_on_column: str
) -> None:
    attribute_columns = [
        "PropertyNo",
        "Category",
        "Use1",
        "Use2",
        "List_Status",
        "Benchmark",
        "Total_SQM",
        "bounded_area_m2",
    ]
    boundary_columns = [
        "X_ITM",
        "Y_ITM",
        "small_area",
        "cso_ed_id",
        "countyname",
        "local_authority",
        "RoutingKey",
    ]
    use_columns = attribute_columns + columns + boundary_columns
    buildings = pd.read_csv(
        upstream["link_valuation_office_to_boundaries"], index_col=0
    ).loc[:, use_columns]
    non_zero_rows = buildings[filter_on_column] > 0
    buildings[non_zero_rows].to_csv(product, index=False)
