from app.core.evaluation import evaluate_analysis, recommendation_metrics


def test_recommendation_metrics_counts_precision_and_recall():
    metrics = recommendation_metrics({"TC-1", "TC-2"}, {"TC-2", "TC-3"})
    assert metrics == {"true_positive": 1, "false_positive": 1, "false_negative": 1, "precision": 0.5, "recall": 0.5, "f1": 0.5}


def test_evaluate_analysis_lists_missing_and_unexpected_ids():
    result = {"decisions": [{"tc_id": "TC-1", "recommended": True}, {"tc_id": "TC-X", "recommended": False}]}
    report = evaluate_analysis(result, {"case_id": "login", "expected_tc_ids": ["TC-1", "TC-2"]})
    assert report["missing_tc_ids"] == ["TC-2"]
    assert report["unexpected_tc_ids"] == []
