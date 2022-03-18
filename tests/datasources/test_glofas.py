"""Tests for GloFAS data download and processing."""
from pathlib import Path
from typing import List, Union

import numpy as np
import pandas as pd
import pytest
import xarray as xr
from cdsapi import Client

from aatoolbox.config.countryconfig import CountryConfig
from aatoolbox.datasources.glofas import glofas
from aatoolbox.datasources.glofas.forecast import (
    GlofasForecast,
    GlofasReforecast,
)
from aatoolbox.datasources.glofas.reanalysis import GlofasReanalysis
from aatoolbox.utils.geoboundingbox import GeoBoundingBox


def test_expand_dims():
    """Simple test case for expand dims."""
    rs = np.random.RandomState(12345)
    size_x, size_y = (10, 20)
    ds = xr.Dataset(
        data_vars={"var_a": (("x", "y"), rs.rand(size_x, size_y))},
        coords={"x": np.arange(size_x), "y": np.arange(size_y)},
    )
    ds.coords["z"] = 1
    assert "z" not in ds.dims.keys()
    ds = glofas.expand_dims(
        ds=ds,
        dataset_name="var_a",
        coord_names=["z", "x", "y"],
        expansion_dim=0,
    )
    assert "z" in ds.dims.keys()


class TestDownload:
    """Tests for GloFAS downloading."""

    geo_bounding_box = GeoBoundingBox(
        north=1.0, south=-2.2, east=3.3, west=-4.4
    )
    year = 2000
    leadtime_max = 3
    expected_geo_bounding_box = [1.05, -4.45, -2.25, 3.35]
    expected_months = [str(x + 1).zfill(2) for x in range(12)]
    expected_days = [str(x + 1).zfill(2) for x in range(31)]
    expected_leadtime = ["24", "48", "72"]

    @pytest.fixture()
    def mock_retrieve(self, mocker):
        """Mock out the CDS API."""
        mocker.patch.object(Path, "mkdir", return_value=None)
        mocker.patch.object(Client, "__init__", return_value=None)
        return mocker.patch.object(Client, "retrieve")

    def test_reanalysis_download(
        self,
        mock_country_config,
        mock_aa_data_dir,
        mock_retrieve,
    ):
        """
        Test GloFAS reanalysis download.

        Test that the query generated by the download method of GlofasReanlysis
        with default parameters is as expected
        """
        glofas_reanalysis = GlofasReanalysis(
            country_config=mock_country_config,
            geo_bounding_box=self.geo_bounding_box,
        )
        glofas_reanalysis.download(
            year_min=self.year,
            year_max=self.year,
        )
        expected_args = {
            "name": "cems-glofas-historical",
            "request": {
                "variable": "river_discharge_in_the_last_24_hours",
                "format": "grib",
                "dataset": ["consolidated_reanalysis"],
                "hyear": f"{self.year}",
                "hmonth": self.expected_months,
                "hday": self.expected_days,
                "geo_bounding_box": self.expected_geo_bounding_box,
                "system_version": "version_3_1",
                "hydrological_model": "lisflood",
            },
            "target": Path(
                f"{mock_aa_data_dir}/public/raw/{mock_country_config.iso3}"
                f"/glofas/cems-glofas-historical/"
                f"{mock_country_config.iso3}_"
                f"cems-glofas-historical_2000_Np1d1Sm2d2Ep3d4Wm4d5.grib"
            ),
        }
        mock_retrieve.assert_called_with(**expected_args)

    def test_forecast_download(
        self, mock_country_config, mock_aa_data_dir, mock_retrieve
    ):
        """
        Test GloFAS forecast download.

        Test that the query generated by the download method of GlofasForecast
        with default parameters is as expected
        """
        glofas_forecast = GlofasForecast(
            country_config=mock_country_config,
            geo_bounding_box=self.geo_bounding_box,
        )
        glofas_forecast.download(
            leadtime_max=self.leadtime_max,
            year_min=self.year,
            year_max=self.year,
        )
        expected_args = {
            "name": "cems-glofas-forecast",
            "request": {
                "variable": "river_discharge_in_the_last_24_hours",
                "format": "grib",
                "product_type": [
                    "control_forecast",
                    "ensemble_perturbed_forecasts",
                ],
                "year": f"{self.year}",
                "month": self.expected_months,
                "day": self.expected_days,
                "geo_bounding_box": self.expected_geo_bounding_box,
                "system_version": "operational",
                "hydrological_model": "lisflood",
                "leadtime_hour": self.expected_leadtime,
            },
            "target": Path(
                f"{mock_aa_data_dir}/public/raw/{mock_country_config.iso3}/"
                f"glofas/cems-glofas-forecast/"
                f"{mock_country_config.iso3}_"
                f"cems-glofas-forecast_2000_ltmax03d_Np1d1Sm2d2Ep3d4Wm4d5"
                f".grib"
            ),
        }
        mock_retrieve.assert_called_with(**expected_args)

    def test_reforecast_download(
        self, mock_country_config, mock_aa_data_dir, mock_retrieve
    ):
        """
        Test GloFAS reforecast download.

        Test that the query generated by the download method of
        GlofasReforecast with default parameters is as expected
        """
        glofas_reforecast = GlofasReforecast(
            country_config=mock_country_config,
            geo_bounding_box=self.geo_bounding_box,
        )
        glofas_reforecast.download(
            leadtime_max=self.leadtime_max,
            year_min=self.year,
            year_max=self.year,
        )
        expected_args = {
            "name": "cems-glofas-reforecast",
            "request": {
                "variable": "river_discharge_in_the_last_24_hours",
                "format": "grib",
                "product_type": [
                    "control_reforecast",
                    "ensemble_perturbed_reforecasts",
                ],
                "hyear": f"{self.year}",
                "hmonth": self.expected_months,
                "hday": self.expected_days,
                "geo_bounding_box": self.expected_geo_bounding_box,
                "system_version": "version_3_1",
                "hydrological_model": "lisflood",
                "leadtime_hour": self.expected_leadtime,
            },
            "target": Path(
                f"{mock_aa_data_dir}/public/raw/{mock_country_config.iso3}/"
                f"glofas/cems-glofas-reforecast/"
                f"{mock_country_config.iso3}_"
                f"cems-glofas-reforecast_2000_ltmax03d_Np1d1Sm2d2Ep3d4Wm4d5"
                f".grib"
            ),
        }
        mock_retrieve.assert_called_with(**expected_args)


class TestProcess:
    """Tests for GloFAS processing."""

    geo_bounding_box = GeoBoundingBox(north=1, south=-2, east=3, west=-4)
    year = 2000
    leadtime_max = 3
    numbers = [0, 1, 2, 3, 4, 5, 6]

    def get_raw_data(
        self,
        number_coord: Union[List[int], int] = None,
        include_step: bool = False,
        include_history: bool = False,
        dis24: np.ndarray = None,
    ) -> xr.Dataset:
        """
        Construct a simple fake GloFAS xarray dataset.

        Parameters
        ----------
        number_coord : list or int, default = None
            The ensemble number coordinate
        include_step :  bool, default = False
            Whether to include the forecast step coordinate
        include_history : bool, default = False
            Whether to include the history attribute
        dis24 : np.ndarray, default = None
            Optional array of discharge values, that should have the combined
            dimensions of the coordinates. If not passed, generated using
            random numbers.

        Returns
        -------
        Simplified GloFAS xarray dataset
        """
        rng = np.random.default_rng(12345)
        coords = {}
        if number_coord is not None:
            coords["number"] = number_coord
        coords["time"] = pd.date_range("2014-09-06", periods=2)
        if include_step:
            coords["step"] = [np.datetime64(n + 1, "D") for n in range(5)]
        coords["latitude"] = (
            np.arange(
                start=self.geo_bounding_box.south,
                stop=self.geo_bounding_box.north + 2,
                step=0.1,
            )
            - 0.05
        )
        coords["longitude"] = (
            np.arange(
                start=self.geo_bounding_box.west,
                stop=self.geo_bounding_box.east + 2,
                step=0.1,
            )
            - 0.05
        )
        dims = list(coords.keys())
        if number_coord is not None and isinstance(number_coord, int):
            dims = dims[1:]
        if dis24 is None:
            dis24 = 5000 + 100 * rng.random([len(coords[dim]) for dim in dims])
        attrs = {}
        if include_history:
            attrs = {"history": "fake history"}
        return xr.Dataset({"dis24": (dims, dis24)}, coords=coords, attrs=attrs)

    @pytest.fixture()
    def mock_ensemble_raw(self) -> (xr.Dataset, xr.Dataset, np.ndarray):
        """
        Create fake raw ensemble data.

        For the forecast and reforecast, generate the raw data, which consists
        of the control and perturbed forecast, and combine the discharge
        values for the processed data. Return both xarray datasets and the
        combined array.
        """
        cf_raw = self.get_raw_data(
            number_coord=self.numbers[0],
            include_step=True,
            include_history=True,
        )
        pf_raw = self.get_raw_data(
            number_coord=self.numbers[1:],
            include_step=True,
            include_history=True,
        )
        expected_dis24 = np.concatenate(
            (cf_raw["dis24"].values[np.newaxis, ...], pf_raw["dis24"].values)
        )
        return cf_raw, pf_raw, expected_dis24

    def get_processed_data(
        self,
        country_config: CountryConfig,
        number_coord: [List[int], int] = None,
        include_step: bool = False,
        dis24: np.ndarray = None,
    ) -> xr.Dataset:
        """
        Create a simplified fake processed GloFAS dataset.

        Parameters
        ----------
        country_config : CountryConfig
            Country configuration object
        number_coord : list or int, default = None
            The ensemble number coordinate
        include_step : bool, default = False
            Whether to include the forecast step coordinate
        dis24 : np.ndarray, default = None
            Optional array of discharge values, that should have the combined
            dimensions of the coordinates. If not passed, generated using
            random numbers.

        Returns
        -------
        GloFAS processed xarray dataset
        """
        raw_data = self.get_raw_data(
            number_coord=number_coord, include_step=include_step, dis24=dis24
        )
        coords = {}
        if number_coord is not None:
            coords = {"number": number_coord}
        coords["time"] = raw_data.time
        if include_step:
            coords["step"] = raw_data.step
        return xr.Dataset(
            {
                reporting_point.name: (
                    list(coords.keys()),
                    raw_data["dis24"]
                    .sel(
                        longitude=reporting_point.lon,
                        latitude=reporting_point.lat,
                        method="nearest",
                    )
                    .data,
                )
                for reporting_point in country_config.glofas.reporting_points
            },
            coords=coords,
        )

    @pytest.fixture()
    def mock_processed_data_reanalysis(
        self, mocker, mock_country_config
    ) -> xr.Dataset:
        """Create fake processed GloFAS reanalysis data."""
        mocker.patch.object(
            xr, "open_mfdataset", return_value=self.get_raw_data()
        )
        return self.get_processed_data(country_config=mock_country_config)

    @pytest.fixture()
    def mock_processed_data_forecast(
        self, mock_ensemble_raw, mocker, mock_country_config
    ):
        """Create fake processed GloFAS forecast or reforecast data."""
        cf_raw, pf_raw, expected_dis24 = mock_ensemble_raw
        mocker.spy(xr, "open_mfdataset").side_effect = [cf_raw, pf_raw]
        return self.get_processed_data(
            country_config=mock_country_config,
            number_coord=self.numbers,
            include_step=True,
            dis24=mock_ensemble_raw[2],
        )

    def test_reanalysis_process(
        self, mock_country_config, mock_processed_data_reanalysis
    ):
        """Test GloFAS reanalysis process method."""
        glofas_reanalysis = GlofasReanalysis(
            country_config=mock_country_config,
            geo_bounding_box=self.geo_bounding_box,
        )
        output_filepath = glofas_reanalysis.process()
        output_ds = xr.load_dataset(output_filepath)
        assert output_ds.equals(mock_processed_data_reanalysis)

    def test_reforecast_process(
        self, mock_country_config, mock_processed_data_forecast
    ):
        """Test GloFAS reforecast process method."""
        glofas_reforecast = GlofasReforecast(
            country_config=mock_country_config,
            geo_bounding_box=self.geo_bounding_box,
        )
        output_filepath = glofas_reforecast.process(
            leadtime_max=self.leadtime_max,
            year_min=self.year,
            year_max=self.year,
        )
        output_ds = xr.load_dataset(output_filepath)
        assert output_ds.equals(mock_processed_data_forecast)

    def test_forecast_process(
        self, mock_country_config, mock_processed_data_forecast
    ):
        """Test GloFAS forecast process method."""
        glofas_forecast = GlofasReforecast(
            country_config=mock_country_config,
            geo_bounding_box=self.geo_bounding_box,
        )
        output_filepath = glofas_forecast.process(
            leadtime_max=self.leadtime_max,
            year_min=self.year,
            year_max=self.year,
        )
        output_ds = xr.load_dataset(output_filepath)
        assert output_ds.equals(mock_processed_data_forecast)