CHIRPS
===

Background
----------

The Climate Hazards Center at UC Santa Barbara (`CHC <https://www.chc.ucsb.edu/>`_),
in collaboration with scientists at the USGS Earth Resources Observation and Science
(`EROS <https://www.usgs.gov/centers/eros>`_) Center, created the Climate Hazards group
Infrared Precipitation with Stations (`CHIRPS <https://www.chc.ucsb.edu/data/chirps>`_)
environmental record.

CHIRPS is a quasi-global (50°S-50°N), high resolution (0.05°), daily, pentadal,
and monthly precipitation dataset, ranging from 1981 to near-present. It incorporates
CHPclim (CHC in-house climatology), 0.05° resolution satellite imagery, and in-situ station
data to create gridded rainfall time series for trend analysis and seasonal drought
monitoring. More information are available `here <https://www.nature.com/articles/sdata201566>`_.

Through the AA toolbox, it is possible to have access to daily and monthly data.

The data is downloaded from `IRI's maproom
<http://iridl.ldeo.columbia.edu/SOURCES/.UCSB/.CHIRPS/.v2p0>`_ as the platform allows
for the selection of geographical areas, and the delay in the upload
of the data between CHC servers and IRI servers is less than one day.
The data for a certain month is usually available two-three weeks after the end
of the month.


Usage
-----

In order to access CHIRPS data, you first need to create a country
configuration for the country you would like to get data for. In this example
we will use Burkina Faso, which corresponds to the ISO3 code "bfa":

.. code-block:: python

    from aatoolbox import create_country_config
    country_config = create_country_config(iso3="bfa")

Another required input is the geographic area of interest. A simple
way to identify the area around the chosen country is to use the COD
administrative boundaries. As a first step, you need to download them:

.. code-block:: python

    from aatoolbox import CodAB
    codab = CodAB(country_config=country_config)
    codab.download()
    admin0 = codab.load(admin_level=0)

Next, an instance of the class GeoBoundingBox needs to be created:

.. code-block:: python

    from aatoolbox import GeoBoundingBox
    geo_bounding_box = GeoBoundingBox.from_shape(admin0)

You can then choose start and end date of the dataset to be considered in your
analysis, by specifying both of them as `datetime.date` objects.
Both parameters are optional: if not specified, the start and end
date will be respectively set to 1981-1-1 and the most recent date for which
the data is available on the server.

You can make use of the Chirps classes: two classes are
available, one to retrieve daily data and one to retrieve monthly data. Daily
data are available with two spatial resolutions (0.05 and 0.25 degrees),
whereas monthly data can be obtained only with a 0.05-degree resolution.

In the following example, monthly data ranging from February 2001 to March
2006 is downloaded.

.. code-block:: python

    from aatoolbox import ChirpsMonthly

    start_date = datetime.date(year=2001, month=2, day=1)
    end_date = datetime.date(year=2006, month=3, day=31)

    chirps_monthly = ChirpsMonthly(
        country_config=country_config,
        geo_bounding_box=geo_bounding_box,
        start_date=start_date,
        end_date=end_date
        )

    chirps_monthly.download()

Similarly, the code snippet below allows to download daily CHIRPS data with
0.25 degrees resolution and ranging from October 23, 2007 to the most recent
available data:

.. code-block:: python

    from aatoolbox import ChirpsDaily

    start_date = datetime.date(year=2007, month=10, day=23)

    chirps_daily = ChirpsDaily(
        country_config=country_config,
        geo_bounding_box=geo_bounding_box,
        start_date=start_date
        )

    chirps_daily.download()

After having downloaded the datasets, a processing step is needed before
being able to use them.

.. code-block:: python

    chirps_monthly.process()
    chirps_daily.process()

Finally, the data can be loaded as an ``xarray`` dataset, which is the result
of the merging of all processed datasets, with fixed time resolution and
location. Below are two examples of the use of the ``load`` method,
respectively for monthly and daily data.

.. code-block:: python

    chirps_monthly_data = chirps_monthly.load()
    chirps_daily_data = chirps_daily.load()
