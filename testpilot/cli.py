import os
from pathlib import Path
from contextlib import contextmanager

import click
from dotenv import load_dotenv, set_key

# Optional rich spinner
try:
    from rich.progress import Progress, SpinnerColumn, TextColumn  # type: ignore
except ImportError:  # pragma: no cover
    Progress = None  # type: ignore


@contextmanager
def show_spinner(message: str):
    """Context manager to display a spinner while executing a block."""

    if Progress is None:
        # Fallback: simple message
        click.echo(f"{message}...")
        yield
    else:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            transient=True,
        ) as progress:
            task = progress.add_task(description=message, total=None)
            try:
                yield
            finally:
                progress.update(task, completed=1)

from testpilot.core import (
    create_github_issue,
    generate_tests_llm,
    run_pytest_tests,
)

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
@click.argument(
    'source_file',
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option('--provider', default='openai', help='LLM provider (default: openai)')
@click.option('--model', default='gpt-4o', help='Model name (default: gpt-4o)')
@click.option(
    '--api-key',
    default=None,
    help='API key for LLM provider (default: env var)',
)
@click.option(
    '--output-dir',
    default='./generated_tests',
    help='Directory to save generated tests',
)
@click.option('--overwrite', is_flag=True, default=False, help='Overwrite existing test file')
@click.option('--append', 'append_mode', is_flag=True, default=False, help='Append to existing test file')
@click.option(
    '--prompt-file',
    default=None,
    type=click.Path(exists=True, dir_okay=False, readable=True),
    help='YAML file containing prompt templates',
)
@click.option(
    '--prompt-name',
    default=None,
    help='Name of template inside prompt YAML (default: "default")',
)
@click.option(
    '--temperature',
    type=float,
    default=None,
    help='Generation temperature',
)
@click.option(
    '--max-tokens',
    'max_tokens',
    type=int,
    default=None,
    help='Maximum number of tokens to generate',
)
@click.option(
    '--stop',
    multiple=True,
    help='Stop sequence (can be repeated)',
)
@click.option(
    '--retries',
    default=0,
    type=int,
    help='Retries to regenerate until tests compile',
)
def generate(
    source_file,
    provider,
    model,
    api_key,
    output_dir,
    prompt_file,
    prompt_name,
    overwrite,
    append_mode,
    temperature,
    max_tokens,
    stop,
    retries,
):
    """
    Generate unit tests for a SOURCE_FILE using an LLM.
    """
    os.makedirs(output_dir, exist_ok=True)
    extra_kwargs = {}
    if prompt_file is not None:
        extra_kwargs["prompt_file"] = prompt_file
    if prompt_name is not None:
        extra_kwargs["prompt_name"] = prompt_name
    if temperature is not None:
        extra_kwargs["temperature"] = temperature
    if max_tokens is not None:
        extra_kwargs["max_tokens"] = max_tokens
    if stop:
        extra_kwargs["stop"] = list(stop)
    if retries:
        extra_kwargs["max_retries"] = retries

    with show_spinner("Generating tests"):
        if retries:
            from testpilot.core import generate_tests_llm_with_retry

            test_code = generate_tests_llm_with_retry(
                source_file,
                provider,
                model,
                api_key=api_key,
                **extra_kwargs,
            )
        else:
            test_code = generate_tests_llm(
                source_file,
                provider,
                model,
                api_key,
                **extra_kwargs,
            )
    base = os.path.basename(source_file)
    test_file = os.path.join(output_dir, f"test_{base}")

    file_exists = os.path.exists(test_file)
    if file_exists and not (overwrite or append_mode):
        click.echo(
            f"[generate] Error: {test_file} already exists. Use --overwrite or --append to modify.",
            err=True,
        )
        raise SystemExit(1)

    mode = 'a' if append_mode else 'w'
    with open(test_file, mode) as f:
        if append_mode:
            f.write("\n\n")
        f.write(test_code)

    action = "Appended to" if append_mode and file_exists else "Test file written to"
    click.echo(f"[generate] {action} {test_file}")

@cli.command()
@click.argument(
    'test_file',
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option('--quiet', is_flag=True, default=False, help='Machine-friendly output (pass/fail only)')
def run(test_file, quiet):
    """
    Run tests in TEST_FILE using pytest.
    """
    with show_spinner("Running tests"):
        output, failed, trace = run_pytest_tests(test_file, return_trace=True)

    if quiet:
        click.echo("pass" if not failed else "fail")
        raise SystemExit(0 if not failed else 1)

    click.echo(output)

    # Colourised summary line
    if failed:
        click.secho("[run] Tests failed ❌", fg="red")
    else:
        click.secho("[run] Tests passed ✅", fg="green")

@cli.command()
@click.argument(
    'test_file',
    type=click.Path(exists=True, dir_okay=False, readable=True),
)
@click.option('--repo', required=True, help='GitHub repo (e.g. user/repo)')
@click.option('--labels', default=None, help='Comma-separated GitHub labels')
@click.option('--assignees', default=None, help='Comma-separated GitHub assignees')
@click.option('--gist/--no-gist', default=True, help='Attach failing test file as a gist')
def triage(test_file, repo, labels, assignees, gist):
    """
    Run tests and create a GitHub issue for failures.
    """
    with show_spinner("Running tests"):
        result, failed, trace = run_pytest_tests(test_file, return_trace=True)

    click.echo(result)

    labels_list = [s.strip() for s in labels.split(',')] if labels else None
    assignees_list = [s.strip() for s in assignees.split(',')] if assignees else None

    if failed:
        body = trace

        token = os.getenv("GITHUB_TOKEN")
        if gist and token:
            from testpilot.core import create_github_gist

            try:
                gist_url = create_github_gist(test_file, token, public=False)
                body += f"\n\nFailing test file shared as Gist: {gist_url}"
            except Exception as e:
                click.echo(f"[triage] Warning: failed to create gist ({e})", err=True)

        url = create_github_issue(
            repo,
            f"Test failure in {test_file}",
            body,
            token,
            labels=labels_list,
            assignees=assignees_list,
        )
        click.secho(f"[triage] Issue created: {url}", fg="red")
    else:
        click.secho("[triage] All tests passed. No issue created.", fg="green")

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


# ---------------------------------------------------------------------------
# Init command to scaffold default config
# ---------------------------------------------------------------------------


@cli.command(name="init")
@click.option('--force', is_flag=True, default=False, help='Overwrite existing config files')
def init_cmd(force):
    """Scaffold .env and .testpilot config files in the current directory."""

    created_any = False

    # .env template
    env_template = """# TestPilot configuration – populate your secrets
OPENAI_API_KEY=
GITHUB_TOKEN=
ANTHROPIC_API_KEY=
HF_API_TOKEN=
"""

    if ENV_PATH.exists() and not force:
        click.echo(".env already exists – skipping (use --force to overwrite)")
    else:
        with open(ENV_PATH, "w", encoding="utf-8") as f:
            f.write(env_template)
        click.echo("[init] .env scaffolded. Remember to add your API keys.")
        created_any = True

    # .testpilot config (YAML)
    testpilot_cfg_path = Path(".testpilot.yml")
    cfg_template = """# Default TestPilot configuration
default_provider: openai
default_model: gpt-4o
output_dir: generated_tests
"""

    if testpilot_cfg_path.exists() and not force:
        click.echo(".testpilot.yml already exists – skipping (use --force to overwrite)")
    else:
        testpilot_cfg_path.write_text(cfg_template)
        click.echo("[init] .testpilot.yml scaffolded.")
        created_any = True

    if not created_any:
        click.echo("Nothing to do. All config files already present.")

if __name__ == '__main__':
    cli() 
