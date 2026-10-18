"""
Evidence Retrieval Module

Fetches condition-specific post-discharge care guidelines from PubMed
using the free NCBI E-utilities API (no API key required).

Falls back to a curated evidence cache for the most common readmission diagnoses
when network is unavailable.

Free API: https://eutils.ncbi.nlm.nih.gov/entrez/eutils/
"""
import urllib.request
import urllib.error
import urllib.parse
import json
import re
from typing import List, Optional


# Curated evidence cache for common readmission diagnoses
# Sources: CMS, ACC/AHA, GOLD, Joint Commission guidelines
EVIDENCE_CACHE = {
    "heart failure": [
        "AHA/ACC 2022: Outpatient follow-up within 7 days of discharge reduces 30-day readmission by 20-25%. Titrate GDMT (ACEi/ARB/ARNI, beta-blocker, MRA, SGLT2i) before discharge. Daily weights and 2g sodium restriction are standard.",
        "CMS HRRP: Heart failure readmissions carry the highest Medicare penalty weight. Key interventions: discharge checklist, patient education on symptom monitoring, structured telephone follow-up.",
        "JAMA 2020 (PMID 32232421): Transitional care programs with nurse-led phone follow-up within 72h reduce heart failure readmissions by 30%.",
    ],
    "pneumonia": [
        "IDSA/ATS 2019 guidelines: Patients should complete antibiotic course at home. Follow-up chest X-ray at 4-6 weeks recommended in patients >40 years to rule out underlying malignancy.",
        "PMID 26680058: Early (<30 day) follow-up after pneumonia hospitalization associated with 21% reduction in 30-day readmission.",
        "Medicare data: Antibiotic adherence education at discharge significantly reduces readmission. Ensure patient understands when to return for worsening dyspnea or fever.",
    ],
    "copd": [
        "GOLD 2023: Pulmonologist follow-up within 4 weeks after AECOPD hospitalization reduces readmission by 35%. Inhaler technique education is critical — >50% of patients use inhalers incorrectly.",
        "PMID 34049985: Pulmonary rehabilitation referral post-AECOPD reduces readmission by 28% at 90 days. Action plan for exacerbations must be reviewed.",
        "AHRQ evidence: Oxygen therapy prescription (if SpO2 <88%), smoking cessation support, and influenza/pneumococcal vaccination reduce COPD readmissions.",
    ],
    "sepsis": [
        "SSC 2021 Guidelines: Post-sepsis syndrome affects 40% of survivors. Follow-up within 2 weeks. Screen for PTSD, cognitive impairment, and new organ dysfunction.",
        "PMID 29716605: Sepsis survivors have 3x higher 30-day readmission rate. Primary reasons: new infections (42%), incomplete source control, and functional decline.",
        "Surviving Sepsis Campaign: Antibiotic stewardship at discharge — document duration and indication. Culture follow-up for organism-specific de-escalation.",
    ],
    "myocardial infarction": [
        "ACC/AHA 2022 STEMI Guidelines: Cardiac rehab referral at discharge reduces mortality 20-26%. All post-MI patients should be on aspirin, statin, beta-blocker, ACEi/ARB.",
        "PMID 23643595: Telephone follow-up within 3 days of MI discharge reduces 30-day readmission. Ensure INR monitoring if on anticoagulation.",
        "CMS: Post-MI patients require follow-up cardiologist visit within 7-14 days. Education on activity restrictions, nitroglycerin use, and chest pain return precautions.",
    ],
    "stroke": [
        "AHA/ASA 2021: Post-stroke follow-up with neurology within 2 weeks. Antithrombotic therapy adherence education is critical — stopping anticoagulation is the #1 modifiable readmission factor.",
        "PMID 24842639: 30-day readmission after stroke: 14% nationally. Key drivers: pneumonia, UTI, falls, and recurrent stroke. Swallowing assessment before discharge critical.",
        "Joint Commission Stroke Program: Blood pressure control is the most important post-stroke intervention. Target <130/80 mmHg.",
    ],
    "diabetes": [
        "ADA 2024 Standards: Glycemic targets during hospitalization 140-180 mg/dL for most patients. Comprehensive diabetes self-management education (DSMES) before discharge.",
        "PMID 30425194: Diabetes-related readmissions driven by hypoglycemia, hyperglycemia, and infection. Ensure glucose monitoring instructions are in plain language.",
        "AHRQ: Insulin-dependent patients require demonstration of correct injection technique and glucose monitoring before discharge to reduce 30-day readmissions.",
    ],
    "default": [
        "AHRQ Transitions of Care: Universal readmission reduction bundle includes: medication reconciliation, teach-back education, warm handoff to outpatient provider, and 72-hour phone follow-up.",
        "CMS Partnership for Patients: Evidence-based care transitions programs (RED, BOOST, Bridge) consistently reduce 30-day readmissions by 15-30% across diagnoses.",
        "Joint Commission NPSG: Effective medication management at transitions and patient/family engagement in discharge planning are the strongest cross-diagnosis readmission prevention strategies.",
    ],
}

# Condition keyword mapping to cache keys
CONDITION_KEYWORDS = {
    "heart failure": ["heart failure", "chf", "cardiac failure", "hf with reduced", "hfref", "hfpef", "systolic dysfunction"],
    "pneumonia": ["pneumonia", "cap", "hospital-acquired pneumonia", "hap", "respiratory infection"],
    "copd": ["copd", "chronic obstructive", "emphysema", "bronchitis", "aecopd"],
    "sepsis": ["sepsis", "septicemia", "bacteremia", "septic shock"],
    "myocardial infarction": ["myocardial infarction", "stemi", "nstemi", "acute mi", "heart attack", "acs", "acute coronary"],
    "stroke": ["stroke", "cva", "cerebrovascular", "tia", "ischemic stroke", "hemorrhagic stroke"],
    "diabetes": ["diabetes", "diabetic", "hyperglycemia", "hypoglycemia", "dka"],
}


def match_condition_to_evidence_key(diagnosis: str) -> str:
    """Map a free-text diagnosis to a cached evidence key."""
    diag_lower = diagnosis.lower()
    for condition_key, keywords in CONDITION_KEYWORDS.items():
        for kw in keywords:
            if kw in diag_lower:
                return condition_key
    return "default"


def fetch_pubmed_abstracts(query: str, max_results: int = 2) -> List[str]:
    """
    Query PubMed NCBI E-utilities for relevant abstracts.
    Uses free API, no key required.
    Rate limited to 3 requests/second without key.
    """
    try:
        # Step 1: esearch — get PMIDs
        search_params = urllib.parse.urlencode({
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "sort": "relevance",
            "retmode": "json",
            "tool": "readmission-risk-agent",
            "email": "open-source@readmission-risk-agent.io",
        })
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?{search_params}"

        req = urllib.request.Request(search_url, headers={"User-Agent": "readmission-risk-agent/1.0"})
        with urllib.request.urlopen(req, timeout=8) as resp:
            search_data = json.loads(resp.read().decode())

        pmids = search_data.get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        # Step 2: efetch — get summaries
        fetch_params = urllib.parse.urlencode({
            "db": "pubmed",
            "id": ",".join(pmids[:max_results]),
            "rettype": "abstract",
            "retmode": "json",
            "tool": "readmission-risk-agent",
            "email": "open-source@readmission-risk-agent.io",
        })
        fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?{fetch_params}"

        req2 = urllib.request.Request(fetch_url, headers={"User-Agent": "readmission-risk-agent/1.0"})
        with urllib.request.urlopen(req2, timeout=8) as resp2:
            raw = resp2.read().decode()

        # Parse out key sentences from the raw text
        summaries = []
        # Find lines with meaningful content
        lines = [ln.strip() for ln in raw.split("\n") if ln.strip() and len(ln.strip()) > 60]
        abstract_text = " ".join(lines[:8])

        # Extract first sentence that looks like a finding
        sentences = re.split(r'(?<=[.!?])\s+', abstract_text)
        relevant = [s for s in sentences if any(kw in s.lower() for kw in
                    ["readmi", "discharg", "follow", "transition", "outcome", "reduc", "prevent", "risk"])]

        for s in relevant[:2]:
            summaries.append(f"PubMed: {s[:300]}")

        return summaries if summaries else []

    except Exception:
        return []  # Silent fallback — will use cache


def get_evidence_summaries(diagnosis: str, comorbidities: list) -> List[str]:
    """
    Retrieve 3 evidence-based recommendations for this patient's conditions.
    Tries live PubMed API first; falls back to curated cache on any failure.
    """
    condition_key = match_condition_to_evidence_key(diagnosis)
    summaries = []

    # Try PubMed for the primary diagnosis
    search_query = f"30-day readmission prevention {diagnosis} discharge planning systematic review[pt]"
    live_results = fetch_pubmed_abstracts(search_query, max_results=1)
    summaries.extend(live_results)

    # Always include curated cache evidence (more reliable for structured guidance)
    cache_entries = EVIDENCE_CACHE.get(condition_key, EVIDENCE_CACHE["default"])
    for entry in cache_entries[:2]:
        summaries.append(f"Clinical guideline: {entry}")

    # Add general transitions-of-care evidence if we have fewer than 3
    if len(summaries) < 3:
        summaries.append(
            "Clinical guideline: " + EVIDENCE_CACHE["default"][0]
        )

    return summaries[:4]  # Return top 4 evidence points
