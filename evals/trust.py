# evals/trust.py
"""The deterministic trust interlock: private code -> private-safe model ONLY.

Like the honesty gate, this is provable in code, never a judgement call: a
provider is private-safe iff it declares private_safe=True (set only at
construction from a dedicated paid-key env -- see evals/provider.py). Anything
else, including a provider that never declared itself, is refused."""


class PrivateDataError(RuntimeError):
    """Raised instead of ever sending private code to a non-private-safe model."""


def assert_safe_for_private(provider) -> None:
    if not getattr(provider, "private_safe", False):
        raise PrivateDataError(
            f"{type(provider).__name__} is not private-safe: refusing to send "
            "private code to a model that may train on it")
