"""Class to download and process USGS FEWS NET NDVI data.

Data is downloaded from the `USGS FEWS NET data portal
<https://earlywarning.usgs.gov/fews>`_. Data is
generated from eMODIS AQUA, with full methodological
details available on the `Documentation page
<https://earlywarning.usgs.gov/fews/product/449>`_
for the specific product. The available areas of
coverage are:

- `North Africa<https://earlywarning.usgs.gov/fews/product/449>`_
- `East Africa<https://earlywarning.usgs.gov/fews/product/448>`_
- `Southern Africa<https://earlywarning.usgs.gov/fews/product/450>`_
- `West Africa<https://earlywarning.usgs.gov/fews/product/451>`_
- `Central Asia<https://earlywarning.usgs.gov/fews/product/493>`_
- `Yemen<https://earlywarning.usgs.gov/fews/product/502>`_
- `Central America<https://earlywarning.usgs.gov/fews/product/445>`_
- `Hispaniola<https://earlywarning.usgs.gov/fews/product/446>`_

Data is made available on the backend USGS file explorer. For example,
dekadal temporally smooth NDVI data for West Africa is available at
`this link
<https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/fews/web/africa/west/dekadal/emodis/ndvi_c6/temporallysmoothedndvi/downloads/monthly/>`_

The products include temporally smoothed NDVI, median anomaly,
difference from the previous year, and median anomaly
presented as a percentile.

Data by USGS is published quickly after the dekad.
After about 1 month this data is updated with temporal smoothing
and error correction for cloud cover. Files for a specific
dekad and region can range from 30MB up to over 100MB, so
downloading and processing can take a long time.
"""

# TODO: add progress bar
import logging
import re
from datetime import date
from io import BytesIO
from pathlib import Path
from typing import List, Tuple, Union
from urllib.error import HTTPError
from urllib.request import urlopen
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr

import aatoolbox.utils.raster  # noqa: F401
from aatoolbox.config.countryconfig import CountryConfig
from aatoolbox.datasources.datasource import DataSource
from aatoolbox.utils.dates import (
    _compare_dekads_gt,
    _compare_dekads_lt,
    _dekad_to_date,
    _expand_dekads,
    _get_dekadal_date,
)

# from aatoolbox.utils.check_file_existence import check_file_existence

logger = logging.getLogger(__name__)

_DATE_TYPE = Union[date, str, Tuple[int, int], None]
_EARLIEST_DATE = (2002, 19)


class _UsgsNdvi(DataSource):
    """Base class to retrieve USGS NDVI data.

    Parameters
    ----------
    country_config : CountryConfig
        Country configuration
    data_variable : str
        Data variable date
    data_variable_suffix : str
        Data variable file string
    data_variable_url : str
        URL string for data variable
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
    """

    def __init__(
        self,
        country_config: CountryConfig,
        data_variable: str,
        data_variable_suffix: str,
        data_variable_url: str,
        start_date: _DATE_TYPE = None,
        end_date: _DATE_TYPE = None,
    ):
        super().__init__(
            country_config=country_config,
            datasource_base_dir="usgs_ndvi",
            is_public=True,
            is_global_raw=True,
        )

        # set area url and prefix from config
        if self._country_config.usgs_ndvi is None:
            raise AttributeError(
                "The country configuration file does not contain "
                "any USGS NDVI area name. Please update the config file and "
                "try again. See the documentation for the valid area names."
            )
        self._area_url = self._country_config.usgs_ndvi.area_url
        self._area_prefix = self._country_config.usgs_ndvi.area_prefix

        # set data variable
        self._data_variable = data_variable
        self._data_variable_url = data_variable_url
        self._data_variable_suffix = data_variable_suffix

        # set dates for data download and processing
        self._start_year, self._start_dekad = _get_dekadal_date(
            input_date=start_date, default_date=_EARLIEST_DATE
        )

        self._end_year, self._end_dekad = _get_dekadal_date(
            input_date=end_date, default_date=date.today()
        )

        # warn if dates outside earliest dates
        earliest_year, earliest_dekad = _EARLIEST_DATE
        if self._start_year < earliest_year or (
            self._start_year == earliest_year
            and self._start_dekad < earliest_dekad
        ):
            logger.warning(
                "Start date is before earliest date data is available. "
                f"Data will be downloaded from {earliest_year}, dekad "
                f"{earliest_dekad}."
            )

    def download(self, clobber: bool = False) -> Path:
        """Download raw NDVI data as .tif files.

        NDVI data is downloaded from the USGS API,
        with data for individual regions, years, and
        dekads stored as separate .tif files. No
        authentication is required. Data is downloaded
        for all available dekads from ``self.start_date``
        to ``self.end_date``.

        Parameters
        ----------
        clobber : bool, default = False
            If True, overwrites existing files

        Returns
        -------
        Path
            The downloaded filepath

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
        """
        download_dekads = _expand_dekads(
            y1=self._start_year,
            d1=self._start_dekad,
            y2=self._end_year,
            d2=self._end_dekad,
        )
        for year, dekad in download_dekads:
            self._download_ndvi_dekad(year=year, dekad=dekad, clobber=clobber)
        return self._raw_base_dir

    def process(  # type: ignore
        self,
        gdf: gpd.GeoDataFrame,
        feature_col: str,
        clobber: bool = False,
        **kwargs,
    ) -> Path:
        """Process NDVI data for specific area.

        NDVI data is clipped to the provided
        ``geometries``, usually a geopandas
        dataframes ``geometry`` feature. ``kwargs``
        are passed on to ``aat.computer_raster_stats()``.
        The ``feature_col`` is used to define
        the unique processed file.

        Parameters
        ----------
        gdf : geopandas.GeoDataFrame
            GeoDataFrame with row per area for stats computation.
            If ``pd.DataFrame`` is passed, geometry column must
            have the name ``geometry``. Passed to
            ``aat.compute_raster_stats()``.
        feature_col : str
            Column in ``gdf`` to use as row/feature identifier.
            and dates. Passed to ``aat.compute_raster_stats()``.
            The string is also used as a suffix to the
            processed file path for unique identication of
            analyses done on different files and columns.
        clobber : bool, default = False
            If True, overwrites existing processed dates. If
            the new file matches the old file, dates will be
            reprocessed and appended to the data frame. If
            files do not match, the old file will be replaced.
            If False, stats are only calculated for year-dekads
            that have not already been calculated within the
            file. However, if False and files do not match,
            value error will be raised.
        **kwargs
            Additional keyword arguments passed to
            ``aat.computer_raster_stats()``.

        Returns
        -------
        Path
            The processed path

        Examples
        --------
        >>> from aatoolbox import create_country_config, \
        ...  CodAB, UsgsNdviSmoothed
        >>>
        >>> # Retrieve admin 2 boundaries for Burkina Faso
        >>> country_config = create_country_config(iso3="bfa")
        >>> codab = CodAB(country_config=country_config)
        >>> bfa_admin2 = codab.load(admin_level=2)
        >>> bfa_admin1 = codab.load(admin_level=1)
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
        >>> # process for admin1
        >>> bfa_ndvi.process(
        ...     gdf=bfa_admin1,
        ...     feature_col="ADM1_FR"
        ... )
        """
        processed_path = self._get_processed_path(feature_col=feature_col)

        # get dates for processing
        all_dates_to_process = _expand_dekads(
            y1=self._start_year,
            d1=self._start_dekad,
            y2=self._end_year,
            d2=self._end_dekad,
        )

        # check to see if file exists and remove
        # if clobber or check dates already processed
        # if not
        if processed_path.is_file():
            dates_to_process, df = self._determine_process_dates(
                clobber=clobber,
                feature_col=feature_col,
                dates_to_process=all_dates_to_process,
                kwargs=kwargs,
            )

            if not dates_to_process:
                logger.info(
                    (
                        "No new data to process between "
                        f"{self._start_year}, "
                        f"dekad {self._start_dekad} "
                        f"and {self._end_year}, "
                        f"dekad {self._end_dekad}, "
                        "set `clobber = True` to re-process this data."
                    )
                )
                return processed_path
        else:
            dates_to_process = all_dates_to_process
            df = pd.DataFrame()

        # process data for necessary dates
        data = [df]
        for process_date in dates_to_process:
            da = self.load_raster(process_date)
            stats = da.aat.compute_raster_stats(
                gdf=gdf, feature_col=feature_col, **kwargs
            )
            data.append(stats)

        # join data together and sort
        df = pd.concat(data)
        df.sort_values(by="date", inplace=True)
        df.reset_index(inplace=True, drop=True)

        # saving file
        self._processed_base_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(processed_path, index=False)

        return processed_path

    def load(self, feature_col: str) -> pd.DataFrame:  # type: ignore
        """
        Load the processed USGS NDVI data.

        Parameters
        ----------
        feature_col : str
            String is  used as a suffix to the
            processed file path for unique identication of
            analyses done on different files and columns.
            The same value must be passed to ``process()``.

        Returns
        -------
        pd.DataFrame
            The processed NDVI dataset.

        Raises
        ------
        FileNotFoundError
            If the requested file cannot be found.

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
        ...    gdf=bfa_admin2,
        ...    feature_col="ADM2_FR"
        )
        >>> bfa_ndvi.load(feature_col="ADM2_FR")
        """
        processed_path = self._get_processed_path(feature_col=feature_col)
        try:
            df = pd.read_csv(processed_path, parse_dates=["date"])
        except FileNotFoundError as err:
            raise FileNotFoundError(
                f"Cannot open the CSV file {processed_path.name}. "
                f"Make sure that you have already called the 'process' method "
                f"and that the file {processed_path} exists."
            ) from err

        # filter loaded data frame between our instances dates
        load_dates = _expand_dekads(
            y1=self._start_year,
            d1=self._start_dekad,
            y2=self._end_year,
            d2=self._end_dekad,
        )
        loaded_dates = df[["year", "dekad"]].values.tolist()
        keep_rows = [d in load_dates for d in loaded_dates]
        df = df.loc[keep_rows]

        return df

    def load_raster(
        self, date: Union[date, str, Tuple[int, int]]
    ) -> xr.DataArray:
        """Load raster for specific year and dekad.

        Parameters
        ----------
        date : Union[date, str, Tuple[int, int]]
            Date. Can be passed as a ``datetime.date``
            object and the relevant dekad will be determined,
            as a date string in ISO8601 format, or as a
            year-dekad tuple, i.e. (2020, 1).

        Returns
        -------
        xr.DataArray
            Data array of NDVI data.

        Raises
        ------
        FileNotFoundError
            If the requested file cannot be found.
        """
        year, dekad = _get_dekadal_date(input_date=date)

        filepath = self._get_raw_path(year=year, dekad=dekad, local=True)
        try:
            da = rioxarray.open_rasterio(filepath)
            # assign coordinates for year/dekad
            # time dimension
            da = (
                da.assign_coords(
                    {
                        "year": year,
                        "dekad": dekad,
                        "date": _dekad_to_date(year=year, dekad=dekad),
                    }
                )
                .expand_dims("date")
                .squeeze("band", drop=True)
            )

            return da

        except FileNotFoundError as err:
            # check if the requested date is outside the instance bounds
            # don't prevent loading, but use for meaningful error
            gt_end = _compare_dekads_gt(
                y1=year, d1=dekad, y2=self._end_year, d2=self._end_dekad
            )
            lt_start = _compare_dekads_lt(
                y1=year, d1=dekad, y2=self._start_year, d2=self._start_dekad
            )
            if gt_end or lt_start:
                file_warning = (
                    f"The requested year and dekad, {year}-{dekad}"
                    f"are {'greater' if gt_end else 'less'} than the "
                    f"instance {'end' if gt_end else 'start'} year and dekad"
                    f", {self._end_year if gt_end else self._start_year}-"
                    f"{self._end_dekad if gt_end else self._start_dekad}. "
                    "Calling the `download()` method will not download this "
                    "file, and you need to re-instantiate the class to "
                    "include these dates."
                )
            else:
                file_warning = (
                    "Make sure that you have called the `download()` "
                    f"method and that the file {filepath.name} exists "
                    f"in {filepath.parent}."
                )
            raise FileNotFoundError(
                f"Cannot open the .tif file {filepath}. {file_warning}"
            ) from err

    def _download_ndvi_dekad(
        self, year: int, dekad: int, clobber: bool
    ) -> None:
        """Download NDVI for specific dekad.

        Parameters
        ----------
        year : int
            Year
        dekad : int
            Dekad
        clobber : bool
            If True, overwrites existing file
        """
        filepath = self._get_raw_path(year=year, dekad=dekad, local=True)
        url_filename = self._get_raw_filename(
            year=year, dekad=dekad, local=False
        )
        self._download(
            filepath=filepath, url_filename=url_filename, clobber=clobber
        )

    # @check_file_existence
    def _download(self, filepath: Path, url_filename: str, clobber: bool):
        # filepath just necessary for checking file existence
        # now just extract filename
        local_filename = filepath.stem

        url = self._get_url(filename=url_filename)
        try:
            resp = urlopen(url)
        except HTTPError:
            year, dekad = self._fp_year_dekad(filepath)
            logger.error(
                f"No NDVI data available for "
                f"dekad {dekad} of {year}, skipping."
            )
            return

        # open file within memory
        zf = ZipFile(BytesIO(resp.read()))

        # extract single .tif file from .zip
        for file in zf.infolist():
            if file.filename.endswith(".tif"):
                # rename the file to standardize to name of zip
                file.filename = f"{local_filename}.tif"
                zf.extract(file, self._raw_base_dir)

        resp.close()
        return filepath

    def _determine_process_dates(
        self,
        clobber: bool,
        feature_col: str,
        dates_to_process: list,
        kwargs: dict,
    ) -> Tuple[list, pd.DataFrame]:
        """Determine dates to process.

        Parameters
        ----------
        clobber : bool
            If True, overwrites existing file
        feature_col : str
            Column in ``gdf`` to use as row/feature identifier.
            and dates. Passed to ``aat.compute_raster_stats()``.
        dates_to_process : list
            List of dates to process
        kwargs : dict
             Additional keyword arguments passed to
            ``aat.computer_raster_stats()``. Here used to
            compare processed file with processing.

        Returns
        -------
        Tuple[list, pd.DataFrame]
            Returns a list of dates to process, filtered
            based on clobber, and a data frame of existing
            data to build upon in processing

        Raises
        ------
        ValueError
            Raised if not `clobber` but the statistics
            and `feature_col` for processing do not
            match the existing file.
        """
        df = self.load(feature_col=feature_col)

        # check that the processed file has the same analyzed
        # indicators and column for aggregation as passed
        # to process()
        cols = kwargs.get(
            "stats_list", ["mean", "std", "min", "max", "sum", "count"]
        )
        percentile_list = kwargs.get("percentile_list")
        if percentile_list is not None:
            for percent in percentile_list:
                cols.append(f"{percent}quant")
        cols.append(feature_col)
        exist_cols = df.columns[3:].tolist()
        cols_same = cols == exist_cols

        # get dates that have already been processed
        dates_already_processed = df[["year", "dekad"]].values.tolist()

        if not cols_same:
            if clobber:
                # erase old data frame since columns don't match
                # but clobber=True
                logger.warning(
                    "Original data frame with columns "
                    f"{', '.join(exist_cols)} being overwritten "
                    f"by data frame with columns {', '.join(cols)}."
                )
                df = pd.DataFrame()
            else:
                raise ValueError(
                    (
                        "`clobber` set to False but "
                        "the statistics for aggregation "
                        "do not match existing processed "
                        f"file for {feature_col}. Use "
                        f"`self.load(feature_col={feature_col})`"
                        " to check existing processed file and "
                        "reconcile call to `process()`."
                    )
                )
        else:
            if clobber:
                # remove processed dates from file
                # so they can be reprocessed
                keep_rows = [
                    d not in dates_to_process for d in dates_already_processed
                ]
                df = df.loc[keep_rows]
            else:
                # remove processed dates from dates to process
                dates_to_process = [
                    d
                    for d in dates_to_process
                    if d not in dates_already_processed
                ]
        return (dates_to_process, df)

    def _get_raw_filename(self, year: int, dekad: int, local: bool) -> str:
        """Get raw filename (excluding file type suffix).

        Parameters
        ----------
        year : int
            4-digit year
        dekad : int
            Dekad
        local : bool
            If True, returns filepath for local storage,
            which includes full 4-digit year and _
            separating with dekad. If False, filepath
            corresponds to the zip file stored in the
            USGS server.

        Returns
        -------
        str
            File path prefix for .zip file at URL and
            for .tif files stored within the .zip
        """
        if local:
            file_year = f"{year:04}_"
        else:
            file_year = f"{year-2000:02}"
        file_name = (
            f"{self._area_prefix}{file_year}"
            f"{dekad:02}{self._data_variable_suffix}"
        )
        return file_name

    def _get_raw_path(self, year: int, dekad: int, local: bool) -> Path:
        """Get raw filepath.

        Parameters
        ----------
        year : int
            4-digit year
        dekad : int
            Dekad
        local : bool
            If True, returns filepath for local storage,
            which includes full 4-digit year and _
            separating with dekad. If False, filepath
            corresponds to the zip file stored in the
            USGS server.

        Returns
        -------
        Path
            Path to raw file
        """
        filename = self._get_raw_filename(year=year, dekad=dekad, local=local)
        return self._raw_base_dir / f"{filename}.tif"

    def _get_processed_filename(self, feature_col: str) -> str:
        """Return processed filename.

        Returns the processed filename. The suffix
        of the filename is always the ``feature_col``
        the statistics are aggregated to.

        Returns
        -------
        str
            Processed filename
        """
        file_name = (
            f"{self._country_config.iso3}"
            f"_usgs_ndvi_{self._data_variable}"
            f"_{feature_col}.csv"
        )
        return file_name

    def _get_processed_path(self, feature_col: str) -> Path:
        return self._processed_base_dir / self._get_processed_filename(
            feature_col=feature_col
        )

    def _get_url(self, filename) -> str:
        """Get USGS NDVI URL.

        Parameters
        ----------
        filename : str
            File name string generated for specific year, dekad, and data type

        Returns
        -------
        str
            Download URL string
        """
        return (
            f"https://edcintl.cr.usgs.gov/downloads/sciweb1/shared/fews/web/"
            f"{self._area_url}/dekadal/emodis"
            f"/ndvi_c6/{self._data_variable_url}/"
            f"downloads/dekadal/{filename}.zip"
        )

    # TODO: potentially move from static method to
    # wider USGS function repository
    @staticmethod
    def _fp_year_dekad(path: Path) -> List[int]:
        """Extract year and dekad from filepath.

        Parameters
        ----------
        path : Path
            Filepath

        Returns
        -------
        list
            List of year and dekad
        """
        filename = path.stem
        # find two groups, first for year second for dekad
        regex = re.compile(r"(\d{4})_(\d{2})")
        return [int(x) for x in regex.findall(filename)[0]]
