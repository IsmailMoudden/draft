"""AI writer — structured output today, LLM tomorrow.

Generates one PnL comment per desk using EnrichedDeskContext.

TO ENABLE LLM: replace the body of _draft_desk_comment() with:

    from mo_intelligence.prompts.prompt_builder import build_desk_prompt
    from mo_intelligence.shared.config import settings
    from openai import AsyncAzureOpenAI

    client = AsyncAzureOpenAI(
        azure_endpoint=settings.azure_openai_endpoint,
        api_key=settings.azure_openai_api_key,
        api_version=settings.azure_openai_api_version,
    )

    system, user = build_desk_prompt(enriched, run_type)
    response = await client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=settings.azure_openai_max_tokens,
        temperature=settings.azure_openai_temperature,
    )
    return response.choices[0].message.content.strip()

The prompt (built by prompts/prompt_builder.py) includes:
  - MO analyst persona + style rules (prompts/system_prompt.py)
  - Attribution bucket breakdown (MTM, Pricing, Trades, Costs...)
  - Per-strategy insights from TPT snapshot: commodity, counterpart, direction, delivery
  - TPT trade log events when available (future API)
  - Few-shot style examples from real Desk Comments (prompts/examples.py)
  - Prior comment for style reference (not facts)
"""

from __future__ import annotations

from mo_intelligence.shared.models import (
    EnrichedDeskContext,
    GeneratedComment,
    OrchestratorState,
    RunType,
    StrategyInsight,
)


async def generate(state: OrchestratorState) -> dict:
    comments: list[GeneratedComment] = []
    sources = {s for s in [state.pnl_attr_file, state.tpt_file_t] if s}

    # Use enriched desks if available, else fall back to raw desk_pnl
    if state.enriched_desks:
        for enriched in sorted(state.enriched_desks, key=lambda d: d.desk):
            comment_text = _draft_desk_comment(enriched, state.run_type)
            comments.append(GeneratedComment(
                desk=enriched.desk,
                run_type=state.run_type,
                period_end=enriched.cob,
                comment=comment_text,
                sources_used=sorted(sources),
            ))
    else:
        for row in sorted(state.desk_pnl, key=lambda r: r.desk):
            comments.append(GeneratedComment(
                desk=row.desk,
                run_type=state.run_type,
                period_end=row.cob,
                comment=f"DTD: {_fmt(row.pnl_dtd)} (no enrichment available)",
                sources_used=sorted(sources),
            ))

    summary_short = _build_short(state, comments)
    summary_detailed = _build_detailed(state, comments)
    return {
        "generated_comments": comments,
        "summary_short": summary_short,
        "summary_detailed": summary_detailed,
    }



# Comment drafting — per desk


def _draft_desk_comment(enriched: EnrichedDeskContext, run_type: RunType) -> str:
    """Structured comment using enriched strategy context — no LLM.

    Format mirrors real Desk Comments sheet style:
      BUCKET: +$Xk [instrument] [direction] [commodity] vs [counterpart]
    """
    row = enriched.pnl
    parts: list[str] = []

    # Top attribution buckets (non-trivial)
    attr_parts = _format_attribution(row)
    if attr_parts:
        parts.append(attr_parts)

    # Strategy insights — only the ones we can explain
    explained = [i for i in enriched.insights if not i.unclear and i.explanation]
    unclear   = [i for i in enriched.insights if i.unclear]

    if explained:
        # Group by bucket, take top 5
        top = sorted(explained, key=lambda i: abs(i.pnl_dtd), reverse=True)[:5]
        for ins in top:
            parts.append(ins.explanation)

    # Unclear items flag
    if unclear:
        strat_ids = ", ".join(i.strategy_num for i in unclear[:3])
        suffix = "..." if len(unclear) > 3 else ""
        parts.append(f"[Investigation needed: {strat_ids}{suffix}]")

    # Prior comment reference (style context)
    if enriched.prior_comment:
        parts.append(f"[Prior: {enriched.prior_comment[:120]}]")

    if not parts:
        parts.append(f"DTD: {_fmt(row.pnl_dtd)}")

    return "\n".join(parts)


def _format_attribution(row) -> str:
    """MTM: +$Xk  Pricing: +$Xk  Costs: -$Xk  (only non-zero buckets)"""
    buckets = [
        ("MTM", row.mtm),
        ("Pricing", row.pricing),
        ("Trades", row.trades),
        ("Costs", row.costs),
        ("Outturns", row.outturns),
        ("FX", row.fx),
        ("Other", row.other),
        ("Residual", row.residual),
    ]
    parts = [f"{label}: {_fmt(val)}" for label, val in buckets if abs(val) >= 1.0]
    return "  ".join(parts)


def _fmt(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:+.2f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:+.0f}k"
    return f"${val:+.0f}"



# Run-level summaries


def _build_short(state: OrchestratorState, comments: list[GeneratedComment]) -> str:
    run_label = state.run_type.value.title()
    n = len(comments)
    grand = sum(r.pnl_dtd for r in state.desk_pnl)
    line = f"[{run_label} PnL {state.trade_date}] {n} desk(s) | Total DTD: {_fmt(grand)}"
    return line[:300]


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

    enriched_by_desk = {d.desk: d for d in state.enriched_desks}
    pnl_by_desk = {r.desk: r for r in state.desk_pnl}

    for gen in sorted(comments, key=lambda x: x.desk):
        row = pnl_by_desk.get(gen.desk)
        dtd_str = f"  DTD: {_fmt(row.pnl_dtd)}" if row else ""
        lines.append(f"[{gen.desk}]{dtd_str}")
        lines.append(gen.comment)

        # Attribution bucket summary
        if row:
            attr = {
                "MTM": row.mtm, "Pricing": row.pricing, "Trades": row.trades,
                "Costs": row.costs, "Outturns": row.outturns,
                "FX": row.fx, "Other": row.other, "Residual": row.residual,
            }
            detail = "  ".join(
                f"{k}: {_fmt(v)}" for k, v in attr.items() if abs(v) >= 1.0
            )
            if detail:
                lines.append(f"  [{detail}]")

            if row.book_breakdown:
                top3 = sorted(row.book_breakdown.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
                lines.append("  Books: " + ", ".join(f"{k} {_fmt(v)}" for k, v in top3))

        # Unclear items
        enriched = enriched_by_desk.get(gen.desk)
        if enriched and enriched.unclear_items:
            lines.append(f"  UNCLEAR ({len(enriched.unclear_items)}): " +
                         ", ".join(enriched.unclear_items[:5]))

        lines.append("")

    return "\n".join(lines)
