"""
Patient Discharge Instructions Generator

Creates personalized, plain-language discharge instructions based on:
- Primary diagnosis
- Identified risk factors and barriers
- Medication list
- Follow-up arrangements

Follows AHRQ "Five Major Steps to Safer Outpatient Prescribing" and
CMS Meaningful Use criteria for patient-specific discharge documentation.
"""
from typing import List
from .models import Patient, DischargeInstruction, RiskLevel, BarrierAssessment

# Condition-specific instruction templates
CONDITION_INSTRUCTIONS = {
    "heart failure": {
        "key_activities": [
            "Weigh yourself EVERY MORNING before eating — if you gain 2+ pounds in 1 day or 5 pounds in 1 week, call your care team immediately",
            "Limit fluid intake to {fluid_limit} per day (includes soups, ice cream, anything that melts)",
            "Limit sodium (salt) to less than 2,000 mg per day — avoid canned soups, deli meats, fast food",
            "Elevate your legs when sitting to reduce swelling",
            "Take all heart medications EXACTLY as prescribed — do not stop without calling your doctor",
        ],
        "dietary_restrictions": [
            "Low sodium diet: <2,000 mg sodium per day",
            "Fluid restriction: discuss specific limit with your doctor",
            "Avoid alcohol completely",
        ],
        "warning_signs": [
            "Shortness of breath that wakes you up at night",
            "You can no longer walk across a room without stopping to breathe",
            "New or worsening swelling in your legs, ankles, or feet",
            "Weight gain of 2 or more pounds overnight",
            "Dizziness or fainting",
            "Chest pain or pressure",
        ],
        "follow_up_timeline": "URGENT: Cardiology or primary care follow-up within 7 days",
    },
    "pneumonia": {
        "key_activities": [
            "Complete your ENTIRE antibiotic course even if you feel better",
            "Rest and limit activity for the first week",
            "Stay well-hydrated — drink 6-8 glasses of water daily",
            "Use an incentive spirometer (breathing exercise device) if provided: 10 times every hour while awake",
            "Do NOT smoke — smoking significantly slows your lung recovery",
        ],
        "dietary_restrictions": [
            "No specific dietary restrictions",
            "Stay well-hydrated with water, clear broths, and warm liquids",
            "Avoid alcohol — it weakens your immune system",
        ],
        "warning_signs": [
            "Fever returns after being gone for more than 24 hours",
            "You are coughing up blood",
            "Severe difficulty breathing or bluish lips/fingernails",
            "Confusion or difficulty thinking clearly",
            "Chest pain that worsens with breathing",
        ],
        "follow_up_timeline": "Primary care visit within 4-6 weeks (chest X-ray to confirm resolution)",
    },
    "copd": {
        "key_activities": [
            "Use your rescue inhaler (e.g., albuterol) ONLY when needed — if you need it more than 4x/day, call your doctor",
            "Use your controller inhaler (e.g., tiotropium, fluticasone) EVERY DAY as prescribed — even when feeling well",
            "Practice pursed-lip breathing during activities: breathe in through nose for 2 counts, breathe out slowly through pursed lips for 4 counts",
            "Avoid smoke, dust, strong fumes, and air pollution",
            "Get annual flu shot and pneumococcal vaccine",
        ],
        "dietary_restrictions": [
            "Eat smaller, more frequent meals — large meals make breathing harder",
            "Limit carbonated beverages — they cause bloating which presses on the diaphragm",
            "High-protein foods support respiratory muscle strength",
        ],
        "warning_signs": [
            "Increased shortness of breath beyond your normal baseline",
            "Change in color, amount, or thickness of sputum (mucus)",
            "Fever above 101°F (38.3°C)",
            "More coughing than usual",
            "Waking up at night due to breathing problems",
            "Confusion or new sleepiness",
        ],
        "follow_up_timeline": "Pulmonology or primary care within 4 weeks; urgent visit if exacerbation symptoms",
    },
    "diabetes": {
        "key_activities": [
            "Check your blood sugar as instructed: {glucose_frequency}",
            "Take all diabetes medications exactly as prescribed — do NOT skip doses",
            "Eat meals at regular times — skipping meals can cause dangerous low blood sugar",
            "Check your feet DAILY for cuts, sores, redness, or swelling — wear shoes at all times",
            "Stay hydrated — drink plenty of water, avoid sugary drinks",
        ],
        "dietary_restrictions": [
            "Consistent carbohydrate diet: aim for 45-60g carbohydrates per meal",
            "Limit sugary drinks (juice, soda, sports drinks)",
            "Avoid high-glycemic index foods: white bread, potatoes, white rice",
            "Eat regular meals — do not skip",
        ],
        "warning_signs": [
            "Blood sugar below 70 mg/dL (shaking, sweating, confusion, fast heartbeat)",
            "Blood sugar above 300 mg/dL despite taking medications",
            "Nausea, vomiting, or stomach pain",
            "Fruity-smelling breath or increased urination",
            "Wound or sore that is not healing",
            "Signs of infection: fever, redness, warmth, swelling",
        ],
        "follow_up_timeline": "Primary care or endocrinology within 1-2 weeks for glucose management review",
    },
    "default": {
        "key_activities": [
            "Take all prescribed medications exactly as directed",
            "Attend ALL follow-up appointments",
            "Rest and gradually increase your activity level as tolerated",
            "Stay well-hydrated unless told to restrict fluids",
            "Keep track of any new or worsening symptoms",
        ],
        "dietary_restrictions": [
            "Follow any specific diet instructions given by your care team",
            "Eat balanced meals to support healing",
        ],
        "warning_signs": [
            "Fever above 101°F (38.3°C)",
            "Severe or worsening pain",
            "Difficulty breathing",
            "Confusion or difficulty thinking clearly",
            "Symptoms that are getting significantly worse",
        ],
        "follow_up_timeline": "Primary care follow-up within 1-2 weeks",
    },
}

def get_condition_key(diagnosis: str) -> str:
    """Map diagnosis to instruction template key."""
    diag_lower = diagnosis.lower()
    if any(k in diag_lower for k in ["heart failure", "chf", "hfpef", "hfref"]):
        return "heart failure"
    if any(k in diag_lower for k in ["pneumonia", "respiratory infection"]):
        return "pneumonia"
    if any(k in diag_lower for k in ["copd", "emphysema", "bronchitis"]):
        return "copd"
    if any(k in diag_lower for k in ["diabetes", "diabetic", "hyperglycemia"]):
        return "diabetes"
    return "default"


def generate_medication_reminders(medications: List[str], high_risk_meds: List[str]) -> List[str]:
    """Generate personalized medication reminders."""
    reminders = []

    if not medications:
        return ["Take all prescribed medications as directed by your care team"]

    # Generic reminder
    reminders.append(f"You are being discharged with {len(medications)} medications — fill all prescriptions before leaving or on the way home")

    # High-risk medication specifics
    for med in high_risk_meds[:3]:
        med_lower = med.lower()
        if "warfarin" in med_lower or "coumadin" in med_lower:
            reminders.append(f"⚠️  WARFARIN: Do NOT change your dose without calling your doctor. Get your INR (blood test) checked on schedule. Avoid sudden changes in green leafy vegetables.")
        elif "insulin" in med_lower:
            reminders.append(f"⚠️  INSULIN: Store properly (refrigerate if unopened). Do not skip doses. Always carry fast-acting sugar (juice, glucose tablets) in case of low blood sugar.")
        elif any(x in med_lower for x in ["morphine", "oxycodone", "hydrocodone", "fentanyl", "tramadol"]):
            reminders.append(f"⚠️  OPIOID PAIN MEDICATION: Take ONLY as prescribed. Do not drive. Do not drink alcohol. Take stool softener to prevent constipation.")
        elif "furosemide" in med_lower or "lasix" in med_lower:
            reminders.append(f"⚠️  DIURETIC: Take in the morning. Monitor for dizziness when standing. Eat foods with potassium (banana, orange, potato).")

    return reminders


def generate_discharge_instructions(
    patient: Patient,
    barrier_assessment: BarrierAssessment,
    composite_risk: RiskLevel,
    high_risk_meds: List[str],
) -> DischargeInstruction:
    """
    Generate comprehensive, personalized discharge instructions.
    Adjusts complexity based on health literacy level.
    """
    condition_key = get_condition_key(patient.primary_diagnosis)
    template = CONDITION_INSTRUCTIONS.get(condition_key, CONDITION_INSTRUCTIONS["default"])

    # Build key activities (personalized)
    activities = list(template["key_activities"])

    # Adapt for health literacy
    if patient.health_literacy.lower() == "low":
        activities.insert(0, "📞 Call your doctor's office today to schedule your follow-up visit")
        activities.insert(1, "📋 Ask a family member or friend to help you understand these instructions")

    # Add risk-specific activities
    if composite_risk in (RiskLevel.HIGH, RiskLevel.VERY_HIGH):
        activities.append("📞 Your care team will call you within 48-72 hours to check on you — make sure your phone number is correct")

    # Build medication reminders
    med_reminders = generate_medication_reminders(patient.medications, high_risk_meds)

    # Determine follow-up timeline
    follow_up = template["follow_up_timeline"]
    if composite_risk == RiskLevel.VERY_HIGH:
        follow_up = follow_up.replace("within", "URGENT: within")

    # Build plain language summary
    risk_word = {
        RiskLevel.LOW: "low",
        RiskLevel.MODERATE: "moderate",
        RiskLevel.HIGH: "high",
        RiskLevel.VERY_HIGH: "high",
    }.get(composite_risk, "unknown")

    lang_note = ""
    if patient.primary_language.lower() not in ("english", "en"):
        lang_note = f"Note: Patient's primary language is {patient.primary_language}. Provide interpreter and translated materials."

    plain_summary = (
        f"You were treated for {patient.primary_diagnosis}. "
        f"Based on your health history, your risk of needing to come back to the hospital within 30 days is {risk_word}. "
        f"The most important things you can do: (1) take all your medications as prescribed, "
        f"(2) attend your follow-up appointment, and (3) return to the emergency room right away "
        f"if your symptoms get worse. {lang_note}"
    )

    return DischargeInstruction(
        condition=patient.primary_diagnosis,
        key_activities=activities[:6],  # Keep concise
        dietary_restrictions=template["dietary_restrictions"],
        medication_reminders=med_reminders,
        warning_signs=template["warning_signs"],
        follow_up_timeline=follow_up,
        plain_language_summary=plain_summary,
    )
