"""Column buckling — Euler for long columns, J.B. Johnson for intermediate.

Buckling is sudden and imperfection-sensitive. A safety factor of 3 or more is
common practice, unlike the 1.5-2 you might accept on a yield check.
"""

import math
from dataclasses import dataclass

from .materials import Material, get as get_material
from .result import Result
from .sections import SectionProps

#: end condition -> theoretical K. AISC recommends design values of 0.65
#: (fixed-fixed) and 0.80 (fixed-pinned) to allow for real end fixity.
END_CONDITIONS: dict[str, float] = {
    "pinned_pinned": 1.0,
    "fixed_free": 2.0,
    "fixed_pinned": 0.7,
    "fixed_fixed": 0.5,
}

AISC_DESIGN_K: dict[str, float] = {
    "pinned_pinned": 1.0,
    "fixed_free": 2.1,
    "fixed_pinned": 0.8,
    "fixed_fixed": 0.65,
}


@dataclass
class ColumnResult(Result):
    slenderness: float = 0.0
    Cc: float = 0.0
    regime: str = ""
    critical_stress: float = 0.0
    Pcr: float = 0.0
    sf: float | None = None


def analyze(
    L: float,
    P: float,
    section: SectionProps,
    material: Material | str,
    end_condition: str = "pinned_pinned",
    use_aisc_k: bool = False,
) -> ColumnResult:
    """Check a column against buckling.

    Args:
        L: unbraced length, in.
        P: applied axial load, lbf.
        section: use the WEAK axis — a column buckles about its smaller I.
        material: Material or name.
        end_condition: key from `END_CONDITIONS`.
        use_aisc_k: use AISC design K instead of the theoretical value.
    """
    mat = get_material(material) if isinstance(material, str) else material
    key = end_condition.lower().replace(" ", "_").replace("-", "_")
    table = AISC_DESIGN_K if use_aisc_k else END_CONDITIONS
    if key not in table:
        raise ValueError(f"Unknown end condition {end_condition!r}. Try: {', '.join(table)}")
    K = table[key]

    slenderness = K * L / section.r
    Cc = math.sqrt(2 * math.pi**2 * mat.E / mat.Sy)

    if slenderness >= Cc:
        regime = "Euler (long column)"
        sigma_cr = math.pi**2 * mat.E / slenderness**2
        formula = "σcr = π²E/(KL/r)²"
    else:
        regime = "Johnson (intermediate column)"
        sigma_cr = mat.Sy * (1 - mat.Sy * slenderness**2 / (4 * math.pi**2 * mat.E))
        formula = "σcr = Sy(1 − Sy(KL/r)²/4π²E)"

    Pcr = sigma_cr * section.A
    sf = Pcr / P if P else None

    warnings = []
    if sf is not None and sf < 3.0:
        warnings.append(
            f"Safety factor {sf:.2f} — buckling failure is sudden, 3+ is the usual target"
        )
    if not use_aisc_k and key in ("fixed_fixed", "fixed_pinned"):
        warnings.append(
            "Theoretical K assumes ideal end fixity; real joints are softer — "
            "rerun with use_aisc_k=True"
        )

    return ColumnResult(
        title=f"Column buckling — {key.replace('_', '-')}",
        reference="Euler / J.B. Johnson transition at Cc",
        inputs=[("Unbraced length L", L, "in"), ("Applied load P", P, "lbf"),
                ("Material", mat.name, ""), ("K", K, ""),
                ("Area A", section.A, "in²"), ("Weak-axis r", section.r, "in")],
        outputs=[("Slenderness KL/r", slenderness, ""), ("Transition Cc", Cc, ""),
                 ("Regime", regime, ""), ("Critical stress", sigma_cr, "psi"),
                 ("Critical load Pcr", Pcr, "lbf"), ("Safety factor", sf, "")],
        formula=f"KL/r = {slenderness:.1f}, Cc = {Cc:.1f} → {formula},  Pcr = σcr·A",
        warnings=warnings,
        slenderness=slenderness, Cc=Cc, regime=regime,
        critical_stress=sigma_cr, Pcr=Pcr, sf=sf,
    )
