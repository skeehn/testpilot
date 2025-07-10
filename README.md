# TestPilot

AI-powered test generation, execution, and triage CLI for Python projects.

[![license badge](https://img.shields.io/github/license/yourusername/testpilot.svg)](./LICENSE)

---

## Purpose & Philosophy
TestPilot automates the most tedious parts of testing: generating unit tests with LLMs, running them, and triaging failures (including GitHub issue creation). It's designed for rapid onboarding, extensibility, and a seamless "fork-and-go" experience. Our philosophy: **make high-quality testing accessible, fast, and AI-native for every developer.**

## Installation
```bash
# Clone and install dependencies
pip install -e .
```

## Core Concepts
- **LLM-powered test generation:** Uses OpenAI (and future providers) to generate pytest tests for your code.
- **Unified CLI workflow:** One tool for generating, running, and triaging tests.
- **Fork-and-go onboarding:** Prompts for API keys on first run, stores them locally in `.env` (never committed).
- **Extensible architecture:** Ready for plugins, new LLMs, and IDE integration.

## Quick Start Example
```bash
# 1. First run: enter your OpenAI and GitHub API keys when prompted
# 2. Generate tests for a Python file
$ testpilot generate my_module.py
# OR if console script doesn't work:
$ python -m testpilot.cli generate my_module.py

# 3. Run the generated tests
$ testpilot run generated_tests/test_my_module.py
# OR:
$ python -m testpilot.cli run generated_tests/test_my_module.py

# 4. Triage failures (creates GitHub issues)
$ testpilot triage generated_tests/test_my_module.py --repo yourusername/yourrepo
# OR:
$ python -m testpilot.cli triage generated_tests/test_my_module.py --repo yourusername/yourrepo
```

## Usage Patterns
### Pattern 1: Generate and run tests for a new module
```bash
testpilot generate path/to/your_module.py
testpilot run generated_tests/test_your_module.py
```
### Pattern 2: Triage test failures to GitHub
```bash
testpilot triage generated_tests/test_your_module.py --repo yourusername/yourrepo
```
### Pattern 3: Reset API keys
```bash
testpilot reset-keys
```

**Note:** If the `testpilot` command doesn't work, you can always use `python -m testpilot.cli` instead of `testpilot`.

#### Anti-patterns to Avoid
- Don't commit your `.env` file or API keys.
- Don't run `triage` without a valid GitHub token.

## API Overview
### CLI Commands
- `generate <source_file>`: Generate pytest tests for a Python file using an LLM.
- `run <test_file>`: Run tests with pytest and show results.
- `triage <test_file> --repo <repo>`: Run tests and create GitHub issues for failures.
- `reset-keys`: Clear and re-enter your API keys.

### Key Functions (Python API)
- `generate_tests_llm(source_file, provider, model, api_key=None)`
- `run_pytest_tests(test_file)`
- `create_github_issue(repo, title, body, github_token)`

## Using TestPilot in Your IDE

### VS Code
Add this to `.vscode/tasks.json` for quick access:
```json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "TestPilot: Generate Tests",
            "type": "shell",
            "command": "python",
            "args": ["-m", "testpilot.cli", "generate", "${file}"],
            "group": "test",
            "presentation": {
                "echo": true,
                "reveal": "always"
            }
        },
        {
            "label": "TestPilot: Run Tests",
            "type": "shell",
            "command": "python",
            "args": ["-m", "testpilot.cli", "run", "${input:testFile}"],
            "group": "test"
        }
    ],
    "inputs": [
        {
            "id": "testFile",
            "description": "Test file to run",
            "default": "generated_tests/test_${fileBasenameNoExtension}.py",
            "type": "promptString"
        }
    ]
}
```

### PyCharm/JetBrains
1. Go to **Run > Edit Configurations**
2. Add a new **Python** configuration:
   - **Script path:** Path to your Python executable
   - **Parameters:** `-m testpilot.cli generate $FilePath$`
   - **Working directory:** `$ProjectFileDir$`

### Python API
```python
from testpilot.core import generate_tests_llm, run_pytest_tests, create_github_issue

# Generate tests programmatically
test_code = generate_tests_llm("my_module.py", "openai", "gpt-4o")
print(test_code)

# Run tests and get results
result = run_pytest_tests("test_my_module.py")
print(result)

# Create GitHub issue for failures
url = create_github_issue("user/repo", "Test failed", "Details...", "token")
```

## Integration Guide
- **Works with any Python project.**
- **GitHub Actions:** See `.github/workflows/testpilot_ci.yml` for CI integration.
- **Extensible:** Add new LLM providers or plugins via `llm_providers.py` and future plugin hooks.

## Troubleshooting
- **Import errors:** Ensure you're in your virtual environment and have run `pip install -e .`.
- **Missing dependencies:** If you see errors about `openai` or `PyGithub` not being installed, run `pip install openai PyGithub`.
- **API key issues:** Run `testpilot reset-keys` to re-enter keys.
- **Permission errors:** Make sure your GitHub token has `repo` scope for issue creation.
- **Test failures:** Check the generated test file and your source code for errors.
- **Console script issues:** If `testpilot` command doesn't work, use `python -m testpilot.cli` instead.

## Additional Resources
- [Project Wiki](./docs/)
- [Examples](./examples/)
- [Contributing Guide](./CONTRIBUTING.md)

## Security
- `.env` is in `.gitignore` and never committed.
- Each user manages their own keys locally.

## License
MIT © TestPilot Authors
