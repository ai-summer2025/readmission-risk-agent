"""Transition-of-care plan: risk tier + barriers -> concrete actions.

Actions are drawn from published care-transition programs:
  RED  AHRQ Re-Engineered Discharge (Project RED) toolkit
  BOOST  SHM Project BOOST (Better Outcomes by Optimizing Safe Transitions)
They are suggestions for the care team, not orders.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from .models import Encounter
from .scores import HOSPITAL, LACE, hospital, lace


@dataclass
class Action:
    priority: int  # 1 = do before discharge
    text: str
    reason: str
    source: str


@dataclass
class Assessment:
    encounter_id: str
    lace: LACE
    hospital: Optional[HOSPITAL]
    tier: str
    barriers: List[str] = field(default_factory=list)
    not_assessed: List[str] = field(default_factory=list)
    actions: List[Action] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "encounter_id": self.encounter_id,
            "lace": {**self.lace.__dict__, "total": self.lace.total, "tier": self.lace.tier},
            "hospital": None if self.hospital is None else
            {**self.hospital.__dict__, "total": self.hospital.total, "tier": self.hospital.tier},
            "tier": self.tier, "barriers": self.barriers, "not_assessed": self.not_assessed,
            "actions": [a.__dict__ for a in self.actions],
        }


BARRIERS = {
    "lives_alone": ("Lives alone",
                    "Confirm who will help in the first days at home; consider a home health referral.", "BOOST"),
    "no_pcp": ("No primary care clinician",
               "Establish a primary care clinician and book the follow-up visit before discharge.", "RED"),
    "housing_instability": ("Housing instability",
                            "Social work consult before discharge; confirm a safe discharge address.", "BOOST"),
    "transportation_barrier": ("Transportation barrier",
                               "Arrange transport for the follow-up visit or offer a telehealth visit.", "RED"),
    "medication_cost_barrier": ("Cannot afford medications",
                                "Pharmacist or social work review for lower-cost alternatives or assistance; "
                                "fill prescriptions before the patient leaves if possible.", "RED"),
    "limited_health_literacy": ("Limited health literacy",
                                "Use plain-language instructions and teach-back for medications and warning signs.",
                                "RED"),
    "needs_interpreter": ("Needs an interpreter",
                          "Provide instructions in the patient's preferred language with a qualified interpreter.",
                          "RED"),
}

TIER_RANK = {"low": 0, "moderate": 1, "intermediate": 1, "high": 2}


def assess(e: Encounter) -> Assessment:
    lc = lace(e)
    try:
        hs: Optional[HOSPITAL] = hospital(e)
    except ValueError:
        hs = None
    tiers = [lc.tier] + ([hs.tier] if hs else [])
    tier = max(tiers, key=TIER_RANK.get)
    tier = "moderate" if tier == "intermediate" else tier

    a = Assessment(e.id, lc, hs, tier)
    for attr, (label, action, src) in BARRIERS.items():
        v = getattr(e, attr)
        if v is True:
            a.barriers.append(label)
            a.actions.append(Action(1, action, label, src))
        elif v is None:
            a.not_assessed.append(label)

    # Baseline actions for every patient (Project RED core components)
    a.actions += [
        Action(1, "Reconcile the discharge medication list against the pre-admission list.",
               "All discharges", "RED"),
        Action(1, "Give a written, plain-language discharge plan with warning signs and who to call.",
               "All discharges", "RED"),
    ]
    if tier in ("moderate", "high"):
        a.actions.append(Action(1, "Book the follow-up appointment before the patient leaves (within 7 days).",
                                f"{tier} risk", "RED"))
        a.actions.append(Action(2, "Phone call within 2-3 days of discharge to review medications and the plan.",
                                f"{tier} risk", "RED"))
    if tier == "high":
        a.actions.append(Action(1, "Teach-back on each medication and warning sign before discharge.",
                                "high risk", "BOOST"))
        a.actions.append(Action(2, "Consider a transitional care or home visit program referral.",
                                "high risk", "BOOST"))
    if e.discharge_med_count is not None and e.discharge_med_count >= 10:
        a.actions.append(Action(1, "Pharmacist medication review before discharge (10 or more medications).",
                                "polypharmacy", "BOOST"))
    if hs is None:
        a.not_assessed.append("HOSPITAL score (discharge hemoglobin and sodium missing)")
    a.actions.sort(key=lambda x: x.priority)
    return a
