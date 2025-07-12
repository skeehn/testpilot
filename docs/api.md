# TestPilot API Reference

## Core Functions

### `generate_tests_llm(source_file, provider_name, model_name, api_key=None, enhanced_mode=True)`

Generate comprehensive unit tests for a Python source file using AI.

**Parameters:**
- `source_file` (str): Path to the Python file to generate tests for
- `provider_name` (str): AI provider ('openai', 'anthropic', 'ollama')
- `model_name` (str): Model name (e.g., 'gpt-4o', 'claude-3-sonnet-20240229')
- `api_key` (str, optional): API key for the provider (defaults to environment variable)
- `enhanced_mode` (bool): Use enhanced mode with code analysis and verification (default: True)

**Returns:**
- `str`: Generated test code

**Example:**
```python
from testpilot.core import generate_tests_llm

test_code = generate_tests_llm(
    "my_module.py", 
    "openai", 
    "gpt-4o", 
    enhanced_mode=True
)
print(test_code)
```

### `run_pytest_tests(test_file, return_trace=False, coverage=False)`

Run pytest tests and return comprehensive results.

**Parameters:**
- `test_file` (str): Path to the test file
- `return_trace` (bool): Return detailed trace information (default: False)
- `coverage` (bool): Include coverage analysis (default: False)

**Returns:**
- `tuple`: (output, failed, trace) where:
  - `output` (str): Test execution output
  - `failed` (bool): Whether any tests failed
  - `trace` (str): Detailed trace information

**Example:**
```python
from testpilot.core import run_pytest_tests

output, failed, trace = run_pytest_tests(
    "test_my_module.py", 
    return_trace=True, 
    coverage=True
)

if not failed:
    print("All tests passed!")
else:
    print(f"Tests failed: {trace}")
```

### `create_github_issue(repo, title, body, github_token)`

Create a GitHub issue with enhanced formatting.

**Parameters:**
- `repo` (str): Repository in 'owner/repo' format
- `title` (str): Issue title
- `body` (str): Issue body content
- `github_token` (str): GitHub API token

**Returns:**
- `str`: URL of the created issue

**Example:**
```python
from testpilot.core import create_github_issue

url = create_github_issue(
    "myorg/myrepo",
    "Test failures detected",
    "Detailed test failure information...",
    "ghp_your_token_here"
)
print(f"Issue created: {url}")
```

## Advanced Functions

### `generate_integration_tests(source_file, provider_name, model_name, api_key=None)`

Generate integration tests that focus on component interactions.

**Parameters:**
- `source_file` (str): Path to the Python file
- `provider_name` (str): AI provider name
- `model_name` (str): Model name
- `api_key` (str, optional): API key

**Returns:**
- `str`: Generated integration test code

### `analyze_test_coverage(test_file, source_file)`

Analyze test coverage and provide insights.

**Parameters:**
- `test_file` (str): Path to the test file
- `source_file` (str): Path to the source file being tested

**Returns:**
- `dict`: Coverage analysis with keys:
  - `total_coverage` (int): Percentage coverage
  - `missing_lines` (list): Lines not covered
  - `covered_lines` (list): Lines covered
  - `analysis` (str): Coverage analysis summary

## Code Analysis Classes

### `CodeAnalyzer(source_code)`

Analyzes Python code to provide context for intelligent test generation.

**Methods:**

#### `analyze()`
Perform comprehensive code analysis.

**Returns:**
- `dict`: Analysis results with keys:
  - `functions` (list): Function information
  - `classes` (list): Class information
  - `imports` (list): Import statements
  - `async_functions` (list): Async function information
  - `complexity` (str): Code complexity level
  - `has_exceptions` (bool): Whether code has exception handling
  - `has_decorators` (bool): Whether code uses decorators
  - `project_type` (str): Detected project type
  - `requirements` (list): Special testing requirements

**Example:**
```python
from testpilot.core import CodeAnalyzer

with open("my_module.py", "r") as f:
    code = f.read()

analyzer = CodeAnalyzer(code)
analysis = analyzer.analyze()

print(f"Complexity: {analysis['complexity']}")
print(f"Project type: {analysis['project_type']}")
print(f"Functions: {len(analysis['functions'])}")
```

### `TestVerifier(test_code, source_file)`

Verifies generated tests for quality and correctness.

**Methods:**

#### `verify()`
Verify test quality and return validation results.

**Returns:**
- `tuple`: (is_valid, issues, corrected_code) where:
  - `is_valid` (bool): Whether tests are valid
  - `issues` (list): List of identified issues
  - `corrected_code` (str): Auto-corrected test code

**Example:**
```python
from testpilot.core import TestVerifier

verifier = TestVerifier(test_code, "my_module.py")
is_valid, issues, corrected_code = verifier.verify()

if not is_valid:
    print(f"Issues found: {issues}")
    test_code = corrected_code
```

## LLM Provider System

### `get_llm_provider(provider_name, api_key=None, **kwargs)`

Get an instance of a registered LLM provider.

**Parameters:**
- `provider_name` (str): Provider name ('openai', 'anthropic', 'ollama')
- `api_key` (str, optional): API key
- `**kwargs`: Additional provider-specific arguments

**Returns:**
- `LLMProvider`: Provider instance

### `get_available_providers()`

Get list of available LLM providers.

**Returns:**
- `list`: List of provider names

### LLM Provider Interface

All providers implement the `LLMProvider` interface:

#### `generate_text(prompt, model_name)`
Generate text using the provider's model.

#### `generate_with_context(prompt, model_name, context)`
Generate text with additional context for enhanced quality.

**Context Dictionary:**
- `project_type` (str): Type of project
- `testing_framework` (str): Testing framework being used
- `complexity` (str): Code complexity level
- `requirements` (str): Special testing requirements

## CLI Integration

### Command Line Interface

The CLI provides access to all core functionality:

```bash
# Generate tests
testpilot generate <source_file> [options]

# Run tests
testpilot run <test_file> [options]

# Triage failures
testpilot triage <test_file> --repo <repo> [options]

# Interactive mode
testpilot interactive

# Coverage analysis
testpilot coverage <test_file> <source_file>

# Provider management
testpilot providers
testpilot reset-keys
```

### Options

**Generate Command:**
- `--provider`: AI provider (openai, anthropic, ollama)
- `--model`: Model name
- `--enhanced`: Use enhanced mode with code analysis
- `--integration`: Generate integration tests
- `--interactive`: Interactive mode with questions
- `--output-dir`: Output directory for tests

**Run Command:**
- `--coverage`: Show coverage report
- `--watch`: Watch for file changes (future feature)

**Triage Command:**
- `--repo`: GitHub repository (required)
- `--auto-fix`: Attempt auto-fix (future feature)

## Configuration

### Environment Variables

```bash
# API Keys
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GITHUB_TOKEN=your_github_token

# Configuration
TESTPILOT_DEBUG=1
TESTPILOT_CACHE_DIR=~/.testpilot/cache
```

### Configuration File

Create `.testpilot_config.json`:

```json
{
  "defaultProvider": "openai",
  "defaultModel": "gpt-4o",
  "enhancedMode": true,
  "outputDirectory": "./generated_tests",
  "autoRunTests": false,
  "showCoverage": true,
  "githubRepo": "owner/repo"
}
```

## Error Handling

### Custom Exceptions

TestPilot defines several custom exceptions:

- `InventoryError`: Raised for inventory-related errors
- `PaymentError`: Raised for payment processing errors
- `ImportError`: Raised when required packages are missing
- `ValueError`: Raised for invalid parameter values

### Error Recovery

TestPilot includes automatic error recovery:

1. **Syntax Errors**: Auto-corrected in generated tests
2. **Import Errors**: Missing imports automatically added
3. **Runtime Errors**: Caught and corrected in test verification
4. **API Errors**: Graceful fallback to alternative providers

## Performance Considerations

### Caching

TestPilot implements intelligent caching:

- **Code Analysis Cache**: Avoids re-analyzing unchanged files
- **Provider Response Cache**: Caches AI responses for similar code
- **Test Result Cache**: Remembers test execution results

### Optimization Tips

1. **Use Enhanced Mode**: Better quality with verification loops
2. **Local Models**: Use Ollama for offline/faster generation
3. **Parallel Processing**: Generate tests for multiple files simultaneously
4. **Incremental Testing**: Only test changed components

### Rate Limits

Be aware of API rate limits:

- **OpenAI**: 3,000 requests per minute (varies by tier)
- **Anthropic**: 1,000 requests per minute
- **Ollama**: No limits (local processing)

## Examples

### Complete Workflow

```python
from testpilot.core import (
    generate_tests_llm, 
    run_pytest_tests, 
    analyze_test_coverage,
    create_github_issue
)

# 1. Generate tests
test_code = generate_tests_llm(
    "my_module.py", 
    "openai", 
    "gpt-4o", 
    enhanced_mode=True
)

# Save to file
with open("test_my_module.py", "w") as f:
    f.write(test_code)

# 2. Run tests
output, failed, trace = run_pytest_tests(
    "test_my_module.py", 
    return_trace=True, 
    coverage=True
)

# 3. Analyze coverage
coverage_data = analyze_test_coverage(
    "test_my_module.py", 
    "my_module.py"
)

print(f"Coverage: {coverage_data['total_coverage']}%")

# 4. Handle failures
if failed:
    issue_url = create_github_issue(
        "myorg/myrepo",
        "Test failures detected",
        trace,
        "your_github_token"
    )
    print(f"Issue created: {issue_url}")
```

### Advanced Usage

```python
from testpilot.core import CodeAnalyzer, TestVerifier
from testpilot.llm_providers import get_llm_provider

# Advanced code analysis
with open("complex_module.py", "r") as f:
    source_code = f.read()

analyzer = CodeAnalyzer(source_code)
analysis = analyzer.analyze()

# Use analysis for context-aware generation
provider = get_llm_provider("anthropic", api_key="your_key")

context = {
    'project_type': analysis['project_type'],
    'complexity': analysis['complexity'],
    'requirements': ', '.join(analysis['requirements'])
}

test_code = provider.generate_with_context(
    "Generate comprehensive tests...",
    "claude-3-sonnet-20240229",
    context
)

# Verify and improve tests
verifier = TestVerifier(test_code, "complex_module.py")
is_valid, issues, corrected_code = verifier.verify()

if not is_valid:
    print(f"Auto-correcting {len(issues)} issues...")
    test_code = corrected_code
```