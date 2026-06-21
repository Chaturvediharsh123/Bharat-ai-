"""bharatai.orchestration.graph_builder — wire the 7 agents into a compiled StateGraph.

Each node is a thin wrapper that reads the state slice it needs, calls an injected agent,
and returns a state delta. Every node is wrapped by ``_safe`` so a single agent failure is
recorded as a NodeError and the run degrades instead of crashing. Routing skips the document
node when nothing was uploaded and the translator node when the target language is English.
"""
from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any

from langgraph.graph import END, StateGraph

from bharatai.agents.base import AgentContext
from bharatai.agents.bureaucracy_translator_agent import TranslateInput
from bharatai.agents.citizen_profile_agent import RawProfileInput
from bharatai.agents.document_intelligence_agent import DocumentInput
from bharatai.agents.eligibility_agent import EligibilityInput
from bharatai.agents.recommendation_agent import RecommendationInput
from bharatai.agents.reminder_agent import ReminderInput
from bharatai.agents.scheme_discovery_agent import DiscoveryInput
from bharatai.common.logging import get_logger
from bharatai.orchestration.registry import GraphDependencies
from bharatai.orchestration.state import BharatState, NodeError

_logger = get_logger(__name__)
_ENGLISH = {"en", "english"}

NodeFn = Callable[[BharatState], dict[str, Any]]

# Sentinel returned by a node that deliberately did nothing (e.g. no profile yet) — it is
# NOT recorded as a completed node, so completed_nodes reflects only real work.
_SKIP: dict[str, Any] = {}


def _ctx(state: BharatState) -> AgentContext:
    return AgentContext(
        trace_id=state.run_id,
        citizen_id=state.citizen_profile.id if state.citizen_profile else None,
        locale=state.locale,
        now=state.now,
    )


def _safe(name: str, fn: NodeFn) -> NodeFn:
    @functools.wraps(fn)
    def wrapper(state: BharatState) -> dict[str, Any]:
        try:
            update = fn(state)
        except Exception as exc:  # noqa: BLE001 - one node failing must not crash the run
            _logger.warning("node failed", extra={"node": name, "error": str(exc)})
            return {
                "errors": [NodeError(node=name, error_type=type(exc).__name__, message=str(exc))],
                "messages": [f"{name} failed: {exc}"],
            }
        if update is _SKIP:
            return {"messages": [f"{name} skipped"]}
        update["completed_nodes"] = [name]
        return update

    return wrapper


def _node_profile(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    result = deps.profile.run(
        RawProfileInput(existing=state.citizen_profile, raw_fields=state.raw_input), _ctx(state)
    )
    return {"citizen_profile": result.profile, "messages": result.warnings}


def _node_discovery(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    if state.citizen_profile is None:
        return _SKIP
    result = deps.discovery.run(
        DiscoveryInput(
            profile=state.citizen_profile,
            candidate_schemes=state.candidate_schemes,
            requested_scheme_id=state.requested_scheme_id,
        ),
        _ctx(state),
    )
    return {"discovered_schemes": result.schemes}


def _node_document(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    if state.citizen_profile is None:
        return _SKIP
    required = sorted(
        {
            doc
            for scheme in state.discovered_schemes
            for doc in scheme.eligibility_criteria.required_documents
        },
        key=lambda doc: doc.value,
    )
    result = deps.document.run(
        DocumentInput(
            documents=state.uploaded_documents,
            profile=state.citizen_profile,
            required_documents=required,
        ),
        _ctx(state),
    )
    return {
        "document_reports": result.documents,
        "validated_doc_types": result.validated_doc_types,
        "readiness_score": result.readiness_score,
        "messages": result.warnings,
    }


def _node_eligibility(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    if state.citizen_profile is None:
        return _SKIP
    results = deps.eligibility.run(
        EligibilityInput(
            profile=state.citizen_profile,
            schemes=state.discovered_schemes,
            validated_doc_types=state.validated_doc_types,
        ),
        _ctx(state),
    )
    return {"eligibility_results": results}


def _node_recommendation(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    if state.citizen_profile is None:
        return _SKIP
    result = deps.recommendation.run(
        RecommendationInput(
            profile=state.citizen_profile,
            eligibility_results=state.eligibility_results,
            schemes=state.discovered_schemes,
            applications=state.applications,
        ),
        _ctx(state),
    )
    return {"recommendations": result.recommendations, "messages": [result.summary]}


def _node_reminder(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    if state.citizen_profile is None:
        return _SKIP
    result = deps.reminder.run(
        ReminderInput(
            profile=state.citizen_profile,
            schemes=state.discovered_schemes,
            eligibility_results=state.eligibility_results,
            applications=state.applications,
            existing_reminders=state.existing_reminders,
            lead_days=state.lead_days,
        ),
        _ctx(state),
    )
    return {"reminders": result.reminders, "messages": [result.summary]}


def _node_translator(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    text = "\n".join(r.explanation for r in state.eligibility_results if r.explanation)
    if not text.strip():
        return _SKIP
    result = deps.translator.run(
        TranslateInput(text=text, target_language=state.target_language), _ctx(state)
    )
    return {"translations": [result]}


def _node_aggregate(state: BharatState, *, deps: GraphDependencies) -> dict[str, Any]:
    completed = len(state.completed_nodes) + 1
    failed = len(state.errors)
    return {"messages": [f"Run complete: {completed} nodes succeeded, {failed} failed."]}


def _route_documents(state: BharatState) -> str:
    return "document" if state.uploaded_documents else "eligibility"


def _route_translate(state: BharatState) -> str:
    return "translator" if state.target_language.lower() not in _ENGLISH else "aggregate"


def build_graph(deps: GraphDependencies) -> Any:
    """Build and compile the BharatAI multi-agent StateGraph for the given dependencies."""
    graph = StateGraph(BharatState)
    nodes = {
        "profile": _node_profile,
        "discovery": _node_discovery,
        "document": _node_document,
        "eligibility": _node_eligibility,
        "recommendation": _node_recommendation,
        "reminder": _node_reminder,
        "translator": _node_translator,
        "aggregate": _node_aggregate,
    }
    for name, fn in nodes.items():
        # LangGraph's add_node overloads don't model a plain state->dict callable cleanly.
        graph.add_node(name, _safe(name, functools.partial(fn, deps=deps)))  # type: ignore[call-overload]

    graph.set_entry_point("profile")
    graph.add_edge("profile", "discovery")
    graph.add_conditional_edges(
        "discovery", _route_documents, {"document": "document", "eligibility": "eligibility"}
    )
    graph.add_edge("document", "eligibility")
    graph.add_edge("eligibility", "recommendation")
    graph.add_edge("recommendation", "reminder")
    graph.add_conditional_edges(
        "reminder", _route_translate, {"translator": "translator", "aggregate": "aggregate"}
    )
    graph.add_edge("translator", "aggregate")
    graph.add_edge("aggregate", END)
    return graph.compile()
