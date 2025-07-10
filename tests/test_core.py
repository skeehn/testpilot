from testpilot.core import generate_tests_llm, run_pytest_tests


def test_generate_tests_llm(monkeypatch, tmp_path):
    source = tmp_path / "example.py"
    source.write_text("def foo():\n    return 1\n")

    captured = {}

    class FakeProvider:
        def generate_text(self, prompt: str, model_name: str) -> str:
            captured['prompt'] = prompt
            captured['model_name'] = model_name
            return "TEST_CODE"

    def fake_get(provider_name, api_key=None):
        captured['provider_name'] = provider_name
        captured['api_key'] = api_key
        return FakeProvider()

    monkeypatch.setattr('testpilot.core.get_llm_provider', fake_get)

    result = generate_tests_llm(str(source), 'openai', 'gpt-4o', api_key='key')
    assert result == "TEST_CODE"
    assert 'foo()' in captured['prompt']
    assert captured['model_name'] == 'gpt-4o'
    assert captured['provider_name'] == 'openai'
    assert captured['api_key'] == 'key'


def test_run_pytest_tests(tmp_path):
    test_file = tmp_path / "test_sample.py"
    test_file.write_text("def test_ok():\n    assert 2 == 1 + 1\n")

    output = run_pytest_tests(str(test_file))
    assert "1 passed" in output
