# evals/trust.py
"""The deterministic trust interlock: private code -> private-safe model ONLY.

Like the honesty gate, the routing decision is provable in code: a provider is
private-safe iff it declares private_safe=True, and anything else is refused.
For the network writer, that flag exists only on the class using the dedicated
paid-key env (see evals/provider.py). The code proves fail-closed routing; the
operator must separately verify that the configured Cloud Project is actively
billed, because no key string can prove its contractual tier."""


class PrivateDataError(RuntimeError):
    """Raised instead of ever sending private code to a non-private-safe model."""


def assert_safe_for_private(provider) -> None:
    if not getattr(provider, "private_safe", False):
        raise PrivateDataError(
            f"{type(provider).__name__} is not private-safe: refusing to send "
            "private code to a model that may train on it")
