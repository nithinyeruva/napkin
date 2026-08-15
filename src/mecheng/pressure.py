"""Thin-wall pressure vessels — hoop stress, required wall, end-cap bolt loads.

Thin-wall theory holds while t <= r/10. Past that use Lamé thick-wall equations.

Anything code-regulated gets sized per ASME BPVC, not from here.
"""

import math
from dataclasses import dataclass

from .materials import Material, get as get_material
from .result import Result, classify_sf


@dataclass
class PressureResult(Result):
    hoop_stress: float = 0.0
    longitudinal_stress: float = 0.0
    sf: float | None = None
    required_t: float = 0.0
    thin_wall_valid: bool = True


def cylinder(
    ID: float, t: float, P: float, material: Material | str, target_sf: float = 3.0
) -> PressureResult:
    """Thin-wall cylinder under internal pressure.

    Args:
        ID: inside diameter, in.
        t: wall thickness, in.
        P: internal pressure, psi.
        target_sf: safety factor for the back-solved wall.
    """
    mat = get_material(material) if isinstance(material, str) else material
    r = ID / 2
    hoop = P * r / t
    longitudinal = P * r / (2 * t)
    sf = mat.Sy / hoop if hoop else None
    req_t = target_sf * P * r / mat.Sy
    thin_ok = t <= r / 10

    warnings = []
    if not thin_ok:
        warnings.append(f"t = {t:.4g} in exceeds r/10 = {r / 10:.4g} in — use thick-wall (Lamé)")
    if sf is not None and sf < 1.5:
        warnings.append(f"Safety factor {sf:.2f} is {classify_sf(sf)}")
    warnings.append("Code-regulated vessels must be sized per ASME BPVC")

    return PressureResult(
        title="Thin-wall cylinder",
        inputs=[("Inside diameter", ID, "in"), ("Wall thickness t", t, "in"),
                ("Internal pressure P", P, "psi"), ("Material", mat.name, "")],
        outputs=[("Hoop stress", hoop, "psi"),
                 ("Longitudinal stress", longitudinal, "psi"),
                 ("Safety factor", sf, ""), ("Status", classify_sf(sf), ""),
                 (f"Required t for SF {target_sf:g}", req_t, "in")],
        formula="σ_hoop = Pr/t,  σ_long = Pr/2t,  t_req = SF·P·r/Sy",
        warnings=warnings,
        hoop_stress=hoop, longitudinal_stress=longitudinal,
        sf=sf, required_t=req_t, thin_wall_valid=thin_ok,
    )


def sphere(
    ID: float, t: float, P: float, material: Material | str, target_sf: float = 3.0
) -> PressureResult:
    """Sphere or dished end under internal pressure. Half the hoop stress of a cylinder."""
    mat = get_material(material) if isinstance(material, str) else material
    r = ID / 2
    stress = P * r / (2 * t)
    sf = mat.Sy / stress if stress else None
    req_t = target_sf * P * r / (2 * mat.Sy)
    thin_ok = t <= r / 10

    warnings = []
    if not thin_ok:
        warnings.append(f"t exceeds r/10 = {r / 10:.4g} in — use thick-wall")
    if sf is not None and sf < 1.5:
        warnings.append(f"Safety factor {sf:.2f} is {classify_sf(sf)}")

    return PressureResult(
        title="Sphere / dished end",
        inputs=[("Inside diameter", ID, "in"), ("Wall thickness t", t, "in"),
                ("Internal pressure P", P, "psi"), ("Material", mat.name, "")],
        outputs=[("Stress", stress, "psi"), ("Safety factor", sf, ""),
                 ("Status", classify_sf(sf), ""),
                 (f"Required t for SF {target_sf:g}", req_t, "in")],
        formula="σ = Pr/2t,  t_req = SF·P·r/2Sy",
        warnings=warnings,
        hoop_stress=stress, longitudinal_stress=stress,
        sf=sf, required_t=req_t, thin_wall_valid=thin_ok,
    )


def end_cap_bolts(ID: float, P: float, n_bolts: int) -> Result:
    """Blow-off load on a flat cover and the tensile share per bolt.

    Feed the per-bolt load straight into `bolts.analyze(P=...)`.
    """
    r = ID / 2
    force = P * math.pi * r**2
    per_bolt = force / n_bolts if n_bolts else 0.0
    return Result(
        title="End-cap blow-off load",
        inputs=[("Inside diameter", ID, "in"), ("Pressure P", P, "psi"),
                ("Number of bolts", n_bolts, "")],
        outputs=[("Total end force", force, "lbf"),
                 ("Tensile load per bolt", per_bolt, "lbf")],
        formula="F = P·π·r²,  per bolt = F/n",
        warnings=["Use the per-bolt load as P on a bolted-joint check"],
    )
