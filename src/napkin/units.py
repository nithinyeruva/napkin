"""Unit conversions and handy constants.

The calculators work in US customary throughout (in, lbf, psi, F). Convert at the
boundary rather than mixing systems inside a calculation.
"""

G_IN_S2 = 386.09
G_FT_S2 = 32.174

WATER_LB_PER_GAL = 8.34
WATER_PSI_PER_FT_HEAD = 0.4331
WATER_LB_PER_HR_PER_GPM = 500.0

# factor converts FROM the first unit TO the second
_FACTORS: dict[tuple[str, str], float] = {
    ("in", "mm"): 25.4,
    ("ft", "m"): 0.3048,
    ("lbf", "N"): 4.44822,
    ("in-lbf", "N-m"): 0.112985,
    ("ft-lbf", "N-m"): 1.35582,
    ("psi", "kPa"): 6.89476,
    ("psi", "bar"): 0.0689476,
    ("psi", "MPa"): 0.00689476,
    ("ksi", "MPa"): 6.89476,
    ("GPM", "L/min"): 3.78541,
    ("HP", "kW"): 0.7457,
    ("BTU/hr", "W"): 0.293071,
    ("lb", "kg"): 0.453592,
    ("in3", "cm3"): 16.3871,
    ("lb/in3", "g/cm3"): 27.6799,
    ("in-lbf", "ft-lbf"): 1 / 12,
}


def convert(value: float, frm: str, to: str) -> float:
    """Convert between units. Handles either direction of any known pair.

    >>> round(convert(1, "in", "mm"), 1)
    25.4
    >>> round(convert(25.4, "mm", "in"), 3)
    1.0
    """
    if frm == to:
        return value
    if (frm, to) in _FACTORS:
        return value * _FACTORS[(frm, to)]
    if (to, frm) in _FACTORS:
        return value / _FACTORS[(to, frm)]
    if {frm, to} == {"F", "C"}:
        return (value - 32) / 1.8 if frm == "F" else value * 1.8 + 32
    raise ValueError(f"No conversion from {frm!r} to {to!r}")


def torque_from_power(hp: float, rpm: float) -> float:
    """Shaft torque in in-lbf from horsepower and speed. T = 63025*HP/RPM."""
    if hp == 0 or rpm == 0:
        return 0.0
    return 63025 * hp / rpm
