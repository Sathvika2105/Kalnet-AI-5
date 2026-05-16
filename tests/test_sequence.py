"""
Tests for email sequence logic
"""

import pytest
from datetime import date, timedelta
from pipeline.sequence import get_sequence_due_today


class TestSequence:

    def test_new_lead_day0(self):
        leads = [{
            "lead_id": "1",
            "email_sent_at": "",
            "sequence_step": 0,
            "replied": False
        }]

        result = get_sequence_due_today(leads)
        assert len(result) == 1

    def test_day5_email(self):
        today = date.today()
        five_days_ago = str(today - timedelta(days=5))

        leads = [{
            "lead_id": "1",
            "email_sent_at": five_days_ago,
            "sequence_step": 1,
            "replied": False
        }]

        result = get_sequence_due_today(leads)
        assert len(result) == 1

    def test_skip_replied(self):
        leads = [{
            "lead_id": "1",
            "email_sent_at": "",
            "sequence_step": 0,
            "replied": True
        }]

        result = get_sequence_due_today(leads)
        assert len(result) == 0

    def test_skip_completed(self):
        leads = [{
            "lead_id": "1",
            "email_sent_at": "",
            "sequence_step": 3,
            "replied": False
        }]

        result = get_sequence_due_today(leads)
        assert len(result) == 0