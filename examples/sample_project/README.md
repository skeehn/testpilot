# Sample Project

This example shows how TestPilot fits into a small Python project.

## Files
- `calculator.py` – simple functions that we want to test.

## Steps
1. From the project root, install TestPilot in editable mode:
   ```bash
   pip install -e .
   ```
2. Generate tests for the calculator module:
   ```bash
   testpilot generate examples/sample_project/calculator.py
   ```
   This creates `generated_tests/test_calculator.py`.
3. Run the generated tests:
   ```bash
   testpilot run generated_tests/test_calculator.py
   ```
4. Triage any failures to GitHub (requires token):
   ```bash
   testpilot triage generated_tests/test_calculator.py --repo youruser/yourrepo
   ```
