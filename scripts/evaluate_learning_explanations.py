#!/usr/bin/env python3
"""Evaluate Oracle-conditioned Learning Explanation outputs and blind reviews."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
METHODS = {
    "001a_deterministic_paraphrase": {
        "evidence_mode": "forbidden",
        "selectable": False,
    },
    "001b_relation_only_llm": {
        "evidence_mode": "forbidden",
        "selectable": False,
    },
    "002_evidence_grounded": {
        "evidence_mode": "required_for_why_connected",
        "selectable": True,
    },
}
FIELDS = {
    "connection_summary",
    "why_connected",
    "learning_value",
}
SUPPORT_LABELS = {
    "SOURCE_GROUNDED",
    "RELATION_ENTAILED",
    "GENERIC_PEDAGOGICAL_INFERENCE",
    "UNSUPPORTED",
    "CONTRADICTED",
    "UNRESOLVED",
}
SUPPORTED_LABELS = {
    "SOURCE_GROUNDED",
    "RELATION_ENTAILED",
    "GENERIC_PEDAGOGICAL_INFERENCE",
}
FAILURE_LABELS = {
    "RELATION_DISTORTION",
    "DIRECTION_REVERSAL",
    "EVIDENCE_OVERREACH",
    "ENDPOINT_DRIFT",
    "CONTRADICTION",
    "PEDAGOGICALLY_EMPTY",
    "PEDAGOGICAL_OVERREACH",
}
OUTPUT_KEYS = {
    "explanation_instance_id",
    "source_ko_id",
    "relation_type",
    "target_ko_id",
    *FIELDS,
}
REVIEW_KEYS = {
    "blind_review_id",
    "explanation_instance_id",
    "claims",
    "faithfulness",
    "failure_labels",
    "learning_value_scores",
}
SCORE_FIELDS = {
    "conceptual_mechanism",
    "learning_relevance",
    "specificity",
    "clarity",
}
ARTIFACT_NAMES = (
    "evaluation_status.json",
    "metrics.json",
    "errors.json",
    "matches.json",
    "summary.md",
)


class FatalEvaluationError(Exception):
    """Raised when predictions or reviews cannot be aligned safely."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Learning Explanation evaluation is structurally invalid.")
        self.errors = errors


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_rate(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def validate_prediction(
    instance: dict[str, Any],
    result: Any,
    method_id: str,
) -> dict[str, Any]:
    instance_id = instance["explanation_instance_id"]
    if not isinstance(result, dict):
        raise ValueError(f"{instance_id}: prediction must be an object.")
    if set(result) != OUTPUT_KEYS:
        raise ValueError(f"{instance_id}: prediction keys do not match the contract.")

    immutable = {
        "explanation_instance_id": instance_id,
        "source_ko_id": instance["source_ko"]["canonical_ko_id"],
        "relation_type": instance["relation_type"],
        "target_ko_id": instance["target_ko"]["canonical_ko_id"],
    }
    for field, expected in immutable.items():
        if result.get(field) != expected:
            raise ValueError(f"{instance_id}: immutable field {field} changed.")

    supplied_ids = {
        item["evidence_id"] for item in instance.get("evidence", [])
    }
    all_refs: list[str] = []
    for field in sorted(FIELDS):
        value = result[field]
        if not isinstance(value, dict) or set(value) != {"text", "evidence_refs"}:
            raise ValueError(f"{instance_id}: {field} has invalid structure.")
        text = value["text"]
        refs = value["evidence_refs"]
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"{instance_id}: {field}.text must be non-empty.")
        if (
            not isinstance(refs, list)
            or any(not isinstance(item, str) or not item for item in refs)
            or len(refs) != len(set(refs))
        ):
            raise ValueError(f"{instance_id}: {field}.evidence_refs is invalid.")
        unknown = sorted(set(refs) - supplied_ids)
        if unknown:
            raise ValueError(
                f"{instance_id}: {field} references unknown Evidence IDs {unknown}."
            )
        all_refs.extend(refs)

    evidence_mode = METHODS[method_id]["evidence_mode"]
    if evidence_mode == "forbidden" and all_refs:
        raise ValueError(f"{instance_id}: no-Evidence method cited Evidence.")
    if (
        evidence_mode == "required_for_why_connected"
        and not result["why_connected"]["evidence_refs"]
    ):
        raise ValueError(
            f"{instance_id}: Evidence-grounded why_connected omitted Evidence."
        )
    return result


def validate_review(
    instance_id: str,
    review: Any,
    method_id: str,
) -> dict[str, Any]:
    if not isinstance(review, dict) or set(review) != REVIEW_KEYS:
        raise ValueError(f"{instance_id}: review keys do not match the contract.")
    if review["explanation_instance_id"] != instance_id:
        raise ValueError(f"{instance_id}: review instance alignment changed.")
    if not isinstance(review["blind_review_id"], str) or not review[
        "blind_review_id"
    ]:
        raise ValueError(f"{instance_id}: blind_review_id must be non-empty.")

    claims = review["claims"]
    if not isinstance(claims, list) or not claims:
        raise ValueError(f"{instance_id}: review must contain claims.")
    claim_ids: set[str] = set()
    support_counts: Counter[str] = Counter()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {
            "claim_id",
            "field",
            "claim_text",
            "support_label",
        }:
            raise ValueError(f"{instance_id}: claim structure is invalid.")
        claim_id = claim["claim_id"]
        if not isinstance(claim_id, str) or not claim_id or claim_id in claim_ids:
            raise ValueError(f"{instance_id}: claim_id is invalid or duplicated.")
        claim_ids.add(claim_id)
        if claim["field"] not in FIELDS:
            raise ValueError(f"{instance_id}: claim field is invalid.")
        if not isinstance(claim["claim_text"], str) or not claim[
            "claim_text"
        ].strip():
            raise ValueError(f"{instance_id}: claim_text must be non-empty.")
        if claim["support_label"] not in SUPPORT_LABELS:
            raise ValueError(f"{instance_id}: support label is invalid.")
        if (
            METHODS[method_id]["evidence_mode"] == "forbidden"
            and claim["support_label"] == "SOURCE_GROUNDED"
        ):
            raise ValueError(
                f"{instance_id}: no-Evidence method cannot use SOURCE_GROUNDED."
            )
        support_counts[claim["support_label"]] += 1

    faithfulness = review["faithfulness"]
    if not isinstance(faithfulness, dict) or set(faithfulness) != {
        "relation_faithful",
        "direction_faithful",
        "endpoint_faithful",
        "evidence_faithful",
    }:
        raise ValueError(f"{instance_id}: faithfulness structure is invalid.")
    for field in (
        "relation_faithful",
        "direction_faithful",
        "endpoint_faithful",
    ):
        if not isinstance(faithfulness[field], bool):
            raise ValueError(f"{instance_id}: {field} must be boolean.")
    if METHODS[method_id]["evidence_mode"] == "forbidden":
        if faithfulness["evidence_faithful"] is not None:
            raise ValueError(
                f"{instance_id}: no-Evidence method must use null evidence status."
            )
    elif not isinstance(faithfulness["evidence_faithful"], bool):
        raise ValueError(
            f"{instance_id}: Evidence-grounded method needs boolean evidence status."
        )

    labels = review["failure_labels"]
    if (
        not isinstance(labels, list)
        or len(labels) != len(set(labels))
        or any(label not in FAILURE_LABELS for label in labels)
    ):
        raise ValueError(f"{instance_id}: failure_labels is invalid.")
    label_set = set(labels)
    required_labels = []
    if not faithfulness["relation_faithful"]:
        required_labels.append("RELATION_DISTORTION")
    if not faithfulness["direction_faithful"]:
        required_labels.append("DIRECTION_REVERSAL")
    if not faithfulness["endpoint_faithful"]:
        required_labels.append("ENDPOINT_DRIFT")
    if support_counts["CONTRADICTED"]:
        required_labels.append("CONTRADICTION")
    if support_counts["UNSUPPORTED"] and not (
        {"EVIDENCE_OVERREACH", "PEDAGOGICAL_OVERREACH"} & label_set
    ):
        raise ValueError(
            f"{instance_id}: unsupported claims need an overreach failure label."
        )
    missing_labels = sorted(set(required_labels) - label_set)
    if missing_labels:
        raise ValueError(
            f"{instance_id}: review is missing failure labels {missing_labels}."
        )

    pending = support_counts["UNRESOLVED"]
    has_unsupported = bool(
        support_counts["UNSUPPORTED"] or support_counts["CONTRADICTED"]
    )
    evidence_pass = (
        True
        if faithfulness["evidence_faithful"] is None
        else faithfulness["evidence_faithful"]
    )
    faithfulness_pass = (
        faithfulness["relation_faithful"]
        and faithfulness["direction_faithful"]
        and faithfulness["endpoint_faithful"]
        and evidence_pass
        and not has_unsupported
        and not pending
    )

    scores = review["learning_value_scores"]
    if pending:
        if scores is not None:
            raise ValueError(
                f"{instance_id}: unresolved claims cannot receive final scores."
            )
    elif faithfulness_pass:
        if not isinstance(scores, dict) or set(scores) != SCORE_FIELDS:
            raise ValueError(
                f"{instance_id}: faithful explanation requires all rubric scores."
            )
        if any(
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
            or value > 2
            for value in scores.values()
        ):
            raise ValueError(f"{instance_id}: rubric scores must be integers 0-2.")
        empty = (
            scores["conceptual_mechanism"] == 0
            and scores["learning_relevance"] == 0
        )
        if empty != ("PEDAGOGICALLY_EMPTY" in label_set):
            raise ValueError(
                f"{instance_id}: PEDAGOGICALLY_EMPTY is inconsistent with scores."
            )
    elif scores is not None:
        raise ValueError(
            f"{instance_id}: failed faithfulness gate must have null scores."
        )

    return {
        **review,
        "_support_counts": dict(support_counts),
        "_pending": pending,
        "_faithfulness_pass": faithfulness_pass,
    }


def clear_artifacts(evaluation_dir: Path) -> None:
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    for name in ARTIFACT_NAMES:
        path = evaluation_dir / name
        if path.exists():
            path.unlink()


def invalid_result(
    evaluation_dir: Path,
    errors: list[dict[str, Any]],
) -> dict[str, Any]:
    status = {
        "artifact_type": "learning_explanation_evaluation_status",
        "evaluation_status": "invalid",
        "fatal_error_count": len(errors),
    }
    write_json(evaluation_dir / "evaluation_status.json", status)
    write_json(
        evaluation_dir / "errors.json",
        {
            "evaluation_status": "invalid",
            "fatal_errors": errors,
        },
    )
    return status


def evaluate_files(
    *,
    benchmark_path: Path,
    predictions_path: Path,
    reviews_path: Path,
    method_id: str,
    evaluation_dir: Path,
) -> dict[str, Any]:
    clear_artifacts(evaluation_dir)
    if method_id not in METHODS:
        return invalid_result(
            evaluation_dir,
            [{"error_type": "unknown_method", "method_id": method_id}],
        )

    try:
        benchmark = read_json(benchmark_path)
        predictions = read_json(predictions_path)
        reviews = read_json(reviews_path)
    except (OSError, json.JSONDecodeError) as exc:
        return invalid_result(
            evaluation_dir,
            [{"error_type": "unreadable_input", "detail": str(exc)}],
        )

    fatal_errors: list[dict[str, Any]] = []
    instances = benchmark.get("instances") if isinstance(benchmark, dict) else None
    results = predictions.get("results") if isinstance(predictions, dict) else None
    review_items = reviews.get("reviews") if isinstance(reviews, dict) else None
    if not isinstance(instances, list) or not instances:
        fatal_errors.append({"error_type": "invalid_benchmark_bundle"})
    if not isinstance(results, list):
        fatal_errors.append({"error_type": "invalid_prediction_bundle"})
    if not isinstance(review_items, list):
        fatal_errors.append({"error_type": "invalid_review_bundle"})
    if fatal_errors:
        return invalid_result(evaluation_dir, fatal_errors)

    expected_ids = [item["explanation_instance_id"] for item in instances]
    result_ids = [
        item.get("explanation_instance_id") if isinstance(item, dict) else None
        for item in results
    ]
    review_ids = [
        item.get("explanation_instance_id") if isinstance(item, dict) else None
        for item in review_items
    ]
    for label, ids in (("prediction", result_ids), ("review", review_ids)):
        duplicates = sorted(
            item for item, count in Counter(ids).items() if count > 1
        )
        missing = sorted(set(expected_ids) - set(ids))
        unknown = sorted(
            str(item) for item in set(ids) - set(expected_ids) if item is not None
        )
        if duplicates:
            fatal_errors.append(
                {"error_type": f"duplicate_{label}_ids", "ids": duplicates}
            )
        if missing:
            fatal_errors.append(
                {"error_type": f"missing_{label}_ids", "ids": missing}
            )
        if unknown:
            fatal_errors.append(
                {"error_type": f"unknown_{label}_ids", "ids": unknown}
            )

    declared_method = predictions.get("method_id")
    if declared_method != method_id:
        fatal_errors.append(
            {
                "error_type": "prediction_method_mismatch",
                "expected": method_id,
                "actual": declared_method,
            }
        )
    expected_prediction_hash = reviews.get("prediction_sha256")
    actual_prediction_hash = sha256(predictions_path)
    if expected_prediction_hash != actual_prediction_hash:
        fatal_errors.append(
            {
                "error_type": "stale_review_snapshot",
                "expected": expected_prediction_hash,
                "actual": actual_prediction_hash,
            }
        )
    if fatal_errors:
        return invalid_result(evaluation_dir, fatal_errors)

    results_by_id = {item["explanation_instance_id"]: item for item in results}
    reviews_by_id = {
        item["explanation_instance_id"]: item for item in review_items
    }
    validated: list[dict[str, Any]] = []
    for instance in instances:
        instance_id = instance["explanation_instance_id"]
        try:
            prediction = validate_prediction(
                instance, results_by_id[instance_id], method_id
            )
            review = validate_review(
                instance_id, reviews_by_id[instance_id], method_id
            )
            source_grounded_fields = {
                claim["field"]
                for claim in review["claims"]
                if claim["support_label"] == "SOURCE_GROUNDED"
            }
            missing_field_refs = sorted(
                field
                for field in source_grounded_fields
                if not prediction[field]["evidence_refs"]
            )
            if missing_field_refs:
                raise ValueError(
                    f"{instance_id}: SOURCE_GROUNDED claims lack field-level "
                    f"Evidence references in {missing_field_refs}."
                )
        except (KeyError, TypeError, ValueError) as exc:
            fatal_errors.append(
                {
                    "error_type": "invalid_aligned_record",
                    "explanation_instance_id": instance_id,
                    "detail": str(exc),
                }
            )
            continue
        validated.append(
            {
                "instance": instance,
                "prediction": prediction,
                "review": review,
            }
        )
    if fatal_errors:
        return invalid_result(evaluation_dir, fatal_errors)

    claim_counts: Counter[str] = Counter()
    failure_counts: Counter[str] = Counter()
    relation_pass = direction_pass = endpoint_pass = evidence_pass = 0
    evidence_denominator = 0
    faithfulness_pass_count = 0
    pending_count = 0
    scored: list[dict[str, int]] = []
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    for item in validated:
        instance_id = item["instance"]["explanation_instance_id"]
        review = item["review"]
        faithfulness = review["faithfulness"]
        support_counts = Counter(review["_support_counts"])
        claim_counts.update(support_counts)
        failure_counts.update(review["failure_labels"])
        relation_pass += int(faithfulness["relation_faithful"])
        direction_pass += int(faithfulness["direction_faithful"])
        endpoint_pass += int(faithfulness["endpoint_faithful"])
        if faithfulness["evidence_faithful"] is not None:
            evidence_denominator += 1
            evidence_pass += int(faithfulness["evidence_faithful"])
        pending_count += review["_pending"]
        if review["_faithfulness_pass"]:
            faithfulness_pass_count += 1
            scored.append(review["learning_value_scores"])
        if review["failure_labels"] or review["_pending"]:
            errors.append(
                {
                    "explanation_instance_id": instance_id,
                    "failure_labels": review["failure_labels"],
                    "support_counts": dict(support_counts),
                    "pending_claims": review["_pending"],
                }
            )
        matches.append(
            {
                "blind_review_id": review["blind_review_id"],
                "explanation_instance_id": instance_id,
                "faithfulness_pass": review["_faithfulness_pass"],
                "support_counts": dict(support_counts),
                "failure_labels": review["failure_labels"],
            }
        )

    total = len(validated)
    resolved_claims = sum(
        count
        for label, count in claim_counts.items()
        if label != "UNRESOLVED"
    )
    unsupported_claims = (
        claim_counts["UNSUPPORTED"] + claim_counts["CONTRADICTED"]
    )
    secondary_denominator = len(scored)
    secondary = {
        "denominator": secondary_denominator,
        "mean_conceptual_mechanism_score": (
            mean(item["conceptual_mechanism"] for item in scored)
            if scored
            else None
        ),
        "mean_learning_relevance_score": (
            mean(item["learning_relevance"] for item in scored)
            if scored
            else None
        ),
        "mean_specificity_score": (
            mean(item["specificity"] for item in scored) if scored else None
        ),
        "mean_clarity_score": (
            mean(item["clarity"] for item in scored) if scored else None
        ),
        "pedagogically_non_empty_rate": safe_rate(
            sum(
                not (
                    item["conceptual_mechanism"] == 0
                    and item["learning_relevance"] == 0
                )
                for item in scored
            ),
            secondary_denominator,
        ),
    }
    evaluation_status = (
        "draft_pending_adjudication" if pending_count else "final"
    )
    metrics = {
        "artifact_type": "learning_explanation_evaluation_metrics",
        "artifact_schema_version": "v0.1",
        "evaluation_status": evaluation_status,
        "method_id": method_id,
        "method_selectable": METHODS[method_id]["selectable"],
        "counts": {
            "instances": total,
            "substantive_claims": sum(claim_counts.values()),
            "resolved_claims": resolved_claims,
            "pending_claim_adjudications": pending_count,
            "faithfulness_passing_instances": faithfulness_pass_count,
        },
        "hard_metrics": {
            "schema_valid_output_rate": 1.0,
            "immutable_field_accuracy": 1.0,
            "exact_evidence_id_validity_rate": (
                1.0
                if METHODS[method_id]["evidence_mode"]
                == "required_for_why_connected"
                else None
            ),
            "relation_faithfulness_rate": safe_rate(relation_pass, total),
            "direction_faithfulness_rate": safe_rate(direction_pass, total),
            "endpoint_faithfulness_rate": safe_rate(endpoint_pass, total),
            "explanation_evidence_faithfulness_rate": safe_rate(
                evidence_pass, evidence_denominator
            ),
            "faithfulness_pass_rate": safe_rate(
                faithfulness_pass_count, total
            ),
            "unsupported_claim_rate": safe_rate(
                unsupported_claims, resolved_claims
            ),
            "contradicted_claim_count": claim_counts["CONTRADICTED"],
            "direction_reversal_count": failure_counts["DIRECTION_REVERSAL"],
        },
        "claim_support_counts": dict(claim_counts),
        "failure_label_counts": dict(failure_counts),
        "secondary_metrics": secondary,
        "input_snapshots": {
            "benchmark_sha256": sha256(benchmark_path),
            "predictions_sha256": actual_prediction_hash,
            "reviews_sha256": sha256(reviews_path),
        },
    }
    status = {
        "artifact_type": "learning_explanation_evaluation_status",
        "evaluation_status": evaluation_status,
        "method_id": method_id,
        "pending_claim_adjudications": pending_count,
    }
    write_json(evaluation_dir / "evaluation_status.json", status)
    write_json(evaluation_dir / "metrics.json", metrics)
    write_json(
        evaluation_dir / "errors.json",
        {
            "evaluation_status": evaluation_status,
            "errors": errors,
        },
    )
    write_json(
        evaluation_dir / "matches.json",
        {
            "evaluation_status": evaluation_status,
            "matches": matches,
        },
    )
    (evaluation_dir / "summary.md").write_text(
        "\n".join(
            [
                "# Learning Explanation Evaluation",
                "",
                f"- Status: `{evaluation_status}`",
                f"- Method: `{method_id}`",
                f"- Instances: `{total}`",
                f"- Faithfulness pass rate: `{metrics['hard_metrics']['faithfulness_pass_rate']}`",
                f"- Unsupported claim rate: `{metrics['hard_metrics']['unsupported_claim_rate']}`",
                f"- Pending claim adjudications: `{pending_count}`",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return metrics


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--reviews", required=True)
    parser.add_argument("--method", required=True, choices=sorted(METHODS))
    parser.add_argument("--evaluation-dir", required=True)
    return parser.parse_args()


def resolve(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def main() -> int:
    args = parse_args()
    result = evaluate_files(
        benchmark_path=resolve(args.benchmark),
        predictions_path=resolve(args.predictions),
        reviews_path=resolve(args.reviews),
        method_id=args.method,
        evaluation_dir=resolve(args.evaluation_dir),
    )
    status = result["evaluation_status"]
    print(
        f"Learning Explanation evaluation status: {status} "
        f"({args.evaluation_dir})"
    )
    return 1 if status == "invalid" else 0


if __name__ == "__main__":
    raise SystemExit(main())
