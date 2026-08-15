"""Cooling lines and heat — flow for a heat load, turbulence, pressure drop.

Water as the coolant throughout. The turbulence check is the one that matters
for mold cooling: laminar flow moves very little heat regardless of how much
water you push through.
"""

import math
from dataclasses import dataclass

from .materials import Material, get as get_material
from .result import Result

#: water temperature (F) -> kinematic viscosity (cSt)
WATER_VISCOSITY: dict[int, float] = {
    50: 1.40, 70: 0.95, 100: 0.68, 140: 0.47, 180: 0.35,
}


def viscosity_at(temp_f: float) -> float:
    """Kinematic viscosity of water in cSt, linearly interpolated."""
    temps = sorted(WATER_VISCOSITY)
    if temp_f <= temps[0]:
        return WATER_VISCOSITY[temps[0]]
    if temp_f >= temps[-1]:
        return WATER_VISCOSITY[temps[-1]]
    for lo, hi in zip(temps, temps[1:]):
        if lo <= temp_f <= hi:
            f = (temp_f - lo) / (hi - lo)
            return WATER_VISCOSITY[lo] + f * (WATER_VISCOSITY[hi] - WATER_VISCOSITY[lo])
    return WATER_VISCOSITY[temps[-1]]


def required_flow(Q_btu_hr: float = 0.0, Q_watts: float = 0.0, dT: float = 4.0) -> Result:
    """Coolant flow to carry a heat load at a given temperature rise.

    GPM = Q / (500·dT), where 500 = 8.33 lb/gal x 60 min x cp of water.

    Args:
        Q_btu_hr: heat load in BTU/hr.
        Q_watts: heat load in watts, used when Q_btu_hr is 0.
        dT: allowable in-to-out rise, F. Molds want <= 4 F for uniform cooling.
    """
    Q = Q_btu_hr if Q_btu_hr > 0 else Q_watts * 3.412
    gpm = Q / (500 * dT) if dT else 0.0
    return Result(
        title="Required coolant flow",
        inputs=[("Heat load Q", Q, "BTU/hr"), ("Temperature rise dT", dT, "F")],
        outputs=[("Required total flow", gpm, "GPM")],
        formula="GPM = Q/(500·dT)",
        warnings=[] if dT <= 4 else [f"dT of {dT:g} F is high for uniform mold cooling"],
    )


@dataclass
class CircuitResult(Result):
    velocity: float = 0.0
    reynolds: float = 0.0
    regime: str = ""
    friction_factor: float = 0.0
    pressure_drop: float = 0.0
    margin: float | None = None


def circuit(
    d: float,
    gpm: float,
    length_ft: float,
    water_temp_f: float = 100,
    roughness: float = 0.0018,
    K_total: float = 6.0,
    pump_psi: float | None = None,
) -> CircuitResult:
    """Velocity, Reynolds number and pressure drop for one cooling circuit.

    Args:
        d: channel diameter, in.
        gpm: flow through this circuit.
        length_ft: total developed length including every baffle pass.
        water_temp_f: sets viscosity.
        roughness: absolute wall roughness, in. Drilled steel ~0.0018,
            smooth tube ~0.0001.
        K_total: summed minor-loss coefficients. ~0.9 per sharp bend,
            1.5-2 per baffle turnaround, 0.5-1 per fitting.
        pump_psi: available pump pressure at this flow, from the pump curve.
    """
    nu = viscosity_at(water_temp_f)
    V = 0.4085 * gpm / d**2
    Re = 3160 * gpm / (d * nu)

    if Re >= 10000:
        regime = "Fully turbulent — ideal for mold cooling"
    elif Re >= 4000:
        regime = "Turbulent — OK, 10,000+ is better"
    elif Re >= 2300:
        regime = "Transitional — increase flow"
    else:
        regime = "Laminar — poor heat transfer, increase flow"

    f = 0.25 / (math.log10(roughness / (3.7 * d) + 5.74 / Re**0.9)) ** 2
    h_friction = f * (12 * length_ft / d) * V**2 / (2 * 32.174)
    h_minor = K_total * V**2 / (2 * 32.174)
    dp = 0.4331 * (h_friction + h_minor)
    margin = pump_psi - dp if pump_psi is not None else None

    warnings = []
    if Re < 4000:
        warnings.append(f"Re = {Re:,.0f} — not reliably turbulent, heat transfer will disappoint")
    if V < 1:
        warnings.append(f"Velocity {V:.2f} ft/s is below the 1-2 ft/s minimum")
    if V > 10:
        warnings.append(f"Velocity {V:.2f} ft/s risks erosion")
    if margin is not None and margin < 0:
        warnings.append("Short on head — bigger pump, larger d, or split the circuit")

    return CircuitResult(
        title="Cooling circuit",
        inputs=[("Channel diameter d", d, "in"), ("Flow", gpm, "GPM"),
                ("Circuit length", length_ft, "ft"), ("Water temperature", water_temp_f, "F"),
                ("Viscosity", nu, "cSt"), ("Roughness", roughness, "in"),
                ("Minor-loss K total", K_total, "")],
        outputs=[("Velocity", V, "ft/s"), ("Reynolds", Re, ""), ("Regime", regime, ""),
                 ("Friction factor f", f, ""), ("Friction head", h_friction, "ft"),
                 ("Minor-loss head", h_minor, "ft"), ("Total pressure drop", dp, "psi"),
                 ("Pump margin", margin, "psi")],
        formula="V = 0.4085·GPM/d²,  Re = 3160·GPM/(d·v),  f Swamee-Jain,  Δp = 0.4331(hf + hm)",
        warnings=warnings,
        velocity=V, reynolds=Re, regime=regime,
        friction_factor=f, pressure_drop=dp, margin=margin,
    )


def conduction(material: Material | str, area_in2: float, thickness_in: float, dT: float) -> Result:
    """Steady conduction through a wall. Q = k·A·dT/L."""
    mat = get_material(material) if isinstance(material, str) else material
    Q = mat.k * (area_in2 / 144) * dT / (thickness_in / 12)
    return Result(
        title="Conduction",
        inputs=[("Material", mat.name, ""), ("k", mat.k, "BTU/hr-ft-F"),
                ("Area", area_in2, "in²"), ("Path length", thickness_in, "in"),
                ("dT", dT, "F")],
        outputs=[("Heat flow Q", Q, "BTU/hr")],
        formula="Q = k·A·dT/L",
    )


def convection(h: float, area_in2: float, dT: float) -> Result:
    """Convective heat transfer. Q = h·A·dT.

    Typical h: still air 1-5, forced air 2-20, turbulent water 200-2000
    (BTU/hr-ft²-F).
    """
    Q = h * (area_in2 / 144) * dT
    return Result(
        title="Convection",
        inputs=[("h", h, "BTU/hr-ft²-F"), ("Area", area_in2, "in²"), ("dT", dT, "F")],
        outputs=[("Heat flow Q", Q, "BTU/hr")],
        formula="Q = h·A·dT",
    )
