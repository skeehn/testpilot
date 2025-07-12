import os
import subprocess
import sys
from string import Template
from typing import TYPE_CHECKING, Optional, Set

import importlib.resources as pkg_resources

try:
    import yaml  # type: ignore
except ImportError as exc:  # pragma: no cover
    yaml = None  # type: ignore

from testpilot.llm_providers import get_llm_provider

# Package resource folder for templates
_TEMPLATE_PKG = "testpilot"
_DEFAULT_PROMPT_RES = "prompt.yaml"

# Optional PyGithub import: provide graceful fallback when unavailable.
try:
    from github import Github  # type: ignore
except ImportError:  # pragma: no cover
    Github = None  # type: ignore

# For static type checkers, expose a stub so type resolution succeeds even when
# PyGithub is absent at runtime.
if TYPE_CHECKING:  # pragma: no cover
    from github import Github as _Github  # type: ignore
    Github = _Github  # type: ignore


def _validate_model(provider, model_name: Optional[str]):
    """Return a valid model name for *provider* or raise.

    If *model_name* is None, fall back to provider.default_model.
    If provider.supported_models is populated, ensure the chosen model is in it.
    """

    chosen = model_name or getattr(provider, "default_model", None)
    if chosen is None:
        raise ValueError(
            f"Model name must be provided for provider without default ({provider.__class__.__name__})"
        )

    supported: Optional[Set[str]] = getattr(provider, "supported_models", None)
    if supported:
        if chosen not in supported:
            raise ValueError(
                f"Model '{chosen}' not supported by provider {provider.__class__.__name__}. "
                f"Supported models: {', '.join(sorted(supported))}"
            )
    return chosen


# ------------------------------------------------------------
# Prompt loading helpers
# ------------------------------------------------------------

def _load_prompt_template(prompt_file: Optional[str], prompt_name: Optional[str]) -> str:
    """Load a prompt template string from YAML file.

    If *prompt_file* is None, loads the built-in template resource.
    If YAML maps names to templates, *prompt_name* selects which one (default 'default').
    If YAML is a plain string, return it directly.
    """

    # Obtain template content
    if prompt_file is None:
        # Load from package resources
        with pkg_resources.files(_TEMPLATE_PKG).joinpath(_DEFAULT_PROMPT_RES).open("r", encoding="utf-8") as f:
            raw = f.read()
    else:
        with open(prompt_file, "r", encoding="utf-8") as f:
            raw = f.read()

    if yaml is None:
        # PyYAML missing – treat file as plain text
        return raw

    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError:
        # If parsing fails, fall back to raw text
        return raw

    # If the YAML is just a string, return it
    if isinstance(data, str):
        return data

    if not isinstance(data, dict):
        raise ValueError("Prompt YAML must be a string or mapping of name → template.")

    key = prompt_name or "default"
    if key not in data:
        raise KeyError(f"Prompt name '{key}' not found in template file.")
    return str(data[key])


def _build_prompt(source_code: str, prompt_file: Optional[str], prompt_name: Optional[str]) -> str:
    template_str = _load_prompt_template(prompt_file, prompt_name)
    # Use string.Template to avoid conflicts with `{}` braces inside source code
    tmpl = Template(template_str)
    return tmpl.safe_substitute(source_code=source_code)



def generate_tests_llm(
    source_file: str,
    provider_name: str,
    model_name: Optional[str] = None,
    api_key: Optional[str] = None,
    prompt_file: Optional[str] = None,
    prompt_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[list[str]] = None,
):
    """
    Generates unit tests for a source file using the specified LLM provider.
    Returns the generated test code as a string.
    """

    provider = get_llm_provider(provider_name, api_key)
    model_name_validated = _validate_model(provider, model_name)

    with open(source_file, "r", encoding="utf-8") as f:
        source_code = f.read()

    prompt = _build_prompt(source_code, prompt_file, prompt_name)
    
    gen_kwargs = {}
    if temperature is not None:
        gen_kwargs["temperature"] = temperature
    if max_tokens is not None:
        gen_kwargs["max_tokens"] = max_tokens
    if stop is not None:
        gen_kwargs["stop"] = stop

    test_code = provider.generate_text(
        prompt,
        model_name_validated,
        **gen_kwargs,
    )
    return test_code

# ------------------------------------------------------------
# Regenerate until tests compile helper
# ------------------------------------------------------------


def generate_tests_llm_with_retry(
    source_file: str,
    provider_name: str,
    model_name: Optional[str] = None,
    *,
    api_key: Optional[str] = None,
    prompt_file: Optional[str] = None,
    prompt_name: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    stop: Optional[list[str]] = None,
    max_retries: int = 3,
) -> str:
    """Generate tests and retry up to *max_retries* times if they don't compile.

    Compilation is validated by attempting to run pytest. Retries occur only for
    syntax/import errors; logical assertion failures are returned as-is.
    """

    import tempfile
    import uuid

    last_code: str | None = None
    last_trace: str | None = None

    for attempt in range(max_retries + 1):
        last_code = generate_tests_llm(
            source_file,
            provider_name,
            model_name,
            api_key=api_key,
            prompt_file=prompt_file,
            prompt_name=prompt_name,
            temperature=temperature,
            max_tokens=max_tokens,
            stop=stop,
        )

        # Write to a temporary file
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, f"test_{uuid.uuid4().hex}.py")
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(last_code)

            output, failed, trace = run_pytest_tests(test_path, return_trace=True)

            if not failed:
                return last_code

            # If failure due to SyntaxError or ImportError regenerate
            if "SyntaxError" in trace or "ImportError" in trace:
                last_trace = trace
                continue  # try again
            else:
                # Logical failures: return as-is
                return last_code

    # After retries, return last generated code even if still failing
    # Could log last_trace for caller (CLI will show)
    return last_code or ""


def run_pytest_tests(test_file, return_trace=False):
    """
    Runs pytest on the given test file and returns results.
    If return_trace=True, returns (output, failed, trace) tuple.
    Otherwise, returns just the output string.
    """
    try:
        cmd = [sys.executable, '-m', 'pytest', test_file, '-v']
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
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

# Duplicate 'Optional' import removed above. Function signature updated:
def create_github_issue(
    repo: str,
    title: str,
    body: str,
    github_token: Optional[str],
    *,
    labels: Optional[list[str]] = None,
    assignees: Optional[list[str]] = None,
):
    """Creates a GitHub issue and returns the issue URL.

    Additional parameters:
        labels – list of label names to set on the issue (default adds
                  "test-failure" & "testpilot-auto" if not supplied).
        assignees – list of GitHub usernames to assign.
    """
    if Github is None:
        raise ImportError(
            "PyGithub is not installed. Please install it to use GitHub integration."
        )
    
    if not github_token:
        raise ValueError("GitHub token is required for creating issues.")
    
    try:
        g = Github(github_token)
        repository = g.get_repo(repo)
        
        from typing import cast, List

        final_labels = labels if labels else ["test-failure", "testpilot-auto"]

        # PyGithub stubs expect List[NamedUser] | NotSet. We cast our list[str]
        # to satisfy the type checker while PyGithub accepts list[str] at runtime.
        assignees_param: list[str] = assignees or []

        issue = repository.create_issue(
            title=title,
            body=body,
            labels=final_labels,
            assignees=assignees_param,
        )
        
        return issue.html_url
        
    except Exception as e:
        raise Exception(f"Failed to create GitHub issue: {str(e)}")
