"""Cross-section properties about the horizontal bending axis.

A (in^2), I (in^4), S (in^3), r (in).
"""

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SectionProps:
    A: float
    I: float
    S: float
    r: float

    def __str__(self) -> str:
        return f"A={self.A:.4g} in²  I={self.I:.4g} in⁴  S={self.S:.4g} in³  r={self.r:.4g} in"


def rectangle(b: float, h: float) -> SectionProps:
    """Solid rectangle, b wide by h tall. Bending about the axis normal to h."""
    return SectionProps(A=b * h, I=b * h**3 / 12, S=b * h**2 / 6, r=h / math.sqrt(12))


def solid_round(d: float) -> SectionProps:
    return SectionProps(
        A=math.pi * d**2 / 4, I=math.pi * d**4 / 64, S=math.pi * d**3 / 32, r=d / 4
    )


def round_tube(od: float, id: float) -> SectionProps:
    """Round tube. `id` shadows the builtin but matches shop usage."""
    if id >= od:
        raise ValueError(f"ID ({id}) must be less than OD ({od})")
    A = math.pi * (od**2 - id**2) / 4
    I = math.pi * (od**4 - id**4) / 64
    return SectionProps(A=A, I=I, S=I / (od / 2), r=math.sqrt(I / A))


def i_beam(H: float, B: float, tf: float, tw: float) -> SectionProps:
    """Symmetric I-beam: H overall tall, flanges B wide by tf thick, web tw thick."""
    if 2 * tf >= H:
        raise ValueError(f"Flanges (2 x {tf}) leave no web within H={H}")
    A = 2 * B * tf + (H - 2 * tf) * tw
    I = B * H**3 / 12 - (B - tw) * (H - 2 * tf) ** 3 / 12
    return SectionProps(A=A, I=I, S=I / (H / 2), r=math.sqrt(I / A))


def for_shape(shape: str, **dims: float) -> SectionProps:
    """Dispatch by shape name — convenient when the shape is a user choice.

    >>> for_shape("rectangle", b=1, h=2).S
    0.6666666666666666
    """
    builders = {
        "rectangle": rectangle,
        "solid_round": solid_round,
        "round_tube": round_tube,
        "i_beam": i_beam,
    }
    key = shape.lower().replace(" ", "_").replace("-", "_")
    if key not in builders:
        raise ValueError(f"Unknown shape {shape!r}. Try one of: {', '.join(builders)}")
    return builders[key](**dims)
