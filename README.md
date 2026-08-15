# mecheng

Mechanical engineering hand calcs — beams, plates, columns, shafts, bolts,
pressure vessels, cooling lines.

Preliminary sizing and sanity checks using Shigley and Roark closed-form
solutions. Static loads, small deflections, room temperature. Ported from
`MechEng_HandCalcs.xlsx`, with every formula validated against that workbook's
own computed values.

```python
from mecheng import beams, sections

s = sections.round_tube(od=1.5, id=1.25)
r = beams.analyze("cant_point", L=20, section=s, material="Al 6061-T6", P=500)
print(r)
```

```
Beam bending — Cantilever, end point load
  Max moment M              10,000 in-lbf
  Max bending stress        58,292 psi
  Max deflection              1.04 in
  Allowable L/240          0.08333 in
  Safety factor             0.6862
  Status                      FAIL
  ! Deflection 1.036 in exceeds L/240 = 0.08333 in — stiffen
  ! Safety factor 0.69 is FAIL
```

## Design records

Every result renders itself as markdown — inputs, the formula used, results, and
any warnings — so a hand calc goes straight into a part design record instead of
being retyped.

```python
print(r.markdown())
```

## Back-solving

Each module sizes for a target safety factor rather than making you iterate:

```python
beams.required_diameter(M=2500, material="Steel A36 (HR)", target_sf=2.0)
shafts.required_diameter(M=200, T=180, material="Steel 4140 (Q&T 28 HRC)")
plates.circular(a=3, q=200, t=0.75, material="Tool steel P20 (30 HRC)").required_t
```

## Modules

| Module | Covers |
| --- | --- |
| `materials` | 17 materials — E, Sy, Su, ν, density, CTE, k. `add()` your own |
| `sections` | Rectangle, solid round, round tube, I-beam — A, I, S, r |
| `beams` | Six load cases, stress, deflection, SF, required size |
| `plates` | Circular and rectangular under pressure (Roark) |
| `columns` | Euler / Johnson buckling with end-condition K |
| `shafts` | Combined torsion and bending (von Mises), twist |
| `bolts` | UNC threads and grades — preload, torque, separation, shear |
| `pressure` | Thin-wall cylinder and sphere, end-cap bolt loads |
| `cooling` | Flow for a heat load, Reynolds, pressure drop, conduction/convection |
| `units` | Conversions and constants |

## Units

US customary throughout: inches, lbf, psi, °F. Convert at the boundary:

```python
from mecheng import units
units.convert(100, "psi", "MPa")
```

## What this is not

Preliminary sizing only. It will not tell you about fatigue, stress
concentration at a keyway or fillet, thick-wall vessels, large-deflection plate
behaviour, or anything code-regulated. Results carry warnings when an assumption
stops holding — read them.

## Development

```bash
pytest
```

54 tests, all checked against the source workbook.
