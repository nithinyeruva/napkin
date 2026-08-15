"""Mechanical engineering hand calcs.

Preliminary sizing and sanity checks — Shigley and Roark closed-form solutions,
static loads, small deflections, room temperature. US customary throughout
(in, lbf, psi, F); use `units.convert` at the boundary.

Ported from MechEng_HandCalcs.xlsx.

    >>> from mecheng import beams, sections
    >>> s = sections.round_tube(od=1.5, id=1.25)
    >>> r = beams.analyze("cant_point", L=20, section=s, material="Al 6061-T6", P=500)
    >>> round(r.sf, 2)
    0.69
    >>> r.status
    'FAIL'

Every result renders itself for a design record:

    >>> print(r.markdown())   # doctest: +SKIP
"""

from . import (
    beams,
    bolts,
    columns,
    cooling,
    materials,
    plates,
    pressure,
    sections,
    shafts,
    units,
)
from .materials import MATERIALS, Material
from .result import Result, classify_sf

__version__ = "0.1.0"

__all__ = [
    "beams", "bolts", "columns", "cooling", "materials", "plates",
    "pressure", "sections", "shafts", "units",
    "Material", "MATERIALS", "Result", "classify_sf",
]
