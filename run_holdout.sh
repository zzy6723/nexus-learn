#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_ROOT"

python3 scripts/run_entity_extraction.py \
  --experiment 001_baseline \
  --split holdout \
  --model deepseek-v4-flash \
  --temperature 0 \
  --top-p 1 \
  --max-tokens 4096 \
  --output-dir experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01/output \
  --rendered-inputs-dir experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01/rendered_inputs \
  --raw-responses-dir experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01/raw_responses \
  --metadata-dir experiments/entity_extraction/001_baseline/runs/holdout_v0_1/run_01/metadata

python3 scripts/run_entity_extraction.py \
  --experiment 002_prompt_refinement \
  --split holdout \
  --model deepseek-v4-flash \
  --temperature 0 \
  --top-p 1 \
  --max-tokens 4096 \
  --output-dir experiments/entity_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/output \
  --rendered-inputs-dir experiments/entity_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/rendered_inputs \
  --raw-responses-dir experiments/entity_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/raw_responses \
  --metadata-dir experiments/entity_extraction/002_prompt_refinement/runs/holdout_v0_1/run_01/metadata
