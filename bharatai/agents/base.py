"""bharatai.agents.base — the uniform agent contract.

Every core agent obeys one interface: ``run(data, ctx) -> result``. Agents depend only
on the domain and injected ports — never on the DB, UI, or any framework directly.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Generic, Protocol, TypeVar, runtime_checkable

from bharatai.common.ids import now_utc

In = TypeVar("In")
Out = TypeVar("Out")
I_contra = TypeVar("I_contra", contravariant=True)
O_co = TypeVar("O_co", covariant=True)


@dataclass(frozen=True)
class AgentContext:
    """Request-scoped metadata passed to every agent run."""

    trace_id: str
    citizen_id: str | None = None
    locale: str = "en"
    now: datetime = field(default_factory=now_utc)


class BaseAgent(ABC, Generic[In, Out]):
    """Abstract base for the core agents. Subclasses set ``name`` and implement ``run``."""

    name: ClassVar[str] = ""
    version: ClassVar[str] = "1.0"

    @abstractmethod
    def run(self, data: In, ctx: AgentContext) -> Out:
        """Execute the agent on its typed input and return its typed output."""


@runtime_checkable
class Agent(Protocol[I_contra, O_co]):
    """Structural interface that orchestration nodes depend on (not the concrete class)."""

    name: ClassVar[str]

    def run(self, data: I_contra, ctx: AgentContext) -> O_co:
        """Execute the agent on its typed input and return its typed output."""
        ...
