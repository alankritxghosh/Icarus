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
import re
import time
import urllib.error
import urllib.request

# Some providers (Groq) sit behind Cloudflare and 403 the default urllib
# User-Agent; a plain UA is enough to pass. Harmless for the others.
_USER_AGENT = "icarus/0.1"


_RETRY_DELAY = re.compile(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)s"')

# Cap a single backoff sleep. One per-minute free-tier window; named so the
# interactive server's patience is visible and adjustable in one place.
_MAX_BACKOFF_SECONDS = 65


def _with_retry(call, retries: int = 6, base: float = 2.0):
    """Run `call()`, retrying on HTTP 429 with backoff (free tiers cap RPM).

    Wait order of preference: a Retry-After header, else the `retryDelay` Gemini
    returns in its 429 body, else base*2**attempt. Capped at 65s (covers a
    per-minute window). Non-429 errors raise immediately. Unit-tested offline."""
    for attempt in range(retries):
        try:
            return call()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == retries - 1:
                raise
            wait = None
            header = e.headers.get("Retry-After") if e.headers else None
            if header:
                wait = float(header)
            else:
                try:  # Gemini puts the delay in the body, not a header
                    m = _RETRY_DELAY.search(e.read().decode())
                    if m:
                        wait = float(m.group(1))
                except Exception:
                    pass
            if wait is None:
                wait = base * (2 ** attempt)
            time.sleep(min(wait, _MAX_BACKOFF_SECONDS))


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

    def _do():
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())

    return _with_retry(_do)["choices"][0]["message"]["content"]


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

    # flash-lite is the free-tier-friendly model; full flash has a tight free cap.
    def __init__(self, model: str = "gemini-2.5-flash-lite", timeout: float = 60.0):
        self.model = model
        self.timeout = timeout

    def _build_request(self, prompt: str, key: str) -> urllib.request.Request:
        # Key goes in the x-goog-api-key header, NOT the URL query string — a key
        # in a URL leaks into proxy/server logs, history, and tracebacks.
        url = f"{self.BASE}/{self.model}:generateContent"
        body = json.dumps(
            {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0}}
        ).encode()
        return urllib.request.Request(
            url,
            data=body,
            headers={
                "Content-Type": "application/json",
                "User-Agent": _USER_AGENT,
                "x-goog-api-key": key,
            },
        )

    def complete(self, prompt: str) -> str:
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY not set")
        req = self._build_request(prompt, key)

        def _do():
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return json.loads(resp.read())

        return _parse_gemini(_with_retry(_do))


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
