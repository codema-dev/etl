# %%
from os import path
from shutil import unpack_archive
from urllib.request import urlretrieve

import dask.dataframe as dd
from berpublicsearch.download import download_berpublicsearch_parquet
import pandas as pd
import numpy as np

# %%
path_to_census_stock = "../data/dublin_building_stock_up_to_2011.csv"
if not path.exists(path_to_census_stock):
    urlretrieve(
        url="https://zenodo.org/record/4552498/files/dublin_building_stock_up_to_2011.csv",
        filename=path_to_census_stock,
    )
residential_stock_pre_2011 = pd.read_csv(path_to_census_stock)

# %%
path_to_berpublicsearch = "../data/BERPublicsearch_parquet"
if not path.exists(path_to_berpublicsearch):
    download_berpublicsearch_parquet(
        email_address="rowan.molony@codema.ie", savedir="../data"
    )

berpublicsearch_ireland = dd.read_parquet(path_to_berpublicsearch)
berpublicsearch_dublin = (
    berpublicsearch_ireland[
        berpublicsearch_ireland["CountyName"].str.contains("Dublin")
    ]
    .query("`CountyName` != ['Dublin 23']")  # doesn't exist
    .compute()
)

# %%
total_pre_2010 = residential_stock_pre_2011.groupby("postcodes")[
    "dwelling_type_unstandardised"
].count()

# %%
totals = []
for year in range(2011, 2020, 1):
    total_from_2010_to_year = (
        berpublicsearch_dublin.query(
            f"`Year_of_Construction` > 2010 and `Year_of_Construction` <= {year}"
        )
        .groupby("CountyName")["DwellingTypeDescr"]
        .count()
        .reindex(total_pre_2010.index)
        .fillna(0)
    )
    total = total_pre_2010 + total_from_2010_to_year
    total = total.rename(year)
    totals.append(total)

total_by_year = pd.concat(totals, axis="columns")

# %%
total_by_year.to_csv(f"../data/residential_total_buildings_by_year.csv")
