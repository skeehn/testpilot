"""
TestPilot: AI-powered test generation, execution, and triage CLI for Python projects.
"""

__version__ = "0.1.0"
__author__ = "TestPilot Authors"

from .core import generate_tests_llm, run_pytest_tests, create_github_issue
from .llm_providers import get_llm_provider

__all__ = [
    "generate_tests_llm",
    "run_pytest_tests", 
    "create_github_issue",
    "get_llm_provider"
] 