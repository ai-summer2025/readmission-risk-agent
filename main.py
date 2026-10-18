#!/usr/bin/env python3
"""
readmission-risk-agent — CLI Entry Point

Autonomous 6-step hospital discharge planning and 30-day readmission risk assessment agent.

Usage:
  python main.py                         # Run all 4 sample patients
  python main.py --patient PT-001        # Run specific patient from sample data
  python main.py --list                  # List available sample patients
  python main.py --json --patient PT-001 # Output JSON report

Problem:
  3.8 million preventable hospital readmissions per year cost CMS $17 billion.
  Under the Hospital Readmissions Reduction Program (HRRP), hospitals face penalties
  up to 3% of Medicare base payments. Yet discharge planning remains fragmented —
  nurses spend 45–90 minutes per patient, SDOH screening is inconsistent, and
  patient instructions are generic. This agent automates the full workflow.

References:
  - LACE+ Index: van Walraven et al., CMAJ 2010 (PMID 20713753)
  - HOSPITAL Score: Donzé et al., J Hosp Med 2013 (PMID 24167211)
  - Charlson Index: Charlson et al., J Chronic Dis 1987 (PMID 3558716)
  - CMS HRRP: https://www.cms.gov/medicare/quality/hospital/readmissions-reduction-program
"""
import argparse
import json
import sys
import os

# Ensure package is importable from project root
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.models import Patient
from src.agent import ReadmissionRiskAgent, ReportPrinter


SAMPLE_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "sample_patients.json")


def load_patients(path: str = SAMPLE_DATA_PATH) -> list:
    """Load patient data from JSON file."""
    try:
        with open(path, "r") as f:
            raw = json.load(f)
        patients = []
        for p in raw:
            patients.append(Patient(**p))
        return patients
    except FileNotFoundError:
        print(f"❌ Sample data not found at: {path}", file=sys.stderr)
        sys.exit(1)
    except (json.JSONDecodeError, TypeError) as e:
        print(f"❌ Error parsing patient data: {e}", file=sys.stderr)
        sys.exit(1)


def report_to_dict(report) -> dict:
    """Convert a DischargeReport to a JSON-serializable dict."""
    result = {
        "patient_id": report.patient_id,
        "timestamp": report.timestamp,
        "completed": report.completed,
        "risk_assessment": {
            "lace_score": {
                "total": report.lace_score.total,
                "l": report.lace_score.l_score,
                "a": report.lace_score.a_score,
                "c": report.lace_score.c_score,
                "e": report.lace_score.e_score,
                "cci_raw": report.lace_score.cci_raw,
                "risk_level": report.lace_score.risk_level.value,
                "readmission_probability": report.lace_score.readmission_probability,
            },
            "hospital_score": {
                "total": report.hospital_score.total,
                "h_hemoglobin": report.hospital_score.h_hemoglobin,
                "o_oncology": report.hospital_score.o_oncology,
                "s_sodium": report.hospital_score.s_sodium,
                "p_procedure": report.hospital_score.p_procedure,
                "i_index": report.hospital_score.i_index,
                "t_admissions": report.hospital_score.t_admissions,
                "a_malignancy": report.hospital_score.a_malignancy,
                "l_los": report.hospital_score.l_los,
                "risk_level": report.hospital_score.risk_level.value,
                "readmission_probability": report.hospital_score.readmission_probability,
            },
            "composite_risk": report.composite_risk.value,
            "composite_probability_pct": round(report.composite_probability * 100, 1),
        },
        "barriers": {
            "social": [
                {
                    "domain": b.domain,
                    "risk_factor": b.risk_factor,
                    "severity": b.severity,
                    "intervention": b.intervention,
                }
                for b in (report.barrier_assessment.social_barriers if report.barrier_assessment else [])
            ],
            "clinical": report.barrier_assessment.clinical_barriers if report.barrier_assessment else [],
            "high_risk_medications": report.barrier_assessment.high_risk_medications if report.barrier_assessment else [],
            "priority_interventions": report.barrier_assessment.priority_interventions if report.barrier_assessment else [],
        },
        "evidence_summaries": report.evidence_summaries,
        "discharge_plan": report.discharge_plan,
        "sbar_note": report.sbar_note,
        "patient_instructions": {
            "condition": report.patient_instructions.condition,
            "key_activities": report.patient_instructions.key_activities,
            "dietary_restrictions": report.patient_instructions.dietary_restrictions,
            "medication_reminders": report.patient_instructions.medication_reminders,
            "warning_signs": report.patient_instructions.warning_signs,
            "follow_up_timeline": report.patient_instructions.follow_up_timeline,
            "plain_language_summary": report.patient_instructions.plain_language_summary,
        } if report.patient_instructions else None,
    }
    return result


def main():
    parser = argparse.ArgumentParser(
        description="🏥 Readmission Risk Agent — Autonomous Discharge Planning & Risk Assessment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                          # Run all 4 sample patients
  python main.py --patient PT-001         # Run only PT-001
  python main.py --patient PT-003 --json  # Output JSON for PT-003
  python main.py --list                   # Show available patients

The agent computes:
  • LACE+ Index (validated 30-day readmission predictor)
  • HOSPITAL Score (avoidable readmission predictor)
  • Social determinants of health barriers
  • Personalized discharge plan + SBAR handoff note
  • Patient-specific discharge instructions
        """,
    )
    parser.add_argument("--patient", metavar="PATIENT_ID", help="Run for a specific patient ID")
    parser.add_argument("--data", metavar="PATH", default=SAMPLE_DATA_PATH, help="Path to patient JSON data file")
    parser.add_argument("--list", action="store_true", help="List available sample patients")
    parser.add_argument("--json", action="store_true", help="Output report as JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress verbose agent output")

    args = parser.parse_args()

    patients = load_patients(args.data)

    if args.list:
        print("\n📋 Available Sample Patients:")
        for p in patients:
            print(f"  {p.patient_id:10s} | Age {p.age:3d} | {p.sex} | {p.primary_diagnosis}")
        print()
        return

    # Filter to specific patient if requested
    if args.patient:
        patients = [p for p in patients if p.patient_id == args.patient]
        if not patients:
            print(f"❌ Patient '{args.patient}' not found. Use --list to see available patients.", file=sys.stderr)
            sys.exit(1)

    # Run agent
    agent = ReadmissionRiskAgent(verbose=not args.quiet)
    all_reports = []

    for patient in patients:
        report = agent.run(patient)
        all_reports.append(report)

        if args.json and not args.quiet:
            print("\n📄 JSON REPORT:")
            print(json.dumps(report_to_dict(report), indent=2))

        if len(patients) > 1:
            print(f"\n{'─'*70}\n")

    # Summary when running all patients
    if len(all_reports) > 1 and not args.json:
        print(f"\n{'='*70}")
        print("  📊 BATCH SUMMARY — All Patients")
        print(f"{'='*70}")
        for r in all_reports:
            risk_icons = {
                "LOW": "🟢", "MODERATE": "🟡", "HIGH": "🟠", "VERY_HIGH": "🔴"
            }
            icon = risk_icons.get(r.composite_risk.value, "⚪")
            print(f"  {r.patient_id:10s} | {icon} {r.composite_risk.value:12s} | "
                  f"{r.composite_probability*100:.0f}% 30-day risk | "
                  f"{r.barrier_assessment.total_barrier_count if r.barrier_assessment else 0} barriers")
        print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
