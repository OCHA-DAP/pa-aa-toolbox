"""Tests for the Chirps module."""
import calendar
from datetime import date
from pathlib import Path

import cftime
import numpy as np
import pytest
import xarray as xr
from xarray.coding.cftimeindex import CFTimeIndex

from aatoolbox import ChirpsDaily, ChirpsMonthly, GeoBoundingBox

DATASOURCE_BASE_DIR = "chirps"

START_DATE = date(year=2020, month=7, day=15)
END_DATE = date(year=2020, month=8, day=1)
CURRENT_DATE = date(year=2022, month=5, day=31)
PAST_DATE = date(year=1970, month=1, day=1)
FUTURE_DATE = date(year=2100, month=10, day=2)

START_YEAR = "2020"
START_MONTH = "07"
START_MONTH_NAME = "Jul"
START_DAY = "15"

END_YEAR = "2020"
END_MONTH = "08"
END_MONTH_NAME = "Aug"
END_DAY = "01"


@pytest.fixture
def mock_chirps(mocker, mock_country_config):
    """Create Chirps class with mock country config."""
    geo_bounding_box = GeoBoundingBox(
        lat_max=6, lat_min=3.2, lon_max=2, lon_min=-3
    )

    mocker.patch(
        (
            "aatoolbox.datasources.chirps.chirps.ChirpsDaily"
            "._get_last_available_date"
        ),
        return_value=CURRENT_DATE,
    )

    mocker.patch(
        (
            "aatoolbox.datasources.chirps.chirps.ChirpsMonthly"
            "._get_last_available_date"
        ),
        return_value=CURRENT_DATE,
    )

    def _mock_chirps(
        frequency: str = "daily",
        resolution: float = 0.05,
        start_date: date = START_DATE,
        end_date: date = END_DATE,
    ):
        if frequency == "daily":
            chirps = ChirpsDaily(
                country_config=mock_country_config,
                geo_bounding_box=geo_bounding_box,
                resolution=resolution,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            chirps = ChirpsMonthly(
                country_config=mock_country_config,
                geo_bounding_box=geo_bounding_box,
                start_date=start_date,
                end_date=end_date,
            )
        return chirps

    return _mock_chirps


@pytest.fixture
def mock_xr_open_multiple_dataset(mocker):
    """Mock GeoPandas file reading function."""
    ds = xr.Dataset()
    return mocker.patch(
        "aatoolbox.datasources.chirps.chirps.xr.open_mfdataset",
        return_value=ds,
    )


@pytest.fixture
def mock_dataset_to_netcdf(mocker):
    """Mock GeoPandas file writing function."""
    return mocker.patch(
        "aatoolbox.datasources.chirps.chirps.xr.Dataset.to_netcdf",
    )


@pytest.fixture
def mock_download(mocker, mock_chirps):
    """Create mock for download method."""
    download_mock = mocker.patch(
        "aatoolbox.datasources.chirps.chirps._Chirps._download"
    )

    def _mock_download(
        frequency: str,
    ):
        chirps = mock_chirps(
            frequency=frequency,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        chirps.download()
        args_download = download_mock.call_args_list
        url_list = [k["url"] for (_, k) in args_download]
        filepath_list = [k["filepath"] for (_, k) in args_download]
        return url_list, filepath_list

    return _mock_download


def test_valid_arguments_class(mocker, mock_country_config):
    """Test for resolution and wrong dates in initialisation class."""
    mocker.patch(
        (
            "aatoolbox.datasources.chirps.chirps.ChirpsDaily"
            "._get_last_available_date"
        ),
        return_value=CURRENT_DATE,
    )

    geo_bounding_box = GeoBoundingBox(
        lat_max=6, lat_min=3.2, lon_max=2, lon_min=-3
    )
    with pytest.raises(ValueError):
        ChirpsDaily(
            country_config=mock_country_config,
            geo_bounding_box=geo_bounding_box,
            resolution=0.10,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        ChirpsDaily(
            country_config=mock_country_config,
            geo_bounding_box=geo_bounding_box,
            resolution=0.10,
            start_date=START_DATE,
            end_date=FUTURE_DATE,
        )
        ChirpsDaily(
            country_config=mock_country_config,
            geo_bounding_box=geo_bounding_box,
            resolution=0.10,
            start_date=PAST_DATE,
            end_date=END_DATE,
        )


def test_download_monthly(
    mock_aa_data_dir, mock_country_config, mock_download
):
    """Test of call download for monthly data."""
    url_list, filepath_list = mock_download(frequency="monthly")

    url_list_control = [
        (
            "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/"
            ".CHIRPS/.v2p0/.monthly/.global/.precipitation/"
            f"X/%28-3.0%29%282.0%29RANGEEDGES/"
            f"Y/%286.0%29%283.2%29RANGEEDGES/"
            f"T/%28{MONTH_NAME}%20{START_YEAR}%29"
            f"%28{MONTH_NAME}%20{START_YEAR}"
            "%29RANGEEDGES/data.nc"
        )
        for MONTH_NAME in [
            calendar.month_abbr[month]
            for month in range(int(START_MONTH), int(END_MONTH) + 1)
        ]
    ]

    filepath_list_control = [
        mock_aa_data_dir
        / (
            f"public/raw/{mock_country_config.iso3}/{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_monthly_{START_YEAR}_{MONTH:02d}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
        for MONTH in range(int(START_MONTH), int(END_MONTH) + 1)
    ]

    assert url_list == url_list_control
    assert filepath_list == filepath_list_control


def test_download_daily(mock_aa_data_dir, mock_country_config, mock_download):
    """Test of call download for daily data."""
    url_list, filepath_list = mock_download(frequency="daily")

    url_list_control = [
        (
            "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/"
            ".CHIRPS/.v2p0/.daily-improved/.global/.0p05/.prcp/"
            f"X/%28-3.0%29%282.0%29RANGEEDGES/"
            f"Y/%286.0%29%283.2%29RANGEEDGES/"
            f"T/%28{DAY:02d}%20{START_MONTH_NAME}%20{START_YEAR}"
            f"%29%28{DAY:02d}%20{START_MONTH_NAME}%20{START_YEAR}"
            "%29RANGEEDGES/data.nc"
        )
        for DAY in range(int(START_DAY), 32)
    ]

    url_list_control.append(
        "https://iridl.ldeo.columbia.edu/SOURCES/.UCSB/"
        ".CHIRPS/.v2p0/.daily-improved/.global/.0p05/.prcp/"
        f"X/%28-3.0%29%282.0%29RANGEEDGES/"
        f"Y/%286.0%29%283.2%29RANGEEDGES/"
        f"T/%2801%20{END_MONTH_NAME}%20{START_YEAR}"
        f"%29%2801%20{END_MONTH_NAME}%20{START_YEAR}"
        "%29RANGEEDGES/data.nc"
    )

    filepath_list_control = [
        mock_aa_data_dir
        / (
            f"public/raw/{mock_country_config.iso3}/{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_daily_{START_YEAR}_{START_MONTH}_{DAY}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
        for DAY in range(int(START_DAY), 32)
    ]

    filepath_list_control.append(
        mock_aa_data_dir
        / (
            f"public/raw/{mock_country_config.iso3}/{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_daily_{START_YEAR}_{END_MONTH}_{END_DAY}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
    )

    assert url_list == url_list_control
    assert filepath_list == filepath_list_control


def test_process_monthly(
    mocker,
    mock_chirps,
    mock_aa_data_dir,
    mock_country_config,
    mock_dataset_to_netcdf,
):
    """Test process monthl data."""
    ds = xr.DataArray(
        np.reshape(a=np.arange(8), newshape=(2, 2, 2)),
        dims=("X", "Y", "T"),
        coords={
            "X": [1, 2],
            "Y": [2, -3],
            "T": [685.5, 686.5],
        },
    ).to_dataset(name="prcp")

    ds["T"].attrs["calendar"] = "360"
    ds["T"].attrs["units"] = "months since 1960-01-01"

    mock_xr_open_dataset = mocker.patch(
        "aatoolbox.datasources.chirps.chirps.xr.open_dataset",
        return_value=ds,
    )

    input_filepath_list_control = [
        mock_aa_data_dir
        / (
            f"public/raw/{mock_country_config.iso3}/"
            f"{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_monthly_{START_YEAR}_{MONTH:02d}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
        for MONTH in range(int(START_MONTH), int(END_MONTH) + 1)
    ]

    output_filepath_list_control = [
        Path(str(f).replace("raw", "processed"))
        for f in input_filepath_list_control
    ]

    chirps = mock_chirps(frequency="monthly")
    processed_path = chirps.process()

    args_input_process = mock_xr_open_dataset.call_args_list
    input_filepath_list = [k[0] for (k, _) in args_input_process]

    args_output_process = mock_dataset_to_netcdf.call_args_list
    output_filepath_list = [k["path"] for (_, k) in args_output_process]
    output_dataset_list = [k[0] for (k, _) in args_output_process]
    output_ds = output_dataset_list[0]

    assert input_filepath_list == input_filepath_list_control
    assert output_filepath_list == output_filepath_list_control

    assert processed_path == (
        mock_aa_data_dir
        / f"public/processed/{mock_country_config.iso3}/{DATASOURCE_BASE_DIR}/"
    )

    expected_f = CFTimeIndex(
        [
            cftime.Datetime360Day(year=2017, month=2, day=16),
            cftime.Datetime360Day(year=2017, month=3, day=16),
        ]
    )

    assert np.array_equal(output_ds.X.values, [1, 2])
    assert np.array_equal(output_ds.Y.values, [2, -3])
    assert output_ds.get_index("T").equals(expected_f)
    assert np.array_equal(
        output_ds.precipitation.values,
        np.reshape(a=np.arange(8), newshape=(2, 2, 2)),
    )


def test_process_daily(
    mocker,
    mock_chirps,
    mock_aa_data_dir,
    mock_country_config,
    mock_dataset_to_netcdf,
):
    """Test process daily data."""
    ds = xr.DataArray(
        np.reshape(a=np.arange(8), newshape=(2, 2, 2)),
        dims=("X", "Y", "T"),
        coords={
            "X": [1, 2],
            "Y": [2, -3],
            "T": [2454397.0, 2454398.0],
        },
    ).to_dataset(name="prcp")

    ds["T"].attrs["calendar"] = "standard"
    ds["T"].attrs["units"] = "julian_day"

    mock_xr_open_dataset = mocker.patch(
        "aatoolbox.datasources.chirps.chirps.xr.open_dataset",
        return_value=ds,
    )

    input_filepath_list_control = [
        mock_aa_data_dir
        / (
            f"public/raw/{mock_country_config.iso3}/"
            f"{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_daily_{START_YEAR}_{START_MONTH}_{DAY}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
        for DAY in range(int(START_DAY), 32)
    ]

    input_filepath_list_control.append(
        mock_aa_data_dir
        / (
            f"public/raw/{mock_country_config.iso3}/"
            f"{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_daily_{START_YEAR}_{END_MONTH}_{END_DAY}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
    )

    output_filepath_list_control = [
        Path(str(f).replace("raw", "processed"))
        for f in input_filepath_list_control
    ]

    chirps = mock_chirps(frequency="daily")
    processed_path = chirps.process()

    args_input_process = mock_xr_open_dataset.call_args_list
    input_filepath_list = [k[0] for (k, _) in args_input_process]

    args_output_process = mock_dataset_to_netcdf.call_args_list
    output_filepath_list = [k["path"] for (_, k) in args_output_process]
    output_dataset_list = [k[0] for (k, _) in args_output_process]
    output_ds = output_dataset_list[0]

    assert input_filepath_list == input_filepath_list_control
    assert output_filepath_list == output_filepath_list_control

    assert processed_path == (
        mock_aa_data_dir
        / f"public/processed/{mock_country_config.iso3}/{DATASOURCE_BASE_DIR}/"
    )

    expected_f = CFTimeIndex(
        [
            cftime.DatetimeGregorian(year=2007, month=10, day=23, hour=12),
            cftime.DatetimeGregorian(year=2007, month=10, day=24, hour=12),
        ]
    )

    assert np.array_equal(output_ds.X.values, [1, 2])
    assert np.array_equal(output_ds.Y.values, [2, -3])
    assert output_ds.get_index("T").equals(expected_f)
    assert np.array_equal(
        output_ds.precipitation.values,
        np.reshape(a=np.arange(8), newshape=(2, 2, 2)),
    )


def test_chirps_load_monthly(
    mock_xr_open_multiple_dataset,
    mock_chirps,
    mock_aa_data_dir,
    mock_country_config,
):
    """Test load monthly data."""
    filepath_list_control = [
        mock_aa_data_dir
        / (
            f"public/processed/{mock_country_config.iso3}/"
            f"{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_monthly_{START_YEAR}_{MONTH:02d}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
        for MONTH in range(int(START_MONTH), int(END_MONTH) + 1)
    ]

    chirps = mock_chirps(frequency="monthly")
    chirps.load()
    args_download = mock_xr_open_multiple_dataset.call_args
    filepath_list = args_download[0][0]

    ds = mock_xr_open_multiple_dataset()

    assert ds.attrs["included_files"] == [
        filepath.stem for filepath in filepath_list
    ]
    assert filepath_list == filepath_list_control


def test_chirps_load_daily(
    mock_xr_open_multiple_dataset,
    mock_chirps,
    mock_aa_data_dir,
    mock_country_config,
):
    """Test load daily data."""
    filepath_list_control = [
        mock_aa_data_dir
        / (
            f"public/processed/{mock_country_config.iso3}/"
            f"{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_daily_{START_YEAR}_{START_MONTH}_{DAY}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
        for DAY in range(int(START_DAY), 32)
    ]

    filepath_list_control.append(
        mock_aa_data_dir
        / (
            f"public/processed/{mock_country_config.iso3}/"
            f"{DATASOURCE_BASE_DIR}/"
            f"abc_chirps_daily_{START_YEAR}_{END_MONTH}_{END_DAY}_"
            "r0.05_Np6Sp3Ep2Wm3.nc"
        )
    )

    chirps = mock_chirps(frequency="daily")
    chirps.load()
    args_download = mock_xr_open_multiple_dataset.call_args
    filepath_list = args_download[0][0]

    ds = mock_xr_open_multiple_dataset()

    assert ds.attrs["included_files"] == [
        filepath.stem for filepath in filepath_list
    ]
    assert filepath_list == filepath_list_control
