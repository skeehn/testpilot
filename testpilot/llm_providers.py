import importlib
import os
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING

# Optional runtime dependency handling for the OpenAI client library.
try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

# For static type checkers, provide a stub so that `OpenAI` is always defined.
if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI as _OpenAI  # type: ignore
    OpenAI = _OpenAI  # type: ignore

PROVIDER_REGISTRY = {}


def register_provider(name: str):
    """Decorator to register an LLM provider class by name."""

    def _wrapper(cls):
        PROVIDER_REGISTRY[name.lower()] = cls
        return cls

    return _wrapper


class LLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, model_name: str) -> str:
        pass


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: Optional[str] = None):
        if OpenAI is None:
            raise ImportError("openai package is not installed.")

        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided via argument or "
                "OPENAI_API_KEY env var."
            )
        # Instantiate OpenAI client with the provided key.
        self.client = OpenAI(api_key=self.api_key)

    def generate_text(self, prompt: str, model_name: str) -> str:
        chat_completion = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert software engineer."},
                {"role": "user", "content": prompt},
            ],
        )
        content = chat_completion.choices[0].message.content
        if "```python" in content:
            content = content.split("```python")[1].split("```", 1)[0]
        return content.strip()


@register_provider("anthropic")
class AnthropicProvider(LLMProvider):
    """Stub provider for Anthropic's Claude models."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key must be provided via argument or "
                "ANTHROPIC_API_KEY env var."
            )

    def generate_text(self, prompt: str, model_name: str) -> str:
        return "Anthropic provider is not yet implemented"


def get_llm_provider(provider_name: str, api_key: Optional[str] = None) -> LLMProvider:
    """Return an instance of a registered LLM provider."""

    provider_cls = PROVIDER_REGISTRY.get(provider_name.lower())
    if provider_cls is None and "." in provider_name:
        module_name, class_name = provider_name.rsplit(".", 1)
        module = importlib.import_module(module_name)
        provider_cls = getattr(module, class_name)
    if provider_cls is None:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    return provider_cls(api_key)
