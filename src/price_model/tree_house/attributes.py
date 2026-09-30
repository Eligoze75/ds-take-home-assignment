"""Structured attributes pulled out of catalog descriptions.

The descriptions in this catalog are short and formulaic (`THHN Wire 12 AWG`,
`EMT Conduit 1-1/2in x 10ft`, `15A Single Pole Circuit Breaker`). A pretrained
NER model has nothing to recognise here — there are no people, places, or
organisations — and a custom spaCy model would need labelled spans we do not
have. These patterns are the attribute extraction: each one is a number the
price actually moves with (thicker wire, larger trade size, higher amperage).

Missing attributes stay missing. Callers should leave them as NaN so a tree
can split on "this spec does not apply" instead of a filled-in zero.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

SPEC_COLUMNS: tuple[str, ...] = (
    "awg",
    "n_conductors",
    "size_in",
    "amps",
    "watts",
    "length_ft",
    "gang",
    "pack_qty",
    "n_poles",
    "n_ways",
    "n_spaces",
    "box_l",
    "box_w",
    "box_h",
    "nominal_w",
    "nominal_h",
)

_AWG_RE = re.compile(
    r"(\d+\s*/\s*0|\d+)(?:\s*-\s*(\d+\s*/\s*0|\d+))?\s*AWG",
    re.IGNORECASE,
)
# Cable construction (14/2, 18/8), not a fraction of an inch and not n/0 AWG.
_CONDUCTOR_RE = re.compile(
    r"\b(\d{1,2})\s*/\s*([2-9])\b(?!\s*(?:in\b|\"))",
    re.IGNORECASE,
)
_INCH_RE = re.compile(
    r"(\d+)\s*-\s*(\d+)\s*/\s*(\d+)\s*(?:in\b|inch(?:es)?\b|\")"
    r"|(\d+)\s*/\s*(\d+)\s*(?:in\b|inch(?:es)?\b|\")"
    r"|(\d+(?:\.\d+)?)\s*(?:in\b|inch(?:es)?\b|\")",
    re.IGNORECASE,
)
_AMP_RE = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*(?:amps?\b|a\b)", re.IGNORECASE)
# `(?!/)` keeps `14/2 w/Ground` from looking like 2 watts.
_WATT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*-?\s*w\b(?!/)", re.IGNORECASE)
_LENGTH_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:ft\b|')", re.IGNORECASE)
_GANG_RE = re.compile(r"(\d+)\s*-?\s*gang\b|single\s+gang\b", re.IGNORECASE)
_PACK_RE = re.compile(
    r"(?:box|bag|pack|bx|bg)\s*(?:of\s*)?/?\s*(\d+)\b|(\d+)\s*-?\s*pack\b",
    re.IGNORECASE,
)
_POLE_RE = re.compile(
    r"(\d+)\s*-?\s*poles?\b|single\s+pole\b|double\s+pole\b",
    re.IGNORECASE,
)
_WAY_RE = re.compile(r"(\d+)\s*-?\s*ways?\b", re.IGNORECASE)
_SPACE_RE = re.compile(r"(\d+)\s*-?\s*spaces?\b", re.IGNORECASE)
_BOX_RE = re.compile(r"\b(\d+)\s*x\s*(\d+)\s*x\s*(\d+)\b", re.IGNORECASE)
_NOMINAL_RE = re.compile(r"\b(\d+)\s*x\s*(\d+)\b", re.IGNORECASE)


def _awg_value(token: str) -> float:
    """American wire gauge as a number. 1/0 -> 0, 2/0 -> -1, 4/0 -> -3.

    Smaller (more negative) is thicker, which is the direction price moves.
    """
    token = re.sub(r"\s+", "", token)
    if "/" in token:
        numerator, _zero = token.split("/")
        return float(1 - int(numerator))
    return float(token)


def _first_group(match: re.Match[str] | None, *groups: int) -> str | None:
    if match is None:
        return None
    for group in groups:
        value = match.group(group)
        if value is not None:
            return value
    return None


def parse_description(text: str | None) -> dict[str, float]:
    """One description -> spec numbers. Unrecognised fields are NaN."""
    specs = {col: np.nan for col in SPEC_COLUMNS}
    if text is None or not str(text).strip():
        return specs

    awg = _AWG_RE.search(text)
    if awg is not None:
        # A range like `6-10 AWG` keeps the left (thicker) end.
        specs["awg"] = _awg_value(awg.group(1))

    conductors = _CONDUCTOR_RE.search(text)
    if conductors is not None:
        # "14/2" is gauge / conductor count. Keep the gauge only if AWG was absent.
        specs["n_conductors"] = float(conductors.group(2))
        if np.isnan(specs["awg"]):
            specs["awg"] = float(conductors.group(1))

    inch = _INCH_RE.search(text)
    if inch is not None:
        # Mixed number (1-1/2), then a fraction (3/4), then a decimal (0.5).
        if inch.group(1) is not None:
            whole, num, den = (float(inch.group(i)) for i in (1, 2, 3))
            specs["size_in"] = whole + num / den
        elif inch.group(4) is not None:
            specs["size_in"] = float(inch.group(4)) / float(inch.group(5))
        else:
            specs["size_in"] = float(inch.group(6))

    amps = _AMP_RE.search(text)
    if amps is not None:
        specs["amps"] = float(amps.group(1))

    watts = _WATT_RE.search(text)
    if watts is not None:
        specs["watts"] = float(watts.group(1))

    length = _LENGTH_RE.search(text)
    if length is not None:
        specs["length_ft"] = float(length.group(1))

    gang = _GANG_RE.search(text)
    if gang is not None:
        specs["gang"] = float(gang.group(1)) if gang.group(1) is not None else 1.0

    pack = _PACK_RE.search(text)
    if pack is not None:
        specs["pack_qty"] = float(_first_group(pack, 1, 2))

    pole = _POLE_RE.search(text)
    if pole is not None:
        if pole.group(1) is not None:
            specs["n_poles"] = float(pole.group(1))
        elif pole.group(0).lower().startswith("double"):
            specs["n_poles"] = 2.0
        else:
            specs["n_poles"] = 1.0

    ways = _WAY_RE.search(text)
    if ways is not None:
        specs["n_ways"] = float(ways.group(1))

    spaces = _SPACE_RE.search(text)
    if spaces is not None:
        specs["n_spaces"] = float(spaces.group(1))

    # `12x10x6` is an enclosure. `2x4` is a fixture. The three-number form
    # has to be taken first or the fixture pattern eats `12x10` out of it.
    box = _BOX_RE.search(text)
    if box is not None:
        specs["box_l"] = float(box.group(1))
        specs["box_w"] = float(box.group(2))
        specs["box_h"] = float(box.group(3))
        remainder = text[: box.start()] + text[box.end() :]
    else:
        remainder = text
    nominal = _NOMINAL_RE.search(remainder)
    if nominal is not None:
        specs["nominal_w"] = float(nominal.group(1))
        specs["nominal_h"] = float(nominal.group(2))

    return specs


def parse_descriptions(texts: pd.Series) -> pd.DataFrame:
    """Parse every row, caching by the raw string. Descriptions repeat a lot."""
    cache: dict[str, dict[str, float]] = {}
    rows: list[dict[str, float]] = []
    for text in texts:
        key = "" if pd.isna(text) else str(text)
        if key not in cache:
            cache[key] = parse_description(key)
        rows.append(cache[key])
    return pd.DataFrame(rows, index=texts.index)
