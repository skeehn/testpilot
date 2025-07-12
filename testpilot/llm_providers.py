import importlib
import os
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Tuple

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
    
    @abstractmethod
    def generate_with_context(self, prompt: str, model_name: str, context: Dict) -> str:
        """Generate text with additional context for enhanced quality."""
        pass


@register_provider("openai")
class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = None):
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError("openai package is not installed.") from exc
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key must be provided via argument or "
                "OPENAI_API_KEY env var."
            )
        self.client = OpenAI(api_key=self.api_key)

    def generate_text(self, prompt: str, model_name: str) -> str:
        chat_completion = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert software engineer specializing in comprehensive test generation."},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,  # Lower temperature for more consistent, reliable test generation
        )
        content = chat_completion.choices[0].message.content
        if "```python" in content:
            content = content.split("```python")[1].split("```", 1)[0]
        return content.strip()
    
    def generate_with_context(self, prompt: str, model_name: str, context: Dict) -> str:
        """Generate text with additional context for enhanced quality."""
        system_prompt = f"""You are an expert software engineer specializing in comprehensive test generation.

Context:
- Project type: {context.get('project_type', 'Unknown')}
- Testing framework: {context.get('testing_framework', 'pytest')}
- Code complexity: {context.get('complexity', 'Medium')}
- Special requirements: {context.get('requirements', 'Standard unit tests')}

Your task is to generate high-quality, comprehensive tests that:
1. Cover all edge cases and error conditions
2. Follow best practices for the testing framework
3. Are maintainable and readable
4. Actually test the intended behavior (not just syntax)
5. Include proper mocking where needed
6. Handle async code appropriately if present
"""
        
        chat_completion = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
        )
        content = chat_completion.choices[0].message.content
        if "```python" in content:
            content = content.split("```python")[1].split("```", 1)[0]
        return content.strip()


@register_provider("anthropic")
class AnthropicProvider(LLMProvider):
    """Full implementation of Anthropic's Claude models."""

    def __init__(self, api_key: str = None):
        try:
            import anthropic
        except ImportError as exc:
            raise ImportError(
                "anthropic package is not installed. Install with: pip install anthropic"
            ) from exc
        
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key must be provided via argument or "
                "ANTHROPIC_API_KEY env var."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def generate_text(self, prompt: str, model_name: str) -> str:
        response = self.client.messages.create(
            model=model_name,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
        )
        content = response.content[0].text
        if "```python" in content:
            content = content.split("```python")[1].split("```", 1)[0]
        return content.strip()
    
    def generate_with_context(self, prompt: str, model_name: str, context: Dict) -> str:
        """Generate text with additional context for enhanced quality."""
        enhanced_prompt = f"""You are Claude, an expert software engineer specializing in comprehensive test generation.

Context:
- Project type: {context.get('project_type', 'Unknown')}
- Testing framework: {context.get('testing_framework', 'pytest')}
- Code complexity: {context.get('complexity', 'Medium')}
- Special requirements: {context.get('requirements', 'Standard unit tests')}

Your task is to generate high-quality, comprehensive tests that:
1. Cover all edge cases and error conditions
2. Follow best practices for the testing framework
3. Are maintainable and readable
4. Actually test the intended behavior (not just syntax)
5. Include proper mocking where needed
6. Handle async code appropriately if present

{prompt}"""
        
        response = self.client.messages.create(
            model=model_name,
            max_tokens=4000,
            messages=[
                {"role": "user", "content": enhanced_prompt}
            ],
            temperature=0.1,
        )
        content = response.content[0].text
        if "```python" in content:
            content = content.split("```python")[1].split("```", 1)[0]
        return content.strip()


@register_provider("ollama")
class OllamaProvider(LLMProvider):
    """Local model support via Ollama."""

    def __init__(self, api_key: str = None, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.api_key = api_key  # Not used for Ollama but kept for interface consistency
        
    def generate_text(self, prompt: str, model_name: str) -> str:
        try:
            import requests
        except ImportError as exc:
            raise ImportError(
                "requests package is not installed. Install with: pip install requests"
            ) from exc
        
        response = requests.post(
            f"{self.base_url}/api/generate",
            json={
                "model": model_name,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": 0.1}
            },
            timeout=120,
        )
        response.raise_for_status()
        content = response.json()["response"]
        
        if "```python" in content:
            content = content.split("```python")[1].split("```", 1)[0]
        return content.strip()
    
    def generate_with_context(self, prompt: str, model_name: str, context: Dict) -> str:
        """Generate text with additional context for enhanced quality."""
        enhanced_prompt = f"""You are an expert software engineer specializing in comprehensive test generation.

Context:
- Project type: {context.get('project_type', 'Unknown')}
- Testing framework: {context.get('testing_framework', 'pytest')}
- Code complexity: {context.get('complexity', 'Medium')}
- Special requirements: {context.get('requirements', 'Standard unit tests')}

Your task is to generate high-quality, comprehensive tests that:
1. Cover all edge cases and error conditions
2. Follow best practices for the testing framework
3. Are maintainable and readable
4. Actually test the intended behavior (not just syntax)
5. Include proper mocking where needed
6. Handle async code appropriately if present

{prompt}"""
        
        return self.generate_text(enhanced_prompt, model_name)


def get_llm_provider(provider_name: str, api_key: str = None, **kwargs) -> LLMProvider:
    """Return an instance of a registered LLM provider."""

    provider_cls = PROVIDER_REGISTRY.get(provider_name.lower())
    if provider_cls is None and "." in provider_name:
        module_name, class_name = provider_name.rsplit(".", 1)
        module = importlib.import_module(module_name)
        provider_cls = getattr(module, class_name)
    if provider_cls is None:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
    return provider_cls(api_key, **kwargs)


def get_available_providers() -> List[str]:
    """Return a list of available LLM providers."""
    return list(PROVIDER_REGISTRY.keys())
