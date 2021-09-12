from typing import Any

import geopandas as gpd


def extract_dublin_niah_houses(upstream: Any, product: Any) -> None:
    small_area_boundaries = gpd.read_file(
        str(upstream["download_dublin_small_area_boundaries"])
    )
    ireland_niah = gpd.read_file(
        str(
            upstream[
                "download_ireland_national_inventory_of_architectural_heritage_buildings"
            ]
        )
    )
    dublin_niah = gpd.sjoin(
        ireland_niah.to_crs(epsg=2157), small_area_boundaries, op="within"
    )
    is_a_house = dublin_niah["CLASSDESC"].str.lower().str.contains("house")
    dublin_niah_houses = dublin_niah[is_a_house]
    dublin_niah_houses.to_file(str(product), driver="GPKG")


def extract_dublin_smr_houses(upstream: Any, product: Any) -> None:
    small_area_boundaries = gpd.read_file(
        str(upstream["download_dublin_small_area_boundaries"])
    )
    smr = gpd.read_file(
        str(upstream["download_dublin_sites_and_monuments_record_buildings"])
    )
    dublin_smr = gpd.sjoin(smr.to_crs(epsg=2157), small_area_boundaries, op="within")
    is_a_house = dublin_smr["COMPOSITION"].str.lower().str.contains("house")
    dublin_smr_houses = dublin_smr[is_a_house]
    dublin_smr_houses.to_file(str(product), driver="GPKG")