USGS
======

Background
----------

The United States Geological Survey, `USGS <https://www.usgs.gov/>`_ provides a wide
range of geo-spatial data and satellite imagery products in support of the
Famine Early Warning Systems Network, `FEWS NET <https://earlywarning.usgs.gov/fews>`_.
These products are used to support FEWS NET drought monitoring efforts, from rainfall
data to vegetation measurements.

The availability of data for each source varies,
but are often available for every dekad or pentad for a number of years. The
geographic coverage is typically comprehensive of the African continent, where
the majority of FEWS NET's work is focused, with additional areas covered on an
ad hoc basis. This module for now just provides access to the normalized
difference vegetation index (`NDVI <https://en.wikipedia.org/wiki/Normalized_difference_vegetation_index>`_)
data provided by the USGS.

NDVI data is generated from eMODIS AQUA and published data includes temporally smoothed NDVI, median anomaly,
difference from the previous year, and median anomaly presented as a percentile. Full methodological
details are available on the `Documentation page <https://earlywarning.usgs.gov/fews/product/449#documentation>`_
for the specific coverage area. The data is made available for the following areas of coverage:

- `north-africa<https://earlywarning.usgs.gov/fews/product/449>`_
- `east-africa<https://earlywarning.usgs.gov/fews/product/448>`_
- `southern-africa<https://earlywarning.usgs.gov/fews/product/450>`_
- `west-africa<https://earlywarning.usgs.gov/fews/product/451>`_
- `central-asia<https://earlywarning.usgs.gov/fews/product/493>`_
- `yemen<https://earlywarning.usgs.gov/fews/product/502>`_
- `central-america<https://earlywarning.usgs.gov/fews/product/445>`_
- `hispaniola<https://earlywarning.usgs.gov/fews/product/446>`_

Data is published at the dekadal level, and is released soon after the end of the dekad.
After a period of 3 dekads, data is updated with temporal smoothing and error correction
for cloud cover. Files for a specific dekad and region can range from 30MB up to over 100MB,
so downloading and processing can take a long time.


USGS publishes its data through its `web portal <https://earlywarning.usgs.gov/fews/datadownloads/East%20Africa/eMODIS%20NDVI%20C6>`_,
which allows downloading data for a single geographical area and dekad. This data
is extracted from the `back end data explorer <https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/fews/web/africa/east/dekadal/emodis/ndvi_c6/temporallysmoothedndvi/downloads/monthly/>`_.
This module is designed to allow programmatic access to and analysis of NDVI data from the data explorer.

Usage
-----

To use this class, you first need to create a country configuration
for the country you would like to analyze. You also need to supply the area
of coverage that the country data is contained in. You can Make sure FEWS NET covers the country
of interest. You can find area of coverage for NDVI by searching for eMODIS NDVI C6 on
the  `USGS search portal <https://earlywarning.usgs.gov/fews/search>`_.
The valid values of the area names are listed above under Background.

An example country config for Ethiopia is:

.. code-block:: python

    iso3: eth
    usgs_ndvi:
        region_name: east-africa

For a number of countries this config has been implemented already.
For others, you can create a custom country config.
Once you have created the config you can load it:

.. code-block:: python

    from aatoolbox import create_country_config
    country_config = create_country_config(iso3="eth")

Next you need to instantiate the USGS NDVI class with the country config. For this
example, we will use the class for accessing temporally smoothed NDVI values. Since
the size of the data we will be working with is so large, we will only look at a
sample of data from a few dekads, corresponding to the dates in January:

.. code-block:: python

    from aatoolbox import UsgsNdviSmoothed
    ndvi_smooth = UsgsNdviSmoothed(
        country_config=country_config,
        start_date="2021-01-01",
        end_date="2021-01-31"
    )

We will first need to download the NDVI data if you haven't used the class before.
The code downloads all data between `start_date` and `end_date`. Be careful if not
setting start and end date during instantiation, the method will automatically
look for data between the first available data in the 19th dekad of 2002 and today.
We simply have to call the method to download available data.

.. code-block:: python

    ndvi_smooth.download()

Since each NDVI file is downloaded as a .tif, we can load them in individually as
rasters. We can do this for a specific date. This time we will specify the date
as a year and dekad tuple, although specify as a `datetime.date` or string as
above is equally appropriate.

.. code-block:: python

    ndvi_2021_01 = ndvi_smooth.load_raster(date=(2021, 1))

If time series analysis is desired on the NDVI data, the user can manually do this
using loaded in data arrays. However, given the size of the individual raster files,
this module provides the `process()` method that calculate statistics for
a given area. For this, we need to provide a geodataframe and column to aggregate to.

Let's load the country administrative boundaries for Ethiopia from our country
config, and use this to calculate basic statistics for the dekads we've loaded.

.. code-block:: python

    from aatoolbox import CodAB

    eth_cod = CodAB(country_config=country_config)
    # assuming you've downloaded the file already
    eth_gdf0 = eth_cod.load(admin_level=0)
    ndvi_smooth.process(
        gdf=eth_gdf0,
        feature_col="ADM0_EN"
    )

We can then load in and use the calculated statistics using `load()`. Since the
processed file is saved based on the `feature_col` name, we have to pass
`feature_col` to load in the correct data.

.. code-block:: python
    ndvi_smooth.load(feature_col="ADM0_EN")
