#!/usr/bin/env python3
"""Run entity extraction experiments against the DeepSeek Chat Completions API."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENTITY_EXTRACTION_DIR = ROOT / "experiments" / "entity_extraction"

DEFAULT_MODEL = "deepseek-v4-flash"
BASE_URL = "https://api.deepseek.com/chat/completions"

PROMPT_FILENAMES = {
    "calculus_001": "calculus_001_prompt.md",
    "linear_algebra_001": "linear_algebra_001_prompt.md",
    "optimisation_001": "optimisation_001_prompt.md",
}


SYSTEM_PROMPT = """You extract structured Knowledge Objects from STEM learning materials.

A Knowledge Object is a meaningful educational entity, such as a concept, method, or formula, that may later participate in typed learning relations.

Return only valid JSON. Do not include markdown fences, commentary, or explanations.
"""


def load_dotenv() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Knowledge Object extraction using DeepSeek."
    )
    parser.add_argument(
        "--experiment",
        default="001_baseline",
        help="Experiment directory under experiments/entity_extraction/. Default: 001_baseline",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("DEEPSEEK_MODEL", DEFAULT_MODEL),
        help=f"DeepSeek model name. Default: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.0,
        help="Sampling temperature. Default: 0.0",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=4096,
        help="Maximum output tokens per request. Default: 4096",
    )
    parser.add_argument(
        "--only",
        choices=sorted(PROMPT_FILENAMES.keys()),
        help="Run only one lecture prompt.",
    )
    return parser.parse_args()


def call_deepseek(
    *,
    api_key: str,
    model: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> dict:
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }

    request = urllib.request.Request(
        BASE_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DeepSeek API returned HTTP {exc.code}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to reach DeepSeek API: {exc}") from exc


def extract_content(api_response: dict) -> str:
    try:
        return api_response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Unexpected DeepSeek response shape.") from exc


def write_json_output(output_dir: Path, lecture_id: str, content: str) -> None:
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        bad_path = output_dir / f"{lecture_id}.raw.txt"
        bad_path.write_text(content, encoding="utf-8")
        raise RuntimeError(
            f"Model output for {lecture_id} was not valid JSON. "
            f"Raw output saved to {bad_path}."
        ) from exc

    output_path = output_dir / f"{lecture_id}.json"
    output_path.write_text(
        json.dumps(parsed, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def write_metadata(
    *,
    metadata_dir: Path,
    lecture_id: str,
    api_response: dict,
    model: str,
    temperature: float,
    max_tokens: int,
) -> None:
    metadata_dir.mkdir(parents=True, exist_ok=True)
    metadata = {
        "lecture_id": lecture_id,
        "model_requested": model,
        "model_returned": api_response.get("model"),
        "system_fingerprint": api_response.get("system_fingerprint"),
        "temperature": temperature,
        "max_tokens": max_tokens,
        "created": api_response.get("created"),
        "usage": api_response.get("usage"),
        "run_time_unix": int(time.time()),
    }
    metadata_path = metadata_dir / f"{lecture_id}.json"
    metadata_path.write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    load_dotenv()
    args = parse_args()

    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        print(
            "DEEPSEEK_API_KEY is not set. Set it in your shell or in a local .env file.",
            file=sys.stderr,
        )
        return 2

    experiment_dir = ENTITY_EXTRACTION_DIR / args.experiment
    input_dir = experiment_dir / "input"
    output_dir = experiment_dir / "output"
    metadata_dir = experiment_dir / "metadata"

    prompts = {
        lecture_id: input_dir / filename
        for lecture_id, filename in PROMPT_FILENAMES.items()
    }
    if args.only:
        prompts = {args.only: prompts[args.only]}

    missing_prompts = [str(path) for path in prompts.values() if not path.exists()]
    if missing_prompts:
        print("Missing prompt files:", file=sys.stderr)
        for path in missing_prompts:
            print(f"- {path}", file=sys.stderr)
        return 2

    output_dir.mkdir(parents=True, exist_ok=True)

    for lecture_id, prompt_path in prompts.items():
        print(f"Running {lecture_id} with {args.model}...")
        prompt = prompt_path.read_text(encoding="utf-8")
        response = call_deepseek(
            api_key=api_key,
            model=args.model,
            prompt=prompt,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        content = extract_content(response)
        write_json_output(output_dir, lecture_id, content)
        write_metadata(
            metadata_dir=metadata_dir,
            lecture_id=lecture_id,
            api_response=response,
            model=args.model,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        print(f"Saved output/{lecture_id}.json")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
