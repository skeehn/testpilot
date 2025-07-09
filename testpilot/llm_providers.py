from abc import ABC, abstractmethod
import os

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

class LLMProvider(ABC):
    @abstractmethod
    def generate_text(self, prompt: str, model_name: str) -> str:
        pass

class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str = None):
        if OpenAI is None:
            raise ImportError("openai package is not installed.")
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key must be provided via argument or OPENAI_API_KEY env var.")
        self.client = OpenAI(api_key=self.api_key)

    def generate_text(self, prompt: str, model_name: str) -> str:
        chat_completion = self.client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": "You are an expert software engineer."},
                {"role": "user", "content": prompt}
            ]
        )
        content = chat_completion.choices[0].message.content
        # Extract code block if present
        if "```python" in content:
            content = content.split("```python")[1]
            content = content.split("```", 1)[0]
        return content.strip()

def get_llm_provider(provider_name: str, api_key: str = None) -> LLMProvider:
    if provider_name.lower() == "openai":
        return OpenAIProvider(api_key)
    # Future: add elif for other providers (Anthropic, Ollama, etc.)
    raise ValueError(f"Unsupported LLM provider: {provider_name}") 