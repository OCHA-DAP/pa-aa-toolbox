"""Class to download and process USGS NDVI data.

Download, process, and load NDVI data published
in the `USGS FEWS NET data portal
<https://earlywarning.usgs.gov/fews>`_.
"""

# TODO: add progress bar
import functools
import logging
import re
from datetime import date, datetime
from io import BytesIO
from pathlib import Path
from typing import Generator, List, Optional, Tuple, Union
from urllib.error import HTTPError
from urllib.request import urlopen
from zipfile import ZipFile

import geopandas as gpd
import pandas as pd
import rioxarray  # noqa: F401
import xarray as xr
from rasterio.errors import RasterioIOError

import aatoolbox.utils.raster  # noqa: F401
from aatoolbox.config.countryconfig import CountryConfig
from aatoolbox.datasources.datasource import DataSource
from aatoolbox.utils._dates import (
    compare_dekads_gt,
    compare_dekads_lt,
    dekad_to_date,
    expand_dekads,
    get_dekadal_date,
)

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
            config_datasource_name="usgs_ndvi",
        )

        # set data variable
        self._data_variable = data_variable
        self._data_variable_url = data_variable_url
        self._data_variable_suffix = data_variable_suffix

        # set dates for data download and processing
        self._start_year, self._start_dekad = get_dekadal_date(
            input_date=start_date, default_date=_EARLIEST_DATE
        )

        self._end_year, self._end_dekad = get_dekadal_date(
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
        >>>
        >>> # setup NDVI
        >>> bfa_ndvi = UsgsNdviSmoothed(
        ...     country_config=country_config,
        ...     start_date=[2020, 1],
        ...     end_date=[2020, 3]
        ... )
        >>> bfa_ndvi.download()
        """
        download_dekads = expand_dekads(
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

        The processing keeps track of the latest timestamp of
        when the raw raster files were modified. If the latest
        timestamp of the raw data is greater than when it was
        last processed, the file will automatically be
        re-processed.

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
        # get statistics for processing
        stats_list = kwargs.pop(
            "stats_list", ["mean", "std", "min", "max", "sum", "count"]
        )
        percentile_list = kwargs.pop("percentile_list", None)

        if not stats_list and not percentile_list:
            raise ValueError(
                "At least one of `stats_list` or "
                "`percentile_list` must not be `None` "
                "when passed to `process()`."
            )

        # getting stats and percentiles for processing
        stats_list = [] if not stats_list else stats_list
        percentile_list = (
            []
            if not percentile_list
            else [str(percent) for percent in percentile_list]
        )
        process_stats = stats_list + percentile_list
        percentile_identifier = [True] * len(stats_list) + [False] * len(
            percentile_list
        )

        # get dates for processing
        all_dates_to_process = expand_dekads(
            y1=self._start_year,
            d1=self._start_dekad,
            y2=self._end_year,
            d2=self._end_dekad,
        )

        for stat, is_percentile in zip(process_stats, percentile_identifier):
            self._process(
                clobber=clobber,
                gdf=gdf,
                feature_col=feature_col,
                dates_to_process=all_dates_to_process,
                stat=stat,
                is_percentile=is_percentile,
                kwargs=kwargs,
            )

        return self._processed_base_dir

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
        processed_files = self._find_processed_files(feature_col=feature_col)
        processed_dfs = [
            self._load(filepath=fp, drop_modified=True)
            for fp in processed_files
        ]

        df = functools.reduce(
            lambda df1, df2: pd.merge(
                df1, df2, on=["date", "year", "dekad", feature_col]
            ),
            processed_dfs,
        )

        # filter loaded data frame between our instances dates
        load_dates = expand_dekads(
            y1=self._start_year,
            d1=self._start_dekad,
            y2=self._end_year,
            d2=self._end_dekad,
        )

        loaded_dates = df[["year", "dekad"]].values.tolist()
        keep_rows = [tuple(d) in load_dates for d in loaded_dates]

        df = df.loc[keep_rows]

        # put feature column as 1st column
        df_feature_col = df.pop(feature_col)
        df.insert(loc=0, column=feature_col, value=df_feature_col)

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
        year, dekad = get_dekadal_date(input_date=date)

        filepath = self._get_raw_path(year=year, dekad=dekad, local=True)
        try:
            da = rioxarray.open_rasterio(filepath)
            # get time file was updated
            file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
            # assign coordinates for year/dekad
            # time dimension
            da = (
                da.assign_coords(
                    {
                        "year": year,
                        "dekad": dekad,
                        "date": dekad_to_date(year=year, dekad=dekad),
                        "modified": file_time,
                    }
                )
                .expand_dims("date")
                .squeeze("band", drop=True)
            )

            return da

        except RasterioIOError as err:
            # check if the requested date is outside the instance bounds
            # don't prevent loading, but use for meaningful error
            gt_end = compare_dekads_gt(
                y1=year, d1=dekad, y2=self._end_year, d2=self._end_dekad
            )
            lt_start = compare_dekads_lt(
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

    def _download(self, filepath: Path, url_filename: str, clobber: bool):
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

        if filepath.exists():
            file_time = datetime.fromtimestamp(filepath.stat().st_mtime)
            url_time_str = resp.headers["last-modified"]
            url_time = datetime.strptime(
                url_time_str,
                # Fri, 27 Mar 2015 08:05:42 GMT
                "%a, %d %b %Y %X %Z",
            )
            if not clobber and url_time <= file_time:
                logger.info(
                    f"File {filepath} exists, clobber set to False, and "
                    "file not been modified since last download. "
                    "Using existing files."
                )
                return filepath

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

    def _process(
        self,
        clobber: bool,
        gdf: gpd.GeoDataFrame,
        feature_col: str,
        dates_to_process: list,
        stat: str,
        is_percentile: bool,
        kwargs,
    ) -> Path:
        """Process data for particular statistic."""
        # get processed path for particular statistic
        percentile_list: Optional[List[int]]
        if is_percentile:
            stats_list = None
            percentile_list = [int(stat)]
            stat = f"{stat}quant"
        else:
            stats_list = [stat]
            percentile_list = None

        processed_path = self._get_processed_path(
            feature_col=feature_col, stat=stat
        )

        if processed_path.is_file():
            (
                dates_to_process,
                df_already_processed,
            ) = self._determine_process_dates(
                clobber=clobber,
                filepath=processed_path,
                dates_to_process=dates_to_process,
            )

            if not dates_to_process:
                logger.info(
                    (
                        "No new {stat} data to process between "
                        f"{self._start_year}, "
                        f"dekad {self._start_dekad} "
                        f"and {self._end_year}, "
                        f"dekad {self._end_dekad}, "
                        "set `clobber = True` to re-process this data."
                    )
                )
                return processed_path
        else:
            # no dates already processed
            df_already_processed = pd.DataFrame()

        # process data for necessary dates
        data = [df_already_processed]
        for process_date in dates_to_process:
            da = self.load_raster(process_date)
            stats = da.aat.compute_raster_stats(
                gdf=gdf,
                feature_col=feature_col,
                stats_list=stats_list,
                percentile_list=percentile_list,
                **kwargs,
            )
            data.append(stats)

        # join data together and sort
        df = pd.concat(data).sort_values(by="date").reset_index(drop=True)

        # saving file
        self._processed_base_dir.mkdir(parents=True, exist_ok=True)
        df.to_csv(processed_path, index=False)

        return processed_path

    def _determine_process_dates(
        self, clobber: bool, filepath: Path, dates_to_process: list
    ) -> Tuple[list, pd.DataFrame]:
        """Determine dates to process.

        Parameters
        ----------
        clobber : bool
            If True, overwrites existing file
        filepath : Path
            Filepath to the existing processed file.
        dates_to_process : list
            List of dates to process

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
        df = self._load(filepath=filepath)

        # get dates that have already been processed
        dates_already_processed = df[
            ["year", "dekad", "modified"]
        ].values.tolist()
        dates_already_processed = {
            tuple(d[0:2]): d[2] for d in dates_already_processed
        }

        if clobber:
            # remove processed dates from file
            # so they can be reprocessed
            keep_rows = [
                d not in dates_to_process
                for d in list(dates_already_processed.keys())
            ]
            df = df.loc[keep_rows]
        else:
            # remove processed dates from dates to process
            dates_to_process = [
                d
                for d in dates_to_process
                if d not in list(dates_already_processed.keys())
                or self._get_modified_time(year=d[0], dekad=d[1])
                > dates_already_processed[d]
            ]

            # incase dates still processed based on
            # modified time remove from the df
            keep_rows = [
                d not in dates_to_process
                for d in list(dates_already_processed.keys())
            ]
            df = df.loc[keep_rows]
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
            f"{self._datasource_config.area_prefix}{file_year}"
            f"{dekad:02}{self._data_variable_suffix}"
        )
        return file_name

    @staticmethod
    def _load(filepath: Path, drop_modified: bool = False):
        """Load processed data.

        Parameters
        ----------
        filepath : Path
            Filepath to processed data
        drop_modified : bool, default = False
            Drop modified column, used for merging data frames
            together.

        Returns
        -------
        pd.DataFrame
            Processed data frame
        """
        df = pd.read_csv(filepath, parse_dates=["date", "modified"])
        if drop_modified:
            df.drop(["modified"], axis=1, inplace=True)
        return df

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

    def _get_modified_time(self, year: int, dekad: int) -> datetime:
        """Get modified time of raw file.

        Used to determine when to re-process
        or re-download raw raster files.

        Parameters
        ----------
        year : int
            4-digit year
        dekad : int
            Dekad

        Returns
        -------
        datetime
            Timestamp of when file was modified.
        """
        filepath = self._get_raw_path(year=year, dekad=dekad, local=True)
        return datetime.fromtimestamp(filepath.stat().st_mtime)

    def _get_processed_filename(self, feature_col: str, stat: str) -> str:
        """Return processed filename.

        Returns the processed filename. The suffix
        of the filename is always the ``feature_col``
        the statistics are aggregated to.

        Returns
        -------
        str
            Processed filename
        """
        base_file_name = self._get_processed_base_filename(
            feature_col=feature_col
        )
        return f"{base_file_name}_{stat}.csv"

    def _get_processed_base_filename(self, feature_col: str) -> str:
        base_file_name = (
            f"{self._country_config.iso3}"
            f"_usgs_ndvi_{self._data_variable}"
            f"_{feature_col}"
        )
        return base_file_name

    def _get_processed_path(self, feature_col: str, stat: str) -> Path:
        return self._processed_base_dir / self._get_processed_filename(
            feature_col=feature_col, stat=stat
        )

    def _find_processed_files(self, feature_col: str) -> Generator:
        base_file_name = self._get_processed_base_filename(
            feature_col=feature_col
        )
        return self._processed_base_dir.glob(f"{base_file_name}_*.csv")

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
            f"{self._datasource_config.area_url}/dekadal/emodis"
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
