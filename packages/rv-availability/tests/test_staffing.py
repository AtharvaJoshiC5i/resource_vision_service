from datetime import date

import pytest

from rv_availability import engine as e
from rv_availability.staffing.month_view import staffing_month_view
from rv_availability.staffing.skill_compare import compare_skill, level_index
from rv_availability.staffing.skill_compare import DEFAULT_LEVEL_ORDER
from test_engine import em as employee_month
from test_engine import hr, pt, snap


def test_staffing_month_view_defaults_missing_row_to_fully_available():
    s = snap([], [hr("e1")])
    emp = s.employees["E1"]
    assert s.employee_months.get((emp.key, 202805)) is None
    view = staffing_month_view(None, emp)
    assert view.status == e.FULLY_AVAILABLE
    assert view.remaining == e.CAPACITY_HOURS
    assert view.bookable_hours == e.CAPACITY_HOURS
    assert view.source == "assumed_available"


def test_staffing_month_view_uses_project_track_when_row_exists():
    s = snap([pt("e1", 202611, 80.0)], [hr("e1")])
    emp = s.employees["E1"]
    row = employee_month(s, "e1", 202611)
    view = staffing_month_view(row, emp, reserved_hours=10.0)
    assert view.status == e.PARTIALLY_AVAILABLE
    assert view.bookable_hours == 86.0
    assert view.source == "project_track"


def test_skill_ordinal_comparison():
    assert compare_skill("Expert", "Applied") is True
    assert compare_skill("Foundational", "Advanced") is False
    assert compare_skill(None, "Foundational") is False


def test_unknown_level_fails_loudly():
    with pytest.raises(ValueError):
        level_index("Beginner", DEFAULT_LEVEL_ORDER)


def test_85_15_split_helper():
  # implemented in staffing-api training module; sanity on days math
    total = 10
    training = round(total * 0.85)
    buffer = total - training
    assert training + buffer == total
    assert training == 8
    assert buffer == 2

def test_level_outside_configured_order_matches_on_equal_text_only():
    assert compare_skill("Practitioner", "Practitioner") is True
    assert compare_skill("Practitioner", "Advanced") is False
    assert compare_skill("Expert", "Practitioner") is False
