# Continuous Integration

This repository uses **GitHub Actions** to automatically run TestPilot on every push and pull request. The workflow is defined in [`.github/workflows/testpilot_ci.yml`](../.github/workflows/testpilot_ci.yml).

## Workflow Overview
1. **Checkout** the repository.
2. **Set up Python** using `actions/setup-python`.
3. **Install dependencies** with `pip`.
4. **Generate tests** for `my_module.py` using `testpilot generate`.
   - Requires the `OPENAI_API_KEY` secret.
5. **Run pytest** and produce `pytest.xml`.
6. **Upload the test report** as an artifact so results can be viewed in the Actions UI.

API tokens are never committed. They are provided via repository secrets and exposed to the workflow using environment variables.

## Running CI Steps Locally
You can reproduce the workflow on your own machine:

```bash
python -m pip install --upgrade pip
pip install -e .
pip install pytest
export OPENAI_API_KEY=your-key
# Optional if you need GitHub issue triage
# export GITHUB_TOKEN=your-token

testpilot generate my_module.py
pytest generated_tests/test_my_module.py -v --junitxml=pytest.xml
```

The commands above mirror what the GitHub Actions runner executes. After running them you can inspect `pytest.xml` for the test results.
