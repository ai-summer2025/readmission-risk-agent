"""Validated readmission risk scores, implemented exactly from the source papers.

LACE index
  van Walraven C, Dhalla IA, Bell C, et al. Derivation and validation of an index to
  predict early death or unplanned readmission after discharge from hospital to the
  community. CMAJ. 2010;182(6):551-557.

HOSPITAL score
  Donze J, Aujesky D, Williams D, Schnipper JL. Potentially avoidable 30-day hospital
  readmissions in medical patients: derivation and validation of a prediction model.
  JAMA Intern Med. 2013;173(8):632-638.

Charlson Comorbidity Index (original weights)
  Charlson ME, Pompei P, Ales KL, MacKenzie CR. A new method of classifying prognostic
  comorbidity in longitudinal studies. J Chronic Dis. 1987;40(5):373-383.

Each function returns the per-component points so that a reviewer can audit the
total. Nothing here is fitted or tuned; these are published point tables.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Set

from .models import Encounter

# ---------------------------------------------------------------- Charlson
CHARLSON_WEIGHTS: Dict[str, int] = {
    "myocardial_infarction": 1,
    "congestive_heart_failure": 1,
    "peripheral_vascular_disease": 1,
    "cerebrovascular_disease": 1,
    "dementia": 1,
    "chronic_pulmonary_disease": 1,
    "connective_tissue_disease": 1,
    "peptic_ulcer_disease": 1,
    "mild_liver_disease": 1,
    "diabetes_uncomplicated": 1,
    "hemiplegia": 2,
    "moderate_severe_renal_disease": 2,
    "diabetes_end_organ_damage": 2,
    "any_tumor": 2,
    "leukemia": 2,
    "lymphoma": 2,
    "moderate_severe_liver_disease": 3,
    "metastatic_solid_tumor": 6,
    "aids": 6,
}
# When the more severe category is present, the milder one is not counted.
CHARLSON_HIERARCHY = {
    "diabetes_uncomplicated": "diabetes_end_organ_damage",
    "mild_liver_disease": "moderate_severe_liver_disease",
    "any_tumor": "metastatic_solid_tumor",
}


def effective_categories(categories: Iterable[str]) -> Set[str]:
    """Validate categories and drop milder ones superseded by a more severe one."""
    cats = set(categories)
    unknown = cats - set(CHARLSON_WEIGHTS)
    if unknown:
        raise ValueError(f"Unknown Charlson categories: {sorted(unknown)}")
    for mild, severe in CHARLSON_HIERARCHY.items():
        if severe in cats:
            cats.discard(mild)
    return cats


def charlson_index(categories: Iterable[str]) -> int:
    return sum(CHARLSON_WEIGHTS[c] for c in effective_categories(categories))


# ---------------------------------------------------------------- LACE
@dataclass(frozen=True)
class LACE:
    L: int
    A: int
    C: int
    E: int
    charlson: int

    @property
    def total(self) -> int:
        return self.L + self.A + self.C + self.E

    @property
    def tier(self) -> str:
        # >= 10 is the cutoff most often used operationally for "high risk".
        return "high" if self.total >= 10 else "moderate" if self.total >= 5 else "low"


def lace_length_points(los_days: float) -> int:
    if los_days < 1:
        return 0
    if los_days < 4:
        return int(los_days)  # 1, 2 or 3
    if los_days <= 6:
        return 4
    if los_days <= 13:
        return 5
    return 7


def lace_comorbidity_points(charlson: int) -> int:
    return charlson if charlson <= 3 else 5


def lace(e: Encounter) -> LACE:
    cci = charlson_index(e.charlson_categories)
    return LACE(L=lace_length_points(e.los_days),
                A=3 if e.emergent_admission else 0,
                C=lace_comorbidity_points(cci),
                E=min(e.ed_visits_6mo, 4),
                charlson=cci)


# ---------------------------------------------------------------- HOSPITAL
@dataclass(frozen=True)
class HOSPITAL:
    H: int  # hemoglobin at discharge < 12 g/dL
    O: int  # discharge from an oncology service  # noqa: E741
    S: int  # sodium at discharge < 135 mmol/L
    P: int  # any procedure during the stay
    I: int  # index admission nonelective (urgent/emergent)  # noqa: E741
    A: int  # admissions in the previous 12 months
    L: int  # length of stay >= 5 days

    @property
    def total(self) -> int:
        return self.H + self.O + self.S + self.P + self.I + self.A + self.L

    @property
    def tier(self) -> str:
        return "high" if self.total >= 7 else "intermediate" if self.total >= 5 else "low"


def hospital_admission_points(admissions_12mo: int) -> int:
    if admissions_12mo <= 1:
        return 0
    if admissions_12mo <= 5:
        return 2
    return 5


def hospital(e: Encounter) -> HOSPITAL:
    missing = [n for n, v in (("hemoglobin", e.hemoglobin), ("sodium", e.sodium)) if v is None]
    if missing:
        raise ValueError(f"HOSPITAL score needs discharge {', '.join(missing)}")
    return HOSPITAL(H=1 if e.hemoglobin < 12 else 0,
                    O=2 if e.oncology_discharge else 0,
                    S=1 if e.sodium < 135 else 0,
                    P=1 if e.had_procedure else 0,
                    I=1 if e.emergent_admission else 0,
                    A=hospital_admission_points(e.admissions_12mo),
                    L=2 if e.los_days >= 5 else 0)
