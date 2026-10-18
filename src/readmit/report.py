from __future__ import annotations

from typing import List

from .plan import Assessment


def to_markdown(a: Assessment, assumptions: List[str] = ()) -> str:
    L = a.lace
    out = [f"# Readmission risk and transition plan: {a.encounter_id}", "",
           f"**Overall tier: {a.tier.upper()}**", "",
           "| Score | Components | Total | Tier |", "|---|---|---|---|",
           f"| LACE | L {L.L} + A {L.A} + C {L.C} (Charlson {L.charlson}) + E {L.E} | {L.total} / 19 | {L.tier} |"]
    if a.hospital:
        H = a.hospital
        out.append(f"| HOSPITAL | H {H.H} + O {H.O} + S {H.S} + P {H.P} + I {H.I} + A {H.A} + L {H.L} "
                   f"| {H.total} / 13 | {H.tier} |")
    out.append("")
    if a.barriers:
        out += ["**Barriers identified:** " + ", ".join(a.barriers), ""]
    if a.not_assessed:
        out += ["**Not assessed:** " + ", ".join(a.not_assessed), ""]
    if assumptions:
        out += ["**Assumptions:** " + "; ".join(assumptions), ""]
    out += ["## Actions", ""]
    for x in a.actions:
        when = "Before discharge" if x.priority == 1 else "After discharge"
        out.append(f"- **{when}:** {x.text} _(reason: {x.reason}; source: {x.source})_")
    out += ["", "_Decision support only. Scores are population-level risk indicators, not predictions for this "
            "individual; they require clinical judgment._"]
    return "\n".join(out)
