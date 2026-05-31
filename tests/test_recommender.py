from recommender import recommend_intervention


def test_recommend_returns_message():
    msg, cmd, source = recommend_intervention(intensity=5, category="work", hour_of_day=14)
    assert msg
    assert cmd.startswith("/")
    assert source in ("rules", "ml", "rules_fallback")
