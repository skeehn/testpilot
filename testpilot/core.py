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
Ensure the tests cover edge cases, normal cases, and error conditions.

Source code:
```python
{source_code}
```

Requirements:
- Use pytest framework
- Include proper imports
- Test all functions and methods
- Use descriptive test names
- Include docstrings for test functions
- Cover edge cases and error conditions

Generate only the test code, no explanations:
"""
    
    provider = get_llm_provider(provider_name, api_key)
    test_code = provider.generate_text(prompt, model_name)
    return test_code

def run_pytest_tests(test_file, return_trace=False):
    """
    Runs pytest on the given test file and returns results.
    If return_trace=True, returns (output, failed, trace) tuple.
    Otherwise, returns just the output string.
    """
    try:
        result = subprocess.run(
            ['python', '-m', 'pytest', test_file, '-v'],
            capture_output=True,
            text=True,
            cwd=os.getcwd()
        )
        
        output = result.stdout + result.stderr
        failed = result.returncode != 0
        
        if return_trace:
            return output, failed, output
        else:
            return output
            
    except Exception as e:
        error_msg = f"Error running pytest: {str(e)}"
        if return_trace:
            return error_msg, True, error_msg
        else:
            return error_msg

def create_github_issue(repo, title, body, github_token):
    """
    Creates a GitHub issue and returns the issue URL.
    """
    if Github is None:
        raise ImportError("PyGithub is not installed. Please install it to use GitHub integration.")
    
    if not github_token:
        raise ValueError("GitHub token is required for creating issues.")
    
    try:
        g = Github(github_token)
        repository = g.get_repo(repo)
        
        issue = repository.create_issue(
            title=title,
            body=body,
            labels=["test-failure", "testpilot-auto"]
        )
        
        return issue.html_url
        
    except Exception as e:
        raise Exception(f"Failed to create GitHub issue: {str(e)}") 