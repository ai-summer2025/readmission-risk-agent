"""
Data models for the Readmission Risk Agent.
Defines patient data structures, scores, and discharge plan components.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class RiskLevel(Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class AdmissionType(Enum):
    ELECTIVE = "elective"
    URGENT = "urgent"
    EMERGENT = "emergent"


@dataclass
class Comorbidity:
    name: str
    icd10_prefix: str
    cci_weight: int  # Charlson Comorbidity Index weight
    hospital_score_active_malignancy: bool = False


@dataclass
class LabResult:
    name: str
    value: float
    unit: str
    reference_low: Optional[float] = None
    reference_high: Optional[float] = None

    @property
    def is_abnormal(self) -> bool:
        if self.reference_low is not None and self.value < self.reference_low:
            return True
        if self.reference_high is not None and self.value > self.reference_high:
            return True
        return False


@dataclass
class SocialDeterminant:
    domain: str
    risk_factor: str
    present: bool
    severity: str  # "mild", "moderate", "severe"
    intervention: str


@dataclass
class Patient:
    patient_id: str
    age: int
    sex: str  # "M" or "F"
    primary_diagnosis: str
    primary_icd10: str
    comorbidities: List[str]  # List of condition names
    admission_type: str       # "elective", "urgent", "emergent"
    length_of_stay_days: int
    ed_visits_past_6_months: int
    admissions_past_year: int
    discharge_service: str    # e.g., "medicine", "oncology", "cardiology"
    had_procedure: bool
    active_malignancy: bool
    labs: Dict[str, float]    # {lab_name: value}
    medications: List[str]
    insurance: str
    lives_alone: bool
    housing_stable: bool
    transportation: bool      # True = has transportation
    health_literacy: str      # "low", "moderate", "high"
    primary_language: str
    follow_up_arranged: bool
    notes: Optional[str] = None


@dataclass
class LACEScore:
    """LACE+ Index: validated 30-day readmission predictor"""
    l_score: int    # Length of stay (0-7)
    a_score: int    # Acuity of admission (0 or 3)
    c_score: int    # Charlson comorbidity index converted (0-5)
    e_score: int    # ED visits in past 6 months (0-4)
    total: int
    cci_raw: int
    readmission_probability: float

    @property
    def risk_level(self) -> RiskLevel:
        if self.total <= 4:
            return RiskLevel.LOW
        elif self.total <= 9:
            return RiskLevel.MODERATE
        elif self.total <= 14:
            return RiskLevel.HIGH
        else:
            return RiskLevel.VERY_HIGH


@dataclass
class HOSPITALScore:
    """HOSPITAL Score: 7-factor readmission risk tool"""
    h_hemoglobin: int    # Hemoglobin <12 g/dL at discharge: 1 pt
    o_oncology: int      # Discharge from oncology: 2 pts
    s_sodium: int        # Sodium <135 mEq/L: 1 pt
    p_procedure: int     # Had procedure: 1 pt
    i_index: int         # Urgent/emergent admission: 1 pt
    t_admissions: int    # ≥5 admissions past year: 2 pts
    a_malignancy: int    # Active malignancy: 2 pts
    l_los: int           # LOS >5 days: 2 pts
    total: int
    readmission_probability: float

    @property
    def risk_level(self) -> RiskLevel:
        if self.total <= 4:
            return RiskLevel.LOW
        elif self.total <= 6:
            return RiskLevel.MODERATE
        else:
            return RiskLevel.HIGH


@dataclass
class BarrierAssessment:
    social_barriers: List[SocialDeterminant]
    clinical_barriers: List[str]
    high_risk_medications: List[str]
    total_barrier_count: int
    priority_interventions: List[str]


@dataclass
class DischargeInstruction:
    condition: str
    key_activities: List[str]
    dietary_restrictions: List[str]
    medication_reminders: List[str]
    warning_signs: List[str]        # "Return to ED if..."
    follow_up_timeline: str
    plain_language_summary: str


@dataclass
class DischargeReport:
    """Complete output of the 6-step Readmission Risk Agent"""
    patient_id: str
    timestamp: str
    step_results: Dict[str, Any]

    # Step 2: Scores
    lace_score: Optional[LACEScore] = None
    hospital_score: Optional[HOSPITALScore] = None
    composite_risk: Optional[RiskLevel] = None
    composite_probability: Optional[float] = None

    # Step 3: Barriers
    barrier_assessment: Optional[BarrierAssessment] = None

    # Step 4: Evidence
    evidence_summaries: List[str] = field(default_factory=list)

    # Step 5: Plan
    discharge_plan: List[str] = field(default_factory=list)
    sbar_note: Optional[str] = None

    # Step 6: Instructions
    patient_instructions: Optional[DischargeInstruction] = None

    # Status
    agent_log: List[str] = field(default_factory=list)
    completed: bool = False
