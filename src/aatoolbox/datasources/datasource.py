"""Base class for aatoolbox data source."""
from abc import ABC, abstractmethod
from pathlib import Path

from aatoolbox.config.countryconfig import CountryConfig
from aatoolbox.config.pathconfig import PathConfig

_GLOBAL_DIR = "glb"


class DataSource(ABC):
    """
    Base abstract class object that contains path convenience functions.

    Cannot itself be instantiated. ``__init__``, ``download()``,
    ``load()``, and ``process()`` methods required for subclass to be
    instantiated.

    Parameters
    ----------
    country_config: CountryConfig
        Country configuration
    datasource_base_dir : str
        Module directory name (usually correspond to data source)
    is_public: bool, default = False
        Whether the dataset is public or private. Determines top-level
        directory structure.
    is_global_raw: bool, default = False
        Whether the raw dataset should be saved in the `glb` folder. This is
        normally done when it has global or regional coverage.
    is_global_processed: bool, default = False
        Whether the processed dataset should be saved in the `glb` folder.
        This is normally done when it has global or regional coverage.
    config_datasource_name: str = None
        The name of the attribute in the config file
    """

    @abstractmethod
    def __init__(
        self,
        country_config: CountryConfig,
        datasource_base_dir: str,
        is_public: bool = False,
        is_global_raw: bool = False,
        is_global_processed: bool = False,
        config_datasource_name: str = None,
    ):
        if config_datasource_name is not None:
            self._datasource_config = self._config_attribute_name_validator(
                config_datasource_name=config_datasource_name,
                country_config=country_config,
            )
        self._country_config = country_config
        self._datasource_base_dir = datasource_base_dir
        self._path_config = PathConfig()
        self._raw_base_dir = self._get_base_dir(
            is_public=is_public, is_raw=True, is_global=is_global_raw
        )
        self._processed_base_dir = self._get_base_dir(
            is_public=is_public, is_raw=False, is_global=is_global_processed
        )

    @staticmethod
    def _config_attribute_name_validator(
        config_datasource_name: str, country_config: CountryConfig
    ):
        try:
            return getattr(country_config, config_datasource_name)
        except AttributeError as err:
            raise AttributeError(
                f"{config_datasource_name} needs to be added to the "
                f"config file. See the documentation for more details."
            ) from err

    def _get_base_dir(
        self,
        is_public: bool,
        is_raw: bool,
        is_global: bool = False,
    ) -> Path:
        """
        Define the base_dir.

        Parameters
        ----------
        is_public: bool
            Whether the dataset is public or private. Determines top-level
            directory structure.
        is_raw: bool
            Whether the dataset is raw or processed
        is_global: bool
            Whether the dataset is global (or regional) or specific to the
            iso3
        """
        permission_dir = (
            self._path_config.public
            if is_public
            else self._path_config.private
        )
        state_dir = (
            self._path_config.raw if is_raw else self._path_config.processed
        )
        region_dir = (
            self._country_config.iso3 if not is_global else _GLOBAL_DIR
        )
        return (
            self._path_config.base_path
            / permission_dir
            / state_dir
            / region_dir
            / self._datasource_base_dir
        )

    @abstractmethod
    def download(self, clobber: bool = False):
        """Abstract method for downloading."""
        pass

    @abstractmethod
    def process(self, clobber: bool = False):
        """Abstract method for processing."""
        pass

    @abstractmethod
    def load(self):
        """Abstract method for loading."""
        pass
