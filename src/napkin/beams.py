"""Beam bending — six classic load cases (Shigley App. A-9).

Static, small deflection, elastic. Max moment, max deflection, safety factor on
yield, and back-solved sizes for a target safety factor.
"""

import math
from dataclasses import dataclass, field

from .materials import Material, get as get_material
from .result import Result, classify_sf
from .sections import SectionProps

#: case key -> (description, M(P,w,L), delta(P,w,L,E,I))
CASES: dict[str, tuple[str, str, str]] = {
    "ss_point": ("Simply supported, center point load", "PL/4", "PL³/48EI"),
    "ss_uniform": ("Simply supported, uniform load", "wL²/8", "5wL⁴/384EI"),
    "cant_point": ("Cantilever, end point load", "PL", "PL³/3EI"),
    "cant_uniform": ("Cantilever, uniform load", "wL²/2", "wL⁴/8EI"),
    "fixed_point": ("Fixed-fixed, center point load", "PL/8", "PL³/192EI"),
    "fixed_uniform": ("Fixed-fixed, uniform load", "wL²/12", "wL⁴/384EI"),
}


def _moment(case: str, P: float, w: float, L: float) -> float:
    return {
        "ss_point": P * L / 4,
        "ss_uniform": w * L**2 / 8,
        "cant_point": P * L,
        "cant_uniform": w * L**2 / 2,
        "fixed_point": P * L / 8,
        "fixed_uniform": w * L**2 / 12,
    }[case]


def _deflection(case: str, P: float, w: float, L: float, E: float, I: float) -> float:
    return {
        "ss_point": P * L**3 / (48 * E * I),
        "ss_uniform": 5 * w * L**4 / (384 * E * I),
        "cant_point": P * L**3 / (3 * E * I),
        "cant_uniform": w * L**4 / (8 * E * I),
        "fixed_point": P * L**3 / (192 * E * I),
        "fixed_uniform": w * L**4 / (384 * E * I),
    }[case]


@dataclass
class BeamResult(Result):
    M: float = 0.0
    stress: float = 0.0
    deflection: float = 0.0
    sf: float | None = None
    allowable_deflection: float = 0.0
    deflection_ok: bool = True
    weight: float = 0.0
    status: str = field(default="")


def analyze(
    case: str,
    L: float,
    section: SectionProps,
    material: Material | str,
    P: float = 0.0,
    w: float = 0.0,
    deflection_limit: float = 240,
) -> BeamResult:
    """Analyze a beam.

    Args:
        case: one of `CASES` — e.g. "cant_point".
        L: span or cantilever length, in.
        section: from `napkin.sections`.
        material: a Material or its name.
        P: point load, lbf (point-load cases).
        w: distributed load, lbf/in (uniform cases).
        deflection_limit: denominator x in an L/x allowable. 240 general,
            360 finish-critical.

    Returns:
        BeamResult with stress, deflection, safety factor and checks.
    """
    if case not in CASES:
        raise ValueError(f"Unknown case {case!r}. Try one of: {', '.join(CASES)}")
    mat = get_material(material) if isinstance(material, str) else material

    M = _moment(case, P, w, L)
    stress = M / section.S
    delta = _deflection(case, P, w, L, mat.E, section.I)
    sf = mat.Sy / stress if stress else None
    allow = L / deflection_limit
    desc, m_formula, d_formula = CASES[case]

    warnings = []
    if delta > allow:
        warnings.append(f"Deflection {delta:.4g} in exceeds L/{deflection_limit:.0f} = {allow:.4g} in — stiffen")
    if sf is not None and sf < 1.5:
        warnings.append(f"Safety factor {sf:.2f} is {classify_sf(sf)}")

    return BeamResult(
        title=f"Beam bending — {desc}",
        reference="Shigley App. A-9, static elastic small deflection",
        inputs=[
            ("Length L", L, "in"),
            ("Point load P", P, "lbf") if P else ("Distributed load w", w, "lbf/in"),
            ("Material", mat.name, ""),
            ("Section modulus S", section.S, "in³"),
            ("Moment of inertia I", section.I, "in⁴"),
        ],
        outputs=[
            ("Max moment M", M, "in-lbf"),
            ("Max bending stress", stress, "psi"),
            ("Max deflection", delta, "in"),
            (f"Allowable L/{deflection_limit:.0f}", allow, "in"),
            ("Safety factor", sf, ""),
            ("Status", classify_sf(sf), ""),
        ],
        formula=f"M = {m_formula},  σ = M/S,  δ = {d_formula},  SF = Sy/σ",
        warnings=warnings,
        M=M,
        stress=stress,
        deflection=delta,
        sf=sf,
        allowable_deflection=allow,
        deflection_ok=delta <= allow,
        weight=section.A * L * mat.density,
        status=classify_sf(sf),
    )


def required_S(M: float, material: Material | str, target_sf: float = 2.0) -> float:
    """Section modulus needed to hit a target safety factor. S = M·SF/Sy."""
    mat = get_material(material) if isinstance(material, str) else material
    return M * target_sf / mat.Sy


def required_height(M: float, b: float, material: Material | str, target_sf: float = 2.0) -> float:
    """Rectangle height for a given width. h = sqrt(6·M·SF/(b·Sy))."""
    mat = get_material(material) if isinstance(material, str) else material
    return math.sqrt(6 * M * target_sf / (b * mat.Sy))


def required_diameter(M: float, material: Material | str, target_sf: float = 2.0) -> float:
    """Solid round diameter. d = (32·M·SF/(π·Sy))^(1/3)."""
    mat = get_material(material) if isinstance(material, str) else material
    return (32 * M * target_sf / (math.pi * mat.Sy)) ** (1 / 3)
