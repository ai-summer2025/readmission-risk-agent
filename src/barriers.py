"""
Barrier Assessment Module

Screens for social determinants of health (SDOH) and clinical barriers
that predict readmission risk beyond standard scoring tools.

Based on:
- CMS SDOH screening framework
- Agency for Healthcare Research and Quality (AHRQ) readmission barriers
- PRAPARE (Protocol for Responding to and Assessing Patients' Assets, Risks, and Experiences)
- Joint Commission Transition of Care standards
"""
from typing import List
from .models import Patient, BarrierAssessment, SocialDeterminant


# SDOH domains and their readmission risk weights
SDOH_DEFINITIONS = {
    "Housing Instability": {
        "intervention": "Social work consult for emergency housing assistance and community resources",
        "readmission_multiplier": 1.8,
        "severity_if_present": "severe",
    },
    "Transportation Barrier": {
        "intervention": "Arrange medical transportation; identify telehealth follow-up options",
        "readmission_multiplier": 1.4,
        "severity_if_present": "moderate",
    },
    "Social Isolation / Lives Alone": {
        "intervention": "Home health assessment; community health worker follow-up program",
        "readmission_multiplier": 1.5,
        "severity_if_present": "moderate",
    },
    "Low Health Literacy": {
        "intervention": "Teach-back method for all instructions; pictogram-based discharge summary; phone follow-up within 48h",
        "readmission_multiplier": 1.6,
        "severity_if_present": "moderate",
    },
    "Language Barrier": {
        "intervention": "Certified medical interpreter; translated discharge instructions",
        "readmission_multiplier": 1.3,
        "severity_if_present": "moderate",
    },
    "Medication Cost Barrier": {
        "intervention": "Pharmacy consult for 340B/generic alternatives; patient assistance programs; supply starter pack",
        "readmission_multiplier": 1.5,
        "severity_if_present": "moderate",
    },
}


def screen_social_determinants(patient: Patient) -> List[SocialDeterminant]:
    """
    Screen patient for social determinants of health associated with readmission.
    Returns list of identified barriers with interventions.
    """
    barriers = []

    # Housing instability
    if not patient.housing_stable:
        barriers.append(SocialDeterminant(
            domain="Housing",
            risk_factor="Housing Instability",
            present=True,
            severity="severe",
            intervention=SDOH_DEFINITIONS["Housing Instability"]["intervention"],
        ))

    # Transportation
    if not patient.transportation:
        barriers.append(SocialDeterminant(
            domain="Transportation",
            risk_factor="Transportation Barrier",
            present=True,
            severity="moderate",
            intervention=SDOH_DEFINITIONS["Transportation Barrier"]["intervention"],
        ))

    # Social isolation
    if patient.lives_alone:
        barriers.append(SocialDeterminant(
            domain="Social Support",
            risk_factor="Social Isolation / Lives Alone",
            present=True,
            severity="moderate",
            intervention=SDOH_DEFINITIONS["Social Isolation / Lives Alone"]["intervention"],
        ))

    # Health literacy
    if patient.health_literacy.lower() == "low":
        barriers.append(SocialDeterminant(
            domain="Health Literacy",
            risk_factor="Low Health Literacy",
            present=True,
            severity="moderate",
            intervention=SDOH_DEFINITIONS["Low Health Literacy"]["intervention"],
        ))

    # Language barrier
    if patient.primary_language.lower() not in ("english", "en"):
        barriers.append(SocialDeterminant(
            domain="Language",
            risk_factor="Language Barrier",
            present=True,
            severity="moderate",
            intervention=SDOH_DEFINITIONS["Language Barrier"]["intervention"],
        ))

    # Medication cost (infer from insurance type)
    if patient.insurance.lower() in ("none", "uninsured", "self-pay", "medicaid"):
        barriers.append(SocialDeterminant(
            domain="Financial",
            risk_factor="Medication Cost Barrier",
            present=True,
            severity="moderate",
            intervention=SDOH_DEFINITIONS["Medication Cost Barrier"]["intervention"],
        ))

    return barriers


def identify_clinical_barriers(patient: Patient) -> List[str]:
    """
    Identify clinical factors that represent barriers to safe discharge.
    These are process-based: missing workup, suboptimal control, no follow-up.
    """
    barriers = []

    # No follow-up arranged
    if not patient.follow_up_arranged:
        barriers.append("⚠️  No outpatient follow-up appointment scheduled (increases readmission risk 2.3x)")

    # Abnormal labs without noted plan
    hgb = patient.labs.get("hemoglobin", None)
    if hgb is not None and hgb < 8.0:
        barriers.append(f"⚠️  Severe anemia (Hgb {hgb} g/dL) — ensure outpatient hematology referral")

    sodium = patient.labs.get("sodium", None)
    if sodium is not None and sodium < 130:
        barriers.append(f"⚠️  Severe hyponatremia (Na {sodium} mEq/L) — may require nephrology follow-up")

    creatinine = patient.labs.get("creatinine", None)
    if creatinine is not None and creatinine > 2.5:
        barriers.append(f"⚠️  Elevated creatinine ({creatinine} mg/dL) — nephrology follow-up within 1 week")

    bnp = patient.labs.get("bnp", None)
    if bnp is not None and bnp > 500:
        barriers.append(f"⚠️  Elevated BNP ({bnp} pg/mL) — heart failure team follow-up within 3 days")

    # High comorbidity burden
    if len(patient.comorbidities) >= 5:
        barriers.append(f"⚠️  High comorbidity burden ({len(patient.comorbidities)} conditions) — consider care coordination program enrollment")

    # Polypharmacy
    if len(patient.medications) >= 10:
        barriers.append(f"⚠️  Polypharmacy ({len(patient.medications)} medications) — pharmacist medication reconciliation required")

    # Short LOS (may be premature discharge)
    if patient.length_of_stay_days <= 1 and patient.admission_type.lower() in ("urgent", "emergent"):
        barriers.append("⚠️  Very short LOS for urgent/emergent admission — verify patient stability before discharge")

    return barriers


def prioritize_interventions(
    social_barriers: List[SocialDeterminant],
    clinical_barriers: List[str],
    high_risk_meds: List[str],
) -> List[str]:
    """
    Generate prioritized list of actionable interventions.
    """
    interventions = []
    priority = 1

    # Always-critical: high-risk medication reconciliation
    if high_risk_meds:
        interventions.append(
            f"🔴 PRIORITY {priority}: Pharmacist medication reconciliation — high-risk medications on list: "
            + ", ".join(high_risk_meds[:3])
        )
        priority += 1

    # Social work for housing/financial barriers (immediate)
    housing_barriers = [b for b in social_barriers if b.domain in ("Housing", "Financial")]
    if housing_barriers:
        interventions.append(
            f"🔴 PRIORITY {priority}: Social work consult BEFORE discharge — "
            + "; ".join(b.risk_factor for b in housing_barriers)
        )
        priority += 1

    # Clinical barriers
    for cb in clinical_barriers:
        interventions.append(f"🟠 PRIORITY {priority}: {cb.replace('⚠️  ', '')}")
        priority += 1

    # Social barriers (other)
    for sb in social_barriers:
        if sb.domain not in ("Housing", "Financial"):
            interventions.append(
                f"🟡 PRIORITY {priority}: {sb.risk_factor} — {sb.intervention}"
            )
            priority += 1

    if not interventions:
        interventions.append("✅ No critical discharge barriers identified — standard discharge pathway appropriate")

    return interventions


def assess_barriers(patient: Patient, high_risk_meds: list) -> BarrierAssessment:
    """
    Full barrier assessment combining social, clinical, and medication factors.
    """
    social_barriers = screen_social_determinants(patient)
    clinical_barriers = identify_clinical_barriers(patient)
    priority_interventions = prioritize_interventions(social_barriers, clinical_barriers, high_risk_meds)

    return BarrierAssessment(
        social_barriers=social_barriers,
        clinical_barriers=clinical_barriers,
        high_risk_medications=high_risk_meds,
        total_barrier_count=len(social_barriers) + len(clinical_barriers),
        priority_interventions=priority_interventions,
    )
