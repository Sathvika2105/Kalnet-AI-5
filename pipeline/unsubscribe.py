"""
/pipeline/unsubscribe.py
any lead who replies with STOP must never be emailed again
Handles opt-out detection for inbound replies.
Upgraded to use regex to prevent false positives from check_replies 200-char string.
"""
import re

def is_unsubscribe_request(reply_text: str) -> bool:
    """
    Analyzes a 200-character reply snippet to determine if the lead wants to opt-out.
    Returns True if an opt-out intent is detected, False otherwise.
    """
    if not reply_text:
        return False

    text_lower = reply_text.lower()

    # Unambiguous opt-out phrases
    clear_pattern = r'\b(unsubscribe|unsub|remove me|take me off|do not email)\b'
    if re.search(clear_pattern, text_lower):
        return True

    # Context-Aware "Stop" Detection
    # Matches 'stop' UNLESS it is followed by spaces and 'by', 'in', 'at', or 'over'
    stop_pattern = r'\bstop\b(?!\s+(by|in|at|over))'
    if re.search(stop_pattern, text_lower):
        return True

    # Polite rejections
    rejection_pattern = r'\b(not interested|no thank you|no thanks)\b'
    if re.search(rejection_pattern, text_lower):
        return True

    return False
