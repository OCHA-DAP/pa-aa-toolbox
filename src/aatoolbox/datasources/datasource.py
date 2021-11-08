"""Base class for aatoolbox data source."""
import logging
from functools import wraps

from aatoolbox.config.pathconfig import PathConfig

logger = logging.getLogger(__name__)


class DataSource:
    """
    Base class object that contains path convenience functions.

    Parameters
    ----------
    iso3: str
        Country ISO3
    module_base_dir : str
        Module directory name (usually correspond to data source)
    is_public: bool, default = False
        Whether the dataset is public or private. Determines top-level
        directory structure.
    """

    def __init__(self, iso3: str, module_base_dir: str, is_public=False):

        self._iso3 = iso3
        self._module_base_dir = module_base_dir
        self._path_config = PathConfig()
        self._raw_base_dir = self._get_base_dir(
            is_public=is_public, is_raw=True
        )
        self._processed_base_dir = self._get_base_dir(
            is_public=is_public, is_raw=False
        )

    def _get_base_dir(self, is_public: bool, is_raw: bool):
        public_dir = (
            self._path_config.public
            if is_public
            else self._path_config.private
        )
        raw_dir = (
            self._path_config.raw if is_raw else self._path_config.processed
        )
        return (
            self._path_config.base_path
            / public_dir
            / raw_dir
            / self._iso3
            / self._module_base_dir
        )


def file_clobber(filepath_attribute_name: str):
    """
    Toggle data clobber.

    Avoid recreating data if it already exists and if clobber not
    toggled by user. Only works on class instance methods where the target
    filepath is an attribute.

    Parameters
    ----------
    filepath_attribute_name : str
        The name of the instance attribute that contains the filepath to cache

    Returns
    -------
    If filepath exists, returns filepath. Otherwise, returns the result of
    the decorated function.

    """

    def decorator(func):
        @wraps(func)
        def wrapper(self, *args, clobber: bool = False, **kwargs):
            filepath = getattr(self, filepath_attribute_name)
            if filepath.exists() and not clobber:
                logger.debug(
                    "File {filepath} exists and clobber set to False, "
                    "not downloading"
                )
                return filepath
            return func(self, *args, **kwargs)

        return wrapper

    return decorator
