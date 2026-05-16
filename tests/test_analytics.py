"""
Tests for analytics module
"""

import pytest
from analytics.report import generate_metrics


class TestAnalytics:

    def test_total_sent(self):
        data = [
            {"email_sent_at": "1", "replied": False, "tier": 1, "subject_line": "A"},
            {"email_sent_at": "2", "replied": False, "tier": 1, "subject_line": "B"},
            {"email_sent_at": "", "replied": False, "tier": 1, "subject_line": ""},
        ]

        metrics = generate_metrics(data)
        assert metrics["total_sent"] == 2

    def test_total_replies(self):
        data = [
            {"email_sent_at": "1", "replied": True, "tier": 1, "subject_line": "A"},
            {"email_sent_at": "2", "replied": True, "tier": 1, "subject_line": "B"},
        ]

        metrics = generate_metrics(data)
        assert metrics["total_replies"] == 2

    def test_reply_rate(self):
        data = [
            {"email_sent_at": "1", "replied": True, "tier": 1, "subject_line": "A"},
            {"email_sent_at": "2", "replied": False, "tier": 1, "subject_line": "B"},
        ]

        metrics = generate_metrics(data)
        assert metrics["reply_rate"] == 50.0

    def test_empty_data(self):
        metrics = generate_metrics([])
        assert metrics["total_sent"] == 0
        assert metrics["total_replies"] == 0