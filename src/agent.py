"""Compiled LangGraph state machine for the assortment-planning agent.

Purpose: make each safety gate and business step explicit and auditable.
Workflow step: Step 6 — weekly style review and controlled action routing.
Inputs: StyleWeek and local Chroma stores.
Outputs: AgentResult containing route, recommendation, citations, and audit events.
Controls/rights: kill switch, freshness, cutoff, grounding, rights, and audit gates.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

import config
from src.audit import AuditLog
from src.controls import cutoff_watchdog, freshness_guard, grounding_check, strip_pii
from src.models import Action, AuditEvent, Recommendation, RetrievedChunk, StyleWeek
from src.reason import reason
from src.retrieve import retrieve


class GraphState(TypedDict):
    """State carried between compiled graph nodes."""

    style: StyleWeek
    as_of: date
    store_dir: Path
    kill_switch: bool
    chunks: list[RetrievedChunk]
    recommendation: Recommendation | None
    route: str
    events: list[AuditEvent]


def _event(state: GraphState, node: str, action: str, output: str) -> AuditEvent:
    """Create a redacted audit event for the current graph state."""

    return AuditEvent(
        timestamp=datetime.now(timezone.utc).isoformat(),
        style_id=state["style"].style_id,
        node=node,
        action=action,
        sources=[chunk.source for chunk in state["chunks"]],
        output=strip_pii(output),
    )


def check_kill_switch(state: GraphState) -> dict[str, object]:
    """Route all work to manual review when the emergency switch is active."""

    if state["kill_switch"]:
        event = _event(state, "check_kill_switch", "manual_queue", "Kill switch is on.")
        return {"route": "manual_queue", "events": state["events"] + [event]}
    event = _event(state, "check_kill_switch", "continue", "Kill switch is off.")
    return {"events": state["events"] + [event]}


def freshness_node(state: GraphState) -> dict[str, object]:
    """Hold stale internal data before retrieval or reasoning."""

    result = freshness_guard(state["style"], state["as_of"])
    event = _event(state, "freshness_guard", result.route, result.reason)
    return {
        "route": result.route if not result.allowed else state["route"],
        "events": state["events"] + [event],
    }


def cutoff_node(state: GraphState) -> dict[str, object]:
    """Escalate undecided styles close to a vendor cutoff."""

    result = cutoff_watchdog(state["style"], state["as_of"])
    event = _event(state, "cutoff_watchdog", result.route, result.reason)
    return {
        "route": result.route if not result.allowed else state["route"],
        "events": state["events"] + [event],
    }


def retrieve_node(state: GraphState) -> dict[str, object]:
    """Retrieve cited context from all three Chroma collections."""

    chunks = (
        retrieve("sales demand inventory markdown", "playbook", state["store_dir"])
        + retrieve(
            "demand quality competitor dupe",
            "market_signals",
            state["store_dir"],
            style_id=state["style"].style_id,
        )
        + retrieve("past decision outcome", "past_decisions", state["store_dir"], top_k=3)
    )
    event = _event(
        {**state, "chunks": chunks},
        "retrieve_context",
        "retrieve",
        "Retrieved cited context from three Chroma stores.",
    )
    return {"chunks": chunks, "events": state["events"] + [event]}


def reason_node(state: GraphState) -> dict[str, object]:
    """Generate a structured recommendation from the cited evidence."""

    recommendation = reason(state["style"], state["chunks"])
    event = _event(
        {**state, "recommendation": recommendation},
        "reason",
        recommendation.action.value,
        recommendation.rationale,
    )
    return {"recommendation": recommendation, "events": state["events"] + [event]}


def grounding_node(state: GraphState) -> dict[str, object]:
    """Reject recommendations that lack valid supporting citations."""

    recommendation = state["recommendation"]
    if recommendation is None:
        return {"route": "escalate_to_planner"}
    result = grounding_check(recommendation, state["chunks"])
    event = _event(state, "grounding_check", result.route, result.reason)
    return {
        "route": result.route if not result.allowed else state["route"],
        "events": state["events"] + [event],
    }


def route_node(state: GraphState) -> dict[str, object]:
    """Choose planner review or a controlled draft route after all gates pass."""

    recommendation = state["recommendation"]
    if recommendation is None:
        route = "escalate_to_planner"
    elif recommendation.confidence < config.CONFIDENCE_THRESHOLD:
        route = "escalate_to_planner"
    elif state["style"].is_core_franchise and recommendation.action in {Action.CHASE, Action.RETIRE}:
        route = "escalate_to_planner"
    else:
        route = "draft_for_approval"
    event = _event(state, "route", route, "All applicable graph gates completed.")
    return {"route": route, "events": state["events"] + [event]}


def _next_after_gate(state: GraphState) -> str:
    """Continue only when the current safety gate has not selected an escalation."""

    return "continue" if state["route"] == "start" else "finish"


def build_graph():
    """Compile the LangGraph workflow used by run()."""

    graph = StateGraph(GraphState)
    graph.add_node("check_kill_switch", check_kill_switch)
    graph.add_node("freshness_guard", freshness_node)
    graph.add_node("cutoff_watchdog", cutoff_node)
    graph.add_node("retrieve_context", retrieve_node)
    graph.add_node("reason", reason_node)
    graph.add_node("grounding_check", grounding_node)
    graph.add_node("route", route_node)
    graph.add_edge(START, "check_kill_switch")
    graph.add_conditional_edges("check_kill_switch", _next_after_gate, {"continue": "freshness_guard", "finish": END})
    graph.add_conditional_edges("freshness_guard", _next_after_gate, {"continue": "cutoff_watchdog", "finish": END})
    graph.add_conditional_edges("cutoff_watchdog", _next_after_gate, {"continue": "retrieve_context", "finish": END})
    graph.add_edge("retrieve_context", "reason")
    graph.add_edge("reason", "grounding_check")
    graph.add_conditional_edges("grounding_check", _next_after_gate, {"continue": "route", "finish": END})
    graph.add_edge("route", END)
    return graph.compile()


def run(
    style: StyleWeek,
    store_dir: Path = Path("data/rag"),
    *,
    as_of: date = date(2026, 4, 13),
    audit_path: Path | None = None,
    kill_switch_override: bool | None = None,
) -> AgentResult:
    """Run the compiled graph and optionally persist its audit events."""

    state: GraphState = {
        "style": style,
        "as_of": as_of,
        "store_dir": store_dir,
        "kill_switch": config.KILL_SWITCH if kill_switch_override is None else kill_switch_override,
        "chunks": [],
        "recommendation": None,
        "route": "start",
        "events": [],
    }
    result = build_graph().invoke(state)
    if audit_path:
        log = AuditLog(audit_path)
        for event in result["events"]:
            log.append(event)
    return AgentResult(
        route=result["route"],
        recommendation=result["recommendation"],
        events=result["events"],
    )


class AgentResult:
    """Public result of a complete graph run."""

    def __init__(
        self,
        route: str,
        recommendation: Recommendation | None,
        events: list[AuditEvent],
    ) -> None:
        self.route = route
        self.recommendation = recommendation
        self.events = events
