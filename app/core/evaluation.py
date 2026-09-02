from __future__ import annotations

import re


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


def parse_tc_ids(value: str) -> list[str]:
    """QA 입력을 줄바꿈/쉼표 구분 TC ID 목록으로 정규화한다."""
    return list(dict.fromkeys(item.strip() for item in re.split(r"[,\r\n]+", value) if item.strip()))


def aggregate_evaluations(reports: list[dict]) -> dict[str, float | int]:
    """여러 분석의 confusion count를 합산한 micro 평균을 반환한다."""
    totals = {
        "true_positive": sum(int(item["true_positive"]) for item in reports),
        "false_positive": sum(int(item["false_positive"]) for item in reports),
        "false_negative": sum(int(item["false_negative"]) for item in reports),
    }
    recommended = totals["true_positive"] + totals["false_positive"]
    expected = totals["true_positive"] + totals["false_negative"]
    precision = totals["true_positive"] / recommended if recommended else (1.0 if not expected else 0.0)
    recall = totals["true_positive"] / expected if expected else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "case_count": len(reports), **totals,
        "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
    }
