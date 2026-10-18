"""
Test suite for Readmission Risk Agent

Tests covering:
1. LACE+ Score computation
2. HOSPITAL Score computation
3. Charlson Comorbidity Index
4. Composite risk calculation
5. Barrier assessment (social + clinical)
6. Discharge instruction generation
7. Full end-to-end pipeline (all 4 sample patients)
"""
import unittest
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import Patient, RiskLevel
from src.scoring import (
    compute_charlson_index,
    cci_to_lace_c_score,
    compute_lace_score,
    compute_hospital_score,
    compute_composite_risk,
    identify_high_risk_medications,
)
from src.barriers import (
    screen_social_determinants,
    identify_clinical_barriers,
    assess_barriers,
)
from src.instructions import (
    get_condition_key,
    generate_discharge_instructions,
)
from src.agent import ReadmissionRiskAgent


# ─────────────────────────────────────────────────────────────
# Fixture helpers
# ─────────────────────────────────────────────────────────────

def make_patient(**overrides) -> Patient:
    """Create a baseline test patient with optional overrides."""
    defaults = dict(
        patient_id="TEST-001",
        age=65,
        sex="M",
        primary_diagnosis="Heart Failure",
        primary_icd10="I50.9",
        comorbidities=["Congestive Heart Failure", "Type 2 Diabetes", "Hypertension"],
        admission_type="emergent",
        length_of_stay_days=5,
        ed_visits_past_6_months=2,
        admissions_past_year=3,
        discharge_service="cardiology",
        had_procedure=False,
        active_malignancy=False,
        labs={"hemoglobin": 11.5, "sodium": 133, "creatinine": 1.4},
        medications=["Furosemide 40mg", "Carvedilol 12.5mg", "Warfarin 5mg"],
        insurance="Medicare",
        lives_alone=False,
        housing_stable=True,
        transportation=True,
        health_literacy="moderate",
        primary_language="English",
        follow_up_arranged=True,
        notes=None,
    )
    defaults.update(overrides)
    return Patient(**defaults)


# ─────────────────────────────────────────────────────────────
# GROUP 1: Charlson Comorbidity Index
# ─────────────────────────────────────────────────────────────
class TestCharlsonIndex(unittest.TestCase):

    def test_no_comorbidities(self):
        cci = compute_charlson_index([])
        self.assertEqual(cci, 0)

    def test_single_weight_1(self):
        cci = compute_charlson_index(["Congestive Heart Failure"])
        self.assertEqual(cci, 1)

    def test_multiple_weight_1(self):
        cci = compute_charlson_index([
            "Myocardial Infarction",
            "Congestive Heart Failure",
            "Chronic Pulmonary Disease",
        ])
        self.assertEqual(cci, 3)

    def test_weight_2_conditions(self):
        cci = compute_charlson_index([
            "Chronic Kidney Disease",
            "Cancer",
        ])
        self.assertEqual(cci, 4)

    def test_weight_6_metastatic(self):
        cci = compute_charlson_index(["Metastatic Solid Tumor"])
        self.assertEqual(cci, 6)

    def test_cci_to_lace_c_score_zero(self):
        self.assertEqual(cci_to_lace_c_score(0), 0)

    def test_cci_to_lace_c_score_low(self):
        self.assertEqual(cci_to_lace_c_score(2), 0)

    def test_cci_to_lace_c_score_moderate(self):
        self.assertEqual(cci_to_lace_c_score(4), 1)

    def test_cci_to_lace_c_score_high(self):
        self.assertEqual(cci_to_lace_c_score(7), 5)


# ─────────────────────────────────────────────────────────────
# GROUP 2: LACE+ Score
# ─────────────────────────────────────────────────────────────
class TestLACEScore(unittest.TestCase):

    def test_low_risk_elective(self):
        p = make_patient(
            admission_type="elective",
            length_of_stay_days=1,
            ed_visits_past_6_months=0,
            comorbidities=[],
        )
        lace = compute_lace_score(p)
        self.assertEqual(lace.l_score, 1)
        self.assertEqual(lace.a_score, 0)
        self.assertEqual(lace.risk_level, RiskLevel.LOW)

    def test_high_risk_emergent(self):
        p = make_patient(
            admission_type="emergent",
            length_of_stay_days=8,  # capped at 7
            ed_visits_past_6_months=4,
            comorbidities=["Congestive Heart Failure", "Chronic Kidney Disease", "Peripheral Vascular Disease"],
        )
        lace = compute_lace_score(p)
        self.assertEqual(lace.l_score, 7)   # capped at 7
        self.assertEqual(lace.a_score, 3)   # emergent
        self.assertEqual(lace.e_score, 4)   # capped at 4
        self.assertGreaterEqual(lace.total, 10)
        self.assertIn(lace.risk_level, (RiskLevel.HIGH, RiskLevel.VERY_HIGH))

    def test_los_cap_at_7(self):
        p = make_patient(length_of_stay_days=20)
        lace = compute_lace_score(p)
        self.assertEqual(lace.l_score, 7)

    def test_ed_visits_cap_at_4(self):
        p = make_patient(ed_visits_past_6_months=10)
        lace = compute_lace_score(p)
        self.assertEqual(lace.e_score, 4)

    def test_emergent_acuity_score(self):
        p_emerg = make_patient(admission_type="emergent")
        p_elect = make_patient(admission_type="elective")
        lace_emerg = compute_lace_score(p_emerg)
        lace_elect = compute_lace_score(p_elect)
        self.assertEqual(lace_emerg.a_score, 3)
        self.assertEqual(lace_elect.a_score, 0)

    def test_urgent_same_as_emergent(self):
        p = make_patient(admission_type="urgent")
        lace = compute_lace_score(p)
        self.assertEqual(lace.a_score, 3)

    def test_risk_levels_ordered(self):
        """Risk levels should increase with higher LACE scores."""
        low_p = make_patient(admission_type="elective", length_of_stay_days=1,
                              ed_visits_past_6_months=0, comorbidities=[])
        high_p = make_patient(admission_type="emergent", length_of_stay_days=10,
                               ed_visits_past_6_months=4,
                               comorbidities=["CHF", "CKD", "Diabetes with complications",
                                              "Peripheral Vascular Disease"])
        low_lace = compute_lace_score(low_p)
        high_lace = compute_lace_score(high_p)
        self.assertLess(low_lace.total, high_lace.total)

    def test_probability_set(self):
        p = make_patient()
        lace = compute_lace_score(p)
        self.assertGreater(lace.readmission_probability, 0)
        self.assertLessEqual(lace.readmission_probability, 1)


# ─────────────────────────────────────────────────────────────
# GROUP 3: HOSPITAL Score
# ─────────────────────────────────────────────────────────────
class TestHOSPITALScore(unittest.TestCase):

    def test_low_score_normal_labs(self):
        p = make_patient(
            labs={"hemoglobin": 14.0, "sodium": 140},
            had_procedure=False,
            active_malignancy=False,
            admissions_past_year=1,
            admission_type="elective",
            length_of_stay_days=3,
            discharge_service="medicine",
        )
        h = compute_hospital_score(p)
        self.assertEqual(h.o_oncology, 0)
        self.assertEqual(h.a_malignancy, 0)
        self.assertLessEqual(h.total, 4)
        self.assertEqual(h.risk_level, RiskLevel.LOW)

    def test_hemoglobin_below_threshold(self):
        p = make_patient(labs={"hemoglobin": 11.0, "sodium": 140})
        h = compute_hospital_score(p)
        self.assertEqual(h.h_hemoglobin, 1)

    def test_sodium_below_threshold(self):
        p = make_patient(labs={"hemoglobin": 14, "sodium": 130})
        h = compute_hospital_score(p)
        self.assertEqual(h.s_sodium, 1)

    def test_oncology_service(self):
        p = make_patient(discharge_service="oncology")
        h = compute_hospital_score(p)
        self.assertEqual(h.o_oncology, 2)

    def test_active_malignancy(self):
        p = make_patient(active_malignancy=True)
        h = compute_hospital_score(p)
        self.assertEqual(h.a_malignancy, 2)

    def test_high_admissions(self):
        p = make_patient(admissions_past_year=6)
        h = compute_hospital_score(p)
        self.assertEqual(h.t_admissions, 2)

    def test_long_los(self):
        p = make_patient(length_of_stay_days=7)
        h = compute_hospital_score(p)
        self.assertEqual(h.l_los, 2)

    def test_had_procedure(self):
        p = make_patient(had_procedure=True)
        h = compute_hospital_score(p)
        self.assertEqual(h.p_procedure, 1)

    def test_high_risk_patient(self):
        p = make_patient(
            labs={"hemoglobin": 9.0, "sodium": 128},
            active_malignancy=True,
            admissions_past_year=7,
            length_of_stay_days=8,
            discharge_service="oncology",
            had_procedure=True,
            admission_type="emergent",
        )
        h = compute_hospital_score(p)
        self.assertGreaterEqual(h.total, 7)
        self.assertEqual(h.risk_level, RiskLevel.HIGH)


# ─────────────────────────────────────────────────────────────
# GROUP 4: Composite Risk
# ─────────────────────────────────────────────────────────────
class TestCompositeRisk(unittest.TestCase):

    def test_composite_takes_max_level(self):
        p = make_patient(
            admission_type="emergent",
            length_of_stay_days=10,
            ed_visits_past_6_months=4,
            comorbidities=["Congestive Heart Failure", "Chronic Kidney Disease",
                           "Cancer", "Peripheral Vascular Disease"],
        )
        lace = compute_lace_score(p)
        hospital = compute_hospital_score(p)
        composite_level, composite_prob = compute_composite_risk(lace, hospital)
        self.assertIsInstance(composite_level, RiskLevel)
        self.assertGreater(composite_prob, 0)
        self.assertLessEqual(composite_prob, 1)

    def test_composite_probability_between_0_and_1(self):
        p = make_patient()
        lace = compute_lace_score(p)
        hospital = compute_hospital_score(p)
        _, prob = compute_composite_risk(lace, hospital)
        self.assertGreater(prob, 0)
        self.assertLessEqual(prob, 1)

    def test_high_risk_patient_not_low(self):
        p = make_patient(
            admission_type="emergent",
            length_of_stay_days=10,
            ed_visits_past_6_months=4,
            comorbidities=["Congestive Heart Failure", "Chronic Kidney Disease",
                           "Cancer", "Peripheral Vascular Disease", "Stroke"],
        )
        lace = compute_lace_score(p)
        hospital = compute_hospital_score(p)
        composite_level, _ = compute_composite_risk(lace, hospital)
        self.assertNotEqual(composite_level, RiskLevel.LOW)


# ─────────────────────────────────────────────────────────────
# GROUP 5: Barrier Assessment
# ─────────────────────────────────────────────────────────────
class TestBarrierAssessment(unittest.TestCase):

    def test_no_barriers_clean_patient(self):
        p = make_patient(
            lives_alone=False,
            housing_stable=True,
            transportation=True,
            health_literacy="high",
            primary_language="English",
            insurance="commercial",
            follow_up_arranged=True,
            labs={"hemoglobin": 14, "sodium": 140, "creatinine": 0.9},
            medications=["Aspirin 81mg", "Lisinopril 10mg"],
        )
        social_barriers = screen_social_determinants(p)
        self.assertEqual(len(social_barriers), 0)

    def test_all_social_barriers_present(self):
        p = make_patient(
            lives_alone=True,
            housing_stable=False,
            transportation=False,
            health_literacy="low",
            primary_language="Spanish",
            insurance="none",
        )
        social_barriers = screen_social_determinants(p)
        domains = [b.domain for b in social_barriers]
        self.assertIn("Housing", domains)
        self.assertIn("Transportation", domains)
        self.assertIn("Social Support", domains)
        self.assertIn("Health Literacy", domains)
        self.assertIn("Language", domains)
        self.assertIn("Financial", domains)
        self.assertGreaterEqual(len(social_barriers), 5)

    def test_no_follow_up_is_clinical_barrier(self):
        p = make_patient(follow_up_arranged=False)
        clinical_barriers = identify_clinical_barriers(p)
        self.assertTrue(any("follow-up" in cb.lower() or "follow up" in cb.lower()
                            for cb in clinical_barriers))

    def test_severe_anemia_is_clinical_barrier(self):
        p = make_patient(labs={"hemoglobin": 6.5, "sodium": 140})
        clinical_barriers = identify_clinical_barriers(p)
        self.assertTrue(any("anemia" in cb.lower() or "hgb" in cb.lower()
                            for cb in clinical_barriers))

    def test_high_risk_meds_identified(self):
        meds = ["Warfarin 5mg daily", "Atorvastatin 40mg", "Lisinopril 10mg", "Insulin glargine 20u"]
        found = identify_high_risk_medications(meds)
        hrm_names = [m.lower() for m in found]
        self.assertTrue(any("warfarin" in m for m in hrm_names))
        self.assertTrue(any("insulin" in m for m in hrm_names))

    def test_priority_interventions_generated(self):
        p = make_patient(
            lives_alone=True,
            housing_stable=False,
            transportation=False,
            follow_up_arranged=False,
        )
        assessment = assess_barriers(p, ["Warfarin 5mg", "Insulin glargine"])
        self.assertGreater(len(assessment.priority_interventions), 0)

    def test_polypharmacy_flagged(self):
        many_meds = [f"Med{i} 10mg" for i in range(12)]
        p = make_patient(medications=many_meds, follow_up_arranged=True,
                         labs={"hemoglobin": 13, "sodium": 138})
        clinical = identify_clinical_barriers(p)
        self.assertTrue(any("polypharmacy" in c.lower() or "medic" in c.lower()
                            for c in clinical))


# ─────────────────────────────────────────────────────────────
# GROUP 6: Discharge Instructions
# ─────────────────────────────────────────────────────────────
class TestDischargeInstructions(unittest.TestCase):

    def test_condition_key_heart_failure(self):
        self.assertEqual(get_condition_key("Acute Decompensated Heart Failure"), "heart failure")
        self.assertEqual(get_condition_key("CHF exacerbation"), "heart failure")

    def test_condition_key_copd(self):
        self.assertEqual(get_condition_key("COPD exacerbation"), "copd")
        self.assertEqual(get_condition_key("Exacerbation of Emphysema"), "copd")

    def test_condition_key_pneumonia(self):
        self.assertEqual(get_condition_key("Community-Acquired Pneumonia"), "pneumonia")

    def test_condition_key_diabetes(self):
        self.assertEqual(get_condition_key("Diabetic Ketoacidosis"), "diabetes")

    def test_condition_key_default_for_unknown(self):
        self.assertEqual(get_condition_key("Appendicitis"), "default")

    def test_instructions_generated(self):
        p = make_patient(primary_diagnosis="Heart Failure")
        from src.barriers import assess_barriers
        from src.scoring import compute_lace_score, compute_hospital_score, compute_composite_risk, identify_high_risk_medications
        lace = compute_lace_score(p)
        hospital = compute_hospital_score(p)
        composite_level, _ = compute_composite_risk(lace, hospital)
        hrm = identify_high_risk_medications(p.medications)
        barriers = assess_barriers(p, hrm)
        instructions = generate_discharge_instructions(p, barriers, composite_level, hrm)
        self.assertIsNotNone(instructions)
        self.assertGreater(len(instructions.key_activities), 0)
        self.assertGreater(len(instructions.warning_signs), 0)
        self.assertTrue(len(instructions.plain_language_summary) > 20)

    def test_low_health_literacy_adds_extra_instructions(self):
        p_low = make_patient(health_literacy="low", primary_diagnosis="Heart Failure")
        p_high = make_patient(health_literacy="high", primary_diagnosis="Heart Failure")
        from src.barriers import assess_barriers
        from src.scoring import compute_lace_score, compute_hospital_score, compute_composite_risk, identify_high_risk_medications
        for p in (p_low, p_high):
            lace = compute_lace_score(p)
            hospital = compute_hospital_score(p)
            composite_level, _ = compute_composite_risk(lace, hospital)
            hrm = identify_high_risk_medications(p.medications)
            barriers = assess_barriers(p, hrm)
        instr_low = generate_discharge_instructions(p_low, barriers, composite_level, hrm)
        instr_high = generate_discharge_instructions(p_high, barriers, composite_level, hrm)
        # Low literacy should have call-to-action items
        low_text = " ".join(instr_low.key_activities).lower()
        self.assertTrue("call" in low_text or "family" in low_text or "schedule" in low_text)

    def test_high_risk_medication_reminder_included(self):
        p = make_patient(medications=["Warfarin 5mg daily", "Furosemide 40mg daily"])
        from src.barriers import assess_barriers
        from src.scoring import compute_lace_score, compute_hospital_score, compute_composite_risk, identify_high_risk_medications
        lace = compute_lace_score(p)
        hospital = compute_hospital_score(p)
        composite_level, _ = compute_composite_risk(lace, hospital)
        hrm = identify_high_risk_medications(p.medications)
        barriers = assess_barriers(p, hrm)
        instructions = generate_discharge_instructions(p, barriers, composite_level, hrm)
        reminders_text = " ".join(instructions.medication_reminders).upper()
        self.assertTrue("WARFARIN" in reminders_text or "INR" in reminders_text)


# ─────────────────────────────────────────────────────────────
# GROUP 7: End-to-End Agent Pipeline
# ─────────────────────────────────────────────────────────────
class TestAgentPipeline(unittest.TestCase):

    def _load_sample_patients(self):
        data_path = os.path.join(os.path.dirname(__file__), "data", "sample_patients.json")
        with open(data_path) as f:
            raw = json.load(f)
        return [Patient(**p) for p in raw]

    def test_pipeline_completes_single_patient(self):
        p = make_patient()
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(p)
        self.assertTrue(report.completed)
        self.assertIsNotNone(report.lace_score)
        self.assertIsNotNone(report.hospital_score)
        self.assertIsNotNone(report.composite_risk)
        self.assertIsNotNone(report.barrier_assessment)
        self.assertIsNotNone(report.patient_instructions)
        self.assertGreater(len(report.discharge_plan), 0)
        self.assertIsNotNone(report.sbar_note)
        self.assertGreater(len(report.agent_log), 0)

    def test_pipeline_all_sample_patients(self):
        """Run the full 6-step pipeline on all 4 sample patients."""
        patients = self._load_sample_patients()
        self.assertEqual(len(patients), 4)
        agent = ReadmissionRiskAgent(verbose=False)
        for p in patients:
            with self.subTest(patient_id=p.patient_id):
                report = agent.run(p)
                self.assertTrue(report.completed, f"Report not completed for {p.patient_id}")
                self.assertIsInstance(report.composite_risk, RiskLevel)
                self.assertGreater(report.composite_probability, 0)

    def test_pt001_high_risk(self):
        """PT-001 (heart failure, many barriers) should be high or very high risk."""
        patients = self._load_sample_patients()
        pt001 = next(p for p in patients if p.patient_id == "PT-001")
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(pt001)
        self.assertIn(report.composite_risk, (RiskLevel.HIGH, RiskLevel.VERY_HIGH))

    def test_pt002_lower_risk(self):
        """PT-002 (pneumonia, few comorbidities) should be lower risk than PT-001."""
        patients = self._load_sample_patients()
        pt001 = next(p for p in patients if p.patient_id == "PT-001")
        pt002 = next(p for p in patients if p.patient_id == "PT-002")
        agent = ReadmissionRiskAgent(verbose=False)
        report1 = agent.run(pt001)
        report2 = agent.run(pt002)
        # PT-001 probability should be higher than PT-002
        self.assertGreater(report1.composite_probability, report2.composite_probability)

    def test_sbar_note_contains_key_fields(self):
        p = make_patient()
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(p)
        sbar = report.sbar_note
        self.assertIn("SITUATION", sbar)
        self.assertIn("BACKGROUND", sbar)
        self.assertIn("ASSESSMENT", sbar)
        self.assertIn("RECOMMENDATION", sbar)

    def test_step_results_all_present(self):
        p = make_patient()
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(p)
        expected_steps = {"assess", "score", "barriers", "evidence", "plan", "educate"}
        self.assertEqual(expected_steps, set(report.step_results.keys()))

    def test_report_has_evidence_summaries(self):
        p = make_patient()
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(p)
        self.assertGreater(len(report.evidence_summaries), 0)

    def test_pt003_high_sdoh_barriers(self):
        """PT-003 (DKA, housing instability, no follow-up, Medicaid) has many SDOH barriers."""
        patients = self._load_sample_patients()
        pt003 = next(p for p in patients if p.patient_id == "PT-003")
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(pt003)
        self.assertGreaterEqual(
            len(report.barrier_assessment.social_barriers), 3,
            "PT-003 should have ≥3 social barriers (housing, transport, language, financial)"
        )

    def test_very_high_risk_adds_72h_followup(self):
        """Very high risk patients should have 72-hour follow-up in the plan."""
        p = make_patient(
            admission_type="emergent",
            length_of_stay_days=10,
            ed_visits_past_6_months=4,
            comorbidities=[
                "Congestive Heart Failure", "Chronic Kidney Disease", "Cancer",
                "Peripheral Vascular Disease", "Stroke", "Diabetes with complications"
            ],
        )
        agent = ReadmissionRiskAgent(verbose=False)
        report = agent.run(p)
        if report.composite_risk == RiskLevel.VERY_HIGH:
            plan_text = " ".join(report.discharge_plan).upper()
            self.assertTrue("72" in plan_text or "VERY HIGH" in plan_text)


if __name__ == "__main__":
    import unittest
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(__import__("__main__"))
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
