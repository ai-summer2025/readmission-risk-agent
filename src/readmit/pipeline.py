"""Build an Encounter from JSON or a discharge summary, then assess it."""
from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional, Tuple

from .extract import extract_llm, extract_rules
from .models import Encounter
from .plan import Assessment, assess

REQUIRED = ("age", "los_days", "emergent_admission")
DEFAULTS = {"ed_visits_6mo": 0, "admissions_12mo": 0, "had_procedure": False, "oncology_discharge": False}


def encounter_from_dict(d: dict) -> Encounter:
    known = set(Encounter.__dataclass_fields__)
    return Encounter(**{k: v for k, v in d.items() if k in known})


def load_encounter(path: str) -> Encounter:
    return encounter_from_dict(json.loads(Path(path).read_text()))


def encounter_from_text(text: str, encounter_id: str = "note", use_llm: bool = False, client=None,
                        overrides: Optional[dict] = None) -> Tuple[Encounter, List[str]]:
    """Returns (encounter, assumptions). Raises ValueError if required inputs are missing."""
    if use_llm:
        if client is None:
            from .llm import client_from_env
            client = client_from_env()
        fields, cats = extract_llm(text, client)
    else:
        fields, cats = extract_rules(text)
    fields.update({k: v for k, v in (overrides or {}).items() if v is not None})
    missing = [k for k in REQUIRED if k not in fields]
    if missing:
        raise ValueError(f"Could not find {', '.join(missing)} in the note; pass them explicitly.")
    assumptions = []
    for k, v in DEFAULTS.items():
        if k not in fields:
            fields[k] = v
            assumptions.append(f"{k} not documented; assumed {v}")
    fields.pop("admission_date", None)
    fields.pop("discharge_date", None)
    return encounter_from_dict({"id": encounter_id, **fields, "charlson_categories": cats}), assumptions


def run(e: Encounter) -> Assessment:
    return assess(e)
