# evals/provider.py
"""Provider abstraction for the answer-writer (the rented LLM).

We rent the model, own the pipeline. The gate and pipeline depend only on
Provider.complete(prompt) -> str. OpenRouterProvider calls OpenRouter over
stdlib urllib (no third-party deps); tests use StaticProvider so the unit suite
stays offline and deterministic. API key comes from OPENROUTER_API_KEY -- never
hardcode or commit it. Public repos only while on free models (see CLAUDE.md).
"""

import json
import os
import urllib.request

# Some providers (Groq) sit behind Cloudflare and 403 the default urllib
# User-Agent; a plain UA is enough to pass. Harmless for the others.
_USER_AGENT = "icarus/0.1"


def _openai_chat(url: str, key: str, model: str, prompt: str, timeout: float) -> str:
    """One OpenAI-compatible chat-completions call. Shared by OpenRouter + Groq."""
    body = json.dumps(
        {"model": model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
    ).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data["choices"][0]["message"]["content"]


class Provider:
    def complete(self, prompt: str) -> str:  # pragma: no cover - interface
        raise NotImplementedError


class StaticProvider(Provider):
    """Test double: returns queued responses in order, sticking on the last."""

    def __init__(self, responses):
        self._responses = [responses] if isinstance(responses, str) else list(responses)
        self._i = 0

    def complete(self, prompt: str) -> str:
        r = self._responses[min(self._i, len(self._responses) - 1)]
        self._i += 1
        return r


class OpenRouterProvider(Provider):
    """Calls an OpenRouter chat-completions model. Network. Stdlib only."""

    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, model: str = "cohere/north-mini-code:free", timeout: float = 60.0):
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        key = os.environ.get("OPENROUTER_API_KEY")
        if not key:
            raise RuntimeError("OPENROUTER_API_KEY not set")
        return _openai_chat(self.URL, key, self.model, prompt, self.timeout)


class GroqProvider(Provider):
    """Calls a Groq chat-completions model (OpenAI-compatible). Network. Stdlib.

    Groq's free tier is fast and far more generous than OpenRouter's 50/day. Used
    as the answer-correctness judge (a different model from the writer). Key from
    GROQ_API_KEY. Public repos only (free tiers may train on inputs)."""

    URL = "https://api.groq.com/openai/v1/chat/completions"

    def __init__(self, model: str = "llama-3.3-70b-versatile", timeout: float = 60.0):
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        key = os.environ.get("GROQ_API_KEY")
        if not key:
            raise RuntimeError("GROQ_API_KEY not set")
        return _openai_chat(self.URL, key, self.model, prompt, self.timeout)


def _parse_gemini(data: dict) -> str:
    """Extract the text from a Gemini generateContent response."""
    return data["candidates"][0]["content"]["parts"][0]["text"]


class GeminiProvider(Provider):
    """Calls Google Gemini (generateContent REST). Network. Stdlib only.

    Gemini's free tier (~1,500 req/day) is the default writer -- far more headroom
    than OpenRouter's 50/day. Key from GEMINI_API_KEY (passed as ?key=). Public
    repos only (free tiers may train on inputs)."""

    BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, model: str = "gemini-2.5-flash", timeout: float = 60.0):
        self.model = model
        self.timeout = timeout

    def complete(self, prompt: str) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        url = f"{self.BASE}/{self.model}:generateContent?key={key}"
        body = json.dumps(
            {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}
        ).encode()
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": _USER_AGENT},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        return _parse_gemini(data)


_PROVIDERS = {
    "gemini": GeminiProvider,
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
}
_KEY_ENV = {
    "gemini": "GEMINI_API_KEY",
    "groq": "GROQ_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
}


def make_provider(name: str) -> Provider:
    """Build a provider by name (default-configured). Raises on an unknown name."""
    try:
        return _PROVIDERS[name]()
    except KeyError:
        raise ValueError(f"unknown provider: {name}")


def has_provider_key(name: str) -> bool:
    """True if the env key for this provider is set (so we can run it)."""
    return bool(os.environ.get(_KEY_ENV.get(name, "")))
