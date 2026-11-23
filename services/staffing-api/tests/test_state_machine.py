from datetime import datetime, timedelta

import pytest

from app.state_machine import affects_availability, transition


def test_only_reserved_confirmed_affect_hours():
    assert affects_availability("Reserved")
    assert affects_availability("Confirmed")
    assert not affects_availability("Interview Booked")
    assert not affects_availability("KB Pending")


def test_interview_expiry_window():
    booked = datetime.utcnow()
    expires = booked + timedelta(days=7)
    assert (expires - booked).days == 7


def test_hold_expiry_state():
    with pytest.raises(ValueError):
        transition("New", "expire")
    assert transition("Interview Booked", "expire") == "Expired"