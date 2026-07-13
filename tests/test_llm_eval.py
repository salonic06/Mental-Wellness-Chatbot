from llm_eval_harness import evaluate_vent_reply, run_offline_harness


def test_good_reply_passes():
    results = evaluate_vent_reply(
        "That sounds like a lot to carry. I'm glad you told someone."
    )
    assert all(r.passed for r in results)


def test_medical_advice_fails():
    results = evaluate_vent_reply("You have clinical depression and need medication.")
    medical = next(r for r in results if r.name == "no_medical_advice")
    assert not medical.passed


def test_offline_harness_runs():
    report = run_offline_harness(generate_fn=None)
    assert report.results
    assert any(r.name.startswith("sample_good") for r in report.results)
