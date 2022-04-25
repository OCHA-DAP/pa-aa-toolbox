"""Classes to download and process USGS FEWS NET NDVI data.

Download, process, and load NDVI data published
in the `USGS FEWS NET data portal
<https://earlywarning.usgs.gov/fews>`_. Classes available
to process temporally smoothed NDVI values, percent of
median values, difference to median values, and difference
from current value to the previous year's value.
"""

# TODO: add progress bar
import logging
from datetime import date
from typing import Tuple, Union

from aatoolbox.config.countryconfig import CountryConfig
from aatoolbox.datasources.usgs.usgs_ndvi import _UsgsNdvi

# from aatoolbox.utils.check_file_existence import check_file_existence

logger = logging.getLogger(__name__)


class UsgsNdviSmoothed(_UsgsNdvi):
    """Base class to retrieve smoothed NDVI data.

    The retrieved data is the smoothed NDVI values
    processed by the USGS. Temporal smoothing is done
    to adjust for cloud cover and other errors.
    Data for the 3 most recent dekads is not fully
    smoothed, and are re-smoothed at the end of the
    3 dekad period.

    Parameters
    ----------
    country_config : CountryConfig
        Country configuration
    start_date : _DATE_TYPE, default = None
        Start date. Can be passed as a ``datetime.date``
        object or a data string in ISO8601 format, and
        the relevant dekad will be determined. Or pass
        directly as year-dekad tuple, e.g. (2020, 1).
        If ``None``, ``start_date`` is set to earliest
        date with data: 2002, dekad 19.
    end_date : _DATE_TYPE, default = None
        End date. Can be passed as a ``datetime.date``
        object and the relevant dekad will be determined,
        as a date string in ISO8601 format, or as a
        year-dekad tuple, i.e. (2020, 1). If ``None``,
        ``end_date`` is set to ``date.today()``.

    Examples
    --------
    >>> from aatoolbox import create_country_config, \
    ...  CodAB, UsgsNdviSmoothed
    >>>
    >>> # Retrieve admin 2 boundaries for Burkina Faso
    >>> country_config = create_country_config(iso3="bfa")
    >>> codab = CodAB(country_config=country_config)
    >>> bfa_admin2 = codab.load(admin_level=2)
    >>>
    >>> # setup NDVI
    >>> bfa_ndvi = UsgsNdviSmoothed(
    ...     country_config=country_config,
    ...     start_date=[2020, 1],
    ...     end_date=[2020, 3]
    ... )
    >>> bfa_ndvi.download()
    >>> bfa_ndvi.process(
    ...     gdf=bfa_admin2,
    ...     feature_col="ADM2_FR"
    ... )
    >>>
    >>> # load in processed data
    >>> df = bfa_ndvi.load(feature_col="ADM2_FR")
    """

    def __init__(
        self,
        country_config: CountryConfig,
        start_date: Union[date, str, Tuple[int, int], None] = None,
        end_date: Union[date, str, Tuple[int, int], None] = None,
    ):
        super().__init__(
            country_config=country_config,
            data_variable="smoothed",
            data_variable_suffix="",
            data_variable_url="temporallysmoothedndvi",
            start_date=start_date,
            end_date=end_date,
        )


class UsgsNdviPctMedian(_UsgsNdvi):
    """Base class to retrieve % of median NDVI.

    The retrieved data is the percent of median NDVI
    values calculated from 2003 - 2017, as
    processed by the USGS.

    Parameters
    ----------
    country_config : CountryConfig
        Country configuration
    start_date : _DATE_TYPE, default = None
        Start date. Can be passed as a ``datetime.date``
        object or a data string in ISO8601 format, and
        the relevant dekad will be determined. Or pass
        directly as year-dekad tuple, e.g. (2020, 1).
        If ``None``, ``start_date`` is set to earliest
        date with data: 2002, dekad 19.
    end_date : _DATE_TYPE, default = None
        End date. Can be passed as a ``datetime.date``
        object and the relevant dekad will be determined,
        as a date string in ISO8601 format, or as a
        year-dekad tuple, i.e. (2020, 1). If ``None``,
        ``end_date`` is set to ``date.today()``.

    Examples
    --------
    >>> from aatoolbox import create_country_config, \
    ...  CodAB, UsgsNdviPctMedian
    >>>
    >>> # Retrieve admin 2 boundaries for Burkina Faso
    >>> country_config = create_country_config(iso3="bfa")
    >>> codab = CodAB(country_config=country_config)
    >>> bfa_admin2 = codab.load(admin_level=2)
    >>>
    >>> # setup NDVI
    >>> bfa_ndvi = UsgsNdviPctMedian(
    ...     country_config=country_config,
    ...     start_date=[2020, 1],
    ...     end_date=[2020, 3]
    ... )
    >>> bfa_ndvi.download()
    >>> bfa_ndvi.process(
    ...     gdf=bfa_admin2,
    ...     feature_col="ADM2_FR"
    ... )
    >>>
    >>> # load in processed data
    >>> df = bfa_ndvi.load(feature_col="ADM2_FR")
    """

    def __init__(
        self,
        country_config: CountryConfig,
        start_date: Union[date, str, Tuple[int, int], None] = None,
        end_date: Union[date, str, Tuple[int, int], None] = None,
    ):
        super().__init__(
            country_config=country_config,
            data_variable="percent_median",
            data_variable_suffix="pct",
            data_variable_url="percentofmedian",
            start_date=start_date,
            end_date=end_date,
        )


class UsgsNdviMedianAnomaly(_UsgsNdvi):
    """Base class to retrieve NDVI anomaly data.

    The retrieved data is NDVI anomaly data calculated
    as a subtraction of the median value, based on data
    from 2003 - 2017, from the
    current value. Negative values indicate less
    vegetation than the median, positive values indicate
    more vegetation.

    Parameters
    ----------
    country_config : CountryConfig
        Country configuration
    start_date : _DATE_TYPE, default = None
        Start date. Can be passed as a ``datetime.date``
        object or a data string in ISO8601 format, and
        the relevant dekad will be determined. Or pass
        directly as year-dekad tuple, e.g. (2020, 1).
        If ``None``, ``start_date`` is set to earliest
        date with data: 2002, dekad 19.
    end_date : _DATE_TYPE, default = None
        End date. Can be passed as a ``datetime.date``
        object and the relevant dekad will be determined,
        as a date string in ISO8601 format, or as a
        year-dekad tuple, i.e. (2020, 1). If ``None``,
        ``end_date`` is set to ``date.today()``.

    Examples
    --------
    >>> from aatoolbox import create_country_config, \
    ...  CodAB, UsgsNdviMedianAnomaly
    >>>
    >>> # Retrieve admin 2 boundaries for Burkina Faso
    >>> country_config = create_country_config(iso3="bfa")
    >>> codab = CodAB(country_config=country_config)
    >>> bfa_admin2 = codab.load(admin_level=2)
    >>>
    >>> # setup NDVI
    >>> bfa_ndvi = UsgsNdviMedianAnomaly(
    ...     country_config=country_config,
    ...     start_date=[2020, 1],
    ...     end_date=[2020, 3]
    ... )
    >>> bfa_ndvi.download()
    >>> bfa_ndvi.process(
    ...     gdf=bfa_admin2,
    ...     feature_col="ADM2_FR"
    ... )
    >>>
    >>> # load in processed data
    >>> df = bfa_ndvi.load(feature_col="ADM2_FR")
    """

    def __init__(
        self,
        country_config: CountryConfig,
        start_date: Union[date, str, Tuple[int, int], None] = None,
        end_date: Union[date, str, Tuple[int, int], None] = None,
    ):
        super().__init__(
            country_config=country_config,
            data_variable="median_anomaly",
            data_variable_suffix="stmdn",
            data_variable_url="mediananomaly",
            start_date=start_date,
            end_date=end_date,
        )


class UsgsNdviYearDifference(_UsgsNdvi):
    """Base class to retrieve NDVI year difference data.

    The retrieved data is NDVI yearly difference data,
    calculated as the subtraction of the previous year's
    NDVI value from the current year's. Negative
    values indicate the current vegetation is less
    than the previous year's, positive that there
    is more vegetation in the current year.

    Parameters
    ----------
    country_config : CountryConfig
        Country configuration
    start_date : _DATE_TYPE, default = None
        Start date. Can be passed as a ``datetime.date``
        object or a data string in ISO8601 format, and
        the relevant dekad will be determined. Or pass
        directly as year-dekad tuple, e.g. (2020, 1).
        If ``None``, ``start_date`` is set to earliest
        date with data: 2002, dekad 19.
    end_date : _DATE_TYPE, default = None
        End date. Can be passed as a ``datetime.date``
        object and the relevant dekad will be determined,
        as a date string in ISO8601 format, or as a
        year-dekad tuple, i.e. (2020, 1). If ``None``,
        ``end_date`` is set to ``date.today()``.

    Examples
    --------
    >>> from aatoolbox import create_country_config, \
    ...  CodAB, UsgsNdviDifference
    >>>
    >>> # Retrieve admin 2 boundaries for Burkina Faso
    >>> country_config = create_country_config(iso3="bfa")
    >>> codab = CodAB(country_config=country_config)
    >>> bfa_admin2 = codab.load(admin_level=2)
    >>>
    >>> # setup NDVI
    >>> bfa_ndvi = UsgsNdviDifference(
    ...     country_config=country_config,
    ...     start_date=[2020, 1],
    ...     end_date=[2020, 3]
    ... )
    >>> bfa_ndvi.download()
    >>> bfa_ndvi.process(
    ...     gdf=bfa_admin2,
    ...     feature_col="ADM2_FR"
    ... )
    >>>
    >>> # load in processed data
    >>> df = bfa_ndvi.load(feature_col="ADM2_FR")
    """

    def __init__(
        self,
        country_config: CountryConfig,
        start_date: Union[date, str, Tuple[int, int], None] = None,
        end_date: Union[date, str, Tuple[int, int], None] = None,
    ):
        super().__init__(
            country_config=country_config,
            data_variable="difference",
            data_variable_suffix="dif",
            data_variable_url="differencepreviousyear",
            start_date=start_date,
            end_date=end_date,
        )
