import ast
import os
import subprocess
import sys
from pathlib import Path
from string import Template
from typing import TYPE_CHECKING, Optional, Set, List, Dict, Any

import importlib.resources as pkg_resources
import tempfile
import uuid

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


# ------------------------------------------------------------
# Advanced Codebase Analysis for Context-Aware Generation
# ------------------------------------------------------------

class CodebaseAnalyzer:
    """Analyzes entire codebase to provide rich context for test generation."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.context_cache: Dict[str, Any] = {}
    
    def analyze_file_dependencies(self, target_file: str) -> Dict[str, Any]:
        """Extract imports, function signatures, and class definitions."""
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                source = f.read()
            
            tree = ast.parse(source)
            
            analysis = {
                'imports': [],
                'functions': [],
                'classes': [],
                'constants': [],
                'dependencies': set()
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis['imports'].append(alias.name)
                        analysis['dependencies'].add(alias.name)
                
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        analysis['imports'].append(f"from {node.module}")
                        analysis['dependencies'].add(node.module)
                
                elif isinstance(node, ast.FunctionDef):
                    func_info = {
                        'name': node.name,
                        'args': [arg.arg for arg in node.args.args],
                        'returns': ast.unparse(node.returns) if node.returns else None,
                        'docstring': ast.get_docstring(node),
                        'decorators': [ast.unparse(dec) for dec in node.decorator_list]
                    }
                    analysis['functions'].append(func_info)
                
                elif isinstance(node, ast.ClassDef):
                    class_info = {
                        'name': node.name,
                        'bases': [ast.unparse(base) for base in node.bases],
                        'methods': [],
                        'docstring': ast.get_docstring(node)
                    }
                    
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            class_info['methods'].append(item.name)
                    
                    analysis['classes'].append(class_info)
                
                elif isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            analysis['constants'].append(target.id)
            
            return analysis
            
        except Exception as e:
            return {'error': str(e), 'imports': [], 'functions': [], 'classes': [], 'constants': []}
    
    def find_related_files(self, target_file: str) -> List[str]:
        """Find files that might be related to the target file."""
        target_path = Path(target_file)
        related_files = []
        
        # Look for files in the same directory
        if target_path.parent.exists():
            for file in target_path.parent.glob("*.py"):
                if file != target_path and not file.name.startswith('test_'):
                    related_files.append(str(file))
        
        # Look for existing test files
        test_patterns = [
            target_path.parent / f"test_{target_path.stem}.py",
            target_path.parent / "tests" / f"test_{target_path.stem}.py",
            target_path.parent.parent / "tests" / f"test_{target_path.stem}.py"
        ]
        
        for test_file in test_patterns:
            if test_file.exists():
                related_files.append(str(test_file))
        
        return related_files
    
    def get_project_context(self, target_file: str) -> Dict[str, Any]:
        """Get comprehensive project context for better test generation."""
        if target_file in self.context_cache:
            return self.context_cache[target_file]
        
        context = {
            'target_analysis': self.analyze_file_dependencies(target_file),
            'related_files': self.find_related_files(target_file),
            'project_structure': self._analyze_project_structure(),
            'testing_patterns': self._detect_testing_patterns()
        }
        
        self.context_cache[target_file] = context
        return context
    
    def _analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze overall project structure and conventions."""
        structure = {
            'has_tests_dir': False,
            'testing_framework': 'pytest',  # default assumption
            'package_structure': [],
            'config_files': []
        }
        
        # Check for common test directories
        for test_dir in ['tests', 'test', 'testing']:
            if (self.project_root / test_dir).exists():
                structure['has_tests_dir'] = True
                break
        
        # Look for config files that might indicate testing setup
        config_files = ['pytest.ini', 'tox.ini', 'setup.cfg', 'pyproject.toml']
        for config in config_files:
            if (self.project_root / config).exists():
                structure['config_files'].append(config)
        
        return structure
    
    def _detect_testing_patterns(self) -> Dict[str, Any]:
        """Detect existing testing patterns in the project."""
        patterns = {
            'common_imports': set(),
            'fixture_patterns': [],
            'assertion_styles': set()
        }
        
        # Scan existing test files for patterns
        for test_file in self.project_root.rglob("test_*.py"):
            try:
                with open(test_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract common testing imports
                if 'import pytest' in content:
                    patterns['common_imports'].add('pytest')
                if 'from unittest' in content:
                    patterns['common_imports'].add('unittest')
                if 'import mock' in content or 'from mock' in content:
                    patterns['common_imports'].add('mock')
                
                # Look for fixture patterns
                if '@pytest.fixture' in content:
                    patterns['fixture_patterns'].append('pytest_fixtures')
                
                # Detect assertion styles
                if 'assert ' in content:
                    patterns['assertion_styles'].add('assert')
                if 'self.assert' in content:
                    patterns['assertion_styles'].add('unittest')
                    
            except Exception:
                continue
        
        return patterns


# ------------------------------------------------------------
# Enhanced Test Validation and Quality Assurance
# ------------------------------------------------------------

class TestValidator:
    """Validates generated tests for quality and correctness."""
    
    def __init__(self):
        self.validation_results = []
    
    def validate_test_syntax(self, test_code: str) -> bool:
        """Validate that the generated test code is syntactically correct."""
        try:
            ast.parse(test_code)
            return True
        except SyntaxError:
            return False
    
    def validate_test_execution(self, test_code: str, target_file: str) -> Dict[str, Any]:
        """Run the generated tests to ensure they execute without errors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            test_path = os.path.join(tmpdir, f"test_{uuid.uuid4().hex}.py")
            
            # Write test code to temporary file
            with open(test_path, "w", encoding="utf-8") as f:
                f.write(test_code)
            
            # Try to run the test
            try:
                result = subprocess.run(
                    [sys.executable, "-m", "pytest", test_path, "-v", "--tb=short"],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                return {
                    'success': result.returncode == 0,
                    'output': result.stdout,
                    'errors': result.stderr,
                    'returncode': result.returncode
                }
            except subprocess.TimeoutExpired:
                return {
                    'success': False,
                    'output': '',
                    'errors': 'Test execution timed out',
                    'returncode': -1
                }
            except Exception as e:
                return {
                    'success': False,
                    'output': '',
                    'errors': str(e),
                    'returncode': -1
                }
    
    def check_test_coverage(self, test_code: str, target_file: str) -> Dict[str, Any]:
        """Analyze what the generated tests actually cover."""
        # This is a simplified coverage analysis
        # In a full implementation, we'd use coverage.py or similar
        
        coverage_info = {
            'functions_tested': [],
            'classes_tested': [],
            'edge_cases_covered': [],
            'coverage_score': 0.0
        }
        
        # Parse the test code to see what it's testing
        try:
            test_tree = ast.parse(test_code)
            target_analysis = CodebaseAnalyzer(".").analyze_file_dependencies(target_file)
            
            # Look for function calls in tests that match target functions
            for node in ast.walk(test_tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        for target_func in target_analysis['functions']:
                            if target_func['name'] in func_name or func_name in target_func['name']:
                                coverage_info['functions_tested'].append(target_func['name'])
            
            # Calculate a simple coverage score
            total_functions = len(target_analysis['functions'])
            tested_functions = len(set(coverage_info['functions_tested']))
            
            if total_functions > 0:
                coverage_info['coverage_score'] = tested_functions / total_functions
            
        except Exception as e:
            coverage_info['error'] = str(e)
        
        return coverage_info
    
    def validate_comprehensive(self, test_code: str, target_file: str) -> Dict[str, Any]:
        """Run comprehensive validation on generated tests."""
        results = {
            'syntax_valid': self.validate_test_syntax(test_code),
            'execution_results': self.validate_test_execution(test_code, target_file),
            'coverage_analysis': self.check_test_coverage(test_code, target_file),
            'overall_quality_score': 0.0
        }
        
        # Calculate overall quality score
        score = 0.0
        if results['syntax_valid']:
            score += 0.3
        if results['execution_results']['success']:
            score += 0.4
        score += results['coverage_analysis']['coverage_score'] * 0.3
        
        results['overall_quality_score'] = score
        return results


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
    use_context_analysis: bool = True,
    validation_enabled: bool = True,
):
    """
    Generates unit tests for a source file using advanced AI with context awareness.
    
    This enhanced version provides:
    - Deep codebase analysis for better context
    - Quality validation of generated tests
    - Automatic retry for failed generations
    - Coverage analysis and optimization
    
    Returns the generated test code as a string.
    """

    provider = get_llm_provider(provider_name, api_key)
    model_name_validated = _validate_model(provider, model_name)

    # Initialize context analyzer and validator
    project_root = str(Path(source_file).parent)
    analyzer = CodebaseAnalyzer(project_root) if use_context_analysis else None
    validator = TestValidator() if validation_enabled else None

    with open(source_file, "r", encoding="utf-8") as f:
        source_code = f.read()

    # Build enhanced prompt with context
    if analyzer:
        context = analyzer.get_project_context(source_file)
        enhanced_prompt = _build_context_aware_prompt(
            source_code, context, prompt_file, prompt_name
        )
    else:
        enhanced_prompt = _build_prompt(source_code, prompt_file, prompt_name)

    gen_kwargs = {}
    if temperature is not None:
        gen_kwargs["temperature"] = temperature
    if max_tokens is not None:
        gen_kwargs["max_tokens"] = max_tokens
    if stop is not None:
        gen_kwargs["stop"] = stop

    # Generate tests with potential retry for quality
    max_attempts = 3
    best_test_code = None
    best_quality_score = 0.0

    for attempt in range(max_attempts):
        test_code = provider.generate_text(
            enhanced_prompt,
            model_name_validated,
            **gen_kwargs,
        )

        if not validation_enabled or validator is None:
            return test_code

        # Validate the generated tests
        validation_results = validator.validate_comprehensive(test_code, source_file)
        quality_score = validation_results['overall_quality_score']

        # Keep track of the best attempt
        if quality_score > best_quality_score:
            best_quality_score = quality_score
            best_test_code = test_code

        # If we got high quality tests, return immediately
        if quality_score >= 0.8:  # 80% quality threshold
            return test_code

        # If syntax is invalid or tests don't run, try again with feedback
        if not validation_results['syntax_valid'] or not validation_results['execution_results']['success']:
            # Add feedback to the prompt for next attempt
            error_feedback = f"\n\nPrevious attempt had issues: {validation_results['execution_results'].get('errors', 'Syntax error')}\nPlease fix these issues in the next generation."
            enhanced_prompt += error_feedback

    # Return the best attempt we got
    return best_test_code or test_code


def _build_context_aware_prompt(
    source_code: str, 
    context: Dict[str, Any], 
    prompt_file: Optional[str], 
    prompt_name: Optional[str]
) -> str:
    """Build an enhanced prompt that includes codebase context."""
    
    # Get the base template
    template_str = _load_prompt_template(prompt_file, prompt_name)
    
    # Extract context information
    target_analysis = context.get('target_analysis', {})
    testing_patterns = context.get('testing_patterns', {})
    project_structure = context.get('project_structure', {})
    
    # Build context information string
    context_info = []
    
    if target_analysis.get('functions'):
        func_names = [f['name'] for f in target_analysis['functions']]
        context_info.append(f"Functions to test: {', '.join(func_names)}")
    
    if target_analysis.get('classes'):
        class_names = [c['name'] for c in target_analysis['classes']]
        context_info.append(f"Classes to test: {', '.join(class_names)}")
    
    if target_analysis.get('imports'):
        context_info.append(f"Key dependencies: {', '.join(target_analysis['imports'][:5])}")
    
    if testing_patterns.get('common_imports'):
        context_info.append(f"Project uses: {', '.join(testing_patterns['common_imports'])}")
    
    if testing_patterns.get('assertion_styles'):
        context_info.append(f"Assertion style: {', '.join(testing_patterns['assertion_styles'])}")
    
    # Enhance the template with context
    context_section = "\n".join(context_info) if context_info else "No additional context available."
    
    enhanced_template = template_str.replace(
        "$source_code", 
        f"$source_code\n\nProject Context:\n{context_section}"
    )
    
    # Use string.Template for substitution
    tmpl = Template(enhanced_template)
    return tmpl.safe_substitute(source_code=source_code)


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

# ------------------------------------------------------------
# GitHub Gist helper
# ------------------------------------------------------------


def create_github_gist(file_path: str, github_token: str, *, public: bool = False) -> str:
    """Create a GitHub Gist from *file_path* and return its URL."""

    if Github is None:
        raise ImportError("PyGithub is not installed. Please install it to use GitHub integration.")

    if not github_token:
        raise ValueError("GitHub token is required for creating gists.")

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        from pathlib import Path
        from typing import Any, Dict, cast

        # Build files dict using PyGithub's InputFileContent when available.
        try:
            from github.InputFileContent import InputFileContent  # type: ignore

            files_param: Dict[str, Any] = {  # noqa: ANN401
                Path(file_path).name: InputFileContent(content)
            }
        except Exception:
            # Fallback to raw mapping accepted at runtime; cast for type checker
            files_param = cast(Dict[str, Any], {
                Path(file_path).name: {"content": content}
            })

        g = Github(github_token)
        user = g.get_user()
        filename = Path(file_path).name
        gist = user.create_gist(  # type: ignore[attr-defined]
            public,
            files_param,
            description=f"Failing tests from TestPilot ({filename})",
        )
        return gist.html_url
    except Exception as e:
        raise Exception(f"Failed to create GitHub gist: {str(e)}")
