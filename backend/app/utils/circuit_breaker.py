"""Circuit breaker factory for external service calls.

Uses pybreaker to short-circuit repeated failures and avoid cascading
outages when an upstream (SAP, Salesforce, Azure OCR) is degraded.
"""
from typing import Dict

import pybreaker

_breakers: Dict[str, pybreaker.CircuitBreaker] = {}


def get_breaker(
    name: str,
    fail_max: int = 5,
    reset_timeout: int = 60,
) -> pybreaker.CircuitBreaker:
    """Return (or lazily create) a named circuit breaker."""
    if name not in _breakers:
        _breakers[name] = pybreaker.CircuitBreaker(
            fail_max=fail_max,
            reset_timeout=reset_timeout,
            name=name,
        )
    return _breakers[name]
