# readmission-risk-agent

[![CI](https://github.com/ai-summer2025/readmission-risk-agent/actions/workflows/ci.yml/badge.svg)](https://github.com/ai-summer2025/readmission-risk-agent/actions/workflows/ci.yml)
![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

30-day readmission risk at discharge, computed with two validated scores (**LACE** and **HOSPITAL**) and turned into a transition-of-care checklist. Inputs can be structured JSON or a free-text discharge summary; an optional LLM step extracts the inputs from the summary and must quote the text behind every value.

> **Decision support only.** Not a medical device. The scores are population-level risk indicators, not individual predictions. All bundled data is synthetic.

## How it works

```
 discharge summary ──► extraction ──────────► Encounter ──► LACE + HOSPITAL ──► tier ──► transition plan
                       regex/keyword baseline     ▲           (published point        + barriers   (Project RED / BOOST
                       or LLM + grounding check   │            tables, audited                       actions)
 encounter JSON ──────────────────────────────────┘            per component)
```

- **Scores are computed from the published point tables**, and every component is shown, so a clinician can check the arithmetic.
- **The LLM only extracts.** It returns each value with an exact quote from the note. Values without a verifiable quote are dropped and appear as *not assessed*; they are never guessed.
- **Missing data is visible.** Utilization counts that are not documented are shown as explicit assumptions in the report; unassessed social barriers are listed.

## Scores

| Score | Components | Source |
|---|---|---|
| LACE (0-19) | **L**ength of stay (0-7 pts), **A**cute/emergent admission (3), **C**harlson index (0-5), **E**D visits in prior 6 months (0-4) | van Walraven et al., *CMAJ* 2010;182(6):551-557 |
| HOSPITAL (0-13) | discharge **H**emoglobin < 12 (1), **O**ncology discharge (2), **S**odium < 135 (1), **P**rocedure (1), **I**ndex admission urgent (1), prior-year **A**dmissions (0/2/5), **L**ength of stay ≥ 5 days (2) | Donzé et al., *JAMA Intern Med* 2013;173(8):632-638 |
| Charlson index | 19 categories, original weights, with severity hierarchy (e.g. metastatic tumor supersedes any tumor) | Charlson et al., *J Chronic Dis* 1987;40(5):373-383 |

Tiers: LACE ≥ 10 high, 5-9 moderate; HOSPITAL ≥ 7 high, 5-6 intermediate. The overall tier is the higher of the two.

## Quickstart

```bash
pip install -e .
readmit check data/encounters/hf_high_risk.json
readmit note data/notes/discharge_summary.txt              # regex baseline
readmit note data/notes/discharge_summary.txt --llm        # LLM extraction (see below)
docker build -t readmit . && docker run --rm readmit
```

Example (abridged):

```
**Overall tier: HIGH**

| Score    | Components                                 | Total   | Tier |
| LACE     | L 5 + A 3 + C 5 (Charlson 5) + E 2         | 15 / 19 | high |
| HOSPITAL | H 1 + O 0 + S 1 + P 0 + I 1 + A 2 + L 2    | 7 / 13  | high |

**Barriers identified:** Lives alone
- Before discharge: Book the follow-up appointment before the patient leaves (within 7 days). (RED)
- After discharge: Phone call within 2-3 days of discharge to review medications and the plan. (RED)
```

LLM configuration (no SDK dependency; use a local model for real patient data):

```bash
export ANTHROPIC_API_KEY=...                       # or:
export LLM_PROVIDER=openai LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=llama3.1
```

## Evaluation

`python eval/run_eval.py` regenerates [`eval/RESULTS.md`](eval/RESULTS.md); CI fails on regression.

**Score implementation:** 8 encounters scored by hand from the published tables, chosen to hit boundaries (LOS 4/5/14 days, Hb exactly 12.0, Na exactly 135, 1 vs 2 vs 6 prior admissions, Charlson hierarchies). All 16 scores match on every component.

**Extraction:** 6 synthetic discharge summaries with gold inputs.

| Method | Field accuracy | Charlson precision | Charlson recall | LACE total exact | HOSPITAL total exact |
|---|---|---|---|---|---|
| Regex baseline | 0.94 | 0.93 | 1.00 | 0.83 | 0.83 |
| LLM + grounding | run `python eval/run_eval.py --llm` | | | | |

The baseline's errors are the instructive ones: it takes **admission** labs when the score needs **discharge** labs, counts "myocardial infarction was ruled out" as a history of MI, and misses "admitted through the ED". These are the cases the LLM prompt targets. The LLM row is left for you to run with your own credentials rather than reporting numbers not produced here.

## Limitations

- Scores were validated in specific populations (Ontario medical/surgical patients for LACE; US/international medical patients for HOSPITAL). Calibration in your population is unknown.
- Charlson mapping from free text is keyword- or LLM-based, not from coded ICD-10 diagnoses.
- No outcome data is included, so discrimination (AUROC) is not measured here. See the roadmap.

## Roadmap

- Fit and compare a model on MIMIC-IV (credentialed access) against LACE and HOSPITAL: AUROC, calibration, subgroup fairness
- Accept FHIR R4 `Encounter`, `Condition` and `Observation` resources; Charlson from ICD-10 codes (Quan 2005 coding algorithm)
- Report LLM extraction results for a hosted and a local model

## Project history

Replaces the earlier prototype in this repository and the empty `discharge-readmission-agent`. The prototype's scoring had errors that changed results: LOS points were `min(days, 7)` instead of the LACE table, Charlson 1-2 mapped to 0 LACE points, and the HOSPITAL score included an invented "active malignancy" item, used the wrong prior-admission thresholds and LOS cut-off, and cited the wrong journal. All are corrected and covered by boundary tests. See [CHANGELOG.md](CHANGELOG.md).

## License

MIT. See [LICENSE](LICENSE).

---

## ❓ FAQ

**Q: The LACE score and HOSPITAL score disagree — which do I trust?**  
A: Report both. LACE weighs acuity and ED visits; HOSPITAL weighs lab values and service type. High on either warrants follow-up; high on both is your highest-risk cohort.

**Q: How do I handle patients with no prior admission history?**  
A: Prior admissions default to 0. This scores conservatively (no penalty, no bonus). The SDOH screen still runs and may flag social risk independently.

**Q: Can I adjust the high-risk threshold?**  
A: Yes — set `LACE_HIGH_THRESHOLD` and `HOSPITAL_HIGH_THRESHOLD` in `src/readmit/scores.py` to match your institution's calibration.
