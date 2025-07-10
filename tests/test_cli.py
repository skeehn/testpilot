from pathlib import Path

from click.testing import CliRunner

from testpilot import cli


def test_cli_generate_and_run(monkeypatch):
    runner = CliRunner()
    monkeypatch.setattr(cli, "ensure_api_keys", lambda: None)

    def fake_generate(source_file, provider, model, api_key):
        return "def test_generated():\n    assert True\n"

    monkeypatch.setattr(cli, "generate_tests_llm", fake_generate)

    with runner.isolated_filesystem():
        src = Path("foo.py")
        src.write_text("def foo():\n    return 42\n")

        gen_result = runner.invoke(cli.cli, ["generate", str(src)])
        assert gen_result.exit_code == 0
        test_file = Path("generated_tests") / "test_foo.py"
        assert test_file.exists()
        assert "Test file written" in gen_result.output

        run_result = runner.invoke(cli.cli, ["run", str(test_file)])
        assert run_result.exit_code == 0
        assert "1 passed" in run_result.output
