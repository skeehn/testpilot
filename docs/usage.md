# Usage Guide

This document provides a more in‑depth look at how to use **TestPilot** in day‑to‑day development.

## Setup

1. Install the package in editable mode:
   ```bash
   pip install -e .
   ```
2. Run the CLI once to enter your OpenAI and GitHub tokens:
   ```bash
   testpilot reset-keys
   ```
   Your keys are stored in a local `.env` file and never committed.

## Generating tests

Use the `generate` command to create pytest files from your source code:
```bash
testpilot generate path/to/your_module.py
```
The generated test file is saved in `generated_tests/` by default.

## Running tests

Run generated tests with the `run` command:
```bash
testpilot run generated_tests/test_your_module.py
```

## Triaging failures

After running tests you can automatically open GitHub issues for failures:
```bash
testpilot triage generated_tests/test_your_module.py --repo youruser/yourrepo
```

## Advanced options

- Use `--provider` and `--model` to select the LLM backend.
- Use `--output-dir` to place tests in a custom folder.
- Call the Python API directly for custom workflows:
  ```python
  from testpilot import generate_tests_llm
  code = generate_tests_llm("my_module.py", "openai", "gpt-4o")
  ```
