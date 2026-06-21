"""bharatai.orchestration.runner — a thin facade over the compiled graph.

Invokes the compiled StateGraph for an initial BharatState and returns the final state as a
BharatState (LangGraph returns the channel values as a dict, which is re-validated here).
"""
from __future__ import annotations

from typing import Any

from bharatai.orchestration.graph_builder import build_graph
from bharatai.orchestration.registry import GraphDependencies
from bharatai.orchestration.state import BharatState


class BharatGraphRunner:
    """Runs the compiled multi-agent graph over a BharatState."""

    def __init__(self, compiled_graph: Any) -> None:
        """Wrap an already-compiled StateGraph."""
        self._graph = compiled_graph

    @classmethod
    def from_dependencies(cls, deps: GraphDependencies) -> BharatGraphRunner:
        """Build the graph from agent dependencies and wrap it in a runner."""
        return cls(build_graph(deps))

    def run(self, state: BharatState) -> BharatState:
        """Execute the graph end-to-end and return the final validated state."""
        result = self._graph.invoke(state)
        if isinstance(result, BharatState):
            return result
        return BharatState.model_validate(result)
