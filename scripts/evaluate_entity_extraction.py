#!/usr/bin/env python3
"""Evaluate entity extraction outputs against benchmark ground truth."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
ENTITY_EXTRACTION_DIR = ROOT / "experiments" / "entity_extraction"
ALLOWED_TYPES = {"Concept", "Method", "Formula"}
MANUAL_DECISIONS = {
    "matched",
    "not_matched",
    "unsupported",
    "granularity_error",
}
GENERATED_EVALUATION_ARTIFACTS = [
    "metrics.json",
    "matches.json",
    "summary.md",
    "adjudication_pending.json",
]

DASH_TRANSLATION = str.maketrans({
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
})
APOSTROPHE_TRANSLATION = str.maketrans({
    "‘": "'",
    "’": "'",
    "‛": "'",
    "`": "'",
    "´": "'",
})


@dataclass
class GroundTruthObject:
    lecture_id: str
    obj_id: str
    name: str
    obj_type: str
    category: str
    aliases: list[str]
    source_spans: list[str]


@dataclass
class Prediction:
    lecture_id: str
    index: int
    pred_id: str
    name: str
    obj_type: str
    source_span: str
    raw: dict[str, Any]


@dataclass
class ManualDecision:
    lecture_id: str
    prediction_index: int
    decision: str
    predicted_label: str | None
    ground_truth_id: str | None
    rationale: str


class EvaluationAbort(Exception):
    """Abort evaluation without writing aggregate metrics."""

    def __init__(self, message: str, error: dict[str, Any]) -> None:
        super().__init__(message)
        self.error = error


def normalize_label(label: str) -> str:
    normalized = unicodedata.normalize("NFKC", label)
    normalized = normalized.translate(APOSTROPHE_TRANSLATION)
    normalized = normalized.translate(DASH_TRANSLATION)
    normalized = normalized.strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.casefold()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate Knowledge Object extraction outputs."
    )
    parser.add_argument(
        "--experiment",
        required=True,
        help="Experiment directory under experiments/entity_extraction/.",
    )
    parser.add_argument(
        "--ground-truth",
        default="benchmark/ground_truth/development_v0_1.json",
        help="Ground-truth JSON path. Default: benchmark/ground_truth/development_v0_1.json",
    )
    parser.add_argument(
        "--predictions-dir",
        help="Directory containing prediction JSON files. Default: <experiment>/output.",
    )
    parser.add_argument(
        "--evaluation-dir",
        help="Directory for evaluation artifacts. Default: <experiment>/evaluation.",
    )
    parser.add_argument(
        "--adjudication",
        help=(
            "Optional manual adjudication JSON. Supports either a list of decisions "
            "or an object with a 'decisions' list."
        ),
    )
    return parser.parse_args()


def resolve_path(path_text: str | None, default: Path) -> Path:
    if not path_text:
        return default
    path = Path(path_text)
    if path.is_absolute():
        return path
    return ROOT / path


def resolve_adjudication_path(path_text: str | None, experiment_dir: Path, evaluation_dir: Path) -> Path | None:
    if not path_text:
        return None
    path = Path(path_text)
    if path.is_absolute():
        return path
    candidates = [
        ROOT / path,
        experiment_dir / path,
        evaluation_dir / path,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return ROOT / path


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


def load_ground_truth(path: Path) -> tuple[dict[str, list[GroundTruthObject]], dict[str, str], dict[str, Any]]:
    data = load_json(path)
    by_lecture: dict[str, list[GroundTruthObject]] = {}
    lecture_paths: dict[str, str] = {}

    for lecture in data.get("lectures", []):
        lecture_id = lecture["lecture_id"]
        lecture_paths[lecture_id] = lecture["path"]
        objects = []
        for obj in lecture["objects"]:
            objects.append(
                GroundTruthObject(
                    lecture_id=lecture_id,
                    obj_id=obj["id"],
                    name=obj["name"],
                    obj_type=obj["type"],
                    category=obj["category"],
                    aliases=list(obj.get("aliases", [])),
                    source_spans=list(obj.get("source_spans", [])),
                )
            )
        by_lecture[lecture_id] = objects

    return by_lecture, lecture_paths, data


def prediction_schema_error(
    *,
    output_path: Path,
    lecture_id: str,
    message: str,
    prediction_index: int | None = None,
) -> EvaluationAbort:
    error = {
        "lecture_id": lecture_id,
        "error_type": "invalid_prediction_schema",
        "output_path": display_path(output_path),
        "message": message,
    }
    if prediction_index is not None:
        error["prediction_index"] = prediction_index
    return EvaluationAbort(message, error)


def load_prediction_json(output_path: Path, lecture_id: str) -> dict[str, Any]:
    try:
        data = json.loads(output_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise prediction_schema_error(
            output_path=output_path,
            lecture_id=lecture_id,
            message=f"Prediction output is not valid JSON: {exc}",
        ) from exc

    if not isinstance(data, dict):
        raise prediction_schema_error(
            output_path=output_path,
            lecture_id=lecture_id,
            message="Prediction output must be a JSON object.",
        )

    output_lecture_id = data.get("lecture_id")
    if not isinstance(output_lecture_id, str) or not output_lecture_id.strip():
        raise prediction_schema_error(
            output_path=output_path,
            lecture_id=lecture_id,
            message="Prediction output must contain a non-empty string 'lecture_id'.",
        )
    if output_lecture_id != lecture_id:
        raise prediction_schema_error(
            output_path=output_path,
            lecture_id=lecture_id,
            message=f"Prediction lecture_id is {output_lecture_id!r}, expected {lecture_id!r}.",
        )

    if "knowledge_objects" not in data:
        raise prediction_schema_error(
            output_path=output_path,
            lecture_id=lecture_id,
            message="Prediction output is missing required key 'knowledge_objects'.",
        )
    if not isinstance(data["knowledge_objects"], list):
        raise prediction_schema_error(
            output_path=output_path,
            lecture_id=lecture_id,
            message="'knowledge_objects' must be a list.",
        )

    return data


def load_predictions(output_path: Path, lecture_id: str) -> list[Prediction]:
    data = load_prediction_json(output_path, lecture_id)
    predictions = []
    seen_ids: set[str] = set()

    for index, obj in enumerate(data["knowledge_objects"]):
        if not isinstance(obj, dict):
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message="Each knowledge object must be a JSON object.",
            )

        pred_id = obj.get("id")
        if not isinstance(pred_id, str) or not pred_id.strip():
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message="Each prediction must contain a non-empty string 'id'.",
            )
        if pred_id in seen_ids:
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message=f"Duplicate prediction id {pred_id!r} in the same lecture output.",
            )
        seen_ids.add(pred_id)

        name = obj.get("name")
        if not isinstance(name, str) or not name.strip():
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message="Each prediction must contain a non-empty string 'name'.",
            )

        obj_type = obj.get("type")
        if obj_type not in ALLOWED_TYPES:
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message=(
                    "Each prediction must contain a valid 'type': "
                    f"{sorted(ALLOWED_TYPES)}."
                ),
            )

        source_span = obj.get("source_span")
        if not isinstance(source_span, str):
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message="Each prediction must contain a string 'source_span'.",
            )

        aliases = obj.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message="'aliases' must be a list of strings when present.",
            )

        short_definition = obj.get("short_definition", "")
        if short_definition is not None and not isinstance(short_definition, str):
            raise prediction_schema_error(
                output_path=output_path,
                lecture_id=lecture_id,
                prediction_index=index,
                message="'short_definition' must be a string when present.",
            )

        predictions.append(
            Prediction(
                lecture_id=lecture_id,
                index=index,
                pred_id=pred_id,
                name=name,
                obj_type=obj_type,
                source_span=source_span,
                raw=obj,
            )
        )

    return predictions


def load_adjudication(path: Path | None) -> dict[tuple[str, int], ManualDecision]:
    if path is None:
        return {}
    if not path.is_file():
        raise RuntimeError(f"Missing adjudication file: {path}")

    data = load_json(path)
    if isinstance(data, dict):
        decisions = data.get("decisions")
    else:
        decisions = data
    if not isinstance(decisions, list):
        raise RuntimeError(
            f"{path}: adjudication must be a list or an object with a 'decisions' list."
        )

    by_prediction: dict[tuple[str, int], ManualDecision] = {}
    for index, item in enumerate(decisions):
        if not isinstance(item, dict):
            raise RuntimeError(f"{path}: adjudication decision {index} must be an object.")

        lecture_id = item.get("lecture_id")
        prediction_index = item.get("prediction_index")
        decision = item.get("decision")
        if not isinstance(lecture_id, str) or not lecture_id.strip():
            raise RuntimeError(f"{path}: decision {index} has invalid lecture_id.")
        if not isinstance(prediction_index, int):
            raise RuntimeError(f"{path}: decision {index} has invalid prediction_index.")
        if decision not in MANUAL_DECISIONS:
            raise RuntimeError(
                f"{path}: decision {index} has invalid decision {decision!r}."
            )

        ground_truth_id = item.get("ground_truth_id")
        if decision == "matched" and (
            not isinstance(ground_truth_id, str) or not ground_truth_id.strip()
        ):
            raise RuntimeError(
                f"{path}: matched decision {index} must include ground_truth_id."
            )
        if decision == "granularity_error" and (
            not isinstance(ground_truth_id, str) or not ground_truth_id.strip()
        ):
            raise RuntimeError(
                f"{path}: granularity_error decision {index} must include ground_truth_id."
            )
        if ground_truth_id is not None and not isinstance(ground_truth_id, str):
            raise RuntimeError(f"{path}: decision {index} has invalid ground_truth_id.")

        predicted_label = item.get("predicted_label")
        if predicted_label is not None and not isinstance(predicted_label, str):
            raise RuntimeError(f"{path}: decision {index} has invalid predicted_label.")

        rationale = item.get("rationale", "")
        if not isinstance(rationale, str):
            raise RuntimeError(f"{path}: decision {index} has invalid rationale.")

        key = (lecture_id, prediction_index)
        if key in by_prediction:
            raise RuntimeError(f"{path}: duplicate adjudication decision for {key}.")

        by_prediction[key] = ManualDecision(
            lecture_id=lecture_id,
            prediction_index=prediction_index,
            decision=decision,
            predicted_label=predicted_label,
            ground_truth_id=ground_truth_id,
            rationale=rationale,
        )

    return by_prediction


def build_match_indexes(gt_objects: list[GroundTruthObject]) -> tuple[dict[str, str], dict[str, str]]:
    canonical_index: dict[str, str] = {}
    alias_index: dict[str, str] = {}

    for obj in gt_objects:
        canonical_index[normalize_label(obj.name)] = obj.obj_id
        for alias in obj.aliases:
            alias_index[normalize_label(alias)] = obj.obj_id

    return canonical_index, alias_index


def make_pending_adjudication(prediction: Prediction) -> dict[str, Any]:
    return {
        "lecture_id": prediction.lecture_id,
        "prediction_index": prediction.index,
        "predicted_id": prediction.pred_id,
        "predicted_label": prediction.name,
        "predicted_type": prediction.obj_type,
        "candidate_ground_truth_ids": [],
        "status": "pending",
    }


def evaluate_unmatched_prediction(
    *,
    prediction: Prediction,
    manual_decision: ManualDecision | None,
    source_span_exact: bool,
    pending_adjudications: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    errors: list[dict[str, Any]],
) -> tuple[int, int, int]:
    """Return false positives, unsupported count, manual matches for an unmatched prediction."""

    if manual_decision and manual_decision.decision in {"not_matched", "unsupported"}:
        errors.append({
            "lecture_id": prediction.lecture_id,
            "prediction_index": prediction.index,
            "predicted_id": prediction.pred_id,
            "predicted_label": prediction.name,
            "predicted_type": prediction.obj_type,
            "error_type": "unsupported_object",
            "adjudication_decision": manual_decision.decision,
            "rationale": manual_decision.rationale,
        })
        matches.append({
            "lecture_id": prediction.lecture_id,
            "prediction_index": prediction.index,
            "predicted_id": prediction.pred_id,
            "predicted_label": prediction.name,
            "predicted_type": prediction.obj_type,
            "ground_truth_id": None,
            "ground_truth_label": None,
            "ground_truth_type": None,
            "ground_truth_category": None,
            "match_type": "manual",
            "decision": manual_decision.decision,
            "source_span_exact": source_span_exact,
        })
        return 1, 1, 0

    if manual_decision and manual_decision.decision == "granularity_error":
        errors.append({
            "lecture_id": prediction.lecture_id,
            "prediction_index": prediction.index,
            "predicted_id": prediction.pred_id,
            "predicted_label": prediction.name,
            "predicted_type": prediction.obj_type,
            "ground_truth_id": manual_decision.ground_truth_id,
            "error_type": "granularity_error",
            "rationale": manual_decision.rationale,
        })
        matches.append({
            "lecture_id": prediction.lecture_id,
            "prediction_index": prediction.index,
            "predicted_id": prediction.pred_id,
            "predicted_label": prediction.name,
            "predicted_type": prediction.obj_type,
            "ground_truth_id": manual_decision.ground_truth_id,
            "ground_truth_label": None,
            "ground_truth_type": None,
            "ground_truth_category": None,
            "match_type": "manual",
            "decision": "granularity_error",
            "source_span_exact": source_span_exact,
        })
        return 1, 1, 0

    pending_adjudications.append(make_pending_adjudication(prediction))
    errors.append({
        "lecture_id": prediction.lecture_id,
        "prediction_index": prediction.index,
        "predicted_id": prediction.pred_id,
        "predicted_label": prediction.name,
        "predicted_type": prediction.obj_type,
        "error_type": "unsupported_object",
        "requires_adjudication": True,
    })
    matches.append({
        "lecture_id": prediction.lecture_id,
        "prediction_index": prediction.index,
        "predicted_id": prediction.pred_id,
        "predicted_label": prediction.name,
        "predicted_type": prediction.obj_type,
        "ground_truth_id": None,
        "ground_truth_label": None,
        "ground_truth_type": None,
        "ground_truth_category": None,
        "match_type": None,
        "decision": "adjudication_pending",
        "source_span_exact": source_span_exact,
    })
    return 1, 1, 0


def evaluate_lecture(
    *,
    lecture_id: str,
    gt_objects: list[GroundTruthObject],
    predictions: list[Prediction],
    lecture_text: str,
    manual_decisions: dict[tuple[str, int], ManualDecision],
    used_manual_decisions: set[tuple[str, int]],
    pending_adjudications: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    gt_by_id = {obj.obj_id: obj for obj in gt_objects}
    canonical_index, alias_index = build_match_indexes(gt_objects)
    matched_gt_ids: set[str] = set()
    matches: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    required_total = sum(1 for obj in gt_objects if obj.category == "required")
    optional_total = sum(1 for obj in gt_objects if obj.category == "optional")
    excluded_total = sum(1 for obj in gt_objects if obj.category == "excluded")
    required_tp = 0
    false_positives = 0
    correctly_typed_required = 0
    required_matches = 0
    matched_optional = 0
    optional_type_errors = 0
    unsupported_count = 0
    duplicate_count = 0
    excluded_extracted_count = 0
    invalid_source_span_count = 0
    exact_source_span_count = 0
    manual_match_count = 0

    for prediction in predictions:
        normalized = normalize_label(prediction.name)
        candidate_id = canonical_index.get(normalized)
        match_type = "exact" if candidate_id else None
        if not candidate_id:
            candidate_id = alias_index.get(normalized)
            match_type = "alias" if candidate_id else None

        decision_key = (lecture_id, prediction.index)
        manual_decision = manual_decisions.get(decision_key)
        if manual_decision and manual_decision.predicted_label is not None:
            if normalize_label(manual_decision.predicted_label) != normalize_label(prediction.name):
                raise RuntimeError(
                    "Manual adjudication predicted_label does not match prediction "
                    f"for {lecture_id} index {prediction.index}: "
                    f"{manual_decision.predicted_label!r} != {prediction.name!r}."
                )
        if manual_decision and candidate_id:
            raise RuntimeError(
                "Manual adjudication was provided for an automatically matched prediction "
                f"({lecture_id} index {prediction.index}). Remove the stale decision."
            )
        if not candidate_id and manual_decision and manual_decision.decision == "matched":
            candidate_id = manual_decision.ground_truth_id
            match_type = "manual"
            used_manual_decisions.add(decision_key)
            if candidate_id not in gt_by_id:
                raise RuntimeError(
                    f"Manual adjudication references unknown ground_truth_id {candidate_id!r} "
                    f"for {lecture_id} prediction {prediction.index}."
                )
        elif not candidate_id and manual_decision:
            used_manual_decisions.add(decision_key)

        source_span_exact = bool(prediction.source_span) and prediction.source_span in lecture_text
        if source_span_exact:
            exact_source_span_count += 1
        else:
            invalid_source_span_count += 1
            errors.append({
                "lecture_id": lecture_id,
                "prediction_index": prediction.index,
                "predicted_id": prediction.pred_id,
                "predicted_label": prediction.name,
                "error_type": "invalid_source_span",
                "source_span": prediction.source_span,
            })

        if candidate_id and candidate_id in matched_gt_ids:
            duplicate_count += 1
            false_positives += 1
            errors.append({
                "lecture_id": lecture_id,
                "prediction_index": prediction.index,
                "predicted_id": prediction.pred_id,
                "predicted_label": prediction.name,
                "ground_truth_id": candidate_id,
                "error_type": "duplicate_object",
            })
            matches.append({
                "lecture_id": lecture_id,
                "prediction_index": prediction.index,
                "predicted_id": prediction.pred_id,
                "predicted_label": prediction.name,
                "predicted_type": prediction.obj_type,
                "ground_truth_id": candidate_id,
                "ground_truth_label": gt_by_id[candidate_id].name,
                "ground_truth_type": gt_by_id[candidate_id].obj_type,
                "ground_truth_category": gt_by_id[candidate_id].category,
                "match_type": match_type,
                "decision": "duplicate",
                "source_span_exact": source_span_exact,
            })
            continue

        if not candidate_id:
            fp_delta, unsupported_delta, _manual_delta = evaluate_unmatched_prediction(
                prediction=prediction,
                manual_decision=manual_decision,
                source_span_exact=source_span_exact,
                pending_adjudications=pending_adjudications,
                matches=matches,
                errors=errors,
            )
            false_positives += fp_delta
            unsupported_count += unsupported_delta
            continue

        gt_obj = gt_by_id[candidate_id]
        matched_gt_ids.add(candidate_id)
        type_correct = prediction.obj_type == gt_obj.obj_type

        if gt_obj.category == "required":
            required_tp += 1
            required_matches += 1
            if match_type == "manual":
                manual_match_count += 1
            if type_correct:
                correctly_typed_required += 1
            else:
                errors.append({
                    "lecture_id": lecture_id,
                    "prediction_index": prediction.index,
                    "predicted_id": prediction.pred_id,
                    "predicted_label": prediction.name,
                    "predicted_type": prediction.obj_type,
                    "ground_truth_id": gt_obj.obj_id,
                    "ground_truth_type": gt_obj.obj_type,
                    "error_type": "wrong_type",
                })
        elif gt_obj.category == "optional":
            matched_optional += 1
            if match_type == "manual":
                manual_match_count += 1
            if not type_correct:
                optional_type_errors += 1
                errors.append({
                    "lecture_id": lecture_id,
                    "prediction_index": prediction.index,
                    "predicted_id": prediction.pred_id,
                    "predicted_label": prediction.name,
                    "predicted_type": prediction.obj_type,
                    "ground_truth_id": gt_obj.obj_id,
                    "ground_truth_type": gt_obj.obj_type,
                    "error_type": "optional_type_error",
                })
        elif gt_obj.category == "excluded":
            excluded_extracted_count += 1
            false_positives += 1
            errors.append({
                "lecture_id": lecture_id,
                "prediction_index": prediction.index,
                "predicted_id": prediction.pred_id,
                "predicted_label": prediction.name,
                "ground_truth_id": gt_obj.obj_id,
                "error_type": "excluded_object_extracted",
            })

        matches.append({
            "lecture_id": lecture_id,
            "prediction_index": prediction.index,
            "predicted_id": prediction.pred_id,
            "predicted_label": prediction.name,
            "predicted_type": prediction.obj_type,
            "ground_truth_id": gt_obj.obj_id,
            "ground_truth_label": gt_obj.name,
            "ground_truth_type": gt_obj.obj_type,
            "ground_truth_category": gt_obj.category,
            "match_type": match_type,
            "decision": "matched",
            "type_correct": type_correct,
            "source_span_exact": source_span_exact,
        })

    unmatched_required = [
        obj for obj in gt_objects
        if obj.category == "required" and obj.obj_id not in matched_gt_ids
    ]
    for obj in unmatched_required:
        errors.append({
            "lecture_id": lecture_id,
            "ground_truth_id": obj.obj_id,
            "ground_truth_label": obj.name,
            "error_type": "missing_required_object",
        })

    false_negatives = len(unmatched_required)
    precision_denominator = required_tp + false_positives
    required_precision = required_tp / precision_denominator if precision_denominator else math.nan
    required_recall = required_tp / required_total if required_total else math.nan
    if required_precision + required_recall:
        required_f1 = 2 * required_precision * required_recall / (required_precision + required_recall)
    else:
        required_f1 = math.nan
    type_accuracy = (
        correctly_typed_required / required_matches if required_matches else math.nan
    )
    exact_source_span_rate = (
        exact_source_span_count / len(predictions) if predictions else math.nan
    )

    metrics = {
        "lecture_id": lecture_id,
        "required_total": required_total,
        "optional_total": optional_total,
        "excluded_total": excluded_total,
        "prediction_total": len(predictions),
        "required_true_positives": required_tp,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "required_precision": required_precision,
        "required_recall": required_recall,
        "required_f1": required_f1,
        "required_matches": required_matches,
        "correctly_typed_required_matches": correctly_typed_required,
        "type_accuracy_required": type_accuracy,
        "matched_optional": matched_optional,
        "optional_type_errors": optional_type_errors,
        "unsupported_objects": unsupported_count,
        "duplicate_objects": duplicate_count,
        "excluded_objects_extracted": excluded_extracted_count,
        "manual_matches": manual_match_count,
        "unresolved_adjudications": sum(
            1 for item in pending_adjudications if item["lecture_id"] == lecture_id
        ),
        "exact_source_spans": exact_source_span_count,
        "invalid_source_spans": invalid_source_span_count,
        "exact_source_span_rate": exact_source_span_rate,
    }

    return matches, errors, metrics


def aggregate_metrics(per_lecture: list[dict[str, Any]]) -> dict[str, Any]:
    totals: dict[str, Any] = {
        "required_total": 0,
        "optional_total": 0,
        "excluded_total": 0,
        "prediction_total": 0,
        "required_true_positives": 0,
        "false_positives": 0,
        "false_negatives": 0,
        "required_matches": 0,
        "correctly_typed_required_matches": 0,
        "matched_optional": 0,
        "optional_type_errors": 0,
        "unsupported_objects": 0,
        "duplicate_objects": 0,
        "excluded_objects_extracted": 0,
        "manual_matches": 0,
        "unresolved_adjudications": 0,
        "exact_source_spans": 0,
        "invalid_source_spans": 0,
    }
    for metrics in per_lecture:
        for key in totals:
            totals[key] += metrics[key]

    precision_denominator = totals["required_true_positives"] + totals["false_positives"]
    totals["required_precision"] = (
        totals["required_true_positives"] / precision_denominator
        if precision_denominator
        else math.nan
    )
    totals["required_recall"] = (
        totals["required_true_positives"] / totals["required_total"]
        if totals["required_total"]
        else math.nan
    )
    if totals["required_precision"] + totals["required_recall"]:
        totals["required_f1"] = (
            2
            * totals["required_precision"]
            * totals["required_recall"]
            / (totals["required_precision"] + totals["required_recall"])
        )
    else:
        totals["required_f1"] = math.nan
    totals["type_accuracy_required"] = (
        totals["correctly_typed_required_matches"] / totals["required_matches"]
        if totals["required_matches"]
        else math.nan
    )
    totals["exact_source_span_rate"] = (
        totals["exact_source_spans"] / totals["prediction_total"]
        if totals["prediction_total"]
        else math.nan
    )
    return totals


def validate_manual_decisions(
    *,
    manual_decisions: dict[tuple[str, int], ManualDecision],
    gt_by_lecture: dict[str, list[GroundTruthObject]],
    predictions_by_lecture: dict[str, list[Prediction]],
    used_manual_decisions: set[tuple[str, int]],
) -> None:
    for key, decision in manual_decisions.items():
        lecture_id, prediction_index = key
        if lecture_id not in gt_by_lecture:
            raise RuntimeError(
                f"Manual adjudication references unknown lecture_id {lecture_id!r}."
            )
        predictions = predictions_by_lecture.get(lecture_id, [])
        if prediction_index < 0 or prediction_index >= len(predictions):
            raise RuntimeError(
                "Manual adjudication references missing prediction index "
                f"{prediction_index} for {lecture_id}."
            )
        if decision.ground_truth_id is not None:
            gt_ids = {obj.obj_id for obj in gt_by_lecture[lecture_id]}
            if decision.ground_truth_id not in gt_ids:
                raise RuntimeError(
                    "Manual adjudication references unknown ground_truth_id "
                    f"{decision.ground_truth_id!r} for {lecture_id}."
                )
        prediction = predictions[prediction_index]
        if decision.predicted_label is not None:
            if normalize_label(decision.predicted_label) != normalize_label(prediction.name):
                raise RuntimeError(
                    "Manual adjudication predicted_label does not match prediction "
                    f"for {lecture_id} index {prediction_index}: "
                    f"{decision.predicted_label!r} != {prediction.name!r}."
                )
        if key not in used_manual_decisions:
            raise RuntimeError(
                "Manual adjudication decision was not used by evaluation. "
                f"Remove stale decision for {lecture_id} index {prediction_index}."
            )


def clean_for_json(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, dict):
        return {key: clean_for_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [clean_for_json(item) for item in value]
    return value


def format_metric(value: Any) -> str:
    if isinstance(value, float):
        if math.isnan(value):
            return "N/A"
        return f"{value:.3f}"
    return str(value)


def write_summary(
    *,
    path: Path,
    experiment: str,
    ground_truth_path: Path,
    predictions_dir: Path,
    adjudication_path: Path | None,
    per_lecture_metrics: list[dict[str, Any]],
    aggregate: dict[str, Any],
) -> None:
    lines = [
        "# Entity Extraction Evaluation Summary",
        "",
        f"**Experiment:** `{experiment}`",
        f"**Ground Truth:** `{display_path(ground_truth_path)}`",
        f"**Predictions:** `{display_path(predictions_dir)}`",
        f"**Adjudication:** `{display_path(adjudication_path)}`" if adjudication_path else "**Adjudication:** none",
        f"**Evaluation Status:** `{aggregate['evaluation_status']}`",
        "",
        "# Aggregate Metrics",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key in [
        "required_precision",
        "required_recall",
        "required_f1",
        "type_accuracy_required",
        "required_true_positives",
        "false_positives",
        "false_negatives",
        "matched_optional",
        "optional_type_errors",
        "unsupported_objects",
        "duplicate_objects",
        "manual_matches",
        "unresolved_adjudications",
        "exact_source_span_rate",
        "exact_source_spans",
        "invalid_source_spans",
    ]:
        lines.append(f"| `{key}` | {format_metric(aggregate[key])} |")

    lines.extend([
        "",
        "# Per-Lecture Metrics",
        "",
        "| Lecture | Required Precision | Required Recall | Type Accuracy | Exact Span Rate | Unsupported | Optional Matched | Pending |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])
    for metrics in per_lecture_metrics:
        lines.append(
            "| "
            f"`{metrics['lecture_id']}` | "
            f"{format_metric(metrics['required_precision'])} | "
            f"{format_metric(metrics['required_recall'])} | "
            f"{format_metric(metrics['type_accuracy_required'])} | "
            f"{format_metric(metrics['exact_source_span_rate'])} | "
            f"{metrics['unsupported_objects']} | "
            f"{metrics['matched_optional']} | "
            f"{metrics['unresolved_adjudications']} |"
        )

    lines.extend([
        "",
        "# Notes",
        "",
        "The evaluator reports metrics only. It does not declare a winning prompt.",
        "Exact and alias matches are automatic. Other semantic matches require manual adjudication.",
    ])
    if aggregate["unresolved_adjudications"]:
        lines.append(
            "This run has unresolved adjudication items. Treat the metrics as an automatic draft until `adjudication_pending.json` is resolved and the evaluator is rerun with `--adjudication`."
        )
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_abort_errors(evaluation_dir: Path, error: dict[str, Any]) -> None:
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    for filename in GENERATED_EVALUATION_ARTIFACTS:
        (evaluation_dir / filename).unlink(missing_ok=True)
    (evaluation_dir / "errors.json").write_text(
        json.dumps([clean_for_json(error)], indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_missing_output_errors(evaluation_dir: Path, missing_outputs: list[Path]) -> None:
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    for filename in GENERATED_EVALUATION_ARTIFACTS:
        (evaluation_dir / filename).unlink(missing_ok=True)
    errors = [
        {
            "error_type": "missing_output_file",
            "output_path": display_path(path),
        }
        for path in missing_outputs
    ]
    (evaluation_dir / "errors.json").write_text(
        json.dumps(errors, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    args = parse_args()
    experiment_dir = ENTITY_EXTRACTION_DIR / args.experiment
    predictions_dir = resolve_path(args.predictions_dir, experiment_dir / "output")
    evaluation_dir = resolve_path(args.evaluation_dir, experiment_dir / "evaluation")
    ground_truth_path = resolve_path(args.ground_truth, ROOT / "benchmark" / "ground_truth" / "development_v0_1.json")
    adjudication_path = resolve_adjudication_path(args.adjudication, experiment_dir, evaluation_dir)

    if not predictions_dir.is_dir():
        print(f"Missing predictions directory: {predictions_dir}", file=sys.stderr)
        return 2
    if not ground_truth_path.is_file():
        print(f"Missing ground-truth file: {ground_truth_path}", file=sys.stderr)
        return 2

    gt_by_lecture, lecture_paths, gt_data = load_ground_truth(ground_truth_path)
    manual_decisions = load_adjudication(adjudication_path)

    missing_outputs = [
        predictions_dir / f"{lecture_id}.json"
        for lecture_id in gt_by_lecture
        if not (predictions_dir / f"{lecture_id}.json").is_file()
    ]
    if missing_outputs:
        write_missing_output_errors(evaluation_dir, missing_outputs)
        print("Missing prediction output files:", file=sys.stderr)
        for path in missing_outputs:
            print(f"- {path}", file=sys.stderr)
        return 2

    all_matches: list[dict[str, Any]] = []
    all_errors: list[dict[str, Any]] = []
    pending_adjudications: list[dict[str, Any]] = []
    per_lecture_metrics: list[dict[str, Any]] = []
    predictions_by_lecture: dict[str, list[Prediction]] = {}
    used_manual_decisions: set[tuple[str, int]] = set()

    try:
        for lecture_id, gt_objects in gt_by_lecture.items():
            output_path = predictions_dir / f"{lecture_id}.json"
            lecture_text = (ROOT / lecture_paths[lecture_id]).read_text(encoding="utf-8")
            predictions = load_predictions(output_path, lecture_id)
            predictions_by_lecture[lecture_id] = predictions
            matches, errors, metrics = evaluate_lecture(
                lecture_id=lecture_id,
                gt_objects=gt_objects,
                predictions=predictions,
                lecture_text=lecture_text,
                manual_decisions=manual_decisions,
                used_manual_decisions=used_manual_decisions,
                pending_adjudications=pending_adjudications,
            )
            all_matches.extend(matches)
            all_errors.extend(errors)
            per_lecture_metrics.append(metrics)
    except EvaluationAbort as exc:
        write_abort_errors(evaluation_dir, exc.error)
        print(f"Evaluation aborted: {exc}", file=sys.stderr)
        print(f"Wrote schema error to {evaluation_dir / 'errors.json'}", file=sys.stderr)
        return 2

    validate_manual_decisions(
        manual_decisions=manual_decisions,
        gt_by_lecture=gt_by_lecture,
        predictions_by_lecture=predictions_by_lecture,
        used_manual_decisions=used_manual_decisions,
    )

    aggregate = aggregate_metrics(per_lecture_metrics)
    aggregate["evaluation_status"] = (
        "draft_pending_adjudication"
        if aggregate["unresolved_adjudications"]
        else "final"
    )
    metrics_payload = {
        "experiment": args.experiment,
        "evaluation_status": aggregate["evaluation_status"],
        "ground_truth": display_path(ground_truth_path),
        "ground_truth_version": gt_data.get("version"),
        "ground_truth_split": gt_data.get("split"),
        "predictions_dir": display_path(predictions_dir),
        "adjudication": display_path(adjudication_path) if adjudication_path else None,
        "aggregate": aggregate,
        "by_lecture": per_lecture_metrics,
    }

    evaluation_dir.mkdir(parents=True, exist_ok=True)
    (evaluation_dir / "metrics.json").write_text(
        json.dumps(clean_for_json(metrics_payload), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (evaluation_dir / "matches.json").write_text(
        json.dumps(clean_for_json(all_matches), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (evaluation_dir / "errors.json").write_text(
        json.dumps(clean_for_json(all_errors), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (evaluation_dir / "adjudication_pending.json").write_text(
        json.dumps(clean_for_json(pending_adjudications), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_summary(
        path=evaluation_dir / "summary.md",
        experiment=args.experiment,
        ground_truth_path=ground_truth_path,
        predictions_dir=predictions_dir,
        adjudication_path=adjudication_path,
        per_lecture_metrics=per_lecture_metrics,
        aggregate=aggregate,
    )

    print(f"Wrote evaluation artifacts to {display_path(evaluation_dir)}")
    if pending_adjudications:
        print(
            f"Pending adjudication items: {len(pending_adjudications)} "
            f"({display_path(evaluation_dir / 'adjudication_pending.json')})"
        )
    return 0


def evaluation_dir_from_cli() -> Path | None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--experiment")
    parser.add_argument("--evaluation-dir")
    namespace, _unknown = parser.parse_known_args()
    if not namespace.experiment:
        return None
    experiment_dir = ENTITY_EXTRACTION_DIR / namespace.experiment
    return resolve_path(namespace.evaluation_dir, experiment_dir / "evaluation")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as exc:
        evaluation_dir = evaluation_dir_from_cli()
        if evaluation_dir:
            write_abort_errors(
                evaluation_dir,
                {
                    "error_type": "evaluation_runtime_error",
                    "message": str(exc),
                },
            )
            print(f"Wrote runtime error to {display_path(evaluation_dir / 'errors.json')}", file=sys.stderr)
        print(f"Evaluation aborted: {exc}", file=sys.stderr)
        raise SystemExit(2)
