"""Shared result plumbing.

Every calculator returns a Result subclass. Results carry their inputs, the
formula they used, and know how to render themselves as markdown so a hand calc
can be pasted straight into a design record.
"""

from dataclasses import dataclass, field


def classify_sf(sf: float | None) -> str:
    """Traffic-light a safety factor: red below 1, yellow to 1.5, green above.

    Mirrors the conditional formatting in the source workbook.
    """
    if sf is None:
        return "n/a"
    if sf < 1.0:
        return "FAIL"
    if sf < 1.5:
        return "MARGINAL"
    return "OK"


def _fmt(value: float | str | None) -> str:
    if value is None:
        return "-"
    if isinstance(value, str):
        return value
    a = abs(value)
    if a != 0 and (a >= 1e5 or a < 1e-3):
        return f"{value:.4g}"
    if a >= 100:
        return f"{value:,.0f}"
    if a >= 1:
        return f"{value:.3g}"
    return f"{value:.4g}"


@dataclass
class Result:
    """Base for calculator results.

    Subclasses set `title`, populate `inputs` and `outputs` as
    (label, value, unit) triples, and set `formula` / `reference`.
    """

    title: str = ""
    inputs: list[tuple[str, float | str, str]] = field(default_factory=list)
    outputs: list[tuple[str, float | str, str]] = field(default_factory=list)
    formula: str = ""
    reference: str = ""
    warnings: list[str] = field(default_factory=list)

    def markdown(self) -> str:
        """Render as a markdown block for a part design record.

        Inputs, formula, results and any warnings — the shape a hand calc needs
        to be defensible in a design review months later.
        """
        lines = [f"### {self.title}", ""]
        if self.reference:
            lines += [f"*{self.reference}*", ""]
        lines += ["| Input | Value | Unit |", "| --- | --- | --- |"]
        lines += [f"| {n} | {_fmt(v)} | {u} |" for n, v, u in self.inputs]
        if self.formula:
            lines += ["", f"`{self.formula}`", ""]
        lines += ["| Result | Value | Unit |", "| --- | --- | --- |"]
        lines += [f"| {n} | {_fmt(v)} | {u} |" for n, v, u in self.outputs]
        if self.warnings:
            lines.append("")
            lines += [f"> **{w}**" for w in self.warnings]
        return "\n".join(lines)

    def __str__(self) -> str:
        width = max((len(n) for n, _, _ in self.outputs), default=0)
        lines = [self.title]
        for name, value, unit in self.outputs:
            lines.append(f"  {name:<{width}}  {_fmt(value):>12} {unit}")
        lines += [f"  ! {w}" for w in self.warnings]
        return "\n".join(lines)
