"""Pipeline nodes — retrieve, enrich, write.

retrieve  →  loads PnL attribution rows + desk aggregates + prior comments.
             If TPT files are provided, also loads StrategyContext objects
             and upserts them into the persistent StrategyMemory.

enrich    →  cross-references strategy rows with StrategyMemory to produce
             one EnrichedDeskContext per desk. On its second pass (retry),
             it tries deeper queries for previously unclear strategies.

write     →  uses EnrichedDeskContext to generate desk-level comments.
             Saves the StrategyMemory back to disk after writing.
"""

from __future__ import annotations

import structlog

from mo_intelligence.context_memory.strategy_memory import StrategyMemory
from mo_intelligence.data_loaders import enricher as _enricher
from mo_intelligence.data_loaders import pnl_attr_loader
from mo_intelligence.data_loaders import tpt_loader
from mo_intelligence.shared.models import OrchestratorState

log = structlog.get_logger(__name__)

# Module-level memory instance loaded once per process, reused across graph runs
_memory = StrategyMemory()


async def retrieve(state: OrchestratorState) -> dict:
    updates: dict = {}

    if state.pnl_attr_file:
        log.info("retrieve.pnl_attr", file=state.pnl_attr_file, cob=state.trade_date)
        s_rows = pnl_attr_loader.load_strategy_rows(state.pnl_attr_file, state.trade_date)
        desk_pnl = pnl_attr_loader.load_desk_pnl(state.pnl_attr_file, state.trade_date)
        prior = pnl_attr_loader.load_prior_comments(state.pnl_attr_file, state.trade_date)
        log.info(
            "retrieve.pnl_attr.done",
            strategy_rows=len(s_rows),
            desks=len(desk_pnl),
            prior_comments=len(prior),
        )
        updates["strategy_rows"] = s_rows
        updates["desk_pnl"] = desk_pnl
        updates["prior_comments"] = prior
    else:
        log.warning("retrieve.pnl_attr.missing")

    if state.tpt_file_t and state.tpt_file_t1:
        log.info("retrieve.tpt", file_t=state.tpt_file_t)
        contexts = tpt_loader.build_strategy_contexts(
            state.tpt_file_t, state.tpt_file_t1, state.trade_date
        )
        _memory.upsert_many(contexts)
        log.info("retrieve.tpt.done", contexts_loaded=len(contexts), memory_size=len(_memory))
    else:
        log.warning("retrieve.tpt.missing")

    return updates


async def enrich(state: OrchestratorState) -> dict:
    log.info("enrich.start", desks=len(state.desk_pnl), retry=state.enrich_retries)
    enriched = _enricher.build_enriched_contexts(
        state.strategy_rows,
        state.desk_pnl,
        state.prior_comments,
        _memory,
    )
    unclear_total = sum(len(d.unclear_items) for d in enriched)
    log.info("enrich.done", enriched_desks=len(enriched), unclear_strategies=unclear_total)
    return {
        "enriched_desks": enriched,
        "enrich_retries": state.enrich_retries + 1,
    }


async def write(state: OrchestratorState) -> dict:
    from mo_intelligence.ai_writer.writer import generate
    result = await generate(state)
    _memory.save()
    log.info("memory.saved", strategies_stored=len(_memory))
    return result
