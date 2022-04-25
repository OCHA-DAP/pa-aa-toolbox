"""Tests for the raster utilities module."""
import doctest
import logging
import unittest

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
import xarray as xr
from pandas._testing import assert_frame_equal
from rioxarray.exceptions import DimensionError, MissingCRS
from shapely.geometry import Polygon

from aatoolbox.utils import raster

suite = unittest.TestSuite()
suite.addTest(doctest.DocTestSuite(raster))
unittest.TextTestRunner().run(suite)


@pytest.fixture
def gdf():
    """Create geodataframe for testing."""
    d = {
        "name": ["area_a", "area_b"],
        "geometry": [
            Polygon([(0, 0), (0, 2), (2, 2), (2, 0)]),
            Polygon([(2, 0), (2, 2), (3, 2), (3, 0)]),
        ],
    }
    return gpd.GeoDataFrame(d)


@pytest.fixture
def gdf_missing(gdf):
    """Create geodataframe for testing with area not overlapping raster."""
    d = {
        "name": ["area_c"],
        "geometry": [Polygon([(3, 0), (3, 2), (4, 2), (4, 0)])],
    }
    df_missing = pd.concat([gdf, pd.DataFrame(d)], ignore_index=True)
    return gpd.GeoDataFrame(df_missing)


@pytest.fixture
def da_2d():
    """Create 2d raster array."""
    da = xr.DataArray(
        [[1, 2, 3], [4, 5, 6]],
        dims=("y", "x"),
        coords={"y": [1.5, 0.5], "x": [0.5, 1.5, 2.5]},
    ).rio.write_crs("EPSG:4326")
    return da


@pytest.fixture
def da_3d():
    """Create 3d raster array."""
    da = xr.DataArray(
        [
            [[1, 2, 3], [4, 5, 6]],
            [[1, 2, 3], [4, 5, 6]],
        ],
        dims=("time", "y", "x"),
        coords={
            "time": ["2020-01-01", "2020-01-02"],
            "y": [1.5, 0.5],
            "x": [0.5, 1.5, 2.5],
        },
    ).rio.write_crs("EPSG:4326")
    return da


@pytest.fixture
def ds_3d(da_3d):
    """Create 3d raster dataset."""
    return da_3d.to_dataset(name="val")


@pytest.fixture
def expected_2d():
    """Create expected comped stats for 2d raster."""
    df = pd.DataFrame(
        {
            "mean": {0: 3.0, 1: 4.5},
            "std": {0: 1.5811388300841898, 1: 1.5},
            "min": {0: 1, 1: 3},
            "max": {0: 5, 1: 6},
            "sum": {0: 12.0, 1: 9.0},
            "count": {0: 4, 1: 2},
            "name": {0: "area_a", 1: "area_b"},
        },
    )
    return df


@pytest.fixture
def expected_3d(expected_2d):
    """Create expected comped stats for 3d raster."""
    df_3d = pd.DataFrame(np.repeat(expected_2d.values, 2, axis=0))
    df_3d.columns = expected_2d.columns
    df_3d.insert(loc=0, column="time", value=["2020-01-01", "2020-01-02"] * 2)
    return df_3d


def test_compute_raster_stats_2d(da_2d, gdf, expected_2d):
    """Compute raster stats without time dimensions."""
    result = da_2d.aat.compute_raster_stats(gdf, "name")
    assert_frame_equal(result, expected_2d, check_dtype=False)
    expected_2d.insert(loc=6, column="95quant", value=[4.85, 5.85])
    result_pct = da_2d.aat.compute_raster_stats(
        gdf=gdf, feature_col="name", percentile_list=[95]
    )
    assert_frame_equal(result_pct, expected_2d, check_dtype=False)


def test_compute_raster_stats_3d(ds_3d, gdf, expected_3d):
    """Compute raster stats with time dimensions."""
    result = ds_3d.aat.compute_raster_stats(
        var_names=["val"], gdf=gdf, feature_col="name"
    )
    assert_frame_equal(result[0], expected_3d, check_dtype=False)
    result_all_vars = ds_3d.aat.compute_raster_stats(
        gdf=gdf, feature_col="name"
    )
    assert_frame_equal(result_all_vars[0], expected_3d, check_dtype=False)
    result_str = ds_3d.aat.compute_raster_stats(
        var_names="val", gdf=gdf, feature_col="name"
    )
    assert_frame_equal(result_str[0], expected_3d, check_dtype=False)


def test_compute_raster_stats_da_assertions(da_3d, gdf):
    """Ensure error assertions working in compute raster stats."""
    with pytest.raises(MissingCRS):
        da_3d.aat._crs = False
        da_3d.aat.compute_raster_stats(gdf=gdf, feature_col="name")


def test_set_time_dim(da_2d):
    """Ensure error assertions working in set time dim."""
    with pytest.raises(DimensionError):
        da_2d.aat.set_time_dim("time")


def test_correct_calendar_change(da_3d, caplog):
    """Ensure calendar logs change from 360 to 360_day."""
    caplog.set_level(logging.INFO)
    da_3d[da_3d.aat.t_dim].attrs["calendar"] = "360"
    da_3d.aat.correct_calendar()
    assert "Calendar attribute changed from '360' to '360_day'." in caplog.text


def test_correct_calendar_add(da_3d, caplog):
    """Ensure calendar logs change from units to 360_day."""
    caplog.set_level(logging.INFO)
    da_3d[da_3d.aat.t_dim].attrs["units"] = "months since 1960-01-01"
    da_3d.aat.correct_calendar()
    assert (
        "Calendar attribute '360_day' added, "
        "equivalent of 'units' 'months since'." in caplog.text
    )


def test_correct_calendar_no_change(da_3d, caplog):
    """Ensure calendar logs no change."""
    caplog.set_level(logging.INFO)
    da_3d[da_3d.aat.t_dim].attrs["calendar"] = "360_day"
    da_3d.aat.correct_calendar()
    assert "No 'units' or 'calendar' attributes to correct." in caplog.text


def test_change_longitude_range_no_change(da_2d, caplog):
    """Ensure change longitude logs no change."""
    caplog.set_level(logging.INFO)
    da_2d.aat.change_longitude_range()
    assert "Coordinates already in required range." in caplog.text


def test_compute_raster_stats_no_data_in_bounds(
    da_2d, gdf_missing, expected_2d, caplog
):
    """Ensure compute stats skips non-overlapping areas correctly."""
    caplog.set_level(logging.INFO)
    result = da_2d.aat.compute_raster_stats(
        gdf=gdf_missing, feature_col="name"
    )
    assert "No overlapping raster cells for area_c, skipping." in caplog.text
    assert_frame_equal(result, expected_2d, check_dtype=False)


def test_get_raster_array_crs(ds_3d):
    """Ensure dataset to array works when CRS set."""
    da = ds_3d.aat.get_raster_array("val")
    assert da.rio.crs == ds_3d.rio.crs
