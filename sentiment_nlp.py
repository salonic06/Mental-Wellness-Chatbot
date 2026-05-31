"""
NLP for free-text wellness messages.

- /vent: VADER sentiment (compound score → mood buckets) + optional wellness lexicon
- Crisis: phrase list (safety guardrail, not sentiment)
- /checkin & /mood: structured fields only; ML recommender is tabular (no text NLP)
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

BASE_DIR = Path(__file__).resolve().parent
VENT_JSON = BASE_DIR / "vent_instructions.json"

_vader_analyzer = None

CRISIS_PHRASES = [
    "kill myself",
    "end my life",
    "want to die",
    "don't want to live",
    "dont want to live",
    "do not want to live",
    "not want to live",
    "don't want to be alive",
    "dont want to be alive",
    "suicide",
    "self harm",
    "self-harm",
    "hurt myself",
    "no reason to live",
    "better off dead",
    "wish i was dead",
    "wish i were dead",
    "wish i'd die",
    "ending my life",
    "take my life",
    "overdose",
]

CRISIS_RESPONSE = (
    "I'm really concerned about what you're sharing. You're not alone, and you deserve support.\n\n"
    "This bot is not able to provide emergency or clinical help.\n"
    "Please contact someone you trust now, or reach local emergency / crisis services.\n"
    "If you are in India, you can call iCall (9152987821) or Vandrevala Foundation (1860-2662-345).\n\n"
    "If you are in immediate danger, contact emergency services right away."
)

_BUCKETS = (
    "strong_negative",
    "mild_negative",
    "neutral",
    "mild_positive",
    "strong_positive",
)


def _get_vader():
    global _vader_analyzer
    if _vader_analyzer is None:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

        _vader_analyzer = SentimentIntensityAnalyzer()
    return _vader_analyzer


def _compound_to_bucket(compound: float) -> str:
    if compound >= 0.45:
        return "strong_positive"
    if compound >= 0.05:
        return "mild_positive"
    if compound > -0.05:
        return "neutral"
    if compound > -0.45:
        return "mild_negative"
    return "strong_negative"


def _vader_sentiment(text: str) -> Tuple[str, Dict[str, float]]:
    scores = _get_vader().polarity_scores(text)
    compound = scores["compound"]
    bucket = _compound_to_bucket(compound)
    detail = {
        "engine": "vader",
        "compound": compound,
        "pos": scores["pos"],
        "neu": scores["neu"],
        "neg": scores["neg"],
    }
    return bucket, detail


def _phrase_in_text(phrase: str, lowered: str) -> bool:
    if " " in phrase:
        return phrase in lowered
    return re.search(rf"\b{re.escape(phrase)}\b", lowered) is not None


def _lexicon_sentiment(text: str) -> Tuple[str, Dict[str, int]]:
    """Fallback / boost: curated wellness words in vent_instructions.json."""
    config = _load_vent_config()
    word_lists: Dict[str, List[str]] = config.get("sentiment_words", {})
    lowered = text.lower()
    scores = {bucket: 0 for bucket in _BUCKETS}

    for bucket, words in word_lists.items():
        if bucket not in scores:
            continue
        for word in words:
            if _phrase_in_text(word, lowered):
                scores[bucket] += 1

    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return "neutral", {**scores, "engine": "lexicon"}
    return best, {**scores, "engine": "lexicon"}


def _load_vent_config() -> dict:
    with open(VENT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)


def vent_intro() -> str:
    return _load_vent_config().get(
        "intro", "I'm here to listen. What's on your mind?"
    )


CRISIS_NOTE = "[crisis]"


def log_crisis_dashboard_marker(
    user_phone: str,
    source: str,
    intensity: Optional[int] = None,
    category: Optional[str] = None,
    db_path: str = "wellness.db",
) -> None:
    """Placeholder rows for dashboard — never stores the user's crisis message text."""
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now = datetime.now()
    cat = category or "other"

    if source == "checkin":
        c.execute(
            """INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (user_phone, "crisis", intensity, now, f"[{cat}] {CRISIS_NOTE}"),
        )
        c.execute(
            """INSERT INTO checkins (user_phone, intensity, category, note, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (user_phone, intensity, cat, CRISIS_NOTE, now),
        )
    else:
        c.execute(
            """INSERT INTO mood_logs (user_phone, mood, intensity, timestamp, notes)
               VALUES (?, ?, ?, ?, ?)""",
            (user_phone, "crisis", intensity, now, CRISIS_NOTE),
        )

    conn.commit()
    conn.close()


def handle_crisis(
    user_phone: str,
    text: str,
    source: str = "message",
    intensity: Optional[int] = None,
    category: Optional[str] = None,
    db_path: str = "wellness.db",
) -> str:
    log_vent_event(
        user_phone,
        "crisis",
        len(text.split()),
        is_crisis=True,
        source=source,
        db_path=db_path,
    )
    log_crisis_dashboard_marker(
        user_phone, source, intensity=intensity, category=category, db_path=db_path
    )
    return CRISIS_RESPONSE


def detect_crisis(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in CRISIS_PHRASES)


def analyze_sentiment(text: str) -> Tuple[str, Dict]:
    """
    Mood bucket for /vent replies.

    Primary: VADER (Valence Aware Dictionary) — handles negation, intensifiers
    (e.g. "very happy"), and many words not in a hand-built list.

    Secondary: wellness lexicon in vent_instructions.json nudges the bucket when
    VADER is near-neutral but domain words match.
    """
    try:
        bucket, detail = _vader_sentiment(text)
    except Exception:
        return _lexicon_sentiment(text)

    compound = detail["compound"]
    # Near-neutral VADER: trust curated lexicon if it has clear hits
    if -0.05 <= compound <= 0.05:
        lex_bucket, lex_detail = _lexicon_sentiment(text)
        lex_scores = {k: lex_detail.get(k, 0) for k in _BUCKETS}
        if max(lex_scores.values(), default=0) > 0:
            return lex_bucket, {**detail, "lexicon_tiebreak": lex_scores}

    return bucket, detail


def response_for_bucket(bucket: str) -> str:
    config = _load_vent_config()
    return config.get(bucket, config.get("neutral", "Thank you for sharing."))


def log_vent_event(
    user_phone: str,
    sentiment_bucket: str,
    word_count: int,
    is_crisis: bool = False,
    source: str = "vent",
    db_path: str = "wellness.db",
) -> None:
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute(
        """INSERT INTO vent_logs
           (user_phone, sentiment_bucket, word_count, is_crisis, source, created_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (
            user_phone,
            sentiment_bucket,
            word_count,
            int(is_crisis),
            source,
            datetime.now(),
        ),
    )
    conn.commit()
    conn.close()
