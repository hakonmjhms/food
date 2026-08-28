"""Icelandic date formatting for the (Icelandic) frontend - Python's strftime
month/weekday names depend on the OS locale being installed, which isn't
guaranteed on every host, so we spell them out here instead."""

import datetime as dt

_WEEKDAYS_IS = [
    "mánudagur",
    "þriðjudagur",
    "miðvikudagur",
    "fimmtudagur",
    "föstudagur",
    "laugardagur",
    "sunnudagur",
]

_MONTHS_IS = [
    "janúar",
    "febrúar",
    "mars",
    "apríl",
    "maí",
    "júní",
    "júlí",
    "ágúst",
    "september",
    "október",
    "nóvember",
    "desember",
]


def format_date_is(value: dt.date) -> str:
    """E.g. '28. ágúst 2026'."""
    return f"{value.day}. {_MONTHS_IS[value.month - 1]} {value.year}"


def format_weekday_date_is(value: dt.date) -> str:
    """E.g. 'Fimmtudagur, 28. ágúst 2026'."""
    weekday = _WEEKDAYS_IS[value.weekday()].capitalize()
    return f"{weekday}, {format_date_is(value)}"


def weekday_morning_phrase_is(python_weekday: int) -> str:
    """E.g. 'fimmtudagsmorgni', for phrases like 'á fimmtudagsmorgni'.

    Icelandic weekday names all end in '-dagur'; the genitive ('-dags') used here
    is formed by simply dropping the '-ur', which holds for all seven of them.
    """
    name = _WEEKDAYS_IS[python_weekday]
    return f"{name[:-2]}smorgni"
