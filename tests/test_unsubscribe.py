"""
Tests for unsubscribe detection module
"""

import pytest
from pipeline.unsubscribe import is_unsubscribe_request


class TestUnsubscribeDetection:

    def test_stop_uppercase(self):
        assert is_unsubscribe_request("STOP") is True

    def test_stop_lowercase(self):
        assert is_unsubscribe_request("stop") is True

    def test_unsubscribe_keyword(self):
        assert is_unsubscribe_request("please unsubscribe me") is True

    def test_unsub_short(self):
        assert is_unsubscribe_request("unsub") is True

    def test_remove_request(self):
        assert is_unsubscribe_request("remove me from list") is True

    def test_not_interested(self):
        assert is_unsubscribe_request("not interested") is True

    def test_normal_message(self):
        assert is_unsubscribe_request("hello how are you") is False

    def test_context_stop(self):
        assert is_unsubscribe_request("stop by tomorrow") is False