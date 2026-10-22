"""Discharge summary -> Encounter fields.

`extract_rules` is a regex/keyword baseline with a simple NegEx-style negation
window. `extract_llm` asks a model for each field together with the exact text
that supports it; values without verifiable evidence are discarded and left
unset (so they show up as "not assessed" rather than being guessed).
"""
from __future__ import annotations

import re
from datetime import date
from typing import Dict, List, Optional, Tuple

from .llm import is_grounded, parse_json
from .scores import CHARLSON_WEIGHTS

CHARLSON_TERMS: Dict[str, List[str]] = {
    "myocardial_infarction": [r"myocardial infarction", r"\bn?stemi\b", r"\b(prior|old|history of) mi\b"],
    "congestive_heart_failure": [r"heart failure", r"\bchf\b", r"\bhfref\b", r"\bhfpef\b"],
    "peripheral_vascular_disease": [r"peripheral (vascular|arterial) disease", r"aortic aneurysm"],
    "cerebrovascular_disease": [r"\bstroke\b", r"\bcva\b", r"\btia\b", r"cerebrovascular"],
    "dementia": [r"dementia", r"alzheimer"],
    "chronic_pulmonary_disease": [r"\bcopd\b", r"chronic obstructive", r"\basthma\b", r"emphysema",
                                  r"pulmonary fibrosis"],
    "connective_tissue_disease": [r"rheumatoid arthritis", r"\blupus\b", r"\bsle\b", r"scleroderma",
                                  r"polymyositis"],
    "peptic_ulcer_disease": [r"peptic ulcer", r"(gastric|duodenal) ulcer"],
    "mild_liver_disease": [r"chronic hepatitis", r"hepatitis [bc]\b", r"cirrhosis"],
    "moderate_severe_liver_disease": [r"portal hypertension", r"esophageal varices", r"hepatic encephalopathy"],
    "diabetes_uncomplicated": [r"diabetes", r"\bt2dm\b", r"\bdm2?\b"],
    "diabetes_end_organ_damage": [r"diabetic (nephropathy|retinopathy|neuropathy)",
                                  r"diabetes with [a-z ]*complications"],
    "hemiplegia": [r"hemiplegia", r"paraplegia", r"hemiparesis"],
    "moderate_severe_renal_disease": [r"ckd (stage )?(4|5|iv|v)\b", r"\besrd\b", r"end[- ]stage (renal|kidney)",
                                      r"hemodialysis|\bon dialysis\b"],
    "any_tumor": [r"\bcancer\b", r"carcinoma", r"malignancy"],
    "leukemia": [r"leuka?emia"],
    "lymphoma": [r"lymphoma"],
    "metastatic_solid_tumor": [r"metastatic", r"metastases"],
    "aids": [r"\baids\b"],
}
NEGATION = re.compile(r"\b(no|denies|without|negative for|ruled out|no history of)\b[^.;:\n]{0,40}$")

SDOH_FIELDS = ["lives_alone", "no_pcp", "housing_instability", "transportation_barrier",
               "medication_cost_barrier", "limited_health_literacy", "needs_interpreter"]
FIELDS = ["age", "admission_date", "discharge_date", "los_days", "emergent_admission", "ed_visits_6mo",
          "admissions_12mo", "hemoglobin", "sodium", "had_procedure", "oncology_discharge"] + SDOH_FIELDS
SDOH_TERMS = {
    "lives_alone": r"\blives alone\b",
    "no_pcp": r"\bno (pcp|primary care)",
    "housing_instability": r"\b(homeless|housing insecurity|unstably housed|shelter)\b",
    "transportation_barrier": r"\b(no|lacks|without) (transportation|transport|car|ride)\b",
    "medication_cost_barrier": r"(cannot|can't|unable to) afford",
    "needs_interpreter": r"\binterpreter\b",
}


def _num(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text, re.IGNORECASE)
    return float(m.group(1)) if m else None


def charlson_from_text(text: str) -> List[str]:
    found = set()
    low = text.lower()
    for cat, patterns in CHARLSON_TERMS.items():
        for p in patterns:
            for m in re.finditer(p, low):
                if not NEGATION.search(low[max(0, m.start() - 60):m.start()]):
                    found.add(cat)
    # Keyword overlap: a metastatic or hematologic cancer is not also "any tumor" by these words alone
    if "metastatic_solid_tumor" in found or "leukemia" in found or "lymphoma" in found:
        found.discard("any_tumor")
    return sorted(found)


def extract_rules(text: str) -> Tuple[dict, List[str]]:
    """Return (fields, charlson_categories). Missing fields are omitted."""
    f: dict = {}
    age = _num(r"\b(\d{1,3})[- ](?:year|yo\b|y/o)", text) or _num(r"\bage:?\s*(\d{1,3})\b", text)
    if age is not None:
        f["age"] = int(age)
    adm = re.search(r"admission date:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
    dis = re.search(r"discharge date:?\s*(\d{4}-\d{2}-\d{2})", text, re.I)
    if adm and dis:
        f["los_days"] = (date.fromisoformat(dis.group(1)) - date.fromisoformat(adm.group(1))).days
    if re.search(r"emergency department|\bvia (the )?ed\b|presented to the ed|emergent|urgent admission", text, re.I):
        f["emergent_admission"] = True
    elif re.search(r"elective", text, re.I):
        f["emergent_admission"] = False
    ed = _num(r"(\d+)\s+(?:ed|emergency department) visits", text)
    if ed is not None:
        f["ed_visits_6mo"] = int(ed)
    adm12 = _num(r"(\d+)\s+(?:prior |previous )?(?:hospital )?admissions", text)
    if adm12 is not None:
        f["admissions_12mo"] = int(adm12)
    hb = _num(r"(?:hemoglobin|hgb|hb)\b[^0-9\n]{0,15}(\d+(?:\.\d+)?)", text)
    if hb is not None:
        f["hemoglobin"] = hb
    na = _num(r"(?:sodium|\bna\b)[^0-9\n]{0,15}(\d{3})", text)
    if na is not None:
        f["sodium"] = na
    proc = re.search(r"^\s*procedures?(?: performed)?:\s*(.+)$", text, re.I | re.M)
    if proc:
        f["had_procedure"] = not proc.group(1).strip().lower().startswith("none")
    for k, pat in SDOH_TERMS.items():
        if re.search(pat, text, re.I):
            f[k] = True
    f["oncology_discharge"] = bool(re.search(r"(discharging )?service:?\s*(hematology/)?oncology", text, re.I))
    return f, charlson_from_text(text)


LLM_SYSTEM = """You read a hospital discharge summary and extract readmission-risk inputs.
Return ONLY a JSON object with two keys:
"fields": an object whose keys are a subset of
  age (int), los_days (number, discharge date minus admission date in days),
  emergent_admission (bool: true if urgent/emergent e.g. via the ED; false if elective),
  ed_visits_6mo (int, ED visits in the 6 months BEFORE this admission),
  admissions_12mo (int, hospital admissions in the 12 months BEFORE this admission),
  hemoglobin (number, g/dL, the value AT DISCHARGE), sodium (number, mmol/L, AT DISCHARGE),
  had_procedure (bool), oncology_discharge (bool: discharged from an oncology service),
  and these social barriers, ONLY when explicitly stated (true if present, false if explicitly absent):
  lives_alone, no_pcp, housing_instability, transportation_barrier, medication_cost_barrier,
  limited_health_literacy, needs_interpreter
  and each value is {"value": ..., "evidence": "<exact substring of the summary>"}.
  Omit any field the summary does not state. Do not guess.
"charlson": a list of {"category": <one of CATEGORIES>, "evidence": "<exact substring>"}
  for each comorbidity the patient HAS (ignore negated or ruled-out conditions).
  Choose the most severe applicable category (e.g. diabetes with end-organ damage
  rather than uncomplicated diabetes).
CATEGORIES: """ + ", ".join(sorted(CHARLSON_WEIGHTS))


def extract_llm(text: str, client) -> Tuple[dict, List[str]]:
    data = parse_json(client.complete(LLM_SYSTEM, text), dict)
    fields: dict = {}
    for k, v in (data.get("fields") or {}).items():
        if k in FIELDS and isinstance(v, dict) and "value" in v and is_grounded(v.get("evidence"), text):
            fields[k] = v["value"]
    cats = sorted({c["category"] for c in data.get("charlson") or []
                   if isinstance(c, dict) and c.get("category") in CHARLSON_WEIGHTS
                   and is_grounded(c.get("evidence"), text)})
    return fields, cats

# Extraction fallback: if section detection fails (no recognisable headers),
# the full note text is treated as the Assessment section. This preserves
# recall at the cost of potential false positives from history mentions.
