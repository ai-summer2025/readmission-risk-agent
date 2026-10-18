"""
Evidence-based clinical scoring for 30-day readmission risk.

Implements:
- LACE+ Index (van Walraven et al., CMAJ 2010)
- HOSPITAL Score (Donzé et al., J Hosp Med 2013)
- Charlson Comorbidity Index (Charlson et al., J Chronic Dis 1987)

All algorithms are open-domain validated tools used in clinical practice.
References:
- PMID 20713753 (LACE validation)
- PMID 24167211 (HOSPITAL Score validation)
- PMID 3558716 (Charlson Index original)
"""
from typing import Dict, Tuple
from .models import Patient, LACEScore, HOSPITALScore, RiskLevel

# ─────────────────────────────────────────────────────────────
# Charlson Comorbidity Index condition weights
# ─────────────────────────────────────────────────────────────
CCI_WEIGHTS: Dict[str, int] = {
    # Weight 1
    "myocardial infarction": 1,
    "congestive heart failure": 1,
    "peripheral vascular disease": 1,
    "cerebrovascular disease": 1,
    "dementia": 1,
    "chronic pulmonary disease": 1,
    "copd": 1,
    "rheumatic disease": 1,
    "peptic ulcer disease": 1,
    "mild liver disease": 1,
    "diabetes without complications": 1,
    "type 2 diabetes": 1,
    # Weight 2
    "diabetes with complications": 2,
    "diabetes with end organ damage": 2,
    "hemiplegia": 2,
    "paraplegia": 2,
    "moderate to severe renal disease": 2,
    "chronic kidney disease": 2,
    "ckd": 2,
    "solid tumor without metastasis": 2,
    "cancer": 2,
    "leukemia": 2,
    "lymphoma": 2,
    # Weight 3
    "moderate to severe liver disease": 3,
    "cirrhosis": 3,
    # Weight 6
    "metastatic solid tumor": 6,
    "aids": 6,
    "hiv": 6,
}

# High-risk medications for readmission (ISMP high-alert list)
HIGH_RISK_MEDS = {
    "warfarin", "coumadin", "heparin", "enoxaparin", "lovenox",
    "insulin", "metformin", "digoxin", "lithium", "methotrexate",
    "amiodarone", "phenytoin", "dilantin", "furosemide", "lasix",
    "prednisone", "opioid", "oxycodone", "morphine", "hydrocodone",
    "tramadol", "fentanyl", "carbamazepine", "valproic acid",
    "tacrolimus", "cyclosporine", "sirolimus",
}


def compute_charlson_index(comorbidities: list) -> int:
    """
    Compute raw Charlson Comorbidity Index from a list of condition names.
    Performs case-insensitive substring matching.
    """
    total = 0
    seen_categories = set()
    for condition in comorbidities:
        condition_lower = condition.lower()
        for keyword, weight in CCI_WEIGHTS.items():
            if keyword in condition_lower and keyword not in seen_categories:
                total += weight
                seen_categories.add(keyword)
                break
    return total


def cci_to_lace_c_score(cci: int) -> int:
    """
    Convert raw CCI to LACE 'C' component score.
    Based on van Walraven LACE+ paper conversion table.
    """
    if cci == 0:
        return 0
    elif cci <= 2:
        return 0
    elif cci <= 4:
        return 1
    elif cci == 5:
        return 2
    elif cci == 6:
        return 3
    else:  # 7+
        return 5


def compute_lace_score(patient: Patient) -> LACEScore:
    """
    Compute LACE+ Index for 30-day readmission risk.

    L = Length of stay (1 pt/day, capped at 7)
    A = Acuity: 3 pts if admitted via ED (urgent/emergent)
    C = Charlson score converted (0-5)
    E = ED visits in past 6 months (0-4 pts, capped at 4)

    Total 0-19
    Low (0-4) ≈ 5%, Moderate (5-9) ≈ 12%, High (10-14) ≈ 22%, Very High (15+) ≈ 35%
    """
    # L component
    l_score = min(patient.length_of_stay_days, 7)

    # A component
    a_score = 3 if patient.admission_type.lower() in ("urgent", "emergent", "emergency") else 0

    # C component
    cci_raw = compute_charlson_index(patient.comorbidities)
    c_score = cci_to_lace_c_score(cci_raw)

    # E component
    e_score = min(patient.ed_visits_past_6_months, 4)

    total = l_score + a_score + c_score + e_score

    # Map to approximate probability
    probability_map = {
        RiskLevel.LOW: 0.05,
        RiskLevel.MODERATE: 0.12,
        RiskLevel.HIGH: 0.22,
        RiskLevel.VERY_HIGH: 0.35,
    }

    lace = LACEScore(
        l_score=l_score,
        a_score=a_score,
        c_score=c_score,
        e_score=e_score,
        total=total,
        cci_raw=cci_raw,
        readmission_probability=0.0,
    )
    lace.readmission_probability = probability_map[lace.risk_level]
    return lace


def compute_hospital_score(patient: Patient) -> HOSPITALScore:
    """
    Compute HOSPITAL Score for 30-day potentially avoidable readmission.

    H = Hemoglobin <12 g/dL at discharge: 1 pt
    O = Discharge from oncology service: 2 pts
    S = Sodium <135 mEq/L at discharge: 1 pt
    P = Coded procedure during hospitalization: 1 pt
    I = Admission type urgent/emergent: 1 pt
    T = ≥5 admissions in past year: 2 pts
    A = Active malignancy: 2 pts
    L = LOS >5 days: 2 pts

    Total 0-13 (theoretical max varies by source; 0-13 in practice)
    Low (0-4) <5%, Intermediate (5-6) 10-20%, High (7+) >20%
    """
    h = 1 if patient.labs.get("hemoglobin", 14.0) < 12.0 else 0
    o = 2 if patient.discharge_service.lower() == "oncology" else 0
    s = 1 if patient.labs.get("sodium", 140.0) < 135.0 else 0
    p = 1 if patient.had_procedure else 0
    i = 1 if patient.admission_type.lower() in ("urgent", "emergent", "emergency") else 0
    t = 2 if patient.admissions_past_year >= 5 else 0
    a = 2 if patient.active_malignancy else 0
    l = 2 if patient.length_of_stay_days > 5 else 0

    total = h + o + s + p + i + t + a + l

    probability_map = {
        RiskLevel.LOW: 0.04,
        RiskLevel.MODERATE: 0.14,
        RiskLevel.HIGH: 0.23,
    }

    hosp = HOSPITALScore(
        h_hemoglobin=h,
        o_oncology=o,
        s_sodium=s,
        p_procedure=p,
        i_index=i,
        t_admissions=t,
        a_malignancy=a,
        l_los=l,
        total=total,
        readmission_probability=0.0,
    )
    hosp.readmission_probability = probability_map[hosp.risk_level]
    return hosp


def compute_composite_risk(lace: LACEScore, hospital: HOSPITALScore) -> Tuple[RiskLevel, float]:
    """
    Combine LACE+ and HOSPITAL scores into a composite risk estimate.
    Takes the higher of the two risk levels and averages probabilities.
    """
    levels_order = [RiskLevel.LOW, RiskLevel.MODERATE, RiskLevel.HIGH, RiskLevel.VERY_HIGH]

    lace_idx = levels_order.index(lace.risk_level)
    hosp_idx = levels_order.index(hospital.risk_level)

    # Take max risk level
    composite_level = levels_order[max(lace_idx, hosp_idx)]

    # Average the two probabilities (with slight weighting toward LACE which has more validation)
    composite_prob = round(
        (lace.readmission_probability * 0.6 + hospital.readmission_probability * 0.4), 3
    )

    return composite_level, composite_prob


def identify_high_risk_medications(medications: list) -> list:
    """Identify high-risk medications from patient's medication list."""
    found = []
    for med in medications:
        med_lower = med.lower()
        for hrm in HIGH_RISK_MEDS:
            if hrm in med_lower:
                found.append(med)
                break
    return found
