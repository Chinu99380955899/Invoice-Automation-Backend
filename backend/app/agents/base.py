"""Shared primitives for the agent pipeline."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Dict, Generic, Optional, TypeVar

from app.core.logging import get_logger

log = get_logger("agent")

TIn = TypeVar("TIn")
TOut = TypeVar("TOut")


@dataclass
class AgentResult(Generic[TOut]):
    """Uniform result envelope for every agent."""
    success: bool
    output: Optional[TOut] = None
    agent: str = ""
    duration_ms: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC, Generic[TIn, TOut]):
    """Abstract agent. Each concrete agent does one step of the pipeline."""

    name: str = "base"

    @abstractmethod
    def _run(self, inputs: TIn) -> TOut: ...

    def execute(self, inputs: TIn) -> AgentResult[TOut]:
        """Run the agent with timing, structured logging, and fail-safe errors."""
        start = perf_counter()
        try:
            out = self._run(inputs)
            duration_ms = int((perf_counter() - start) * 1000)
            log.info("agent_ok", agent=self.name, duration_ms=duration_ms)
            return AgentResult(
                success=True,
                output=out,
                agent=self.name,
                duration_ms=duration_ms,
            )
        except Exception as exc:
            duration_ms = int((perf_counter() - start) * 1000)
            log.error(
                "agent_failed",
                agent=self.name,
                duration_ms=duration_ms,
                error=str(exc),
            )
            # Never raise — return a failed result so pipeline can degrade.
            return AgentResult(
                success=False,
                output=None,
                agent=self.name,
                duration_ms=duration_ms,
                error=str(exc),
            )
