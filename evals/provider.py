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
        body = json.dumps(
            {"model": self.model, "messages": [{"role": "user", "content": prompt}], "temperature": 0}
        ).encode()
        req = urllib.request.Request(
            self.URL,
            data=body,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]
