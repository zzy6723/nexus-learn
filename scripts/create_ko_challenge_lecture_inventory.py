#!/usr/bin/env python3
"""Create a hash-bound lecture inventory from authored Markdown challenge files."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LECTURE_DIR = (
    ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1" / "lectures"
)
DEFAULT_OUTPUT = (
    ROOT / "benchmark" / "ko_canonicalization" / "challenge_v0_1" / "lecture_inventory.json"
)


class ChallengeLectureInventoryError(ValueError):
    """Raised when authored lecture files cannot define a valid inventory."""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lecture-dir", default=str(DEFAULT_LECTURE_DIR))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--split", default="development")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args(argv)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def display_path(path: Path) -> str:
    path = path.resolve()
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def model_text(markdown: str) -> str:
    lines = markdown.splitlines()
    if not lines or not lines[0].startswith("# "):
        raise ChallengeLectureInventoryError(
            "Every challenge lecture must start with one Markdown H1."
        )
    body = "\n".join(lines[1:]).strip()
    if not body:
        raise ChallengeLectureInventoryError("Challenge lecture body is empty.")
    return body + "\n"


def build_inventory(
    lecture_dir: Path,
    *,
    split: str,
) -> dict[str, Any]:
    paths = sorted(lecture_dir.glob("*.md"), key=lambda path: path.stem)
    if not paths:
        raise ChallengeLectureInventoryError("No Markdown lecture files found.")
    sources: list[dict[str, str]] = []
    lectures: list[dict[str, str]] = []
    for path in paths:
        raw = path.read_bytes()
        try:
            markdown = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ChallengeLectureInventoryError(f"Lecture is not UTF-8: {path}") from exc
        text = model_text(markdown)
        lecture_id = path.stem
        sources.append(
            {
                "lecture_id": lecture_id,
                "path": display_path(path),
                "markdown_sha256": sha256_bytes(raw),
                "model_text_sha256": sha256_bytes(text.encode("utf-8")),
            }
        )
        lectures.append({"lecture_id": lecture_id, "text": text})
    return {
        "artifact_type": "predicted_ko_relation_lecture_inventory",
        "version": "v0.1",
        "split": split,
        "scope": "002C-2_authored_development_challenge",
        "sources": sources,
        "lectures": lectures,
    }


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
            temporary_path = Path(handle.name)
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    lecture_dir = Path(args.lecture_dir).resolve()
    output_path = Path(args.output).resolve()
    try:
        if output_path.exists() and not args.overwrite:
            raise ChallengeLectureInventoryError(
                f"Refusing to overwrite: {display_path(output_path)}"
            )
        inventory = build_inventory(lecture_dir, split=args.split)
        atomic_write(output_path, inventory)
    except (OSError, ChallengeLectureInventoryError) as exc:
        print(f"Challenge lecture inventory failed: {exc}")
        return 1
    print(
        f"Wrote {len(inventory['lectures'])} challenge lectures to "
        f"{display_path(output_path)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
