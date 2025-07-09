# TestPilot

AI-powered test generation, execution, and triage CLI.

## Features
- Generate unit tests for Python files using LLMs (OpenAI, multi-model ready)
- Run tests with pytest
- Triage failures by creating GitHub issues

## Setup
1. Clone the repo and install dependencies:
   ```bash
   pip install -e .
   ```
2. Set your API keys:
   ```bash
   export OPENAI_API_KEY=sk-...
   export GITHUB_TOKEN=ghp_...  # For triage
   ```

## Usage
Generate tests:
```bash
testpilot generate my_module.py
```

Run tests:
```bash
testpilot run generated_tests/test_my_module.py
```

Triage failures:
```bash
testpilot triage generated_tests/test_my_module.py --repo yourusername/yourrepo
```

## Project Structure
- `testpilot/cli.py` - CLI entry point
- `testpilot/core.py` - Core logic
- `testpilot/llm_providers.py` - LLM abstraction
- `generated_tests/` - Output directory for generated tests

## License
MIT
