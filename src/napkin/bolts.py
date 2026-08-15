"""Bolted joints — preload, tightening torque, separation and shear.

Inch UNC/UNF sizes with SAE and metric-equivalent grades.

Torque-controlled preload scatters ±25% or worse. For a joint that matters,
verify by turn-of-nut or direct measurement rather than trusting a torque wrench.
"""

from dataclasses import dataclass

from .result import Result, classify_sf

#: thread designation -> (nominal diameter in, tensile stress area in^2)
THREADS: dict[str, tuple[float, float]] = {
    "#4-40": (0.112, 0.00604),
    "#6-32": (0.138, 0.00909),
    "#8-32": (0.164, 0.01400),
    "#10-24": (0.190, 0.01750),
    "#10-32": (0.190, 0.02000),
    "1/4-20": (0.250, 0.03180),
    "1/4-28": (0.250, 0.03640),
    "5/16-18": (0.3125, 0.05240),
    "3/8-16": (0.375, 0.07750),
    "7/16-14": (0.4375, 0.10630),
    "1/2-13": (0.500, 0.14190),
    "5/8-11": (0.625, 0.22600),
    "3/4-10": (0.750, 0.33400),
}

#: grade -> (proof psi, yield psi, ultimate psi)
GRADES: dict[str, tuple[float, float, float]] = {
    "SAE Gr 2": (55000, 57000, 74000),
    "SAE Gr 5": (85000, 92000, 120000),
    "SAE Gr 8": (120000, 130000, 150000),
    "SS F593 (18-8 CW)": (65000, 65000, 100000),
    "Metric 8.8": (84100, 92800, 116000),
    "Metric 10.9": (120400, 136300, 150800),
    "Metric 12.9": (140700, 159500, 176900),
}

#: nut factor K by lubrication state
NUT_FACTORS: dict[str, float] = {
    "dry": 0.20,
    "zinc_plated": 0.15,
    "lubricated": 0.12,
}


@dataclass
class BoltResult(Result):
    Fp: float = 0.0
    Fi: float = 0.0
    torque_in_lbf: float = 0.0
    torque_ft_lbf: float = 0.0
    Fb: float = 0.0
    sf_proof: float | None = None
    load_factor: float | None = None
    separation_factor: float | None = None
    sf_shear: float | None = None


def analyze(
    thread: str,
    grade: str = "SAE Gr 5",
    preload_fraction: float = 0.75,
    nut_factor: float | str = 0.20,
    P: float = 0.0,
    C: float = 0.25,
    V: float = 0.0,
) -> BoltResult:
    """Analyze a bolted joint.

    Args:
        thread: key from `THREADS`, e.g. "3/8-16".
        grade: key from `GRADES`.
        preload_fraction: fraction of proof load. 0.75 reusable, 0.90 permanent.
        nut_factor: K value, or a key from `NUT_FACTORS`.
        P: external tensile load per bolt, lbf.
        C: joint stiffness constant — the bolt's share of P. 0.2-0.3 for stiff
            metal joints.
        V: shear load per bolt, lbf.
    """
    if thread not in THREADS:
        raise ValueError(f"Unknown thread {thread!r}. Try: {', '.join(THREADS)}")
    if grade not in GRADES:
        raise ValueError(f"Unknown grade {grade!r}. Try: {', '.join(GRADES)}")
    K = NUT_FACTORS[nut_factor] if isinstance(nut_factor, str) else nut_factor

    d, At = THREADS[thread]
    proof, Sy, _Su = GRADES[grade]

    Fp = proof * At
    Fi = preload_fraction * Fp
    torque = K * Fi * d
    Fb = Fi + C * P
    sf_proof = Fp / Fb if Fb else None
    load_factor = (Sy * At - Fi) / (C * P) if C * P else None
    separation = Fi / ((1 - C) * P) if P else None
    sf_shear = 0.577 * Sy / (V / At) if V else None

    warnings = ["Torque-controlled preload scatters ±25% — verify critical joints directly"]
    if sf_proof is not None and sf_proof < 1.0:
        warnings.append(f"Bolt force exceeds proof load — SF {sf_proof:.2f}")
    if separation is not None and separation < 1.0:
        warnings.append(f"Joint separates at {separation:.2f}× the applied load")

    return BoltResult(
        title=f"Bolted joint — {thread} {grade}",
        reference="Shigley, torque-controlled preload",
        inputs=[("Thread", thread, ""), ("Grade", grade, ""),
                ("Nominal dia d", d, "in"), ("Tensile stress area At", At, "in²"),
                ("Preload fraction", preload_fraction, ""), ("Nut factor K", K, ""),
                ("External load P", P, "lbf"), ("Stiffness constant C", C, "")],
        outputs=[("Proof load Fp", Fp, "lbf"), ("Preload Fi", Fi, "lbf"),
                 ("Tightening torque", torque, "in-lbf"),
                 ("Tightening torque", torque / 12, "ft-lbf"),
                 ("Bolt force Fb", Fb, "lbf"),
                 ("SF vs proof", sf_proof, ""), ("Status", classify_sf(sf_proof), ""),
                 ("Load factor to yield", load_factor, "× P"),
                 ("Separation factor", separation, "× P"),
                 ("SF in shear", sf_shear, "")],
        formula="Fp = proof·At,  Fi = frac·Fp,  T = K·Fi·d,  Fb = Fi + C·P",
        warnings=warnings,
        Fp=Fp, Fi=Fi, torque_in_lbf=torque, torque_ft_lbf=torque / 12, Fb=Fb,
        sf_proof=sf_proof, load_factor=load_factor,
        separation_factor=separation, sf_shear=sf_shear,
    )
