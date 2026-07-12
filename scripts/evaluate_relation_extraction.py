#!/usr/bin/env python3
"""Evaluate Oracle-KO Typed Relation Extraction predictions."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GROUND_TRUTH = (
    ROOT / "benchmark" / "ground_truth" / "relations_development_v0_1.json"
)
RELATION_ORDER = [
    "REQUIRES",
    "APPLIED_IN",
    "EXTENDS",
    "CONTRASTS_WITH",
    "FORMALIZES",
    "RELATED_TO",
    "NO_RELATION",
]
GRAPH_RELATIONS = set(RELATION_ORDER) - {"NO_RELATION"}
ALLOWED_RELATIONS = set(RELATION_ORDER)
SUPPORTED_ADJUDICATION_DECISIONS = {"supported", "not_supported"}

Ref = tuple[str, str]


@dataclass(frozen=True)
class Edge:
    source: Ref
    target: Ref
    relation_type: str
    symmetric: bool = False


@dataclass
class GroundTruthPair:
    pair_id: str
    category: str
    edge: Edge
    evidence_spans: list[dict[str, str]]
    rationale: str
    alternatives: list[Edge]
    raw: dict[str, Any]

    @property
    def candidate(self) -> frozenset[Ref]:
        return frozenset({self.edge.source, self.edge.target})

    @property
    def accepted_edges(self) -> list[Edge]:
        return [self.edge, *self.alternatives]


@dataclass
class Prediction:
    pair_id: str
    source: Ref
    target: Ref
    relation_type: str
    evidence_spans: list[dict[str, str]]
    rationale: str
    raw: dict[str, Any]

    @property
    def edge(self) -> Edge:
        return Edge(self.source, self.target, self.relation_type)


@dataclass
class Adjudication:
    pair_id: str
    predicted_edge: Edge
    predicted_evidence_spans: list[dict[str, str]]
    decision: str
    rationale: str


class FatalPredictionError(Exception):
    """Raised when predictions cannot be aligned safely to the benchmark."""

    def __init__(self, errors: list[dict[str, Any]]) -> None:
        super().__init__("Prediction schema contains fatal alignment errors")
        self.errors = errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Typed Relation Extraction predictions."
    )
    parser.add_argument(
        "--ground-truth",
        default=str(DEFAULT_GROUND_TRUTH.relative_to(ROOT)),
        help="Relation ground-truth JSON path relative to the repository root.",
    )
    parser.add_argument(
        "--predictions",
        required=True,
        help="Prediction JSON containing a top-level results list.",
    )
    parser.add_argument(
        "--evaluation-dir",
        required=True,
        help="Directory in which evaluation artifacts will be written.",
    )
    parser.add_argument(
        "--adjudication",
        help="Optional JSON file containing evidence-support decisions.",
    )
    return parser.parse_args()


def resolve_path(path_text: str) -> Path:
    path = Path(path_text)
    return path if path.is_absolute() else ROOT / path


def display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to read JSON file {path}: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def parse_ref(value: Any, context: str) -> Ref:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object")
    lecture_id = value.get("lecture_id")
    ko_id = value.get("ko_id")
    if not isinstance(lecture_id, str) or not lecture_id:
        raise ValueError(f"{context}.lecture_id must be a non-empty string")
    if not isinstance(ko_id, str) or not ko_id:
        raise ValueError(f"{context}.ko_id must be a non-empty string")
    return lecture_id, ko_id


def ref_json(ref: Ref) -> dict[str, str]:
    return {"lecture_id": ref[0], "ko_id": ref[1]}


def edge_json(edge: Edge) -> dict[str, Any]:
    return {
        "source": ref_json(edge.source),
        "target": ref_json(edge.target),
        "relation_type": edge.relation_type,
    }


def safe_divide(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def load_ground_truth(
    path: Path,
) -> tuple[dict[str, GroundTruthPair], dict[str, Any], dict[str, str]]:
    data = load_json(path)
    if not isinstance(data, dict):
        raise RuntimeError("Ground truth must be a JSON object")

    lecture_paths: dict[str, str] = {}
    for ko_path_text in data.get("knowledge_object_ground_truths", []):
        ko_data = load_json(resolve_path(ko_path_text))
        for lecture in ko_data.get("lectures", []):
            lecture_id = lecture.get("lecture_id")
            lecture_path = lecture.get("path")
            if isinstance(lecture_id, str) and isinstance(lecture_path, str):
                lecture_paths[lecture_id] = lecture_path

    lecture_texts: dict[str, str] = {}
    for lecture_id, lecture_path in lecture_paths.items():
        try:
            lecture_texts[lecture_id] = resolve_path(lecture_path).read_text(
                encoding="utf-8"
            )
        except OSError as exc:
            raise RuntimeError(
                f"Unable to read lecture {lecture_id} from {lecture_path}: {exc}"
            ) from exc

    pairs: dict[str, GroundTruthPair] = {}
    for index, raw_pair in enumerate(data.get("pairs", [])):
        if not isinstance(raw_pair, dict):
            raise RuntimeError(f"Ground-truth pair {index} must be an object")
        try:
            pair_id = raw_pair["pair_id"]
            relation_type = raw_pair["relation_type"]
            source = parse_ref(raw_pair["source"], f"ground truth {pair_id}.source")
            target = parse_ref(raw_pair["target"], f"ground truth {pair_id}.target")
        except (KeyError, ValueError) as exc:
            raise RuntimeError(f"Invalid ground-truth pair at index {index}: {exc}") from exc
        if not isinstance(pair_id, str) or not pair_id:
            raise RuntimeError(f"Ground-truth pair {index} has invalid pair_id")
        if pair_id in pairs:
            raise RuntimeError(f"Duplicate ground-truth pair_id: {pair_id}")
        if relation_type not in ALLOWED_RELATIONS:
            raise RuntimeError(f"{pair_id}: invalid ground-truth Relation label")

        alternatives: list[Edge] = []
        for alt_index, alternative in enumerate(
            raw_pair.get("acceptable_alternatives", [])
        ):
            try:
                alternative_type = alternative["relation_type"]
                if alternative_type not in GRAPH_RELATIONS:
                    raise ValueError(
                        f"invalid Relation label {alternative_type!r}"
                    )
                alternatives.append(
                    Edge(
                        parse_ref(
                            alternative["source"],
                            f"{pair_id}.acceptable_alternatives[{alt_index}].source",
                        ),
                        parse_ref(
                            alternative["target"],
                            f"{pair_id}.acceptable_alternatives[{alt_index}].target",
                        ),
                        alternative_type,
                        bool(alternative.get("symmetric", False)),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise RuntimeError(f"Invalid alternative for {pair_id}: {exc}") from exc

        evidence = raw_pair.get("evidence_spans", [])
        if not isinstance(evidence, list):
            raise RuntimeError(f"{pair_id}: ground-truth evidence_spans must be a list")
        pairs[pair_id] = GroundTruthPair(
            pair_id=pair_id,
            category=str(raw_pair.get("category", "")),
            edge=Edge(
                source,
                target,
                relation_type,
                bool(raw_pair.get("symmetric", False)),
            ),
            evidence_spans=evidence,
            rationale=str(raw_pair.get("rationale", "")),
            alternatives=alternatives,
            raw=raw_pair,
        )

    return pairs, data, lecture_texts


def load_predictions(
    path: Path,
    ground_truth: dict[str, GroundTruthPair],
) -> dict[str, Prediction]:
    data = load_json(path)
    fatal_errors: list[dict[str, Any]] = []
    if not isinstance(data, dict) or not isinstance(data.get("results"), list):
        raise FatalPredictionError(
            [{
                "error_type": "schema_error",
                "message": "Predictions must be an object with a results list.",
            }]
        )

    predictions: dict[str, Prediction] = {}
    for index, result in enumerate(data["results"]):
        context = f"results[{index}]"
        if not isinstance(result, dict):
            fatal_errors.append({
                "error_type": "schema_error",
                "prediction_index": index,
                "message": f"{context} must be an object.",
            })
            continue

        pair_id = result.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            fatal_errors.append({
                "error_type": "missing_pair_id",
                "prediction_index": index,
                "message": f"{context}.pair_id must be a non-empty string.",
            })
            continue
        if pair_id in predictions:
            fatal_errors.append({
                "error_type": "duplicate_pair_id",
                "pair_id": pair_id,
                "prediction_index": index,
            })
            continue
        if pair_id not in ground_truth:
            fatal_errors.append({
                "error_type": "unknown_pair_id",
                "pair_id": pair_id,
                "prediction_index": index,
            })
            continue

        relation_type = result.get("relation_type")
        if relation_type not in ALLOWED_RELATIONS:
            fatal_errors.append({
                "error_type": "invalid_relation_type",
                "pair_id": pair_id,
                "prediction_index": index,
                "value": relation_type,
            })
            continue

        try:
            source = parse_ref(result.get("source"), f"{context}.source")
            target = parse_ref(result.get("target"), f"{context}.target")
        except ValueError as exc:
            fatal_errors.append({
                "error_type": "invalid_candidate_reference",
                "pair_id": pair_id,
                "prediction_index": index,
                "message": str(exc),
            })
            continue

        if frozenset({source, target}) != ground_truth[pair_id].candidate:
            fatal_errors.append({
                "error_type": "candidate_pair_mismatch",
                "pair_id": pair_id,
                "prediction_index": index,
                "predicted_source": ref_json(source),
                "predicted_target": ref_json(target),
            })
            continue

        evidence = result.get("evidence_spans")
        if not isinstance(evidence, list):
            fatal_errors.append({
                "error_type": "schema_error",
                "pair_id": pair_id,
                "message": "evidence_spans must be a list.",
            })
            continue
        evidence_valid_structure = True
        for evidence_index, item in enumerate(evidence):
            lecture_id = item.get("lecture_id") if isinstance(item, dict) else None
            span = item.get("span") if isinstance(item, dict) else None
            if (
                not isinstance(item, dict)
                or not isinstance(lecture_id, str)
                or not lecture_id.strip()
                or not isinstance(span, str)
                or not span.strip()
            ):
                fatal_errors.append({
                    "error_type": "schema_error",
                    "pair_id": pair_id,
                    "evidence_index": evidence_index,
                    "message": (
                        "Evidence requires non-empty string lecture_id and span fields."
                    ),
                })
                evidence_valid_structure = False
        if not evidence_valid_structure:
            continue

        rationale = result.get("rationale", "")
        if not isinstance(rationale, str):
            fatal_errors.append({
                "error_type": "schema_error",
                "pair_id": pair_id,
                "message": "rationale must be a string.",
            })
            continue

        predictions[pair_id] = Prediction(
            pair_id=pair_id,
            source=source,
            target=target,
            relation_type=relation_type,
            evidence_spans=evidence,
            rationale=rationale,
            raw=result,
        )

    expected_ids = set(ground_truth)
    predicted_ids = set(predictions)
    missing_ids = sorted(expected_ids - predicted_ids)
    if missing_ids:
        fatal_errors.append({
            "error_type": "missing_predictions",
            "pair_ids": missing_ids,
        })
    if len(data["results"]) != len(ground_truth):
        fatal_errors.append({
            "error_type": "result_count_mismatch",
            "expected": len(ground_truth),
            "actual": len(data["results"]),
        })

    if fatal_errors:
        raise FatalPredictionError(fatal_errors)
    return predictions


def load_adjudication(path: Path | None) -> dict[str, Adjudication]:
    if path is None:
        return {}
    data = load_json(path)
    decisions = data.get("decisions") if isinstance(data, dict) else data
    if not isinstance(decisions, list):
        raise RuntimeError("Adjudication must be a list or an object with decisions")

    result: dict[str, Adjudication] = {}
    for index, item in enumerate(decisions):
        if not isinstance(item, dict):
            raise RuntimeError(f"Adjudication item {index} must be an object")
        pair_id = item.get("pair_id")
        decision = item.get("decision")
        rationale = item.get("rationale")
        if not isinstance(pair_id, str) or not pair_id:
            raise RuntimeError(f"Adjudication item {index} has invalid pair_id")
        if decision not in SUPPORTED_ADJUDICATION_DECISIONS:
            raise RuntimeError(f"Adjudication item {index} has invalid decision")
        if not isinstance(rationale, str) or not rationale.strip():
            raise RuntimeError(f"Adjudication item {index} requires rationale")
        if pair_id in result:
            raise RuntimeError(f"Duplicate adjudication for {pair_id}")
        predicted_edge_value = item.get("predicted_edge")
        if not isinstance(predicted_edge_value, dict):
            raise RuntimeError(
                f"Adjudication item {index} requires predicted_edge"
            )
        try:
            source = parse_ref(
                predicted_edge_value.get("source"),
                f"adjudication[{index}].predicted_edge.source",
            )
            target = parse_ref(
                predicted_edge_value.get("target"),
                f"adjudication[{index}].predicted_edge.target",
            )
        except ValueError as exc:
            raise RuntimeError(str(exc)) from exc
        relation_type = predicted_edge_value.get("relation_type")
        if relation_type not in ALLOWED_RELATIONS:
            raise RuntimeError(
                f"Adjudication item {index} has invalid predicted Relation type"
            )

        predicted_evidence = item.get("predicted_evidence_spans")
        if not isinstance(predicted_evidence, list):
            raise RuntimeError(
                f"Adjudication item {index} requires predicted_evidence_spans"
            )
        for evidence_index, evidence in enumerate(predicted_evidence):
            if (
                not isinstance(evidence, dict)
                or not isinstance(evidence.get("lecture_id"), str)
                or not isinstance(evidence.get("span"), str)
            ):
                raise RuntimeError(
                    f"Adjudication item {index} evidence {evidence_index} is invalid"
                )

        result[pair_id] = Adjudication(
            pair_id=pair_id,
            predicted_edge=Edge(source, target, relation_type),
            predicted_evidence_spans=predicted_evidence,
            decision=decision,
            rationale=rationale,
        )
    return result


def edge_matches(prediction: Prediction, expected: Edge) -> bool:
    if prediction.relation_type != expected.relation_type:
        return False
    if expected.relation_type == "NO_RELATION" or expected.symmetric:
        return frozenset({prediction.source, prediction.target}) == frozenset(
            {expected.source, expected.target}
        )
    return prediction.source == expected.source and prediction.target == expected.target


def exact_evidence_details(
    prediction: Prediction,
    pair: GroundTruthPair,
    lecture_texts: dict[str, str],
) -> tuple[list[dict[str, Any]], int, int]:
    details: list[dict[str, Any]] = []
    valid_count = 0
    allowed_lectures = {pair.edge.source[0], pair.edge.target[0]}
    for index, item in enumerate(prediction.evidence_spans):
        lecture_id = item["lecture_id"]
        span = item["span"]
        lecture_allowed = lecture_id in allowed_lectures
        exact = (
            lecture_allowed
            and lecture_id in lecture_texts
            and bool(span)
            and span in lecture_texts[lecture_id]
        )
        valid_count += int(exact)
        details.append({
            "evidence_index": index,
            "lecture_id": lecture_id,
            "span": span,
            "lecture_allowed": lecture_allowed,
            "exact_substring": exact,
        })
    return details, valid_count, len(prediction.evidence_spans)


def canonical_evidence(spans: list[dict[str, str]]) -> set[tuple[str, str]]:
    return {(item["lecture_id"], item["span"]) for item in spans}


def evidence_signature(spans: list[dict[str, str]]) -> Counter[tuple[str, str]]:
    return Counter((item["lecture_id"], item["span"]) for item in spans)


def validate_adjudications(
    adjudication: dict[str, Adjudication],
    ground_truth: dict[str, GroundTruthPair],
    predictions: dict[str, Prediction],
    lecture_texts: dict[str, str],
) -> None:
    for pair_id, decision in adjudication.items():
        if pair_id not in ground_truth:
            raise RuntimeError(
                f"stale_or_unused_adjudication: unknown pair ID {pair_id}"
            )

        pair = ground_truth[pair_id]
        prediction = predictions[pair_id]
        if decision.predicted_edge != prediction.edge:
            raise RuntimeError(
                f"stale_or_unused_adjudication: predicted edge changed for {pair_id}"
            )
        if evidence_signature(decision.predicted_evidence_spans) != evidence_signature(
            prediction.evidence_spans
        ):
            raise RuntimeError(
                f"stale_or_unused_adjudication: evidence changed for {pair_id}"
            )

        acceptable_match = any(
            edge_matches(prediction, expected) for expected in pair.accepted_edges
        )
        _, valid_spans, total_spans = exact_evidence_details(
            prediction, pair, lecture_texts
        )
        auto_supported = (
            total_spans > 0
            and valid_spans == total_spans
            and canonical_evidence(prediction.evidence_spans)
            == canonical_evidence(pair.evidence_spans)
        )
        requires_adjudication = (
            acceptable_match
            and prediction.relation_type in GRAPH_RELATIONS
            and not auto_supported
        )
        if not requires_adjudication:
            raise RuntimeError(
                f"stale_or_unused_adjudication: no adjudication is required for {pair_id}"
            )


def make_confusion_matrix(
    ground_truth: dict[str, GroundTruthPair],
    predictions: dict[str, Prediction],
    primary_categories: set[str],
) -> dict[str, Any]:
    matrix = {
        truth: {prediction: 0 for prediction in RELATION_ORDER}
        for truth in RELATION_ORDER
    }
    for pair_id, pair in ground_truth.items():
        if pair.category not in primary_categories:
            continue
        matrix[pair.edge.relation_type][predictions[pair_id].relation_type] += 1

    supported_labels = [
        label for label in RELATION_ORDER if sum(matrix[label].values()) > 0
    ]
    per_type: dict[str, dict[str, int | float | None]] = {}
    f1_values: list[float] = []
    for label in RELATION_ORDER:
        true_positive = matrix[label][label]
        false_positive = sum(
            matrix[truth][label] for truth in RELATION_ORDER if truth != label
        )
        false_negative = sum(
            matrix[label][predicted]
            for predicted in RELATION_ORDER
            if predicted != label
        )
        support = sum(matrix[label].values())
        precision = safe_divide(true_positive, true_positive + false_positive)
        recall = safe_divide(true_positive, true_positive + false_negative)
        if precision is None or recall is None or precision + recall == 0:
            f1 = None if support == 0 else 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)
        per_type[label] = {
            "support": support,
            "true_positive": true_positive,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }
        if label in supported_labels:
            f1_values.append(0.0 if f1 is None else f1)

    return {
        "labels": RELATION_ORDER,
        "matrix": matrix,
        "per_type": per_type,
        "macro_f1_supported_labels": (
            sum(f1_values) / len(f1_values) if f1_values else None
        ),
        "macro_f1_included_labels": supported_labels,
    }


def evaluate(
    ground_truth: dict[str, GroundTruthPair],
    ground_truth_data: dict[str, Any],
    predictions: dict[str, Prediction],
    lecture_texts: dict[str, str],
    adjudication: dict[str, Adjudication],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    primary_categories = set(ground_truth_data.get("primary_scoring_categories", []))
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    pending: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    schema_gap_predictions: list[dict[str, Any]] = []
    used_adjudications: set[str] = set()

    for pair_id, pair in ground_truth.items():
        prediction = predictions[pair_id]
        gold = pair.edge
        primary_scored = pair.category in primary_categories
        type_correct = prediction.relation_type == gold.relation_type
        direction_eligible = (
            pair.category == "positive"
            and not gold.symmetric
            and prediction.relation_type in GRAPH_RELATIONS
        )
        type_conditioned_direction_eligible = direction_eligible and type_correct
        direction_correct: bool | None = None
        if direction_eligible:
            direction_correct = (
                prediction.source == gold.source and prediction.target == gold.target
            )

        strict_edge_correct = edge_matches(prediction, gold)
        acceptable_match = any(
            edge_matches(prediction, expected) for expected in pair.accepted_edges
        )
        evidence_details, valid_spans, total_spans = exact_evidence_details(
            prediction, pair, lecture_texts
        )
        all_evidence_exact = total_spans > 0 and valid_spans == total_spans
        rationale_present = bool(prediction.rationale.strip())

        counters["evidence_valid"] += valid_spans
        counters["evidence_total"] += total_spans
        counters["invalid_evidence"] += total_spans - valid_spans
        if not rationale_present:
            counters["missing_rationale"] += 1
            errors.append({
                "pair_id": pair_id,
                "error_type": "missing_rationale",
            })
        if prediction.relation_type in GRAPH_RELATIONS and not prediction.evidence_spans:
            counters["missing_evidence"] += 1
            errors.append({
                "pair_id": pair_id,
                "error_type": "missing_evidence",
            })
        if prediction.relation_type == "NO_RELATION" and prediction.evidence_spans:
            counters["unexpected_no_relation_evidence"] += 1
            errors.append({
                "pair_id": pair_id,
                "error_type": "unexpected_evidence_for_no_relation",
            })
        for detail in evidence_details:
            if not detail["lecture_allowed"]:
                counters["evidence_outside_candidate"] += 1
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "evidence_lecture_outside_candidate",
                    **detail,
                })
            elif not detail["exact_substring"]:
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "invalid_evidence_span",
                    **detail,
                })

        if primary_scored:
            counters["primary_total"] += 1
            counters["strict_correct"] += int(strict_edge_correct)
            counters["type_correct"] += int(type_correct)
            counters["related_to_predictions"] += int(
                prediction.relation_type == "RELATED_TO"
            )
            if prediction.relation_type == "RELATED_TO" and gold.relation_type != "RELATED_TO":
                counters["related_to_overuse"] += 1
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "overused_related_to",
                    "gold_relation_type": gold.relation_type,
                })

            if pair.category == "positive":
                counters["positive_total"] += 1
                counters["positive_strict_correct"] += int(strict_edge_correct)
            if pair.category == "hard_negative":
                counters["no_relation_total"] += 1
                counters["no_relation_correct"] += int(
                    prediction.relation_type == "NO_RELATION"
                )

            if direction_eligible:
                counters["endpoint_direction_total"] += 1
                counters["endpoint_direction_correct"] += int(bool(direction_correct))
            if type_conditioned_direction_eligible:
                counters["conditioned_direction_total"] += 1
                counters["conditioned_direction_correct"] += int(
                    bool(direction_correct)
                )

            if gold.relation_type == "NO_RELATION" and prediction.relation_type in GRAPH_RELATIONS:
                counters["unsupported_relations"] += 1
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "false_positive_relation",
                    "predicted_relation_type": prediction.relation_type,
                })
            elif gold.relation_type in GRAPH_RELATIONS and prediction.relation_type == "NO_RELATION":
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "false_negative_relation",
                    "gold_relation_type": gold.relation_type,
                })

            if not type_correct:
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "wrong_relation_type",
                    "gold_relation_type": gold.relation_type,
                    "predicted_relation_type": prediction.relation_type,
                })
            elif direction_eligible and not direction_correct:
                errors.append({
                    "pair_id": pair_id,
                    "error_type": "wrong_direction",
                    "gold_edge": edge_json(gold),
                    "predicted_edge": edge_json(prediction.edge),
                })

        if pair.category == "ambiguous":
            counters["ambiguous_total"] += 1
            counters["ambiguous_acceptable"] += int(acceptable_match)
        if pair.category == "schema_gap":
            schema_gap_predictions.append({
                "pair_id": pair_id,
                "predicted_edge": edge_json(prediction.edge),
                "evidence_spans": prediction.evidence_spans,
                "rationale": prediction.rationale,
            })

        evidence_support_status: str | None = None
        if acceptable_match and prediction.relation_type in GRAPH_RELATIONS:
            predicted_evidence = canonical_evidence(prediction.evidence_spans)
            gold_evidence = canonical_evidence(pair.evidence_spans)
            if all_evidence_exact and predicted_evidence == gold_evidence:
                evidence_support_status = "auto_supported_by_gold_evidence"
            elif pair_id in adjudication:
                decision = adjudication[pair_id]
                evidence_support_status = decision.decision
                counters["manual_adjudications"] += 1
                used_adjudications.add(pair_id)
                if decision.decision == "not_supported":
                    errors.append({
                        "pair_id": pair_id,
                        "error_type": "evidence_does_not_support_relation",
                        "adjudication_rationale": decision.rationale,
                    })
            else:
                evidence_support_status = "pending_adjudication"
                pending.append({
                    "pair_id": pair_id,
                    "category": pair.category,
                    "predicted_edge": edge_json(prediction.edge),
                    "predicted_evidence_spans": prediction.evidence_spans,
                    "gold_evidence_spans": pair.evidence_spans,
                    "status": "pending",
                })

        matches.append({
            "pair_id": pair_id,
            "category": pair.category,
            "primary_scored": primary_scored,
            "gold_edge": edge_json(gold),
            "accepted_alternatives": [edge_json(edge) for edge in pair.alternatives],
            "predicted_edge": edge_json(prediction.edge),
            "unordered_candidate_pair_correct": True,
            "relation_type_correct": type_correct,
            "direction_eligible": direction_eligible,
            "direction_type_conditioned_eligible": (
                type_conditioned_direction_eligible
            ),
            "direction_correct": direction_correct,
            "strict_edge_correct": strict_edge_correct,
            "acceptable_alternative_match": acceptable_match,
            "rationale_present": rationale_present,
            "evidence": evidence_details,
            "evidence_support_status": evidence_support_status,
        })

    unused_adjudications = sorted(set(adjudication) - used_adjudications)
    if unused_adjudications:
        raise RuntimeError(
            "stale_or_unused_adjudication: decisions were not applied for "
            + ", ".join(unused_adjudications)
        )

    confusion = make_confusion_matrix(
        ground_truth, predictions, primary_categories
    )
    status = "draft_pending_adjudication" if pending else "final"
    category_counts = Counter(pair.category for pair in ground_truth.values())
    metrics = {
        "evaluation_status": status,
        "total_pairs": len(ground_truth),
        "primary_scored_pairs": counters["primary_total"],
        "positive_pairs": category_counts["positive"],
        "hard_negative_pairs": category_counts["hard_negative"],
        "ambiguous_pairs": category_counts["ambiguous"],
        "schema_gap_pairs": category_counts["schema_gap"],
        "strict_edge_accuracy": safe_divide(
            counters["strict_correct"], counters["primary_total"]
        ),
        "strict_edge_correct_count": counters["strict_correct"],
        "relation_type_accuracy_ignoring_direction": safe_divide(
            counters["type_correct"], counters["primary_total"]
        ),
        "relation_type_correct_count": counters["type_correct"],
        "endpoint_direction_accuracy": safe_divide(
            counters["endpoint_direction_correct"],
            counters["endpoint_direction_total"],
        ),
        "endpoint_direction_correct_count": counters[
            "endpoint_direction_correct"
        ],
        "endpoint_direction_scored_count": counters["endpoint_direction_total"],
        "direction_accuracy_when_type_correct": safe_divide(
            counters["conditioned_direction_correct"],
            counters["conditioned_direction_total"],
        ),
        "direction_when_type_correct_count": counters[
            "conditioned_direction_correct"
        ],
        "direction_when_type_correct_scored_count": counters[
            "conditioned_direction_total"
        ],
        "direction_accuracy": safe_divide(
            counters["endpoint_direction_correct"],
            counters["endpoint_direction_total"],
        ),
        "direction_correct_count": counters["endpoint_direction_correct"],
        "direction_scored_count": counters["endpoint_direction_total"],
        "positive_relation_accuracy": safe_divide(
            counters["positive_strict_correct"], counters["positive_total"]
        ),
        "positive_relation_correct_count": counters["positive_strict_correct"],
        "no_relation_accuracy": safe_divide(
            counters["no_relation_correct"], counters["no_relation_total"]
        ),
        "no_relation_correct_count": counters["no_relation_correct"],
        "acceptable_accuracy_ambiguous": safe_divide(
            counters["ambiguous_acceptable"], counters["ambiguous_total"]
        ),
        "ambiguous_acceptable_count": counters["ambiguous_acceptable"],
        "macro_f1_supported_labels": confusion["macro_f1_supported_labels"],
        "macro_f1_included_labels": confusion["macro_f1_included_labels"],
        "related_to_prediction_rate": safe_divide(
            counters["related_to_predictions"], counters["primary_total"]
        ),
        "related_to_overuse_count": counters["related_to_overuse"],
        "unsupported_relation_count": counters["unsupported_relations"],
        "exact_evidence_span_rate": safe_divide(
            counters["evidence_valid"], counters["evidence_total"]
        ),
        "exact_evidence_span_count": counters["evidence_valid"],
        "evidence_span_count": counters["evidence_total"],
        "invalid_evidence_span_count": counters["invalid_evidence"],
        "evidence_lecture_outside_candidate_count": counters[
            "evidence_outside_candidate"
        ],
        "missing_evidence_count": counters["missing_evidence"],
        "unexpected_no_relation_evidence_count": counters[
            "unexpected_no_relation_evidence"
        ],
        "missing_rationale_count": counters["missing_rationale"],
        "manual_adjudication_count": counters["manual_adjudications"],
        "pending_adjudication_count": len(pending),
        "schema_gap_predictions": schema_gap_predictions,
        "relation_coverage": ground_truth_data.get("relation_coverage", {}),
    }
    return metrics, matches, errors, confusion, pending


def summary_markdown(
    metrics: dict[str, Any],
    *,
    ground_truth_path: Path,
    predictions_path: Path,
) -> str:
    if metrics.get("evaluation_status") == "invalid":
        return (
            "# Relation Extraction Evaluation\n\n"
            "**Status:** Invalid\n\n"
            "Fatal prediction alignment errors prevented aggregate evaluation. "
            "See `errors.json`.\n"
        )

    def metric(name: str) -> str:
        value = metrics.get(name)
        return "n/a" if value is None else f"{value:.3f}"

    coverage = metrics.get("relation_coverage", {})
    coverage_lines = "\n".join(
        f"- `{label}`: {state}" for label, state in coverage.items()
    )
    return f"""# Relation Extraction Evaluation

**Status:** {metrics['evaluation_status']}
**Ground truth:** `{display_path(ground_truth_path)}`
**Predictions:** `{display_path(predictions_path)}`

## Primary Metrics

| Metric | Value |
| --- | ---: |
| Strict edge accuracy | {metric('strict_edge_accuracy')} |
| Relation type accuracy ignoring direction | {metric('relation_type_accuracy_ignoring_direction')} |
| Endpoint direction accuracy | {metric('endpoint_direction_accuracy')} |
| Direction accuracy when type correct | {metric('direction_accuracy_when_type_correct')} |
| Positive Relation accuracy | {metric('positive_relation_accuracy')} |
| NO_RELATION accuracy | {metric('no_relation_accuracy')} |

Primary-scored pairs: {metrics['primary_scored_pairs']} of {metrics['total_pairs']}.

## Grounding And Audit

| Metric | Value |
| --- | ---: |
| Exact evidence-span rate | {metric('exact_evidence_span_rate')} |
| Evidence outside candidate lectures | {metrics['evidence_lecture_outside_candidate_count']} |
| Missing evidence | {metrics['missing_evidence_count']} |
| Missing rationale | {metrics['missing_rationale_count']} |
| Pending adjudication | {metrics['pending_adjudication_count']} |
| RELATED_TO overuse | {metrics['related_to_overuse_count']} |

## Coverage Boundary

{coverage_lines}

Ambiguous and schema-gap pairs are excluded from primary metrics. Unsupported or low-support labels must not be interpreted as validated.
"""


def write_invalid_artifacts(
    evaluation_dir: Path,
    fatal_errors: list[dict[str, Any]],
    ground_truth_path: Path,
    predictions_path: Path,
) -> None:
    metrics = {
        "evaluation_status": "invalid",
        "fatal_error_count": len(fatal_errors),
        "aggregate_metrics_valid": False,
    }
    write_json(evaluation_dir / "metrics.json", metrics)
    write_json(evaluation_dir / "matches.json", [])
    write_json(evaluation_dir / "errors.json", fatal_errors)
    write_json(evaluation_dir / "confusion_matrix.json", {})
    write_json(evaluation_dir / "adjudication_pending.json", [])
    (evaluation_dir / "summary.md").write_text(
        summary_markdown(
            metrics,
            ground_truth_path=ground_truth_path,
            predictions_path=predictions_path,
        ),
        encoding="utf-8",
    )


def write_runtime_error_artifacts(
    evaluation_dir: Path,
    message: str,
    ground_truth_path: Path,
    predictions_path: Path,
) -> None:
    error_type = (
        "stale_or_unused_adjudication"
        if message.startswith("stale_or_unused_adjudication:")
        else "evaluation_runtime_error"
    )
    metrics = {
        "evaluation_status": "invalid",
        "fatal_error_count": 1,
        "aggregate_metrics_valid": False,
    }
    write_json(evaluation_dir / "metrics.json", metrics)
    write_json(evaluation_dir / "matches.json", [])
    write_json(
        evaluation_dir / "errors.json",
        [{
            "error_type": error_type,
            "message": message,
        }],
    )
    write_json(evaluation_dir / "confusion_matrix.json", {})
    write_json(evaluation_dir / "adjudication_pending.json", [])
    (evaluation_dir / "summary.md").write_text(
        summary_markdown(
            metrics,
            ground_truth_path=ground_truth_path,
            predictions_path=predictions_path,
        ),
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    ground_truth_path = resolve_path(args.ground_truth)
    predictions_path = resolve_path(args.predictions)
    evaluation_dir = resolve_path(args.evaluation_dir)
    adjudication_path = resolve_path(args.adjudication) if args.adjudication else None
    evaluation_dir.mkdir(parents=True, exist_ok=True)

    try:
        ground_truth, ground_truth_data, lecture_texts = load_ground_truth(
            ground_truth_path
        )
        predictions = load_predictions(predictions_path, ground_truth)
        adjudication = load_adjudication(adjudication_path)
        validate_adjudications(
            adjudication,
            ground_truth,
            predictions,
            lecture_texts,
        )
        metrics, matches, errors, confusion, pending = evaluate(
            ground_truth,
            ground_truth_data,
            predictions,
            lecture_texts,
            adjudication,
        )
    except FatalPredictionError as exc:
        write_invalid_artifacts(
            evaluation_dir,
            exc.errors,
            ground_truth_path,
            predictions_path,
        )
        print(
            f"Evaluation invalid: wrote fatal errors to {display_path(evaluation_dir)}",
            file=sys.stderr,
        )
        return 1
    except RuntimeError as exc:
        write_runtime_error_artifacts(
            evaluation_dir,
            str(exc),
            ground_truth_path,
            predictions_path,
        )
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    write_json(evaluation_dir / "metrics.json", metrics)
    write_json(evaluation_dir / "matches.json", matches)
    write_json(evaluation_dir / "errors.json", errors)
    write_json(evaluation_dir / "confusion_matrix.json", confusion)
    write_json(evaluation_dir / "adjudication_pending.json", pending)
    (evaluation_dir / "summary.md").write_text(
        summary_markdown(
            metrics,
            ground_truth_path=ground_truth_path,
            predictions_path=predictions_path,
        ),
        encoding="utf-8",
    )
    print(f"Wrote evaluation artifacts to {display_path(evaluation_dir)}")
    print(f"Evaluation status: {metrics['evaluation_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
