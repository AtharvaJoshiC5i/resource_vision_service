from datetime import date

from rv_availability import engine as e
from rv_availability.staffing.launch_filters import (
    employee_matches_launch_filters,
    filters_from_launch_payload,
    launch_filters_empty,
)
from rv_availability import views as v


def _emp(**kw) -> e.Employee:
    defaults = dict(
        key="E1",
        code="E001",
        name="Test",
        name_source="pt",
        hr_matched=True,
        dates_valid=True,
        joining=date(2020, 1, 1),
        exit=None,
        employee_status="Active",
        primary_capability="Data Science",
        secondary_capability="Analytics",
        grade="L5",
        country="India",
        location="Bangalore",
        division="Eng",
        department="Engineering",
        email=None,
        manager_name=None,
        manager_code=None,
        employment_type="FTE",
    )
    defaults.update(kw)
    return e.Employee(**defaults)


def test_launch_filters_empty():
    assert launch_filters_empty(filters_from_launch_payload({}))
    assert launch_filters_empty(filters_from_launch_payload({"department": []}))
    assert not launch_filters_empty(filters_from_launch_payload({"grade": ["E1"]}))


def test_filters_from_launch_strips_empty():
    f = filters_from_launch_payload(
        {
            "primary_capability": ["  Data Science  ", ""],
            "department": ["Engineering"],
        }
    )
    assert f.capabilities == {"Data Science"}
    assert f.departments == {"Engineering"}


def test_case_insensitive_capability_match():
    snap = e.Snapshot(
        today=date(2026, 11, 1),
        window=[202611],
        months_with_data={202611},
        rows=[],
        employees={"E1": _emp()},
        employee_months={},
        projects={},
        data_quality={},
    )
    f = filters_from_launch_payload({"primary_capability": ["data science"]})
    assert employee_matches_launch_filters(snap, _emp(), f)


def test_all_dimensions_and():
    snap = e.Snapshot(
        today=date(2026, 11, 1),
        window=[202611],
        months_with_data={202611},
        rows=[],
        employees={"E1": _emp()},
        employee_months={},
        projects={},
        data_quality={},
    )
    f = filters_from_launch_payload(
        {
            "primary_capability": ["Data Science"],
            "grade": ["L4"],
        }
    )
    assert not employee_matches_launch_filters(snap, _emp(), f)
    f2 = filters_from_launch_payload(
        {
            "primary_capability": ["Data Science"],
            "grade": ["L5"],
        }
    )
    assert employee_matches_launch_filters(snap, _emp(), f2)

def test_org_values_match_across_spellings():
    from rv_availability.staffing.launch_filters import _field_matches, dedupe_options

    assert _field_matches("Pharma_CI", {"Pharma CI"})
    assert _field_matches("  pharma   ci ", {"Pharma_CI"})
    assert not _field_matches("Pharma CI Secondary", {"Pharma CI"})
    assert not _field_matches(None, {"Pharma CI"})
    assert dedupe_options(["Pharma_CI", "Pharma CI", "Program_Management", "MIA"]) == ["MIA", "Pharma CI", "Program_Management"]
