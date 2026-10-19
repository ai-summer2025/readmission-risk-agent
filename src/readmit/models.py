from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import List, Optional


@dataclass
class Encounter:
    """Inputs for LACE, HOSPITAL and the transition-of-care plan. All synthetic in this repo."""

    id: str
    age: int
    los_days: float
    emergent_admission: bool  # admitted urgently/emergently (e.g. via the ED)
    ed_visits_6mo: int = 0  # ED visits in the 6 months before admission
    admissions_12mo: int = 0  # hospital admissions in the 12 months before admission
    charlson_categories: List[str] = field(default_factory=list)
    hemoglobin: Optional[float] = None  # g/dL at discharge
    sodium: Optional[float] = None  # mmol/L at discharge
    had_procedure: bool = False
    oncology_discharge: bool = False
    discharge_med_count: Optional[int] = None
    # Social / transition barriers (True = barrier present, None = not assessed)
    lives_alone: Optional[bool] = None
    no_pcp: Optional[bool] = None
    housing_instability: Optional[bool] = None
    transportation_barrier: Optional[bool] = None
    medication_cost_barrier: Optional[bool] = None
    limited_health_literacy: Optional[bool] = None
    needs_interpreter: Optional[bool] = None

    def to_dict(self) -> dict:
        return asdict(self)
