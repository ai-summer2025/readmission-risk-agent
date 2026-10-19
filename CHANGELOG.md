# Changelog

## 1.0.0

Rewrite of the prototype as the `readmit` package.

- Fixed LACE: length-of-stay points now follow the published table (0, 1, 2, 3, 4 for 4-6 days, 5 for 7-13, 7 for 14+);
  Charlson-to-LACE conversion fixed (1→1, 2→2, 3→3, ≥4→5)
- Fixed HOSPITAL: removed a non-existent "active malignancy" item; prior-year admissions now 0-1→0, 2-5→2, >5→5;
  length of stay is ≥ 5 days (was > 5); citation corrected to JAMA Intern Med 2013
- Charlson index uses the original 19 categories with severity hierarchies
- Discharge-summary extraction: regex/keyword baseline with negation handling, and an optional LLM extractor
  that must quote evidence for each value (Anthropic or any OpenAI-compatible server)
- Transition plan driven by tier and documented social barriers; unassessed barriers and assumptions are reported
- Evaluation: 8 hand-scored boundary encounters and 6 labeled discharge summaries; CI fails on regression
- GitHub Actions on Python 3.9-3.13, ruff, Dockerfile
