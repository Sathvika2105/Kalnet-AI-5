"""
spam_check.py -- Email Spam Score Analyzer
Analyzes email content against common spam rules and returns a score.
"""

import re


SPAM_TRIGGER_WORDS = [
    "free", "guarantee", "act now", "limited time", "hurry",
    "congratulations", "winner", "no obligation", "risk free",
    "buy now", "order now", "click here", "subscribe now",
    "100%", "amazing deal", "incredible offer", "best price",
    "cash bonus", "discount", "earn money", "extra income",
    "get paid", "increase sales", "no cost", "no fees",
    "special promotion", "urgent", "you have been selected",
    "double your", "eliminate debt", "free access", "free gift",
    "free trial", "increase traffic", "lose weight", "make money",
    "miracle", "no catch", "no experience", "no strings attached",
    "obligation", "offer expires", "once in a lifetime", "pennies",
    "potential earnings", "pure profit", "satisfaction",
    "score", "take action", "this isn't spam", "unlimited",
    "what are you waiting for", "while supplies last",
]

SPAMMY_PUNCTUATION_PATTERNS = [
    r'!{2,}',
    r'\?{2,}',
    r'\${2,}',
    r'!{1}\?{1}',
    r'\?{1}!{1}',
]

GREETINGS = [
    "hi ", "hello ", "dear ", "hey ", "good morning",
    "good afternoon", "good evening", "greetings",
]

UNSUBSCRIBE_KEYWORDS = [
    "unsubscribe", "opt out", "remove me", "stop receiving",
    "do not email", "no longer wish", "take me off",
]


def _check_subject_length(subject: str) -> list:
    findings = []
    length = len(subject)
    if length < 10:
        findings.append(("Subject too short (< 10 chars)", 5, "short"))
    elif length > 60:
        findings.append(("Subject too long (> 60 chars)", 5, "long"))
    if length == 0:
        findings.append(("Subject is empty", 10, "critical"))
    return findings


def _check_spam_words(subject: str, body: str) -> list:
    findings = []
    combined = (subject + " " + body).lower()
    found = [w for w in SPAM_TRIGGER_WORDS if w in combined]
    if found:
        word_list = ", ".join(found[:5])
        if len(found) > 5:
            word_list += f" +{len(found) - 5} more"
        findings.append((f"Spam trigger words found: {word_list}", min(len(found) * 10, 30), "high"))
    return findings


def _check_caps(subject: str) -> list:
    findings = []
    if subject and subject == subject.upper() and subject.isalpha():
        findings.append(("Subject is ALL CAPS", 10, "high"))
    elif subject:
        words = subject.split()
        caps_words = [w for w in words if w.isupper() and len(w) > 2]
        if len(caps_words) > len(words) * 0.5 and len(words) > 2:
            findings.append(("Subject has excessive ALL CAPS words", 5, "medium"))
    return findings


def _check_personalization(subject: str, body: str) -> list:
    findings = []
    combined = subject + " " + body
    has_name = "{name}" in combined or "name" in combined.lower()
    has_company = "{company}" in combined or "company" in combined.lower()
    if not has_name and not has_company:
        findings.append(("No personalization ({name}, {company})", 10, "medium"))
    return findings


def _check_punctuation(body: str) -> list:
    findings = []
    for pattern in SPAMMY_PUNCTUATION_PATTERNS:
        matches = re.findall(pattern, body)
        if matches:
            findings.append(("Excessive punctuation detected (!!!, ???)", 5, "low"))
            break
    return findings


def _check_links(body: str) -> list:
    findings = []
    url_count = len(re.findall(r'https?://\S+', body))
    if url_count > 3:
        findings.append((f"Too many URLs ({url_count})", 10, "high"))
    elif url_count > 0:
        findings.append((f"Contains {url_count} URL(s)", 0, "info"))
    return findings


def _check_unsubscribe(body: str) -> list:
    findings = []
    body_lower = body.lower()
    has_unsub = any(kw in body_lower for kw in UNSUBSCRIBE_KEYWORDS)
    if not has_unsub:
        findings.append(("No unsubscribe language in body", 10, "medium"))
    return findings


def _check_greeting(body: str) -> list:
    findings = []
    body_lower = body.lower()
    has_greeting = any(g in body_lower for g in GREETINGS)
    if not has_greeting:
        findings.append(("No personal greeting (Hi {name})", 5, "low"))
    return findings


def _check_body_length(body: str) -> list:
    findings = []
    word_count = len(body.split())
    if word_count < 30:
        findings.append((f"Body too short ({word_count} words)", 5, "low"))
    elif word_count > 500:
        findings.append((f"Body too long ({word_count} words)", 5, "low"))
    return findings


def _check_emoji(subject: str) -> list:
    findings = []
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0\U000024C2-\U0001F251]+",
        flags=re.UNICODE,
    )
    if emoji_pattern.search(subject):
        findings.append(("Emoji detected in subject line", 5, "low"))
    return findings


def _score_label(score: int) -> str:
    if score <= 20:
        return "safe"
    if score <= 40:
        return "low_risk"
    if score <= 60:
        return "medium_risk"
    return "high_risk"


def analyze_email(subject: str, body: str) -> dict:
    """
    Analyze an email and return spam score with findings.
    Returns dict with: score, label, findings[]
    """
    findings = []

    findings.extend(_check_subject_length(subject))
    findings.extend(_check_spam_words(subject, body))
    findings.extend(_check_caps(subject))
    findings.extend(_check_personalization(subject, body))
    findings.extend(_check_punctuation(body))
    findings.extend(_check_links(body))
    findings.extend(_check_unsubscribe(body))
    findings.extend(_check_greeting(body))
    findings.extend(_check_body_length(body))
    findings.extend(_check_emoji(subject))

    total_score = sum(f[1] for f in findings)
    total_score = min(total_score, 100)

    results = [
        {"rule": f[0], "points": f[1], "severity": f[2]}
        for f in findings
    ]

    return {
        "score": total_score,
        "label": _score_label(total_score),
        "findings": results,
    }
