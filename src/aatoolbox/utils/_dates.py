"""Functions for dealing with dates."""

import itertools
from datetime import date, datetime
from typing import List, Tuple, Union, cast


def get_dekadal_date(
    input_date: Union[date, str, Tuple[int, int], None],
    default_date: Union[date, str, Tuple[int, int], None] = None,
) -> Tuple[int, int]:
    """Calculate dekadal date from general input.

    Processes input ``input_date`` and returns two
    values, the year and dekad. Input can be of
    format ``datetime.date``, an ISO8601 date
    string, an already calculated ``(year, dekad)``
    format date, or ``None``. If ``None``,
    ``default_date`` is returned. ``default_date``
    can also be passed in the above formats.
    """
    if input_date is None and default_date is not None:
        input_date = default_date

    # convert date to various values
    if isinstance(input_date, str):
        year, dekad = date_to_dekad(date.fromisoformat(input_date))
    elif isinstance(input_date, date):
        year, dekad = date_to_dekad(input_date)
    else:
        input_date = cast(Tuple[int, int], input_date)
        if len(input_date) == 2:
            year, dekad = input_date
            # assert year-dekad values appropriate, not too strict
            if year < 1000 or year > 9999 or dekad < 1 or dekad > 36:
                raise ValueError(
                    f"(year, dekad) tuple ({year}, {dekad}) invalid. "
                    "Year should be a 4-digit year and dekad between "
                    "1 and 36."
                )

        else:
            raise ValueError(
                (
                    "`date` values for dekadal data "
                    "should be passed in as "
                    "`datetime.date` objects, tuples "
                    "of `(year, dekad)` format, or "
                    "ISO8601 date strings."
                )
            )

    return (year, dekad)


def dekad_to_date(year: int, dekad: int) -> date:
    """Compute date from dekad and year.

    Date computed from dekad and year in
    datetime object, corresponding to
    first day of the dekad. This
    is based on the
    `common dekadal definition
    <http://iridl.ldeo.columbia.edu/maproom/Food_Security/Locusts/Regional/Dekadal_Rainfall/index.html>`_
    of the 1st and 2nd dekad of a month
    being the first 10 day periods, and
    the 3rd dekad being the remaining
    days within that month.
    """
    month = ((dekad - 1) // 3) + 1
    day = 10 * ((dekad - 1) % 3) + 1
    return datetime(year=year, month=month, day=day)


def date_to_dekad(date_obj: date) -> Tuple[int, int]:
    """Compute dekad and year from date.

    Dekad computed from date. This
    is based on the
    `common dekadal definition
    <http://iridl.ldeo.columbia.edu/maproom/Food_Security/Locusts/Regional/Dekadal_Rainfall/index.html>`_
    of the 1st and 2nd dekad of a month
    being the first 10 day periods, and
    the 3rd dekad being the remaining
    days within that month.
    """
    year = date_obj.year
    dekad = min(date_obj.day // 10, 2) + ((date_obj.month - 1) * 3) + 1
    return (year, dekad)


def compare_dekads_lt(y1: int, d1: int, y2: int, d2: int) -> bool:
    """Is year1/dekad1 less than year2/dekad2.

    Compare two pairs of years and dekads,
    that the first pair are less than the
    second pair.
    """
    return y1 < y2 or ((y1 == y2) and (d1 < d2))


def compare_dekads_lte(y1: int, d1: int, y2: int, d2: int) -> bool:
    """Is year1/dekad1 less than or equal to year2/dekad2.

    Compare two pairs of years and dekads,
    that the first pair are less than or
    equal to the second pair.
    """
    return y1 < y2 or ((y1 == y2) and (d1 <= d2))


def compare_dekads_gt(y1: int, d1: int, y2: int, d2: int) -> bool:
    """Is year1/dekad1 greater than year2/dekad2.

    Compare two pairs of years and dekads,
    that the first pair are greater than the
    second pair.
    """
    return compare_dekads_lt(y1=y2, d1=d2, y2=y1, d2=d1)


def compare_dekads_gte(y1: int, d1: int, y2: int, d2: int) -> bool:
    """Is year1/dekad1 greater than or equal to year2/dekad2.

    Compare two pairs of years and dekads,
    that the first pair are greater than or
    equal to the second pair.
    """
    return compare_dekads_lte(y1=y2, d1=d2, y2=y1, d2=d1)


def expand_dekads(y1: int, d1: int, y2: int, d2: int) -> List[Tuple[int, int]]:
    """Expand for all years/dekads between two dates.

    Takes input year and dekads and returns a list
    of year/dekad lists.
    """
    year_range = range(y1, y2 + 1)
    dekad_range = range(1, 37)
    date_combos = itertools.product(*[year_range, dekad_range])

    def valid(y, d):
        return not ((y == y1 and d < d1) or (y == y2 and d > d2))

    return [(y, d) for y, d in date_combos if valid(y, d)]
