"""Flat plates under uniform pressure — Roark's Formulas.

Small-deflection theory: valid while deflection stays under about half the
thickness. Past that the plate carries load in membrane tension and these
closed-form results grow conservative — check the warning on every result.

Rectangular coefficients are tabulated at v = 0.3.
"""

import math
from dataclasses import dataclass

from .materials import Material, get as get_material
from .result import Result, classify_sf

#: (a/b, beta, alpha) — all edges simply supported
_RECT_SS = [
    (1.0, 0.2874, 0.0444), (1.2, 0.3762, 0.0616), (1.4, 0.4530, 0.0770),
    (1.6, 0.5172, 0.0906), (1.8, 0.5688, 0.1017), (2.0, 0.6102, 0.1110),
    (3.0, 0.7134, 0.1335), (4.0, 0.7410, 0.1400), (1000.0, 0.7500, 0.1421),
]

#: (a/b, beta, alpha) — all edges clamped
_RECT_CLAMPED = [
    (1.0, 0.3078, 0.0138), (1.2, 0.3834, 0.0188), (1.4, 0.4356, 0.0226),
    (1.6, 0.4680, 0.0251), (1.8, 0.4872, 0.0267), (2.0, 0.4974, 0.0277),
    (1000.0, 0.5000, 0.0284),
]


def _lookup(table: list[tuple[float, float, float]], ratio: float) -> tuple[float, float]:
    """Step lookup: largest tabulated a/b not exceeding `ratio`, as Excel VLOOKUP TRUE."""
    if ratio < table[0][0]:
        raise ValueError(f"Aspect ratio {ratio:.3g} below tabulated minimum {table[0][0]}")
    beta, alpha = table[0][1], table[0][2]
    for r, b, a in table:
        if ratio >= r:
            beta, alpha = b, a
        else:
            break
    return beta, alpha


@dataclass
class PlateResult(Result):
    stress: float = 0.0
    deflection: float = 0.0
    sf: float | None = None
    required_t: float = 0.0
    small_deflection_ok: bool = True


def circular(
    a: float,
    q: float,
    t: float,
    material: Material | str,
    edge: str = "clamped",
    target_sf: float = 2.0,
) -> PlateResult:
    """Circular plate under uniform pressure.

    Args:
        a: plate radius, in.
        q: uniform pressure, psi.
        t: trial thickness, in.
        material: Material or name.
        edge: "simply_supported" or "clamped".
        target_sf: safety factor for the back-solved thickness.
    """
    mat = get_material(material) if isinstance(material, str) else material
    edge = edge.lower().replace(" ", "_").replace("-", "_")
    if edge not in ("simply_supported", "clamped"):
        raise ValueError(f"edge must be 'simply_supported' or 'clamped', got {edge!r}")

    v = mat.nu
    D = mat.E * t**3 / (12 * (1 - v**2))

    if edge == "simply_supported":
        stress = 3 * (3 + v) * q * a**2 / (8 * t**2)
        delta = ((5 + v) / (1 + v)) * q * a**4 / (64 * D)
        req_t = a * math.sqrt(3 * (3 + v) * q * target_sf / (8 * mat.Sy))
        formula = "σ = 3(3+v)qa²/8t²  (centre),  δ = ((5+v)/(1+v))qa⁴/64D"
    else:
        stress = 3 * q * a**2 / (4 * t**2)
        delta = q * a**4 / (64 * D)
        req_t = a * math.sqrt(3 * q * target_sf / (4 * mat.Sy))
        formula = "σ = 3qa²/4t²  (edge),  δ = qa⁴/64D"

    sf = mat.Sy / stress if stress else None
    small_ok = delta <= t / 2

    warnings = []
    if not small_ok:
        warnings.append(
            f"Deflection {delta:.4g} in exceeds t/2 — small-deflection theory is "
            "stretched; consider membrane behaviour or FEA"
        )
    if sf is not None and sf < 1.5:
        warnings.append(f"Safety factor {sf:.2f} is {classify_sf(sf)}")

    return PlateResult(
        title=f"Circular plate, {edge.replace('_', ' ')} edge",
        reference="Roark's Formulas for Stress and Strain, small deflection",
        inputs=[("Radius a", a, "in"), ("Pressure q", q, "psi"),
                ("Thickness t", t, "in"), ("Material", mat.name, "")],
        outputs=[("Max stress", stress, "psi"), ("Max deflection", delta, "in"),
                 ("Safety factor", sf, ""), ("Status", classify_sf(sf), ""),
                 (f"Required t for SF {target_sf:g}", req_t, "in")],
        formula=formula,
        warnings=warnings,
        stress=stress, deflection=delta, sf=sf,
        required_t=req_t, small_deflection_ok=small_ok,
    )


def rectangular(
    a: float,
    b: float,
    q: float,
    t: float,
    material: Material | str,
    edge: str = "simply_supported",
    target_sf: float = 2.0,
) -> PlateResult:
    """Rectangular plate under uniform pressure.

    Args:
        a: long side, in.
        b: short side, in.
        q: uniform pressure, psi.
        t: trial thickness, in.
        edge: "simply_supported" or "clamped" (all edges).
    """
    if b > a:
        a, b = b, a
    mat = get_material(material) if isinstance(material, str) else material
    edge = edge.lower().replace(" ", "_").replace("-", "_")
    table = _RECT_SS if edge == "simply_supported" else _RECT_CLAMPED

    ratio = a / b
    beta, alpha = _lookup(table, ratio)
    stress = beta * q * b**2 / t**2
    delta = alpha * q * b**4 / (mat.E * t**3)
    sf = mat.Sy / stress if stress else None
    req_t = b * math.sqrt(beta * q * target_sf / mat.Sy)
    small_ok = delta <= t / 2

    warnings = []
    if not small_ok:
        warnings.append(f"Deflection {delta:.4g} in exceeds t/2 — use caution")
    if sf is not None and sf < 1.5:
        warnings.append(f"Safety factor {sf:.2f} is {classify_sf(sf)}")
    if ratio > 4:
        warnings.append(f"a/b = {ratio:.3g} is beyond the tabulated range; coefficients pinned to the strip limit")

    return PlateResult(
        title=f"Rectangular plate, {edge.replace('_', ' ')} edges",
        reference="Roark's Formulas, coefficients tabulated at v = 0.3",
        inputs=[("Long side a", a, "in"), ("Short side b", b, "in"),
                ("Pressure q", q, "psi"), ("Thickness t", t, "in"),
                ("Material", mat.name, ""), ("Aspect ratio a/b", ratio, ""),
                ("β", beta, ""), ("α", alpha, "")],
        outputs=[("Max stress", stress, "psi"), ("Max deflection", delta, "in"),
                 ("Safety factor", sf, ""), ("Status", classify_sf(sf), ""),
                 (f"Required t for SF {target_sf:g}", req_t, "in")],
        formula="σ = βqb²/t²,  δ = αqb⁴/Et³,  t_req = b·sqrt(βq·SF/Sy)",
        warnings=warnings,
        stress=stress, deflection=delta, sf=sf,
        required_t=req_t, small_deflection_ok=small_ok,
    )
