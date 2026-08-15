"""Room-temperature material properties.

Typical handbook values (MatWeb / Shigley). Real stock varies by heat, temper and
thickness — verify against a supplier datasheet before releasing a design.

All values US customary: E and Sy/Su in psi, density lb/in^3, CTE uin/in-F,
k in BTU/hr-ft-F.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    name: str
    E: float
    Sy: float
    Su: float
    nu: float
    density: float
    cte: float
    k: float
    notes: str = ""

    @property
    def G(self) -> float:
        """Shear modulus, G = E / (2(1+v))."""
        return self.E / (2 * (1 + self.nu))


MATERIALS: dict[str, Material] = {
    m.name: m
    for m in [
        Material("Steel A36 (HR)", 29e6, 36000, 58000, 0.29, 0.284, 6.5, 27,
                 "Structural plate & shapes"),
        Material("Steel 1018 (CR)", 29e6, 54000, 64000, 0.29, 0.284, 6.5, 30,
                 "General-purpose machining"),
        Material("Steel 4140 (Q&T 28 HRC)", 29.7e6, 95000, 110000, 0.29, 0.284, 6.8, 24.5,
                 "Pre-hard alloy steel"),
        Material("Tool steel P20 (30 HRC)", 29.7e6, 125000, 140000, 0.29, 0.284, 7.1, 17,
                 "Mold plates / cavities"),
        Material("Tool steel H13 (45 HRC)", 30e6, 185000, 215000, 0.30, 0.280, 6.8, 14,
                 "Hot-work inserts / cores"),
        Material("SS 304 (annealed)", 28e6, 30000, 75000, 0.29, 0.289, 9.6, 9.4,
                 "Corrosion resistant"),
        Material("SS 17-4 PH (H900)", 28.5e6, 170000, 190000, 0.29, 0.282, 6.0, 10.4,
                 "High-strength stainless"),
        Material("Al 6061-T6", 10e6, 40000, 45000, 0.33, 0.098, 13.1, 96,
                 "General aluminum"),
        Material("Al 7075-T6", 10.4e6, 73000, 83000, 0.33, 0.102, 13.0, 75,
                 "High-strength aluminum"),
        Material("Brass C360 (1/2 hard)", 14e6, 45000, 58000, 0.31, 0.307, 11.4, 67,
                 "Free-machining; baffles/fittings"),
        Material("Copper C110 (annealed)", 17e6, 10000, 32000, 0.34, 0.323, 9.8, 226,
                 "High conductivity"),
        Material("Ti-6Al-4V", 16.5e6, 128000, 138000, 0.34, 0.160, 4.8, 3.9,
                 "Titanium"),
        Material("ABS (molded)", 320000, 6000, 6500, 0.35, 0.037, 55, 0.10,
                 "Typical, dry"),
        Material("Polycarbonate", 340000, 9000, 9500, 0.37, 0.043, 39, 0.11),
        Material("Nylon 6/6 (dry)", 400000, 11000, 12000, 0.39, 0.041, 45, 0.14,
                 "Strength drops ~50% conditioned"),
        Material("Acetal (Delrin)", 450000, 10000, 10000, 0.35, 0.051, 47, 0.21),
        Material("PEEK", 500000, 14000, 14500, 0.38, 0.047, 26, 0.14),
    ]
}


def get(name: str) -> Material:
    """Look up a material by name. Raises KeyError listing valid names."""
    try:
        return MATERIALS[name]
    except KeyError:
        raise KeyError(
            f"Unknown material {name!r}. Available: {', '.join(sorted(MATERIALS))}"
        ) from None


def add(material: Material) -> None:
    """Register a custom material so it's available to every calculator."""
    MATERIALS[material.name] = material
