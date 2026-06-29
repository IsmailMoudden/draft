"""LangGraph orchestrator — retrieve → enrich → write.

The enrich node gets one automatic retry pass if there are desks with
unclear items and TPT data is available, allowing it to go fetch more
detail for specific strategies before the writer runs.
"""

from __future__ import annotations

from datetime import date

import structlog
from langgraph.graph import END, StateGraph

from mo_intelligence.shared.models import OrchestratorState, RunType
from mo_intelligence.orchestrator import nodes

log = structlog.get_logger(__name__)


def build_graph() -> StateGraph:
    g = StateGraph(OrchestratorState)
    g.add_node("retrieve", nodes.retrieve)
    g.add_node("enrich",   nodes.enrich)
    g.add_node("write",    nodes.write)

    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "enrich")
    g.add_conditional_edges(
        "enrich",
        _route_after_enrich,
        {"write": "write", "fetch_more": "enrich"},
    )
    g.add_edge("write", END)
    return g


def _route_after_enrich(state: OrchestratorState) -> str:
    """If any desk has unclear items and we haven't retried yet, loop back to enrich."""
    if state.enrich_retries < 1:
        unclear_desks = [d for d in state.enriched_desks if d.unclear_items]
        if unclear_desks and state.tpt_file_t:
            log.info(
                "enrich_retry",
                unclear_desks=[d.desk for d in unclear_desks],
            )
            return "fetch_more"
    return "write"


async def run_pipeline(
    run_type: RunType,
    trade_date: date,
    pnl_attr_file: str = "",
    tpt_file_t: str = "",
    tpt_file_t1: str = "",
) -> OrchestratorState:
    graph = build_graph().compile()
    initial = OrchestratorState(
        run_type=run_type,
        trade_date=trade_date,
        pnl_attr_file=pnl_attr_file,
        tpt_file_t=tpt_file_t,
        tpt_file_t1=tpt_file_t1,
    )
    result = await graph.ainvoke(initial)
    return OrchestratorState.model_validate(result)
