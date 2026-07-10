# Output

Save model outputs in this directory.

Recommended filenames:

- `calculus_001.json`
- `linear_algebra_001.json`
- `optimisation_001.json`

Each file should contain only the JSON returned by the model.

Use the prompt files in `../input/`:

- `../input/calculus_001_prompt.md`
- `../input/linear_algebra_001_prompt.md`
- `../input/optimisation_001_prompt.md`

Recommended run settings:

- Use the same model for all three inputs.
- Use temperature `0` if the interface allows it.
- Do not manually edit model outputs before evaluation.
- Record the model name and date in `../conclusion.md` after the run.

The DeepSeek API runner writes outputs here automatically:

```bash
python3 scripts/run_entity_extraction.py
```
