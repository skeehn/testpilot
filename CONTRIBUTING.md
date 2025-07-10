# Contributing to TestPilot

Thank you for your interest in contributing to TestPilot! We welcome contributions from the community.

## Getting Started

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/yourusername/testpilot.git
   cd testpilot
   ```

2. **Set up your development environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e .
   ```

3. **Set up API keys for testing**
   ```bash
   testpilot reset-keys  # Follow prompts to enter your keys
   ```

## Development Workflow

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow existing code style and patterns
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   # Test the CLI
   testpilot generate my_module.py
   testpilot run generated_tests/test_my_module.py
   
   # Run any existing tests
   python -m pytest
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "feat: add your feature description"
   git push origin feature/your-feature-name
   ```

5. **Create a Pull Request**
   - Describe what your PR does
   - Include examples if applicable
   - Reference any related issues

## Areas for Contribution

- **New LLM providers** (Anthropic, Ollama, local models)
- **IDE integrations** (VS Code extensions, PyCharm plugins)
- **Test framework support** (unittest, nose2, etc.)
- **Output formats** (JUnit XML, coverage reports)
- **Documentation and examples**
- **Bug fixes and performance improvements**

## Code Style

- Follow PEP 8 for Python code
- Use meaningful variable and function names
- Add docstrings to public functions
- Keep functions focused and small

## Linting

We use `pre-commit` to run `black` and `ruff` (a fast flake8 replacement).
Install the hooks once and run them manually with:

```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Questions?

- Open an issue for bugs or feature requests
- Start a discussion for questions or ideas
- Check existing issues before creating new ones

We appreciate your contributions! 🚀 