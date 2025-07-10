# Architecture Overview

TestPilot is organized as a lightweight CLI application with a modular core.

```
cli.py       - command line interface using Click
core.py      - high level operations for generating, running and triaging tests
llm_providers.py - abstraction layer for different LLM backends
```

The CLI commands are thin wrappers around the functions in `core.py`. Those functions in turn rely on pluggable LLM providers defined in `llm_providers.py`.

## Adding providers
New language model providers can be added by implementing the `LLMProvider` abstract class and exposing a factory in `get_llm_provider`.

## Generated tests
Tests are written out to the `generated_tests/` directory so that you can review them before running.

## GitHub integration
When triaging failures, TestPilot uses `PyGithub` to open issues in your repository. This requires a token with `repo` scope.
