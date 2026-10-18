import pytest

from readmit import Encounter, charlson_index, hospital, lace
from readmit.scores import hospital_admission_points, lace_comorbidity_points, lace_length_points


@pytest.mark.parametrize("los,pts", [(0, 0), (0.9, 0), (1, 1), (2, 2), (3, 3), (4, 4), (6, 4),
                                     (7, 5), (13, 5), (14, 7), (40, 7)])
def test_lace_length_table(los, pts):
    assert lace_length_points(los) == pts


@pytest.mark.parametrize("cci,pts", [(0, 0), (1, 1), (2, 2), (3, 3), (4, 5), (9, 5)])
def test_lace_comorbidity_table(cci, pts):
    assert lace_comorbidity_points(cci) == pts


@pytest.mark.parametrize("n,pts", [(0, 0), (1, 0), (2, 2), (5, 2), (6, 5)])
def test_hospital_admissions_table(n, pts):
    assert hospital_admission_points(n) == pts


def test_charlson_hierarchy_counts_severe_only():
    assert charlson_index(["diabetes_uncomplicated", "diabetes_end_organ_damage"]) == 2
    assert charlson_index(["any_tumor", "metastatic_solid_tumor"]) == 6
    assert charlson_index(["mild_liver_disease", "moderate_severe_liver_disease"]) == 3


def test_charlson_rejects_unknown_category():
    with pytest.raises(ValueError):
        charlson_index(["ckd"])


def test_lace_ed_visits_capped_at_4():
    e = Encounter("x", 50, los_days=1, emergent_admission=False, ed_visits_6mo=9)
    assert lace(e).E == 4


def test_hospital_strict_thresholds():
    e = Encounter("x", 50, los_days=5, emergent_admission=True, hemoglobin=12.0, sodium=135)
    h = hospital(e)
    assert (h.H, h.S, h.L, h.I) == (0, 0, 2, 1)


def test_hospital_requires_labs():
    with pytest.raises(ValueError):
        hospital(Encounter("x", 50, los_days=2, emergent_admission=True))
