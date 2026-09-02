from __future__ import annotations


def recommendation_metrics(expected_ids: set[str], recommended_ids: set[str]) -> dict[str, float | int]:
    true_positive = len(expected_ids & recommended_ids)
    false_positive = len(recommended_ids - expected_ids)
    false_negative = len(expected_ids - recommended_ids)
    precision = true_positive / len(recommended_ids) if recommended_ids else (1.0 if not expected_ids else 0.0)
    recall = true_positive / len(expected_ids) if expected_ids else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "true_positive": true_positive, "false_positive": false_positive, "false_negative": false_negative,
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
    }


def evaluate_analysis(result: dict, gold: dict) -> dict:
    expected = {str(value) for value in gold.get("expected_tc_ids", [])}
    recommended = {
        str(item["tc_id"]) for item in result.get("decisions", [])
        if item.get("recommended") and item.get("tc_id")
    }
    metrics = recommendation_metrics(expected, recommended)
    return {
        "case_id": gold.get("case_id", ""), **metrics,
        "expected_tc_ids": sorted(expected), "recommended_tc_ids": sorted(recommended),
        "missing_tc_ids": sorted(expected - recommended), "unexpected_tc_ids": sorted(recommended - expected),
    }
