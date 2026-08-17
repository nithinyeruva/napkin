# napkin

Python port of `~/Projects/MechEng_HandCalcs.xlsx` — mechanical engineering hand
calcs for preliminary sizing.

## Status

Phase 1 complete: all 11 workbook sheets ported, 54 tests passing.

Phase 2 complete: `docs/index.html` is the web app — eight calculators,
diagrams, worked formulas, glossary, projects, export, and AI routing. Hosted at
`nithinyeruva.github.io/napkin` and as a Claude artifact.

The formulas **are** reimplemented in JavaScript there, which an earlier version
of this file forbade. The ban was right about the risk and wrong about the fix:
the browser can't run Python, so the choice was a JS copy or no web app. What
keeps the copies honest is `docs/vectors.json` — 19 full-precision results
exported from the Python package, re-run in the browser on every load, with the
pass count in the footer. Drift fails visibly instead of silently. **Regenerate
the vectors whenever a formula changes**, and never hand-edit them to match JS.

## Conventions

- **US customary internally.** Inches, lbf, psi, °F, BTU/hr. Convert at the
  boundary with `units.convert`, never mid-calculation.
- **Every calculator returns a `Result` subclass** carrying `inputs`, `outputs`,
  `formula`, `reference` and `warnings`. The `markdown()` method is the point of
  the whole design — hand calcs land in part design records without retyping.
- **Warnings are load-bearing.** When an assumption stops holding (deflection
  past t/2, t past r/10, Re below 4000, SF under target) the result says so.
  Don't quietly drop them to tidy up output.
- **Back-solve functions are named `required_*`** and take `target_sf`.
- Materials accept either a `Material` or its name string.

## Testing

```bash
pytest
```

Expected values in `tests/test_against_workbook.py` are the numbers the
**spreadsheet itself computes** for its default inputs, read from the cached
values in the xlsx. That's what makes the port verifiable rather than a
plausible-looking rewrite. When adding a calculator, get its reference value the
same way rather than from your own arithmetic.

`--doctest-modules` is on, so docstring examples run as tests. Don't put a
guessed number in a docstring — it will fail, correctly.

## Accuracy notes

- Rectangular plate β/α tables use Excel `VLOOKUP(..., TRUE)` semantics: step
  **down** to the largest tabulated a/b not exceeding the actual ratio. Not
  interpolation. `test_coefficient_lookup_steps_down` pins this.
- Column K factors default to theoretical values; `use_aisc_k=True` gives the
  AISC design values for real end fixity.
- Shaft results are static only. Anything rotating needs a Shigley fatigue check
  on top, which this package does not do.

## The server

`server/napkin.mjs` — zero-dependency Node, serves `docs/` and holds the API
key. It exists only so the key isn't in the browser; everything else in napkin
works without it.

- The key is read from `server/.env`. **Never** move key handling into
  `docs/index.html` — that was the original design and it was wrong.
- `docs/index.html` probes `api/health` at load. No server, no AI, no error.
  Every AI affordance is behind `aiOn()`.
- Anthropic's structured outputs take a **strict subset** of JSON Schema: no
  union types, and `additionalProperties` may only be `false`, never a schema.
  Both rules were violated in the first version and the only symptom was an
  opaque 400. `server/schema.mjs` exports `illegal()` — run a schema through it
  before shipping a change to it.
- Prices in `MODELS` are dollars per Mtok and drive the spend tracker. Sonnet 5
  carries introductory pricing until 2026-09-01, after which `rates()` returns
  the standard numbers on its own.
- There is no balance endpoint at Anthropic. "Credits left" counts down from a
  figure the user enters, over napkin's own spend only. Don't present it as a
  live account balance.
