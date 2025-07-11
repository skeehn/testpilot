import importlib
import os
from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING, Set

# Optional runtime dependency handling for the OpenAI client library.
try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover
    OpenAI = None  # type: ignore

# For static type checkers, provide a stub so that `OpenAI` is always defined.
if TYPE_CHECKING:  # pragma: no cover
    from openai import OpenAI as _OpenAI  # type: ignore
    OpenAI = _OpenAI  # type: ignore

# Optional runtime dependency handling for Anthropic SDK.
try:
    import anthropic  # type: ignore
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import anthropic as _anthropic  # type: ignore
    anthropic = _anthropic  # type: ignore

PROVIDER_REGISTRY = {}


def register_provider(name: str):
    """Decorator to register an LLM provider class by name."""

    def _wrapper(cls):
        PROVIDER_REGISTRY[name.lower()] = cls
        return cls

    return _wrapper


class LLMProvider(ABC):
    """Abstract provider interface with model metadata."""

    # The provider’s recommended default model (may be None if caller must supply)
    default_model: Optional[str] = None

    # Explicit set of supported model names. If empty/None, skip validation.
    supported_models: Optional[Set[str]] = None

    @abstractmethod
    def generate_text(self, prompt: str, model_name: str) -> str:
        """Return LLM completion for *prompt* using *model_name*."""
        raise NotImplementedError


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    default_model = "gpt-4o"
    supported_models: Set[str] = {
        "gpt-4o",
        "gpt-4o-mini",
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    }

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
    """Provider for Anthropic's Claude models (via official `anthropic` SDK)."""

    default_model = "claude-3-sonnet-20240229"
    supported_models: Set[str] = {
        "claude-instant-1",
        "claude-2",
        "claude-3-sonnet-20240229",
        "claude-3-opus-20240229",
    }

    def __init__(self, api_key: Optional[str] = None):
        if anthropic is None:
            raise ImportError("anthropic package is not installed.")

        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key must be provided via argument or "
                "ANTHROPIC_API_KEY env var."
            )

        # Instantiate Anthropic client.
        self.client = anthropic.Anthropic(api_key=self.api_key)  # type: ignore[attr-defined]

    def generate_text(self, prompt: str, model_name: str) -> str:
        """Generate text using Claude models.

        A high `max_tokens` is used by default; providers requiring stricter
        control can override later when we add CLI flags.
        """

        response = self.client.messages.create(  # type: ignore[attr-defined]
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=4096,
        )

        # The SDK returns `response.content` as a list of blocks; concatenate
        # text parts in order.
        # The exact structure may evolve, so fall back gracefully.
        if hasattr(response, "content") and isinstance(response.content, list):
            text_parts = []
            for block in response.content:
                # Newer SDK versions wrap text blocks in objects with a `.text` attribute
                # Older versions may just be plain dicts.
                if hasattr(block, "text"):
                    text_parts.append(block.text)
                elif isinstance(block, dict):
                    text_parts.append(block.get("text", ""))
                else:
                    text_parts.append(str(block))
            content = "".join(text_parts)
        else:
            # Fallback: stringify whole response.
            content = str(getattr(response, "content", response))

        # Strip code fencing if it exists.
        if "```python" in content:
            content = content.split("```python", 1)[1].split("```", 1)[0]
        return content.strip()


# ---------------------------------------------------------------------------
# Azure OpenAI Provider (extends OpenAIProvider)
# ---------------------------------------------------------------------------


@register_provider("azure-openai")
@register_provider("azure")
class AzureOpenAIProvider(OpenAIProvider):
    """Provider for Azure-hosted OpenAI deployments.

    Required environment variables (unless passed explicitly):
      • AZURE_OPENAI_ENDPOINT – e.g. https://myresource.openai.azure.com
      • AZURE_OPENAI_API_KEY – the resource access key
      • AZURE_OPENAI_DEPLOYMENT – deployment/engine name (maps to *model*)

    Optional:
      • AZURE_OPENAI_API_VERSION – defaults to 2023-05-15
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        endpoint: Optional[str] = None,
        deployment: Optional[str] = None,
        api_version: str | None = None,
    ) -> None:
        if OpenAI is None:
            raise ImportError("openai package is not installed.")

        endpoint = endpoint or os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = api_key or os.environ.get("AZURE_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        deployment = deployment or os.environ.get("AZURE_OPENAI_DEPLOYMENT") or os.environ.get("AZURE_OPENAI_DEPLOYMENT_NAME")
        api_version = api_version or os.environ.get("AZURE_OPENAI_API_VERSION", "2023-05-15")

        if not all([endpoint, api_key, deployment]):
            missing = [n for n, v in {
                "endpoint": endpoint,
                "api_key": api_key,
                "deployment": deployment,
            }.items() if not v]
            raise ValueError(f"Azure OpenAI missing required value(s): {', '.join(missing)}")

        # Azure requires the API version in the query string; the `openai` SDK
        # supports this via a default header or by passing `api_version` param.
        base_url = f"{endpoint}/openai/deployments/{deployment}"

        # Build client with azure endpoint – note the `api_version` header.
        self.client = OpenAI(
            api_key=api_key,
            base_url=base_url,
            default_headers={"api-version": api_version},
        )

        # Store deployment as default & supported model set (since Azure maps 1:1)
        self.deployment = deployment
        self.default_model = deployment
        self.supported_models = {deployment} if deployment else set()

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def generate_text(self, prompt: str, model_name: str | None = None) -> str:  # type: ignore[override]
        """Generate chat completion using Azure deployment.

        If *model_name* is omitted, the configured deployment name is used.
        """

        model = model_name or self.deployment

        chat_completion = self.client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an expert software engineer."},
                {"role": "user", "content": prompt},
            ],
        )
        content = chat_completion.choices[0].message.content
        if "```python" in content:
            content = content.split("```python", 1)[1].split("```", 1)[0]
        return content.strip()


# ---------------------------------------------------------------------------
# Mistral via HuggingFace Inference API
# ---------------------------------------------------------------------------


# The HF Inference API is standard HTTP, we use `requests` if available.
try:
    import requests  # type: ignore
except ImportError:  # pragma: no cover
    requests = None  # type: ignore

if TYPE_CHECKING:  # pragma: no cover
    import requests as _requests  # type: ignore
    requests = _requests  # type: ignore


@register_provider("mistral")
@register_provider("hf-mistral")
class MistralProvider(LLMProvider):
    default_model = "mistralai/Mistral-7B-Instruct-v0.2"
    supported_models: Set[str] = {
        "mistralai/Mistral-7B-Instruct-v0.2",
        "mistralai/Mistral-7B-Instruct-v0.1",
    }

    """Provider that calls Mistral models via HuggingFace Inference API.

    Usage:
        export HF_API_TOKEN=...
        generate_tests_llm(..., provider="mistral", model_name="mistralai/Mistral-7B-Instruct-v0.2")

    The provider streams tokens and accumulates them into a final string. In
    later phases we will surface the generator object for real-time streaming.
    """

    def __init__(self, api_key: Optional[str] = None):
        if requests is None:
            raise ImportError("requests package is required for MistralProvider")

        self.api_key = api_key or os.environ.get("HF_API_TOKEN") or os.environ.get("HUGGINGFACE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "HuggingFace API token must be provided via argument or HF_API_TOKEN env var."
            )

        # HF inference endpoint base.
        self.base_url = "https://api-inference.huggingface.co/models"

    # The HF API model identifier IS the model name (e.g. mistralai/Mistral-7B).
    def generate_text(self, prompt: str, model_name: str) -> str:  # type: ignore[override]
        url = f"{self.base_url}/{model_name}"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "text/event-stream",  # enable server-sent events
            "Content-Type": "application/json",
        }

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": 1024,
                "temperature": 0.1,
                # streaming implicitly enabled by Accept header
            },
            "stream": True,
        }

        # Accumulate chunks as they arrive.
        parts: list[str] = []

        with requests.post(url, headers=headers, json=payload, stream=True, timeout=300) as resp:  # type: ignore[attr-defined]
            resp.raise_for_status()
            for line in resp.iter_lines(decode_unicode=True):  # type: ignore[call-arg]
                if not line:
                    continue
                # The Inference API streams JSON lines; skip the done token.
                if line.strip() == "[DONE]":
                    break
                try:
                    # Each line is a JSON dict with {"token": {"text": "..."}, ...}
                    import json  # local import to avoid top-level cost

                    data = json.loads(line)
                    token_text = data.get("token", {}).get("text", "")
                    parts.append(token_text)
                except Exception:
                    # If parsing fails, append raw line for visibility.
                    parts.append(line)

        content = "".join(parts)

        # Remove code fences if present.
        if "```python" in content:
            content = content.split("```python", 1)[1].split("```", 1)[0]
        return content.strip()


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
