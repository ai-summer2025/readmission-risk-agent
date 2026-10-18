# readmission-risk-agent

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)]()
[![Healthcare AI](https://img.shields.io/badge/Healthcare-AI-red.svg)]()

> **Autonomous 6-step agentic AI for hospital discharge planning and 30-day readmission risk assessment.**  
> Zero API keys. Zero cost. Pure Python. Built on validated clinical scoring tools.

---

## 🏥 The Problem

**3.8 million preventable hospital readmissions per year cost CMS $17 billion.** Under the Hospital Readmissions Reduction Program (HRRP), hospitals face financial penalties up to **3% of all Medicare base payments** for excess readmissions in heart failure, pneumonia, COPD, hip/knee replacement, CABG, and STEMI.

Yet discharge planning is still done *manually*:

- Nurses spend **45–90 minutes per patient** assembling information from multiple systems
- Social determinants of health (SDOH) screening is **inconsistent** — housing instability and medication cost barriers are routinely missed
- Patient instructions are **generic** — not tailored to literacy level, language, or specific risk factors
- No single tool combines risk scoring + barrier identification + care planning in one workflow

The result: **1 in 5 Medicare patients** returns to the hospital within 30 days of discharge, often for preventable reasons.

---

## 🤖 How It Works: The 6-Step Agentic Loop

```
Patient Data
     │
     ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 1 ── 🔍 ASSESS                                    │
│    Parse + validate: diagnosis, comorbidities, labs,    │
│    length of stay, ED history, medications              │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 2 ── 📊 SCORE                                     │
│    LACE+ Index (0-19) — van Walraven CMAJ 2010         │
│    HOSPITAL Score (0-13) — Donzé J Hosp Med 2013       │
│    Charlson Comorbidity Index (CCI)                     │
│    → Composite 30-day readmission risk: 5–35%          │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 3 ── 🚧 BARRIERS                                  │
│    Social determinants: housing, transport, literacy,   │
│    language, financial, social isolation                │
│    Clinical barriers: abnormal labs, no follow-up,     │
│    polypharmacy, high-risk medications (ISMP list)      │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 4 ── 📚 EVIDENCE                                  │
│    PubMed NCBI API (free, no key) — retrieves current  │
│    condition-specific post-discharge guidelines         │
│    + curated evidence cache (ACC/AHA, GOLD, SSC, ADA)  │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 5 ── 📋 PLAN                                      │
│    Risk-stratified discharge plan (72h vs 7d vs 2w)    │
│    Prioritized intervention list (🔴🟠🟡 flagged)      │
│    SBAR handoff note for receiving outpatient team      │
└──────────────────────────┬──────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────┐
│  STEP 6 ── 🎓 EDUCATE                                   │
│    Personalized patient instructions (literacy-adapted) │
│    Condition-specific warning signs ("Return to ED if") │
│    Medication reminders (high-alert drug education)     │
│    Plain-language discharge summary                     │
└─────────────────────────────────────────────────────────┘
```

---

## 🧮 Validated Scoring Tools

| Score | Reference | Predicts | Range |
|-------|-----------|----------|-------|
| **LACE+ Index** | van Walraven et al., CMAJ 2010 (PMID 20713753) | 30-day readmission | 0–19 |
| **HOSPITAL Score** | Donzé et al., J Hosp Med 2013 (PMID 24167211) | Potentially avoidable readmission | 0–13 |
| **Charlson Index** | Charlson et al., J Chronic Dis 1987 (PMID 3558716) | Comorbidity burden | 0–37 |

### Risk Stratification

| Risk Level | LACE+ | HOSPITAL | 30-Day Readmission |
|------------|-------|----------|-------------------|
| 🟢 LOW | 0–4 | 0–4 | ~5% |
| 🟡 MODERATE | 5–9 | 5–6 | ~12% |
| 🟠 HIGH | 10–14 | 7+ | ~22% |
| 🔴 VERY HIGH | 15+ | — | ~35% |

---

## 🚀 Installation

```bash
git clone https://github.com/ai-summer2025/readmission-risk-agent.git
cd readmission-risk-agent
pip install -r requirements.txt
```

**No API keys required.** The agent uses:
- PubMed NCBI E-utilities (free, public)
- Python standard library only (urllib, json, dataclasses)

---

## 💻 Usage

```bash
# Run all 4 included sample patients
python main.py

# Run a specific patient
python main.py --patient PT-001

# List available sample patients
python main.py --list

# Output full JSON report
python main.py --patient PT-001 --json

# Quiet mode (suppress step-by-step logs)
python main.py --patient PT-003 --quiet
```

### Example Output

```
======================================================================
  🏥 READMISSION RISK AGENT — Patient: PT-001
======================================================================
[09:14:02] 🔍 STEP 1: Assessing patient 'PT-001' — Dx: Acute Decompensated Heart Failure | LOS: 6d | Age: 72
[09:14:02] 📊 STEP 2: LACE+=13 (HIGH), HOSPITAL=8 (HIGH) → Composite: 🔴 VERY_HIGH (35% 30-day readmission risk)
[09:14:02] 🚧 STEP 3: 3 barriers identified (1 social, 2 clinical, 3 high-risk meds)
[09:14:03] 📚 STEP 4: Retrieved 3 evidence-based recommendations for 'Acute Decompensated Heart Failure'
[09:14:03] 📋 STEP 5: Generated 8-item discharge plan + SBAR handoff note
[09:14:03] 🎓 STEP 6: Generated personalized discharge instructions (6 activities, 6 warning signs)

📊 READMISSION RISK SCORES
  LACE+ Index:      13/19  → HIGH
  HOSPITAL Score:    8/13  → HIGH

  🔴 COMPOSITE RISK: VERY_HIGH
  📈 30-Day Readmission Probability: 35%
```

### Programmatic API

```python
from src.models import Patient
from src.agent import ReadmissionRiskAgent

patient = Patient(
    patient_id="MY-001",
    age=68,
    sex="F",
    primary_diagnosis="Heart Failure",
    primary_icd10="I50.9",
    comorbidities=["Congestive Heart Failure", "Atrial Fibrillation", "CKD"],
    admission_type="emergent",
    length_of_stay_days=5,
    ed_visits_past_6_months=2,
    admissions_past_year=3,
    discharge_service="cardiology",
    had_procedure=False,
    active_malignancy=False,
    labs={"hemoglobin": 10.5, "sodium": 132},
    medications=["Furosemide 40mg", "Warfarin 5mg", "Carvedilol 12.5mg"],
    insurance="Medicare",
    lives_alone=True,
    housing_stable=True,
    transportation=False,
    health_literacy="low",
    primary_language="English",
    follow_up_arranged=False,
)

agent = ReadmissionRiskAgent(verbose=True)
report = agent.run(patient)

print(f"Risk: {report.composite_risk.value} ({report.composite_probability*100:.0f}%)")
print(f"Barriers: {report.barrier_assessment.total_barrier_count}")
print(report.sbar_note)
```

---

## 📊 What Gets Generated

For each patient, the agent produces:

1. **LACE+ Score** — Length of stay + Acuity + Comorbidity + ED visits → validated readmission predictor
2. **HOSPITAL Score** — 7-factor avoidable readmission risk
3. **Composite Risk Level** — LOW / MODERATE / HIGH / VERY_HIGH with probability estimate
4. **SDOH Barrier Screen** — 6 domains: housing, transportation, social support, health literacy, language, financial
5. **Clinical Barrier Screen** — abnormal labs, missing follow-up, polypharmacy, high-risk medications
6. **Prioritized Discharge Plan** — color-coded (🔴🟠🟡) with risk-stratified follow-up timing
7. **SBAR Handoff Note** — structured Situation-Background-Assessment-Recommendation for care transitions
8. **Personalized Patient Instructions** — literacy-adapted, condition-specific, with plain-language summary
9. **Evidence-Based Guidelines** — PubMed-retrieved + curated clinical guideline summaries

---

## 🧪 Tests

```bash
python -m pytest test_main.py -v
```

**Test groups:**
- Charlson Comorbidity Index (9 tests)
- LACE+ Score (8 tests)
- HOSPITAL Score (9 tests)
- Composite Risk (3 tests)
- Barrier Assessment (7 tests)
- Discharge Instructions (5 tests)
- End-to-End Pipeline (9 tests)

**50 tests total — zero dependencies on external services.**

---

## 💡 Why This Matters

| Metric | Data |
|--------|------|
| Annual US readmissions | 3.8 million |
| Medicare cost | $17 billion/year |
| CMS HRRP hospitals penalized | 2,583 hospitals (FY2024) |
| Average HRRP penalty | $220,000/hospital |
| Avoidable share | ~27% of all readmissions |
| Nurse time per manual discharge | 45–90 minutes |
| SDOH barriers missed without screening | ~60% |

Sources: CMS HRRP FY2024 report, AHRQ Healthcare Cost and Utilization Project, American Hospital Association 2024.

---

## 🗺️ Architecture

```
readmission-risk-agent/
├── main.py                    # CLI entry point
├── src/
│   ├── agent.py               # 6-step orchestrator
│   ├── models.py              # Data models (Patient, Scores, Report)
│   ├── scoring.py             # LACE+, HOSPITAL, Charlson CCI
│   ├── barriers.py            # SDOH + clinical barrier screening
│   ├── evidence.py            # PubMed API + curated cache
│   └── instructions.py        # Patient discharge instructions
├── data/
│   └── sample_patients.json   # 4 realistic test patients
├── test_main.py               # 50 tests, 7 groups
├── requirements.txt
└── README.md
```

---

## 🔄 Extending the Agent

**Add new scoring tools:**
```python
# src/scoring.py — add your own validated score
def compute_lace_index_plus(patient: Patient) -> YourScore:
    ...
```

**Add new SDOH domains:**
```python
# src/barriers.py — extend SDOH_DEFINITIONS dict
SDOH_DEFINITIONS["Food Insecurity"] = {
    "intervention": "Refer to food bank / dietitian",
    "readmission_multiplier": 1.3,
}
```

**Swap in a real EHR connector:**
The `Patient` data class is a clean interface — feed it from FHIR, HL7, or your EHR's API instead of JSON.

---

## 🤝 Contributing

PRs welcome! Areas for contribution:
- Add FHIR R4 patient data ingestion
- Add additional validated scores (SWIFT, 8Ps, LACE-RT)
- Integration with real PubMed full-text retrieval
- Add PDF discharge summary generation
- Benchmark against real readmission datasets

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.

---

## 📚 References

1. van Walraven C et al. "Derivation and validation of an index to predict early death or unplanned readmission after discharge from hospital to the community." *CMAJ* 2010. PMID: 20713753
2. Donzé J et al. "Potentially avoidable 30-day hospital readmissions in medical patients." *J Hosp Med* 2013. PMID: 24167211
3. Charlson ME et al. "A new method of classifying prognostic comorbidity in longitudinal studies." *J Chronic Dis* 1987. PMID: 3558716
4. Centers for Medicare & Medicaid Services. Hospital Readmissions Reduction Program (HRRP) FY2024.
5. Agency for Healthcare Research and Quality (AHRQ). Care Transitions Evidence Review 2023.
