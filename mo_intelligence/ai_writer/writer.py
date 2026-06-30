"""AI writer — generates one PnL comment per desk via Azure OpenAI.

Requires in .env:
    AZURE_OPENAI_ENDPOINT
    AZURE_OPENAI_API_KEY
    AZURE_OPENAI_DEPLOYMENT   (default: gpt-4o)
    AZURE_OPENAI_API_VERSION  (default: 2024-08-01-preview)
"""

from __future__ import annotations

import structlog
from openai import AsyncAzureOpenAI

from mo_intelligence.prompts.prompt_builder import build_desk_prompt
from mo_intelligence.shared.config import settings
from mo_intelligence.shared.models import (
    EnrichedDeskContext,
    GeneratedComment,
    OrchestratorState,
    RunType,
)

log = structlog.get_logger(__name__)


def _get_client() -> AsyncAzureOpenAI:
    return AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )


async def generate(state: OrchestratorState) -> dict:
    if not state.enriched_desks:
        log.warning("writer.no_enriched_desks", run_id=str(state.run_id))
        return {"generated_comments": [], "summary_short": "", "summary_detailed": ""}

    client = _get_client()
    comments: list[GeneratedComment] = []
    sources = {s for s in [state.pnl_attr_file, state.tpt_file_t] if s}

    for enriched in sorted(state.enriched_desks, key=lambda d: d.desk):
        comment_text = await _call_llm(client, enriched, state.run_type)
        comments.append(GeneratedComment(
            desk=enriched.desk,
            run_type=state.run_type,
            period_end=enriched.cob,
            comment=comment_text,
            sources_used=sorted(sources),
        ))

    summary_short    = _build_short(state, comments)
    summary_detailed = _build_detailed(state, comments)

    return {
        "generated_comments": comments,
        "summary_short": summary_short,
        "summary_detailed": summary_detailed,
    }


async def _call_llm(
    client: AsyncAzureOpenAI,
    enriched: EnrichedDeskContext,
    run_type: RunType,
) -> str:
    system_msg, user_msg = build_desk_prompt(enriched, run_type)

    log.info("writer.llm_call", desk=enriched.desk)
    response = await client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": system_msg},
            {"role": "user",   "content": user_msg},
        ],
        max_tokens=settings.azure_openai_max_tokens,
        temperature=settings.azure_openai_temperature,
    )
    comment = response.choices[0].message.content.strip()
    log.info("writer.llm_done", desk=enriched.desk, tokens=response.usage.total_tokens)
    return comment


# ---------------------------------------------------------------------------
# Run-level summaries (plain text, no LLM)
# ---------------------------------------------------------------------------

def _fmt(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:+.2f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:+.0f}k"
    return f"${val:+.0f}"


def _build_short(state: OrchestratorState, comments: list[GeneratedComment]) -> str:
    n = len(comments)
    grand = sum(r.pnl_dtd for r in state.desk_pnl)
    return f"[{state.run_type.value.title()} PnL {state.trade_date}] {n} desk(s) | Total DTD: {_fmt(grand)}"


def _build_detailed(state: OrchestratorState, comments: list[GeneratedComment]) -> str:
    lines: list[str] = [
        "=" * 60,
        f"  PnL COMMENTARY | {state.run_type.value.upper()} | {state.trade_date}",
        "=" * 60,
    ]

    sources: set[str] = set()
    for c in comments:
        sources.update(c.sources_used)
    if sources:
        for s in sorted(sources):
            lines.append(f"Source: {s}")
        lines.append("")

    grand = sum(r.pnl_dtd for r in state.desk_pnl)
    lines.append(f"TOTAL DTD : {_fmt(grand)}")
    lines.append("")

    pnl_by_desk      = {r.desk: r for r in state.desk_pnl}
    enriched_by_desk = {d.desk: d for d in state.enriched_desks}

    for gen in sorted(comments, key=lambda x: x.desk):
        row = pnl_by_desk.get(gen.desk)
        dtd_str = f"  DTD: {_fmt(row.pnl_dtd)}" if row else ""
        lines.append(f"[{gen.desk}]{dtd_str}")
        lines.append(gen.comment)

        if row:
            attr = {
                "MTM": row.mtm, "Pricing": row.pricing, "Trades": row.trades,
                "Costs": row.costs, "Outturns": row.outturns,
                "FX": row.fx, "Other": row.other, "Residual": row.residual,
            }
            detail = "  ".join(f"{k}: {_fmt(v)}" for k, v in attr.items() if abs(v) >= 1.0)
            if detail:
                lines.append(f"  [{detail}]")
            if row.book_breakdown:
                top3 = sorted(row.book_breakdown.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                lines.append("  Books: " + ", ".join(f"{k} {_fmt(v)}" for k, v in top3))

        enriched = enriched_by_desk.get(gen.desk)
        if enriched and enriched.unclear_items:
            lines.append(
                f"  UNCLEAR ({len(enriched.unclear_items)}): " +
                ", ".join(enriched.unclear_items[:5])
            )
        lines.append("")

    return "\n".join(lines)
