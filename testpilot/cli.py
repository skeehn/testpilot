import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv, set_key

from testpilot.core import (
    analyze_test_coverage,
    create_github_issue,
    generate_integration_tests,
    generate_tests_llm,
    run_pytest_tests,
)
from testpilot.llm_providers import get_available_providers

ENV_PATH = Path(".env")
ONBOARD_FLAG = Path(".testpilot_onboarded")
CONFIG_FILE = Path(".testpilot_config.json")

WELCOME = """
🚀 Welcome to TestPilot - Your AI Testing Co-Pilot!

TestPilot is your revolutionary AI-powered CLI for generating, running, and
triaging Python tests. Built to be 50× faster and better than traditional
testing workflows.

What makes TestPilot special?
✨ Advanced AI models (OpenAI, Anthropic, Ollama) with smart context
  understanding
🧠 Intelligent code analysis and comprehensive test coverage
🔄 Automatic test verification and quality assurance
🎯 Integration and unit test generation
📊 Coverage analysis and insights
🐛 Smart GitHub issue creation for failures
🔧 Extensible architecture with plugin support

Get started in seconds:
  1. Enter your API keys when prompted
  2. Run: testpilot generate my_module.py
  3. Run: testpilot run generated_tests/test_my_module.py
  4. Run: testpilot triage ... (optional)

For help, run: testpilot --help
Advanced usage: testpilot interactive
"""

QUICKSTART = """
✅ Setup complete! Here's your next steps:

🎯 Quick Start:
1. Generate comprehensive tests:
   testpilot generate my_module.py --enhanced

2. Run tests with coverage:
   testpilot run generated_tests/test_my_module.py --coverage

3. Triage any failures:
   testpilot triage generated_tests/test_my_module.py --repo user/repo

🚀 Advanced Features:
- Interactive mode: testpilot interactive
- Integration tests: testpilot generate my_module.py --integration
- Multiple providers: testpilot generate my_module.py --provider anthropic
- Coverage analysis: testpilot coverage generated_tests/test_my_module.py
  my_module.py

💡 Pro Tips:
- Use --enhanced for better test quality (slower but worth it)
- Try different AI providers for variety
- Use interactive mode for complex scenarios

For more help: testpilot --help
"""


def ensure_api_keys():
    """Ensure API keys are configured with improved UX."""
    load_dotenv(dotenv_path=ENV_PATH)

    providers = get_available_providers()
    print(f"\n🔧 Available AI providers: {', '.join(providers)}")

    # Check OpenAI key
    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        print("\n🔑 OpenAI API Key Setup:")
        print("Get your API key from: https://platform.openai.com/api-keys")
        openai_key = input("Enter your OpenAI API Key (or press Enter to skip): ").strip()
        if openai_key:
            set_key(str(ENV_PATH), "OPENAI_API_KEY", openai_key)

    # Check Anthropic key
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if not anthropic_key:
        print("\n🤖 Anthropic API Key Setup (optional):")
        print("Get your API key from: https://console.anthropic.com/")
        anthropic_key = input("Enter your Anthropic API Key (or press Enter to skip): ").strip()
        if anthropic_key:
            set_key(str(ENV_PATH), "ANTHROPIC_API_KEY", anthropic_key)

    # Check GitHub token
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        print("\n🐙 GitHub Token Setup (optional, for issue creation):")
        print("Create a token at: https://github.com/settings/tokens")
        github_token = input("Enter your GitHub Token (or press Enter to skip): ").strip()
        if github_token:
            set_key(str(ENV_PATH), "GITHUB_TOKEN", github_token)

    # Show quickstart after first setup
    if not ONBOARD_FLAG.exists():
        print(QUICKSTART)
        ONBOARD_FLAG.write_text("onboarded")


@click.group()
@click.version_option(version="1.0.0", prog_name="TestPilot")
@click.option('--debug', is_flag=True, help='Enable debug mode')
def cli(debug):
    """TestPilot - AI-powered test generation, execution, and triage CLI."""
    if debug:
        os.environ["TESTPILOT_DEBUG"] = "1"

    # On first run, show onboarding message
    if not ONBOARD_FLAG.exists():
        print(WELCOME)
    ensure_api_keys()


@cli.command()
def help():
    """Show comprehensive help and documentation."""
    help_text = """
🚀 TestPilot - Your AI Testing Co-Pilot

COMMANDS:
  generate     Generate unit tests for a Python file
  run          Run tests with pytest
  triage       Run tests and create GitHub issues for failures
  coverage     Analyze test coverage
  interactive  Interactive test generation mode
  reset-keys   Reset API keys
  providers    List available AI providers

EXAMPLES:
  # Basic test generation
  testpilot generate my_module.py

  # Enhanced test generation with Claude
  testpilot generate my_module.py --provider anthropic \\
    --model claude-3-sonnet-20240229 --enhanced

  # Generate integration tests
  testpilot generate my_module.py --integration

  # Run tests with coverage
  testpilot run generated_tests/test_my_module.py --coverage

  # Interactive mode for complex scenarios
  testpilot interactive

  # Coverage analysis
  testpilot coverage generated_tests/test_my_module.py my_module.py

ADVANCED FEATURES:
  - Multiple AI providers (OpenAI, Anthropic, Ollama)
  - Code analysis and intelligent test generation
  - Automatic test verification and correction
  - Integration and unit test modes
  - Coverage analysis and insights
  - Smart GitHub issue creation

Get started: testpilot generate your_file.py --enhanced
Documentation: https://github.com/yourusername/testpilot
"""
    print(help_text)


@cli.command()
@click.argument('source_file', type=click.Path(exists=True, dir_okay=False,
                                               readable=True))
@click.option('--provider', default='openai',
              help='AI provider (openai, anthropic, ollama)')
@click.option('--model', default='gpt-4o', help='Model name')
@click.option('--api-key', default=None, help='API key (default: from env)')
@click.option('--output-dir', default='./generated_tests',
              help='Output directory')
@click.option('--enhanced', is_flag=True,
              help='Use enhanced mode with code analysis')
@click.option('--integration', is_flag=True,
              help='Generate integration tests instead of unit tests')
@click.option('--interactive', is_flag=True,
              help='Interactive generation with clarifying questions')
def generate(source_file, provider, model, api_key, output_dir, enhanced,
             integration, interactive):
    """Generate unit tests for SOURCE_FILE using AI."""

    if interactive:
        click.echo("🤖 Interactive Test Generation Mode")
        click.echo("I'll ask you some questions to generate better tests...")

        # Ask clarifying questions
        test_type = click.prompt(
            "What type of tests do you want?",
            type=click.Choice(['unit', 'integration', 'both']),
            default='unit'
        )

        # Override flags based on interactive input
        if test_type in ['integration', 'both']:
            integration = True
        if test_type == 'both':
            enhanced = True

    try:
        os.makedirs(output_dir, exist_ok=True)

        if integration:
            click.echo(f"[generate] 🧪 Generating integration tests for "
                       f"{source_file}...")
            test_code = generate_integration_tests(source_file, provider,
                                                   model, api_key)
            test_file = os.path.join(output_dir, f"integration_test_"
                                     f"{os.path.basename(source_file)}")
        else:
            click.echo(f"[generate] 🧪 Generating unit tests for "
                       f"{source_file}...")
            if enhanced:
                click.echo("[generate] 🚀 Enhanced mode: Using code analysis "
                           "and verification...")
            test_code = generate_tests_llm(source_file, provider, model,
                                           api_key, enhanced)
            test_file = os.path.join(output_dir, f"test_"
                                     f"{os.path.basename(source_file)}")

        with open(test_file, 'w') as f:
            f.write(test_code)

        click.echo(f"[generate] ✅ Test file written to {test_file}")

        # Optionally run the tests immediately
        if click.confirm("Would you like to run the generated tests now?"):
            click.echo("[generate] 🏃 Running tests...")
            output, failed, _ = run_pytest_tests(test_file, coverage=True)
            click.echo(output)

            if not failed:
                click.echo("[generate] 🎉 All tests passed!")
            else:
                click.echo("[generate] ⚠️  Some tests failed. "
                           "Check the output above.")

    except Exception as e:
        click.echo(f"[generate] ❌ Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('test_file', type=click.Path(exists=True, dir_okay=False,
                                             readable=True))
@click.option('--coverage', is_flag=True, help='Show coverage report')
@click.option('--watch', is_flag=True, help='Watch for file changes and re-run')
def run(test_file, coverage, watch):
    """Run tests in TEST_FILE using pytest."""

    if watch:
        click.echo("🔄 Watch mode not implemented yet. Running tests once...")

    try:
        click.echo(f"[run] 🏃 Running tests in {test_file}...")
        output, failed, _ = run_pytest_tests(test_file, coverage=coverage)
        click.echo(output)

        if not failed:
            click.echo("[run] 🎉 All tests passed!")
        else:
            click.echo("[run] ⚠️  Some tests failed.")

    except Exception as e:
        click.echo(f"[run] ❌ Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('test_file', type=click.Path(exists=True, dir_okay=False,
                                             readable=True))
@click.option('--repo', required=True, help='GitHub repo (e.g. user/repo)')
@click.option('--auto-fix', is_flag=True,
              help='Attempt to auto-fix simple issues')
def triage(test_file, repo, auto_fix):
    """Run tests and create GitHub issues for failures."""

    try:
        click.echo(f"[triage] 🏃 Running tests in {test_file}...")
        output, failed, trace = run_pytest_tests(test_file, return_trace=True)
        click.echo(output)

        if failed:
            click.echo("[triage] 🐛 Tests failed. Creating GitHub issue...")

            # Enhanced issue title and body
            issue_title = f"Test failures in {os.path.basename(test_file)}"
            issue_body = f"""
**Test File:** `{test_file}`
**Generated by:** TestPilot AI Testing Co-Pilot

**Test Output:**
```
{trace}
```

**Environment:**
- Python: {sys.version}
- TestPilot: 1.0.0
- Pytest: (run `pytest --version` to check)
"""

            github_token = os.getenv("GITHUB_TOKEN")
            if not github_token:
                click.echo("[triage] ❌ GitHub token not found. "
                           "Run 'testpilot reset-keys' to configure.",
                           err=True)
                sys.exit(1)
            url = create_github_issue(repo, issue_title, issue_body,
                                      github_token)
            click.echo(f"[triage] 🎯 Issue created: {url}")

            if auto_fix:
                click.echo("[triage] 🔧 Auto-fix not implemented yet.")

        else:
            click.echo("[triage] ✅ All tests passed. No issues to create.")

    except Exception as e:
        click.echo(f"[triage] ❌ Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('test_file', type=click.Path(exists=True, dir_okay=False,
                                             readable=True))
@click.argument('source_file', type=click.Path(exists=True, dir_okay=False,
                                                readable=True))
def coverage(test_file, source_file):
    """Analyze test coverage for SOURCE_FILE using TEST_FILE."""

    try:
        click.echo(f"[coverage] 📊 Analyzing coverage for {source_file}...")
        coverage_data = analyze_test_coverage(test_file, source_file)

        click.echo(f"[coverage] 📈 Total Coverage: "
                   f"{coverage_data['total_coverage']}%")
        click.echo(f"[coverage] 📋 Analysis: {coverage_data['analysis']}")

        if coverage_data['total_coverage'] >= 90:
            click.echo("[coverage] 🎉 Excellent coverage!")
        elif coverage_data['total_coverage'] >= 70:
            click.echo("[coverage] 👍 Good coverage!")
        else:
            click.echo("[coverage] ⚠️  Coverage could be improved.")

    except Exception as e:
        click.echo(f"[coverage] ❌ Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
def interactive():
    """Interactive test generation mode."""

    click.echo("🤖 Welcome to TestPilot Interactive Mode!")
    click.echo("Let's generate some amazing tests together...\n")

    # Get source file
    source_file = click.prompt("Enter the Python file to test",
                               type=click.Path(exists=True))

    # Get provider preference
    providers = get_available_providers()
    provider = click.prompt(
        f"Choose AI provider ({'/'.join(providers)})",
        type=click.Choice(providers),
        default='openai'
    )

    # Get model
    if provider == 'openai':
        model = click.prompt("Model", default='gpt-4o')
    elif provider == 'anthropic':
        model = click.prompt("Model", default='claude-3-sonnet-20240229')
    else:
        model = click.prompt("Model", default='llama2')

    # Get test preferences
    test_type = click.prompt(
        "Test type",
        type=click.Choice(['unit', 'integration', 'both']),
        default='unit'
    )

    enhanced = click.confirm("Use enhanced mode with code analysis?",
                             default=True)

    # Generate tests
    try:
        if test_type in ['unit', 'both']:
            click.echo("\n🧪 Generating unit tests...")
            test_code = generate_tests_llm(source_file, provider, model,
                                           enhanced_mode=enhanced)

            output_dir = "generated_tests"
            os.makedirs(output_dir, exist_ok=True)
            test_file = os.path.join(output_dir, f"test_"
                                     f"{os.path.basename(source_file)}")

            with open(test_file, 'w') as f:
                f.write(test_code)

            click.echo(f"✅ Unit tests written to {test_file}")

        if test_type in ['integration', 'both']:
            click.echo("\n🔄 Generating integration tests...")
            integration_code = generate_integration_tests(source_file,
                                                          provider, model)

            output_dir = "generated_tests"
            os.makedirs(output_dir, exist_ok=True)
            integration_file = os.path.join(output_dir, f"integration_test_"
                                            f"{os.path.basename(source_file)}")

            with open(integration_file, 'w') as f:
                f.write(integration_code)

            click.echo(f"✅ Integration tests written to {integration_file}")

        # Ask if they want to run the tests
        if click.confirm("\nWould you like to run the tests now?"):
            files_to_run = []
            if test_type in ['unit', 'both']:
                files_to_run.append(test_file)
            if test_type in ['integration', 'both']:
                files_to_run.append(integration_file)

            for file in files_to_run:
                click.echo(f"\n🏃 Running {file}...")
                output, failed, _ = run_pytest_tests(file, coverage=True)
                click.echo(output)

                if not failed:
                    click.echo(f"🎉 All tests in {file} passed!")
                else:
                    click.echo(f"⚠️  Some tests in {file} failed.")

    except Exception as e:
        click.echo(f"❌ Error: {str(e)}", err=True)
        sys.exit(1)


@cli.command()
def providers():
    """List available AI providers."""

    providers = get_available_providers()
    click.echo("🤖 Available AI Providers:")

    for provider in providers:
        # Check if provider is configured
        if provider == 'openai':
            configured = "✅" if os.getenv("OPENAI_API_KEY") else "❌"
            click.echo(f"  {provider}: {configured}")
        elif provider == 'anthropic':
            configured = "✅" if os.getenv("ANTHROPIC_API_KEY") else "❌"
            click.echo(f"  {provider}: {configured}")
        elif provider == 'ollama':
            configured = "🔄"  # Ollama doesn't need API key
            click.echo(f"  {provider}: {configured} (local)")
        else:
            click.echo(f"  {provider}: ❓")

    click.echo("\n💡 To configure a provider, run: testpilot reset-keys")


@cli.command()
def reset_keys():
    """Reset API keys and configuration."""

    if ENV_PATH.exists():
        ENV_PATH.unlink()
        click.echo("🔑 API keys cleared.")

    if ONBOARD_FLAG.exists():
        ONBOARD_FLAG.unlink()
        click.echo("🔄 Onboarding flag cleared.")

    click.echo("Re-running setup...")
    ensure_api_keys()


if __name__ == '__main__':
    cli()
