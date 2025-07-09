import os
import subprocess
from testpilot.llm_providers import get_llm_provider

try:
    from github import Github
except ImportError:
    Github = None

def generate_tests_llm(source_file, provider_name, model_name, api_key=None):
    """
    Generates unit tests for a source file using the specified LLM provider.
    Returns the generated test code as a string.
    """
    with open(source_file, 'r') as f:
        source_code = f.read()
    prompt = f"""
You are an expert software engineer specializing in writing comprehensive unit tests.
Generate a complete Python pytest unit test file for the following Python code.
Ensure the tests cover various scenarios, including edge cases and common usage.
Do not include any explanations, just the Python code for the test file.

The original file is: {os.path.basename(source_file)}

```python
{source_code}
```

Generate the pytest code for this file. The output should be a single block of Python code, suitable for writing directly to a .py file.
"""
    provider = get_llm_provider(provider_name, api_key)
    return provider.generate_text(prompt, model_name)

def run_pytest_tests(test_path):
    """
    Runs pytest on the given test_path (file or directory).
    Returns (exit_code, output_str).
    """
    command = ["pytest", test_path, "--tb=long", "-s"]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    return result.returncode, result.stdout + result.stderr

def create_github_issue(repo_full_name, title, body, labels=None, api_key=None):
    """
    Creates a GitHub issue in the specified repo.
    Returns the issue URL or None on failure.
    """
    if Github is None:
        raise ImportError("PyGithub is not installed.")
    token = api_key or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise ValueError("GitHub token must be provided via argument or GITHUB_TOKEN env var.")
    g = Github(token)
    try:
        owner, repo_name = repo_full_name.split('/')
        repo = g.get_user(owner).get_repo(repo_name)
        issue = repo.create_issue(title=title, body=body, labels=labels or [])
        return issue.html_url
    except Exception as e:
        print(f"Error creating GitHub issue: {e}")
        return None 