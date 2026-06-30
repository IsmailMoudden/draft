"""LangGraph nodes: retrieve → enrich → write."""

from __future__ import annotations

import structlog

from mo_intelligence.context_memory.strategy_memory import StrategyMemory
from mo_intelligence.data_loaders import enricher as _enricher
from mo_intelligence.data_loaders import pnl_attr_loader, tpt_loader
from mo_intelligence.shared.models import OrchestratorState

log = structlog.get_logger(__name__)

# loaded once per process, reused across runs
_memory = StrategyMemory()


async def retrieve(state: OrchestratorState) -> dict:
    """Load PnL rows, desk totals, prior comments, and TPT snapshot data."""
    updates: dict = {}

    if state.pnl_attr_file:
        log.info("retrieve.pnl_attr", file=state.pnl_attr_file, cob=state.trade_date)
        s_rows   = pnl_attr_loader.load_strategy_rows(state.pnl_attr_file, state.trade_date)
        desk_pnl = pnl_attr_loader.load_desk_pnl(state.pnl_attr_file, state.trade_date)
        prior    = pnl_attr_loader.load_prior_comments(state.pnl_attr_file, state.trade_date)
        log.info("retrieve.pnl_attr.done", strategy_rows=len(s_rows), desks=len(desk_pnl))
        updates["strategy_rows"]  = s_rows
        updates["desk_pnl"]       = desk_pnl
        updates["prior_comments"] = prior
    else:
        log.warning("retrieve.pnl_attr.missing")

    if state.tpt_file_t and state.tpt_file_t1:
        log.info("retrieve.tpt", file_t=state.tpt_file_t)
        contexts = tpt_loader.build_strategy_contexts(
            state.tpt_file_t, state.tpt_file_t1, state.trade_date
        )
        _memory.upsert_many(contexts)
        log.info("retrieve.tpt.done", contexts=len(contexts), memory_size=len(_memory))
    else:
        log.warning("retrieve.tpt.missing")

    return updates


async def enrich(state: OrchestratorState) -> dict:
    """Cross-reference PnL strategies with TPT memory to build per-desk context."""
    log.info("enrich.start", desks=len(state.desk_pnl), retry=state.enrich_retries)
    enriched = _enricher.build_enriched_contexts(
        state.strategy_rows,
        state.desk_pnl,
        state.prior_comments,
        _memory,
    )
    unclear_total = sum(len(d.unclear_items) for d in enriched)
    log.info("enrich.done", enriched_desks=len(enriched), unclear=unclear_total)
    return {
        "enriched_desks":  enriched,
        "enrich_retries":  state.enrich_retries + 1,
    }


async def write(state: OrchestratorState) -> dict:
    """Call the AI writer then persist the strategy memory to disk."""
    from mo_intelligence.ai_writer.writer import generate
    result = await generate(state)
    _memory.save()
    log.info("memory.saved", strategies=len(_memory))
    return result
