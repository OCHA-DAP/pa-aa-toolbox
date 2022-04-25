"""Country configuration setting base class."""
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

from pydantic import BaseModel, root_validator, validator

from aatoolbox.utils.io import parse_yaml


class CodABConfig(BaseModel):
    """COD AB configuration.

    Parameters
    ----------
    hdx_dataset_name: str
        COD AB dataset name on HDX. Can be found by taking the filename as it
        appears on the dataset page.
    layer_base_name: str
        The base name of the different admin layers, that presumably only
        change by a single custom_layer_number depending on the level. Should
        contain {admin_level} in place of the custom_layer_number.
    admin_level_max: int
        The maximum admin level available in the shapefile.
    custom_layer_names: list, optional
        Any additional layer names that don't fit into the admin level paradigm
    """

    hdx_dataset_name: str
    layer_base_name: str
    admin_level_max: int
    custom_layer_names: Optional[list]

    @validator("layer_base_name")
    def _validate_layer_base_name(cls, layer_base_name):
        if "{admin_level}" not in layer_base_name:
            raise ValueError(
                "The layer base name must contain "
                "an {admin_level} placeholder."
            )
        return layer_base_name


class FewsNetConfig(BaseModel):
    """FEWS NET configuration.

    Parameters
    ----------
    region_name: str
        Name of the region the country belongs to. Needed to download the
        regional FEWS NET data
    """

    # values dictionary gets build in order attributes are listed
    # so first define the dict before the region_name
    region_name_code_mapping: Dict[str, str] = {
        "caribbean-central-america": "LAC",
        "central-asia": "CA",
        "east-africa": "EA",
        "southern-africa": "SA",
        "west-africa": "WA",
    }
    region_name: str

    @validator("region_name")
    def regionname_valid(cls, v, values):
        """Check that regionname is one of the valid ones."""
        valid_regionnames = values["region_name_code_mapping"].keys()
        if v not in valid_regionnames:
            raise ValueError(
                f"Invalid region name: {v}. "
                f"Should be one of {', '.join(valid_regionnames)}"
            )
        return v

    @root_validator(pre=False, skip_on_failure=True)
    def _set_region_code(cls, values) -> dict:
        """Set region code based on region name."""
        values["region_code"] = values["region_name_code_mapping"][
            values["region_name"]
        ]
        return values


class UsgsNdviConfig(BaseModel):
    """USGS NDVI configuration.

    Parameters
    ----------
    area_name : str
        Name of the USGS NDVI coverage area the country belongs to.
        Needed to download the regional NDVI data.
    """

    area_name_mapping: Dict[str, Tuple[str, str]] = {
        "north-africa": ("africa/north", "na"),
        "east-africa": ("africa/east", "ea"),
        "southern-africa": ("africa/southern", "sa"),
        "west-africa": ("africa/west", "wa"),
        "central-asia": ("asia/centralasia", "cta"),
        "yemen": ("asia/middleeast/yemen", "yem"),
        "central-america": ("lac/camcar/centralamerica", "ca"),
        "hispaniola": ("lac/camcar/caribbean/hispaniola", "hi"),
    }
    area_name: str

    @validator("area_name")
    def area_name_valid(cls, v, values) -> str:
        """Check that area_name is valid."""
        valid_area_names = values["area_name_mapping"].keys()
        if v not in valid_area_names:
            raise ValueError(
                f"Invalid area name: {v}. "
                f"Should be one of {', '.join(valid_area_names)}"
            )
        return v

    @root_validator(pre=False, skip_on_failure=True)
    def _set_area_codes(cls, values) -> dict:
        """Set NDVI url and prefix from area."""
        values["area_url"], values["area_prefix"] = values[
            "area_name_mapping"
        ][values["area_name"]]
        return values


class CountryConfig(BaseModel):
    """Country configuration."""

    iso3: str
    codab: Optional[CodABConfig]
    fewsnet: Optional[FewsNetConfig]
    usgs_ndvi: Optional[UsgsNdviConfig]

    @validator("iso3")
    def _validate_iso3(cls, iso3):
        return _validate_iso3(iso3)


def create_country_config(iso3: str) -> CountryConfig:
    """
    Return a country configuration object from AA Toolbox.

    Parameters
    ----------
    iso3 : str
        Country ISO3, must be exactly 3 letters long

    Returns
    -------
    CountryConfig instance
    """
    iso3 = _validate_iso3(iso3)
    try:
        parameters = parse_yaml(
            Path(__file__).parent.resolve() / f"countries/{iso3}.yaml"
        )
    except FileNotFoundError as err:
        raise FileNotFoundError(
            f"A configuration file for {iso3.upper()} is not yet available "
            f"in AA Toolbox. Try using a custom configuration file with "
            f"create_custom_country_config instead, or contact us to "
            f"request that we add this country."
        ) from err
    return CountryConfig(**parameters)


def create_custom_country_config(filepath: Union[str, Path]) -> CountryConfig:
    """
    Return a custom country configuration object.

    Parameters
    ----------
    filepath: str, pathlib.Path
        Path to the configuration file

    Returns
    -------
    CountryConfig instance
    """
    return CountryConfig(**parse_yaml(filepath))


def _validate_iso3(iso3: str):
    if len(iso3) != 3 or not str.isalpha(iso3):
        raise ValueError("ISO3 must be a three letter string.")
    return iso3.lower()
