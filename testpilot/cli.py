import click
import os
from testpilot.core import generate_tests_llm, run_pytest_tests, create_github_issue

@click.group()
def cli():
    """TestPilot: Automate test generation, execution, and triage."""
    pass

@cli.command()
@click.argument('source_file', type=click.Path(exists=True, dir_okay=False, readable=True))
@click.option('--provider', default='openai', help='LLM provider (default: openai)')
@click.option('--model', default='gpt-4o', help='Model name (default: gpt-4o)')
@click.option('--api-key', default=None, help='API key for LLM provider (default: env var)')
@click.option('--output-dir', default='./generated_tests', help='Directory to save generated tests.')
def generate(source_file, provider, model, api_key, output_dir):
    """
    Generate unit tests for a SOURCE_FILE using an LLM.
    """
    click.echo(f"Generating tests for {source_file} using {provider} ({model})...")
    test_code = generate_tests_llm(source_file, provider, model, api_key)
    if not test_code:
        click.echo("Test generation failed or returned empty content.", err=True)
        return
    os.makedirs(output_dir, exist_ok=True)
    file_name = os.path.basename(source_file)
    test_file_name = f"test_{os.path.splitext(file_name)[0]}.py"
    output_path = os.path.join(output_dir, test_file_name)
    with open(output_path, 'w') as f:
        f.write(test_code)
    click.echo(f"Generated tests saved to: {output_path}")

@cli.command()
@click.argument('test_path', type=click.Path(exists=True, readable=True))
def run(test_path):
    """
    Run unit tests at TEST_PATH (file or directory) using pytest.
    """
    click.echo(f"Running tests in {test_path}...")
    exit_code, output = run_pytest_tests(test_path)
    click.echo("--- Pytest Output ---")
    click.echo(output)
    click.echo("--- End Pytest Output ---")
    if exit_code != 0:
        click.echo(f"Tests failed with exit code: {exit_code}", err=True)
        raise click.ClickException("Tests failed.")
    else:
        click.echo("All tests passed!")

@cli.command()
@click.argument('test_path', type=click.Path(exists=True, readable=True))
@click.option('--repo', required=True, help='Full GitHub repository name (e.g., "user/repo").')
@click.option('--api-key', default=None, help='GitHub API token (default: env var)')
def triage(test_path, repo, api_key):
    """
    Run tests and triage failures by creating GitHub issues.
    """
    click.echo(f"Running tests in {test_path} for triage...")
    exit_code, output = run_pytest_tests(test_path)
    if exit_code != 0:
        click.echo("Tests failed. Creating GitHub issue...")
        title = f"Test Failure: {os.path.basename(test_path)}"
        body = f"Automated test run failed for `{test_path}`.\n\nPytest Output:\n```
{output}
```"
        labels = ["test-failure", "needs-investigation", "testpilot-auto"]
        issue_url = create_github_issue(repo, title, body, labels, api_key)
        if issue_url:
            click.echo(f"GitHub issue created: {issue_url}")
        else:
            click.echo("Failed to create GitHub issue.", err=True)
    else:
        click.echo("All tests passed. No issue to triage.")

if __name__ == '__main__':
    cli() 