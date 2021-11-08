"""
Download the data provided by IPC in the tracking tool.

Link: http://www.ipcinfo.org/ipc-country-analysis/population-tracking-tool
IPC also has a mapping tool from which you can download a geojson
but the URL for that is not accessible and not all analyses are published on it
therefore this code uses the excel data provided by the tracking tool
The downloaded data has an "Area" column. It depends on the country which
level this is reported at.
Commonly it is admin2, but can also be at livelihood zone
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Union

import pandas as pd

from aatoolbox.utils.io import download_url, parse_yaml

logger = logging.getLogger(__name__)

# earliest available data can be 2017, so use that in URL
IPC_URL = (
    "http://mapipcissprd.us-east-1.elasticbeanstalk.com/api/"
    "public/population-tracking-tool/data/2017,{max_year}/"
    "?export=true&condition=A&country={iso2}"
)


def download_ipc(
    iso3: str,
    iso2: str,
    raw_output_dir: Union[Path, str],
    preprocess_output_dir: Union[Path, str],
):
    """
    Retrieve the IPC data from their Population Tracking Tool.

    Parameters
    ----------
    iso3: str
        iso3 code of country of interest
    iso2: str
        iso2 code of country of interest
    raw_output_dir: Path or str
        path to directory the raw file should be saved to
    preprocess_output_dir: Path or str
        path to directory the precprocessed file should be saved to

    Examples
    --------
    >>> from tempfile import TemporaryDirectory
    >>> download_fewsnet(iso3="som",iso2="so",output_dir=TemporaryDirectory())
    """
    # convert to path object if str
    if isinstance(raw_output_dir, str):
        raw_output_dir = Path(raw_output_dir)
    if isinstance(preprocess_output_dir, str):
        preprocess_output_dir = Path(preprocess_output_dir)
    # last year to retrieve data for
    # URL also works if this is in the future
    max_year = datetime.now().year
    url = IPC_URL.format(
        max_year=max_year,
        iso2=iso2,
    )
    raw_output_path = raw_output_dir / f"{iso3}_ipc_raw.xlsx"

    # have one file with all data per country, so also download if file already
    # exists to make sure it contains the newest data (contrary to
    # fewsnet)
    download_url(url, raw_output_path)

    preprocessed_output_path = (
        preprocess_output_dir / f"{iso3}_ipc_preprocessed.csv"
    )
    _preprocess_raw_data(raw_output_path, preprocessed_output_path)


def _preprocess_raw_data(
    raw_file_path: Path,
    output_path: Path,
):
    """
    Preprocess the downloaded data by checking.

    Parameters
    ----------
    raw_file_path : Path
        path to the file with the data to read
    output_path : Path
        path to write the preprocessed file to
    """
    df = pd.read_excel(
        raw_file_path,
        # on previous rows there is logo etc
        header=[11],
    )

    # only select rows with data, i.e. have a date of analysis
    # often have some rows with unneeded info for analysis
    # e.g. the disclaimer
    df = df[df["Date of Analysis"].notnull()]
    if df.empty:
        # a file from the url is downloaded regardless of whether
        # the iso2 is corrector ipc has done any analyses
        # thus check if there is actual data
        # we might want to check for correctness of iso2 already
        # before downloading (or when setting-up the config)
        raise RuntimeError(
            "Downloaded file doesn't contain any data. "
            "Make sure your iso2 code is correct."
        )

    # ipc excel file comes with horrible column names, so change them to
    # better understandable ones
    ipc_column_name_mapping = parse_yaml(
        Path(__file__).parent.resolve() / "ipc_column_mapping.yaml"
    )
    df = df.rename(columns=ipc_column_name_mapping)
    # due to excel settings, the percentages are on the 0 to 1 scale so
    # change to 0-100
    perc_cols = [c for c in df.columns if "perc" in c]
    df[perc_cols] = df[perc_cols] * 100
    df["date"] = pd.to_datetime(df["date"])

    # write preprocessed data to file
    df.to_csv(output_path, index=False)
