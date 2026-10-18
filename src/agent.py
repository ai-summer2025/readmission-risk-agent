"""
Readmission Risk Agent — Core Orchestrator

6-step agentic pipeline for hospital discharge planning and readmission risk assessment.

Step 1: ASSESS   — Parse and validate patient data
Step 2: SCORE    — Compute LACE+ and HOSPITAL readmission risk scores
Step 3: BARRIERS — Screen for social determinants and clinical barriers
Step 4: EVIDENCE — Retrieve condition-specific discharge guidelines (PubMed + cache)
Step 5: PLAN     — Generate discharge plan and SBAR handoff note
Step 6: EDUCATE  — Create personalized patient discharge instructions
"""
import json
import sys
from datetime import datetime
from typing import Optional

from .models import (
    Patient, DischargeReport, RiskLevel, AdmissionType
)
from .scoring import (
    compute_lace_score, compute_hospital_score, compute_composite_risk,
    identify_high_risk_medications
)
from .barriers import assess_barriers
from .evidence import get_evidence_summaries
from .instructions import generate_discharge_instructions

STEP_EMOJIS = {
    1: "🔍",
    2: "📊",
    3: "🚧",
    4: "📚",
    5: "📋",
    6: "🎓",
}

RISK_COLORS = {
    RiskLevel.LOW: "🟢",
    RiskLevel.MODERATE: "🟡",
    RiskLevel.HIGH: "🟠",
    RiskLevel.VERY_HIGH: "🔴",
}


class ReadmissionRiskAgent:
    """
    Autonomous 6-step agent for hospital discharge risk assessment and planning.
    """

    def __init__(self, verbose: bool = True):
        self.verbose = verbose

    def _log(self, step: int, message: str) -> str:
        """Log a step message and optionally print to console."""
        emoji = STEP_EMOJIS.get(step, "▶️")
        timestamp = datetime.now().strftime("%H:%M:%S")
        msg = f"[{timestamp}] {emoji} STEP {step}: {message}"
        if self.verbose:
            print(msg)
        return msg

    def run(self, patient: Patient) -> DischargeReport:
        """
        Execute all 6 agent steps and return a complete DischargeReport.
        """
        report = DischargeReport(
            patient_id=patient.patient_id,
            timestamp=datetime.now().isoformat(),
            step_results={},
        )

        if self.verbose:
            print(f"\n{'='*70}")
            print(f"  🏥 READMISSION RISK AGENT — Patient: {patient.patient_id}")
            print(f"{'='*70}")

        # ── STEP 1: ASSESS ─────────────────────────────────────────────────
        log_msg = self._log(1, f"Assessing patient '{patient.patient_id}' — "
                               f"Dx: {patient.primary_diagnosis} | "
                               f"LOS: {patient.length_of_stay_days}d | "
                               f"Age: {patient.age}")
        report.agent_log.append(log_msg)
        report.step_results["assess"] = {
            "patient_id": patient.patient_id,
            "diagnosis": patient.primary_diagnosis,
            "age": patient.age,
            "comorbidity_count": len(patient.comorbidities),
            "medication_count": len(patient.medications),
        }

        # ── STEP 2: SCORE ──────────────────────────────────────────────────
        lace = compute_lace_score(patient)
        hospital = compute_hospital_score(patient)
        composite_level, composite_prob = compute_composite_risk(lace, hospital)

        report.lace_score = lace
        report.hospital_score = hospital
        report.composite_risk = composite_level
        report.composite_probability = composite_prob

        risk_icon = RISK_COLORS.get(composite_level, "⚪")
        log_msg = self._log(2, f"LACE+={lace.total} ({lace.risk_level.value}), "
                               f"HOSPITAL={hospital.total} ({hospital.risk_level.value}) → "
                               f"Composite: {risk_icon} {composite_level.value} "
                               f"({composite_prob*100:.0f}% 30-day readmission risk)")
        report.agent_log.append(log_msg)
        report.step_results["score"] = {
            "lace_total": lace.total,
            "lace_risk": lace.risk_level.value,
            "hospital_total": hospital.total,
            "hospital_risk": hospital.risk_level.value,
            "composite_risk": composite_level.value,
            "readmission_probability_pct": round(composite_prob * 100, 1),
        }

        # ── STEP 3: BARRIERS ───────────────────────────────────────────────
        high_risk_meds = identify_high_risk_medications(patient.medications)
        barrier_assessment = assess_barriers(patient, high_risk_meds)
        report.barrier_assessment = barrier_assessment

        log_msg = self._log(3, f"{barrier_assessment.total_barrier_count} barriers identified "
                               f"({len(barrier_assessment.social_barriers)} social, "
                               f"{len(barrier_assessment.clinical_barriers)} clinical, "
                               f"{len(high_risk_meds)} high-risk meds)")
        report.agent_log.append(log_msg)
        report.step_results["barriers"] = {
            "social_barrier_count": len(barrier_assessment.social_barriers),
            "clinical_barrier_count": len(barrier_assessment.clinical_barriers),
            "high_risk_med_count": len(high_risk_meds),
            "total_barriers": barrier_assessment.total_barrier_count,
        }

        # ── STEP 4: EVIDENCE ───────────────────────────────────────────────
        if self.verbose:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] 📚 STEP 4: Fetching post-discharge guidelines... ", end="", flush=True)

        evidence = get_evidence_summaries(patient.primary_diagnosis, patient.comorbidities)
        report.evidence_summaries = evidence

        log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] 📚 STEP 4: Retrieved {len(evidence)} evidence-based recommendations for '{patient.primary_diagnosis}'"
        if self.verbose:
            print(f"Retrieved {len(evidence)} guidelines")
        report.agent_log.append(log_msg)
        report.step_results["evidence"] = {"evidence_count": len(evidence)}

        # ── STEP 5: PLAN ────────────────────────────────────────────────────
        discharge_plan = self._generate_discharge_plan(patient, barrier_assessment, composite_level, composite_prob)
        sbar_note = self._generate_sbar(patient, lace, hospital, composite_level, barrier_assessment)
        report.discharge_plan = discharge_plan
        report.sbar_note = sbar_note

        log_msg = self._log(5, f"Generated {len(discharge_plan)}-item discharge plan + SBAR handoff note")
        report.agent_log.append(log_msg)
        report.step_results["plan"] = {"plan_item_count": len(discharge_plan)}

        # ── STEP 6: EDUCATE ─────────────────────────────────────────────────
        instructions = generate_discharge_instructions(
            patient, barrier_assessment, composite_level, high_risk_meds
        )
        report.patient_instructions = instructions

        log_msg = self._log(6, f"Generated personalized discharge instructions "
                               f"({len(instructions.key_activities)} activities, "
                               f"{len(instructions.warning_signs)} warning signs)")
        report.agent_log.append(log_msg)
        report.step_results["educate"] = {
            "activity_count": len(instructions.key_activities),
            "warning_sign_count": len(instructions.warning_signs),
        }

        report.completed = True

        if self.verbose:
            self._print_summary(report)

        return report

    def _generate_discharge_plan(
        self, patient: Patient, barriers, composite_level: RiskLevel, composite_prob: float
    ) -> list:
        """Generate a comprehensive, prioritized discharge plan."""
        plan = []

        # Always include
        plan.append(f"✅ Document composite 30-day readmission risk: {composite_level.value} ({composite_prob*100:.0f}%)")
        plan.append(f"✅ Complete pharmacist medication reconciliation for all {len(patient.medications)} medications")

        # Risk-stratified follow-up timing
        if composite_level == RiskLevel.VERY_HIGH:
            plan.append("🔴 Schedule outpatient follow-up WITHIN 72 HOURS (Very High risk — CMS HRRP flag)")
        elif composite_level == RiskLevel.HIGH:
            plan.append("🟠 Schedule outpatient follow-up WITHIN 7 DAYS (High risk)")
        elif composite_level == RiskLevel.MODERATE:
            plan.append("🟡 Schedule outpatient follow-up within 2 weeks (Moderate risk)")
        else:
            plan.append("🟢 Schedule outpatient follow-up within 4 weeks (Low risk)")

        # Priority interventions from barrier assessment
        for intervention in barriers.priority_interventions[:5]:
            plan.append(intervention)

        # Standard transitions-of-care bundle
        plan.append("📞 Arrange 72-hour post-discharge telephone follow-up call")
        plan.append("📋 Perform teach-back: ask patient to explain their top 3 warning signs in their own words")
        plan.append("💊 Ensure 30-day supply of all critical medications before patient leaves unit")

        if not patient.follow_up_arranged:
            plan.append("⚠️  BEFORE DISCHARGE: Patient does NOT have follow-up scheduled — arrange now")

        return plan

    def _generate_sbar(
        self, patient: Patient, lace, hospital, composite_level: RiskLevel, barriers
    ) -> str:
        """
        Generate a structured SBAR (Situation-Background-Assessment-Recommendation)
        handoff note for the receiving outpatient care team.
        """
        risk_icon = RISK_COLORS.get(composite_level, "⚪")
        comorbidities_str = ", ".join(patient.comorbidities[:4]) if patient.comorbidities else "None documented"
        labs_str = ", ".join(f"{k}={v}" for k, v in list(patient.labs.items())[:4]) if patient.labs else "Not available"
        social_str = ", ".join(b.risk_factor for b in barriers.social_barriers) if barriers.social_barriers else "None identified"

        sbar = f"""
╔══════════════════════════════════════════════════════════════════╗
║              SBAR HANDOFF NOTE — CARE TRANSITIONS               ║
╚══════════════════════════════════════════════════════════════════╝

📌 SITUATION
  Patient {patient.patient_id} ({patient.age}yo {patient.sex}) discharged from {patient.discharge_service}
  after {patient.length_of_stay_days}-day admission for {patient.primary_diagnosis} ({patient.primary_icd10}).

  {risk_icon} 30-DAY READMISSION RISK: {composite_level.value} ({report_probability(composite_level)}%)
    • LACE+ Score: {lace.total}/19 ({lace.risk_level.value})
    • HOSPITAL Score: {hospital.total}/13 ({hospital.risk_level.value})

📌 BACKGROUND
  Comorbidities ({len(patient.comorbidities)}): {comorbidities_str}
  Admission type: {patient.admission_type.upper()}
  Prior ED visits (6 months): {patient.ed_visits_past_6_months}
  Prior admissions (past year): {patient.admissions_past_year}
  Discharge labs: {labs_str}
  Medications at discharge: {len(patient.medications)} (see reconciliation list)

📌 ASSESSMENT
  Social Determinants of Health Barriers: {social_str}
  Clinical Barriers: {len(barriers.clinical_barriers)} identified
  High-Risk Medications: {", ".join(barriers.high_risk_medications[:3]) if barriers.high_risk_medications else "None"}
  Health Literacy: {patient.health_literacy.title()}
  Primary Language: {patient.primary_language}
  Lives Alone: {"Yes" if patient.lives_alone else "No"}
  Follow-Up Arranged at Discharge: {"Yes" if patient.follow_up_arranged else "⚠️  NO"}

📌 RECOMMENDATION
  1. Schedule follow-up appointment {'WITHIN 72H' if composite_level == RiskLevel.VERY_HIGH else 'within 7 days' if composite_level == RiskLevel.HIGH else 'within 2 weeks'}
  2. Review and reconcile all {len(patient.medications)} discharge medications
  3. Assess for signs of clinical deterioration related to {patient.primary_diagnosis}
  4. {'URGENT: Arrange social work support for housing/financial instability' if any(b.domain in ("Housing", "Financial") for b in barriers.social_barriers) else 'Reinforce medication adherence and diet instructions'}
  5. Conduct teach-back to confirm patient understands warning signs

  Readmission Risk Agent — Generated: automated discharge analysis
  Evidence basis: LACE+ (PMID 20713753), HOSPITAL Score (PMID 24167211)
"""
        return sbar.strip()


def report_probability(risk_level: RiskLevel) -> str:
    prob_map = {
        RiskLevel.LOW: "~5",
        RiskLevel.MODERATE: "~12",
        RiskLevel.HIGH: "~22",
        RiskLevel.VERY_HIGH: "~35",
    }
    return prob_map.get(risk_level, "unknown")


class ReportPrinter:
    """Formats and prints DischargeReport to the console."""

    @staticmethod
    def print(report: DischargeReport):
        if not report.completed:
            print("⚠️  Report incomplete")
            return

        risk_icon = RISK_COLORS.get(report.composite_risk, "⚪")

        print(f"\n{'='*70}")
        print(f"  DISCHARGE REPORT — Patient {report.patient_id}")
        print(f"{'='*70}\n")

        # Scores
        print("📊 READMISSION RISK SCORES")
        print(f"  LACE+ Index:     {report.lace_score.total:>3}/19  → {report.lace_score.risk_level.value}")
        print(f"    L (LOS):        {report.lace_score.l_score:>3}")
        print(f"    A (Acuity):     {report.lace_score.a_score:>3}")
        print(f"    C (CCI={report.lace_score.cci_raw}):  {report.lace_score.c_score:>3}")
        print(f"    E (ED visits):  {report.lace_score.e_score:>3}")
        print(f"  HOSPITAL Score:  {report.hospital_score.total:>3}/13  → {report.hospital_score.risk_level.value}")
        print(f"\n  {risk_icon} COMPOSITE RISK: {report.composite_risk.value}")
        print(f"  📈 30-Day Readmission Probability: {report.composite_probability*100:.0f}%\n")

        # Barriers
        print("🚧 IDENTIFIED BARRIERS")
        if report.barrier_assessment:
            for b in report.barrier_assessment.social_barriers:
                print(f"  🔸 [Social] {b.risk_factor}: {b.intervention[:60]}...")
            for cb in report.barrier_assessment.clinical_barriers:
                print(f"  {cb}")
            if report.barrier_assessment.high_risk_medications:
                print(f"  💊 High-Risk Meds: {', '.join(report.barrier_assessment.high_risk_medications[:4])}")
        print()

        # Discharge Plan
        print("📋 DISCHARGE PLAN")
        for item in report.discharge_plan:
            print(f"  {item}")
        print()

        # Evidence
        print("📚 EVIDENCE-BASED GUIDELINES")
        for i, ev in enumerate(report.evidence_summaries[:3], 1):
            print(f"  [{i}] {ev[:100]}...")
        print()

        # Patient Instructions
        if report.patient_instructions:
            inst = report.patient_instructions
            print("🎓 PATIENT DISCHARGE INSTRUCTIONS")
            print(f"  📝 Plain Language Summary:")
            print(f"     {inst.plain_language_summary}")
            print(f"\n  ⚠️  Warning Signs — Return to ED if:")
            for ws in inst.warning_signs[:4]:
                print(f"     • {ws}")
            print(f"\n  📅 Follow-Up: {inst.follow_up_timeline}")
        print()

        # SBAR
        if report.sbar_note:
            print("SBAR HANDOFF NOTE:")
            print(report.sbar_note)

        print(f"\n{'='*70}")
        print(f"  ✅ Analysis complete — {len(report.agent_log)} steps executed")
        print(f"{'='*70}\n")
