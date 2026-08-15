"""Shaft sizing — static combined torsion and bending by von Mises, plus twist.

This is a STATIC check. Keyways, steps and press fits concentrate stress, and a
rotating shaft sees fully reversed bending — for anything that turns under load,
run a Shigley fatigue check (Kf, Se) on top of this.
"""

import math
from dataclasses import dataclass

from .materials import Material, get as get_material
from .result import Result, classify_sf
from .units import torque_from_power


@dataclass
class ShaftResult(Result):
    T: float = 0.0
    torsional_shear: float = 0.0
    bending_stress: float = 0.0
    von_mises: float = 0.0
    sf: float | None = None
    twist_deg: float = 0.0


def analyze(
    d: float,
    material: Material | str,
    M: float = 0.0,
    T: float = 0.0,
    hp: float = 0.0,
    rpm: float = 0.0,
    L: float = 0.0,
) -> ShaftResult:
    """Check a solid round shaft under combined bending and torsion.

    Args:
        d: shaft diameter, in.
        material: Material or name.
        M: bending moment, in-lbf.
        T: torque, in-lbf. Overrides hp/rpm when non-zero.
        hp: power, HP — used with rpm when T is not given directly.
        rpm: speed.
        L: length over which to report twist, in. 0 skips the twist check.
    """
    mat = get_material(material) if isinstance(material, str) else material
    torque = T if T > 0 else torque_from_power(hp, rpm)

    J = math.pi * d**4 / 32
    tau = 16 * torque / (math.pi * d**3)
    sigma_b = 32 * M / (math.pi * d**3)
    vm = math.sqrt(sigma_b**2 + 3 * tau**2)
    sf = mat.Sy / vm if vm else None

    twist_deg = 0.0
    if L and torque:
        twist_deg = torque * L / (mat.G * J) * 180 / math.pi

    warnings = []
    if sf is not None and sf < 1.5:
        warnings.append(f"Safety factor {sf:.2f} is {classify_sf(sf)}")
    if L and twist_deg:
        per_ft = twist_deg / (L / 12)
        if per_ft > 0.08:
            warnings.append(
                f"Twist {per_ft:.3g} deg/ft exceeds the 0.08 deg/ft rule of thumb for power shafts"
            )
    warnings.append("Static check only — add fatigue (Kf, Se) for a rotating shaft")

    return ShaftResult(
        title="Shaft — combined bending and torsion",
        reference="von Mises static check; Shigley for the fatigue follow-up",
        inputs=[("Diameter d", d, "in"), ("Bending moment M", M, "in-lbf"),
                ("Torque T", torque, "in-lbf"), ("Material", mat.name, ""),
                ("Length L", L, "in")],
        outputs=[("Torsional shear", tau, "psi"), ("Bending stress", sigma_b, "psi"),
                 ("von Mises stress", vm, "psi"), ("Safety factor", sf, ""),
                 ("Status", classify_sf(sf), ""), ("Twist over L", twist_deg, "deg")],
        formula="τ = 16T/πd³,  σb = 32M/πd³,  σ' = sqrt(σb² + 3τ²),  θ = TL/GJ",
        warnings=warnings,
        T=torque, torsional_shear=tau, bending_stress=sigma_b,
        von_mises=vm, sf=sf, twist_deg=twist_deg,
    )


def required_diameter(
    M: float, T: float, material: Material | str, target_sf: float = 2.0
) -> float:
    """Diameter for a target static safety factor.

    d = (32·SF·sqrt(M² + 0.75T²)/(π·Sy))^(1/3)
    """
    mat = get_material(material) if isinstance(material, str) else material
    return (32 * target_sf * math.sqrt(M**2 + 0.75 * T**2) / (math.pi * mat.Sy)) ** (1 / 3)
