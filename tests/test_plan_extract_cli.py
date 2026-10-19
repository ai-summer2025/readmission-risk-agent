import json
from pathlib import Path

from readmit import Encounter, assess
from readmit.cli import main
from readmit.extract import charlson_from_text, extract_llm, extract_rules

ROOT = Path(__file__).resolve().parents[1]


class FakeClient:
    def __init__(self, reply):
        self.reply = reply

    def complete(self, system, user):
        return self.reply


def test_plan_lists_barriers_and_unassessed_items():
    e = Encounter("x", 80, los_days=8, emergent_admission=True, ed_visits_6mo=3,
                  charlson_categories=["congestive_heart_failure"], hemoglobin=10, sodium=130,
                  lives_alone=True, no_pcp=False)
    a = assess(e)
    assert a.tier == "high"
    assert "Lives alone" in a.barriers
    assert "Housing instability" in a.not_assessed
    assert a.actions[0].priority == 1


def test_missing_labs_still_produces_lace_assessment():
    a = assess(Encounter("x", 60, los_days=2, emergent_admission=False))
    assert a.hospital is None and a.tier == "low"
    assert any("HOSPITAL" in n for n in a.not_assessed)


def test_negation_is_respected():
    assert charlson_from_text("No history of stroke. Denies diabetes.") == []
    assert charlson_from_text("History of stroke and diabetes.") == ["cerebrovascular_disease",
                                                                     "diabetes_uncomplicated"]


def test_rules_extraction_computes_los():
    f, _ = extract_rules("Admission date: 2026-01-01\nDischarge date: 2026-01-05\n70-year-old via the ED")
    assert f["los_days"] == 4 and f["age"] == 70 and f["emergent_admission"] is True


def test_llm_extraction_drops_ungrounded_values():
    note = "Discharge labs: Hgb 8.9, Na 133."
    reply = json.dumps({"fields": {"hemoglobin": {"value": 8.9, "evidence": "Hgb 8.9"},
                                   "sodium": {"value": 140, "evidence": "Na 140"}},
                        "charlson": [{"category": "dementia", "evidence": "dementia"}]})
    fields, cats = extract_llm(note, FakeClient(reply))
    assert fields == {"hemoglobin": 8.9} and cats == []


def test_cli_check_and_note(capsys):
    assert main(["check", str(ROOT / "data/encounters/hf_high_risk.json"), "--format", "json"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["lace"]["total"] == 16 and out["hospital"]["total"] == 7
    assert main(["note", str(ROOT / "data/notes/discharge_summary.txt")]) == 0
    assert "LACE" in capsys.readouterr().out


def test_eval_does_not_regress():
    import subprocess
    import sys
    r = subprocess.run([sys.executable, str(ROOT / "eval/run_eval.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_rules_extraction_finds_explicit_social_barriers():
    f, _ = extract_rules("Social: lives alone, homeless shelter last month. Needs Spanish interpreter.")
    assert f["lives_alone"] and f["housing_instability"] and f["needs_interpreter"]
