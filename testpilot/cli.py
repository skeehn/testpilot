import click
import os
from pathlib import Path
from dotenv import load_dotenv, set_key
from testpilot.core import generate_tests_llm, run_pytest_tests, create_github_issue

ENV_PATH = Path(".env")
ONBOARD_FLAG = Path(".testpilot_onboarded")

WELCOME = """
🚀 Welcome to TestPilot!

TestPilot is your AI-powered CLI for generating, running, and triaging Python tests.

What can you do?
- Generate unit tests for your code with an LLM
- Run tests and see results instantly
- Triage failures to GitHub issues

Get started in seconds:
  1. Enter your API keys when prompted
  2. Run: testpilot generate my_module.py
  3. Run: testpilot run generated_tests/test_my_module.py
  4. Run: testpilot triage ...

For help, run: testpilot help
Docs: https://github.com/yourusername/testpilot#readme
"""

QUICKSTART = """
✅ Setup complete! Here’s your next steps:

1. Generate tests:
   testpilot generate my_module.py
2. Run tests:
   testpilot run generated_tests/test_my_module.py
3. Triage failures:
   testpilot triage generated_tests/test_my_module.py --repo yourusername/yourrepo

For more, run: testpilot help
"""

HELP_TEXT = """
TestPilot CLI - AI-powered test generation, execution, and triage

Usage:
  testpilot generate <source_file>
  testpilot run <test_file>
  testpilot triage <test_file> --repo <repo>
  testpilot reset-keys
  testpilot help

Quick Start:
  1. testpilot generate my_module.py
  2. testpilot run generated_tests/test_my_module.py
  3. testpilot triage generated_tests/test_my_module.py --repo yourusername/yourrepo

Docs: https://github.com/yourusername/testpilot#readme
"""

def ensure_api_keys():
    load_dotenv(dotenv_path=ENV_PATH)
    openai_key = os.getenv("OPENAI_API_KEY")
    github_token = os.getenv("GITHUB_TOKEN")

    if not openai_key:
        openai_key = input("Enter your OpenAI API Key: ").strip()
        set_key(str(ENV_PATH), "OPENAI_API_KEY", openai_key)
    if not github_token:
        github_token = input("Enter your GitHub Token (for triage, optional): ").strip()
        if github_token:
            set_key(str(ENV_PATH), "GITHUB_TOKEN", github_token)
    # Show quickstart after first setup
    if not ONBOARD_FLAG.exists():
        print(QUICKSTART)
        ONBOARD_FLAG.write_text("onboarded")

@click.group()
def cli():
    # On first run, show onboarding message
    if not ONBOARD_FLAG.exists():
        print(WELCOME)
    ensure_api_keys()

@cli.command()
def help():
    """Show help, quick start, and docs."""
    print(HELP_TEXT)

@cli.command()
@click.argument('source_file', type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('--provider', default='openai', help='LLM provider (default: openai)')
@click.option('--model', default='gpt-4o', help='Model name (default: gpt-4o)')
@click.option('--api-key', default=None, help='API key for LLM provider (default: env var)')
@click.option('--output-dir', default='./generated_tests', help='Directory to save generated tests')
def generate(source_file, provider, model, api_key, output_dir):
    """
    Generate unit tests for a SOURCE_FILE using an LLM.
    """
    os.makedirs(output_dir, exist_ok=True)
    test_code = generate_tests_llm(source_file, provider, model, api_key)
    base = os.path.basename(source_file)
    test_file = os.path.join(output_dir, f"test_{base}")
    with open(test_file, 'w') as f:
        f.write(test_code)
    click.echo(f"[generate] Test file written to {test_file}")

@cli.command()
@click.argument('test_file', type=click.Path(exists=True, dir_okay=False, readable=True))
def run(test_file):
    """
    Run tests in TEST_FILE using pytest.
    """
    result = run_pytest_tests(test_file)
    click.echo(result)

@cli.command()
@click.argument('test_file', type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('--repo', required=True, help='GitHub repo (e.g. user/repo)')
def triage(test_file, repo):
    """
    Run tests and create a GitHub issue for failures.
    """
    result, failed, trace = run_pytest_tests(test_file, return_trace=True)
    click.echo(result)
    if failed:
        url = create_github_issue(repo, f"Test failure in {test_file}", trace, os.getenv("GITHUB_TOKEN"))
        click.echo(f"[triage] Issue created: {url}")
    else:
        click.echo("[triage] All tests passed. No issue created.")

@cli.command()
def reset_keys():
    """
    Clear API keys and onboarding flag, then prompt for new keys.
    """
    if ENV_PATH.exists():
        ENV_PATH.unlink()
    if ONBOARD_FLAG.exists():
        ONBOARD_FLAG.unlink()
    print("API keys cleared. Re-running onboarding...")
    ensure_api_keys()

if __name__ == '__main__':
    cli() 