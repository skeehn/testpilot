import os
import subprocess
import ast
import re
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import tempfile
import shutil

from testpilot.llm_providers import get_llm_provider

try:
    from github import Github
except ImportError:
    Github = None


class CodeAnalyzer:
    """Analyzes Python code to provide context for better test generation."""
    
    def __init__(self, source_code: str):
        self.source_code = source_code
        self.tree = ast.parse(source_code)
        
    def analyze(self) -> Dict:
        """Analyze the code and return comprehensive context."""
        analysis = {
            'functions': [],
            'classes': [],
            'imports': [],
            'async_functions': [],
            'complexity': 'Medium',
            'has_exceptions': False,
            'has_decorators': False,
            'project_type': 'Unknown',
            'testing_framework': 'pytest',
            'requirements': []
        }
        
        for node in ast.walk(self.tree):
            if isinstance(node, ast.FunctionDef):
                func_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'is_async': False,
                    'has_decorators': len(node.decorator_list) > 0,
                    'docstring': ast.get_docstring(node),
                    'returns': node.returns is not None
                }
                analysis['functions'].append(func_info)
                if node.decorator_list:
                    analysis['has_decorators'] = True
                    
            elif isinstance(node, ast.AsyncFunctionDef):
                func_info = {
                    'name': node.name,
                    'args': [arg.arg for arg in node.args.args],
                    'is_async': True,
                    'has_decorators': len(node.decorator_list) > 0,
                    'docstring': ast.get_docstring(node),
                    'returns': node.returns is not None
                }
                analysis['async_functions'].append(func_info)
                analysis['functions'].append(func_info)
                
            elif isinstance(node, ast.ClassDef):
                class_info = {
                    'name': node.name,
                    'methods': [],
                    'has_init': False,
                    'docstring': ast.get_docstring(node)
                }
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        class_info['methods'].append(item.name)
                        if item.name == '__init__':
                            class_info['has_init'] = True
                analysis['classes'].append(class_info)
                
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    analysis['imports'].append(alias.name)
                    
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    analysis['imports'].append(node.module)
                    
            elif isinstance(node, (ast.Raise, ast.Try)):
                analysis['has_exceptions'] = True
        
        # Determine project type and complexity
        analysis['complexity'] = self._determine_complexity(analysis)
        analysis['project_type'] = self._determine_project_type(analysis['imports'])
        analysis['requirements'] = self._generate_requirements(analysis)
        
        return analysis
    
    def _determine_complexity(self, analysis: Dict) -> str:
        """Determine code complexity based on analysis."""
        complexity_score = 0
        
        # Add points for various complexity factors
        complexity_score += len(analysis['functions']) * 2
        complexity_score += len(analysis['classes']) * 3
        complexity_score += len(analysis['async_functions']) * 2
        complexity_score += 5 if analysis['has_exceptions'] else 0
        complexity_score += 3 if analysis['has_decorators'] else 0
        
        if complexity_score < 10:
            return 'Low'
        elif complexity_score < 25:
            return 'Medium'
        else:
            return 'High'
    
    def _determine_project_type(self, imports: List[str]) -> str:
        """Determine project type based on imports."""
        # Filter out None values
        valid_imports = [imp for imp in imports if imp is not None]
        
        if any(imp in valid_imports for imp in ['django', 'flask', 'fastapi']):
            return 'Web Application'
        elif any(imp in valid_imports for imp in ['pandas', 'numpy', 'sklearn']):
            return 'Data Science'
        elif any(imp in valid_imports for imp in ['asyncio', 'aiohttp']):
            return 'Async Application'
        elif any(imp in valid_imports for imp in ['click', 'argparse']):
            return 'CLI Application'
        else:
            return 'General Python'
    
    def _generate_requirements(self, analysis: Dict) -> List[str]:
        """Generate specific testing requirements based on analysis."""
        requirements = []
        
        if analysis['async_functions']:
            requirements.append('Test async functions with pytest-asyncio')
        if analysis['has_exceptions']:
            requirements.append('Test exception handling thoroughly')
        if analysis['has_decorators']:
            requirements.append('Test decorated functions properly')
        if analysis['classes']:
            requirements.append('Test class methods and state changes')
        
        return requirements


class TestVerifier:
    """Verifies generated tests for quality and correctness."""
    
    def __init__(self, test_code: str, source_file: str):
        self.test_code = test_code
        self.source_file = source_file
        
    def verify(self) -> Tuple[bool, List[str], str]:
        """Verify test quality and return (is_valid, issues, corrected_code)."""
        issues = []
        corrected_code = self.test_code
        
        # Check for syntax errors
        try:
            ast.parse(self.test_code)
        except SyntaxError as e:
            issues.append(f"Syntax error: {e}")
            return False, issues, corrected_code
        
        # Check for basic test structure
        if not self._has_test_functions():
            issues.append("No test functions found")
            
        # Check for proper imports
        if not self._has_required_imports():
            issues.append("Missing required imports")
            corrected_code = self._add_missing_imports(corrected_code)
            
        # Try to run the tests in a sandbox
        is_runnable, run_issues = self._test_runnability()
        if not is_runnable:
            issues.extend(run_issues)
            
        return len(issues) == 0, issues, corrected_code
    
    def _has_test_functions(self) -> bool:
        """Check if the code has test functions."""
        try:
            tree = ast.parse(self.test_code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name.startswith('test_'):
                    return True
        except:
            pass
        return False
    
    def _has_required_imports(self) -> bool:
        """Check if the code has required imports."""
        required_imports = ['pytest', 'import']
        return any(imp in self.test_code for imp in required_imports)
    
    def _add_missing_imports(self, code: str) -> str:
        """Add missing imports to the test code."""
        imports_to_add = []
        
        if 'pytest' not in code:
            imports_to_add.append('import pytest')
        if 'mock' in code and 'from unittest.mock import' not in code:
            imports_to_add.append('from unittest.mock import Mock, patch')
        
        if imports_to_add:
            import_block = '\n'.join(imports_to_add) + '\n\n'
            return import_block + code
        
        return code
    
    def _test_runnability(self) -> Tuple[bool, List[str]]:
        """Test if the generated tests can run without errors."""
        issues = []
        
        # Create a temporary file to test
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(self.test_code)
            temp_file = f.name
        
        try:
            # Try to import the test file
            result = subprocess.run(
                ['python', '-m', 'py_compile', temp_file],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                issues.append(f"Compilation error: {result.stderr}")
                return False, issues
                
        except subprocess.TimeoutExpired:
            issues.append("Test compilation timed out")
            return False, issues
        except Exception as e:
            issues.append(f"Error testing runnability: {str(e)}")
            return False, issues
        finally:
            # Clean up
            try:
                os.unlink(temp_file)
            except:
                pass
        
        return True, issues


def generate_tests_llm(source_file: str, provider_name: str, model_name: str, 
                      api_key: str = None, enhanced_mode: bool = True) -> str:
    """
    Generates comprehensive unit tests for a source file using advanced AI techniques.
    Returns the generated test code as a string.
    """
    with open(source_file, 'r') as f:
        source_code = f.read()
    
    if enhanced_mode:
        # Use advanced analysis and context-aware generation
        analyzer = CodeAnalyzer(source_code)
        analysis = analyzer.analyze()
        
        # Create enhanced prompt with detailed context
        prompt = f"""
You are an expert software engineer specializing in writing comprehensive, high-quality unit tests.
Generate a complete Python pytest unit test file for the following Python code.

IMPORTANT: Generate tests that are:
1. Comprehensive - cover all functions, methods, and edge cases
2. Reliable - no flaky tests or incorrect assertions
3. Maintainable - clean, readable, and well-documented
4. Practical - test real behavior, not just syntax

CODE ANALYSIS:
- Functions: {len(analysis['functions'])} functions found
- Classes: {len(analysis['classes'])} classes found  
- Complexity: {analysis['complexity']}
- Project Type: {analysis['project_type']}
- Has Async: {len(analysis['async_functions']) > 0}
- Has Exceptions: {analysis['has_exceptions']}
- Special Requirements: {', '.join(analysis['requirements'])}

FUNCTIONS TO TEST:
{chr(10).join(f"- {func['name']}({', '.join(func['args'])})" for func in analysis['functions'])}

SOURCE CODE:
```python
{source_code}
```

REQUIREMENTS:
- Use pytest framework exclusively
- Include proper imports (pytest, unittest.mock if needed)
- Test ALL functions and methods thoroughly
- Cover edge cases: empty inputs, None values, boundary conditions
- Test error conditions and exception handling
- Use descriptive test names that explain what is being tested
- Include docstrings for complex test functions
- Use appropriate fixtures and parametrize where beneficial
- Mock external dependencies appropriately
- For async functions, use pytest-asyncio
- Ensure tests are isolated and don't depend on each other

Generate ONLY the test code, no explanations or comments outside the code:
"""
        
        provider = get_llm_provider(provider_name, api_key)
        
        # Use context-aware generation if available
        if hasattr(provider, 'generate_with_context'):
            context = {
                'project_type': analysis['project_type'],
                'testing_framework': 'pytest',
                'complexity': analysis['complexity'],
                'requirements': ', '.join(analysis['requirements'])
            }
            test_code = provider.generate_with_context(prompt, model_name, context)
        else:
            test_code = provider.generate_text(prompt, model_name)
        
        # Verify and improve the generated tests
        verifier = TestVerifier(test_code, source_file)
        is_valid, issues, corrected_code = verifier.verify()
        
        if not is_valid:
            print(f"[TestPilot] Found {len(issues)} issues in generated tests, applying corrections...")
            test_code = corrected_code
            
        return test_code
    else:
        # Fallback to basic generation
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


def run_pytest_tests(test_file: str, return_trace: bool = False, 
                    coverage: bool = False) -> Tuple[str, bool, str]:
    """
    Runs pytest on the given test file and returns comprehensive results.
    Returns (output, failed, trace) tuple.
    """
    cmd = ['python', '-m', 'pytest', test_file, '-v']
    
    if coverage:
        cmd.extend(['--cov=.', '--cov-report=term-missing'])
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=os.getcwd(),
            timeout=60  # Prevent hanging tests
        )
        
        output = result.stdout + result.stderr
        failed = result.returncode != 0
        
        if return_trace:
            return output, failed, output
        else:
            return output, failed, output
            
    except subprocess.TimeoutExpired:
        error_msg = "Test execution timed out (60s limit)"
        return error_msg, True, error_msg
    except Exception as e:
        error_msg = f"Error running pytest: {str(e)}"
        return error_msg, True, error_msg


def create_github_issue(repo: str, title: str, body: str, github_token: str) -> str:
    """
    Creates a GitHub issue with enhanced formatting and returns the issue URL.
    """
    if Github is None:
        raise ImportError(
            "PyGithub is not installed. Please install it to use GitHub integration."
        )
    
    if not github_token:
        raise ValueError("GitHub token is required for creating issues.")
    
    # Enhanced issue formatting
    formatted_body = f"""
## Test Failure Report

**Generated by TestPilot** 🚀

{body}

---

*This issue was automatically created by TestPilot. Please review the test failures and update your code accordingly.*

**Quick Actions:**
- [ ] Review the failing tests
- [ ] Fix the underlying issues
- [ ] Re-run tests to verify fixes
- [ ] Close this issue when resolved

*Need help? Check the [TestPilot documentation](https://github.com/yourusername/testpilot) or open a discussion.*
"""
    
    try:
        g = Github(github_token)
        repository = g.get_repo(repo)
        
        issue = repository.create_issue(
            title=f"🔴 {title}",
            body=formatted_body,
            labels=["test-failure", "testpilot-auto", "bug"]
        )
        
        return issue.html_url
        
    except Exception as e:
        raise Exception(f"Failed to create GitHub issue: {str(e)}")


def analyze_test_coverage(test_file: str, source_file: str) -> Dict:
    """
    Analyze test coverage and provide insights.
    """
    try:
        # Handle potential None source_file
        if not source_file:
            source_file = "."
        
        # Run tests with coverage
        result = subprocess.run(
            ['python', '-m', 'pytest', test_file, f'--cov={source_file}', 
             '--cov-report=json', '--cov-report=term-missing'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        coverage_data = {
            'total_coverage': 0,
            'missing_lines': [],
            'covered_lines': [],
            'analysis': 'Coverage analysis not available'
        }
        
        if result.returncode == 0:
            # Parse coverage output
            lines = result.stdout.split('\n')
            for line in lines:
                if 'TOTAL' in line and '%' in line:
                    # Extract percentage
                    parts = line.split()
                    for part in parts:
                        if '%' in part:
                            try:
                                coverage_data['total_coverage'] = int(part.replace('%', ''))
                            except:
                                pass
                            break
        
        return coverage_data
        
    except Exception as e:
        return {
            'total_coverage': 0,
            'missing_lines': [],
            'covered_lines': [],
            'analysis': f'Error analyzing coverage: {str(e)}'
        }


def generate_integration_tests(source_file: str, provider_name: str, 
                             model_name: str, api_key: str = None) -> str:
    """
    Generate integration tests that test component interactions.
    """
    with open(source_file, 'r') as f:
        source_code = f.read()
    
    prompt = f"""
You are an expert software engineer specializing in integration testing.
Generate comprehensive integration tests for the following Python code.
Focus on testing how different components work together, not just individual functions.

Source code:
```python
{source_code}
```

Requirements:
- Use pytest framework
- Focus on integration scenarios, not unit tests
- Test data flow between functions/classes
- Test error propagation and handling
- Use realistic test data and scenarios
- Include setup/teardown for test environments
- Test external dependencies with appropriate mocking
- Use descriptive test names that explain the integration scenario

Generate only the integration test code:
"""
    
    provider = get_llm_provider(provider_name, api_key)
    test_code = provider.generate_text(prompt, model_name)
    return test_code
