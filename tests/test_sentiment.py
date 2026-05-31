from sentiment_nlp import analyze_sentiment, detect_crisis


def test_detect_crisis_phrases():
    assert detect_crisis("I don't want to live anymore") is True
    assert detect_crisis("having a rough day") is False


def test_analyze_sentiment_buckets():
    bucket, scores = analyze_sentiment("I feel wonderful and grateful today!")
    assert bucket in ("mild_positive", "strong_positive")
    assert "compound" in scores


def test_negative_sentiment():
    bucket, _ = analyze_sentiment("I feel terrible, hopeless and awful")
    assert bucket in ("mild_negative", "strong_negative")
