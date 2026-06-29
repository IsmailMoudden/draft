"""Enrichment engine — links PnL attribution to TPT context.

For each desk and each of its contributing strategies:
  1. Look up the strategy in StrategyMemory (persistent context from TPT snapshots)
  2. Match TPT detail: instrument, commodity, counterpart, direction, qty
  3. Build a human-readable MO-style explanation
  4. Flag strategies that remain unclear for the writer to call out

Synthetic rows (SOS Analysis pairs, FX WASH, etc.) are handled separately:
they are NOT trading positions so they get no TPT enrichment, but their
PnL is noted separately so the LLM can mention them if significant.
See strategy_classifier.py for the full taxonomy.
"""

from __future__ import annotations

from collections import defaultdict

from mo_intelligence.context_memory.strategy_memory import StrategyMemory
from mo_intelligence.data_loaders.strategy_classifier import is_synthetic_strategy
from mo_intelligence.shared.models import (
    DeskComment,
    DeskPnlRow,
    EnrichedDeskContext,
    StrategyContext,
    StrategyInsight,
    StrategyPnlRow,
)

# Threshold: explain strategies contributing >= this fraction of desk DTD
_SIGNIFICANCE_PCT = 0.05
# Minimum absolute value to be "significant"
_MIN_ABS_USD = 5_000

# Back-compat alias for code that imported is_placeholder_strategy from here
is_placeholder_strategy = is_synthetic_strategy


def build_enriched_contexts(
    strategy_rows: list[StrategyPnlRow],
    desk_pnl: list[DeskPnlRow],
    prior_comments: list[DeskComment],
    memory: StrategyMemory,
) -> list[EnrichedDeskContext]:
    """Build one EnrichedDeskContext per desk."""
    rows_by_desk: dict[str, list[StrategyPnlRow]] = defaultdict(list)
    for r in strategy_rows:
        rows_by_desk[r.desk].append(r)

    prior_by_desk: dict[str, str] = {c.desk: c.comment for c in prior_comments}

    result: list[EnrichedDeskContext] = []
    for pnl_row in desk_pnl:
        desk = pnl_row.desk
        s_rows = rows_by_desk.get(desk, [])

        trading_rows   = [r for r in s_rows if not r.is_synthetic]
        synthetic_rows = [r for r in s_rows if r.is_synthetic]

        insights = _build_insights(trading_rows, pnl_row, memory)
        synthetic_notes = _summarise_synthetic(synthetic_rows)
        unclear = [i.strategy_num for i in insights if i.unclear]

        result.append(EnrichedDeskContext(
            desk=desk,
            cob=pnl_row.cob,
            pnl=pnl_row,
            insights=insights,
            synthetic_notes=synthetic_notes,
            prior_comment=prior_by_desk.get(desk, ""),
            unclear_items=unclear,
        ))

    return result


def _build_insights(
    rows: list[StrategyPnlRow],
    desk_pnl: DeskPnlRow,
    memory: StrategyMemory,
) -> list[StrategyInsight]:
    """Top-N contributing TRADING strategies with MO-style explanations."""
    desk_total = abs(desk_pnl.pnl_dtd) or 1.0

    significant = [
        r for r in rows
        if abs(r.pnl_dtd) >= _MIN_ABS_USD
        or (desk_total > 0 and abs(r.pnl_dtd) / desk_total >= _SIGNIFICANCE_PCT)
    ]
    significant.sort(key=lambda r: abs(r.pnl_dtd), reverse=True)

    insights: list[StrategyInsight] = []
    for row in significant[:15]:
        ctx = memory.get(row.strategy_num)
        main_bucket = _dominant_bucket(row)
        explanation, unclear = _explain(row, ctx, main_bucket)
        insights.append(StrategyInsight(
            strategy_num=row.strategy_num,
            desk=row.desk,
            book=row.book,
            pnl_dtd=row.pnl_dtd,
            main_bucket=main_bucket,
            context=ctx,
            explanation=explanation,
            unclear=unclear,
        ))

    return insights


def _summarise_synthetic(rows: list[StrategyPnlRow]) -> list[str]:
    """Build a short note for each synthetic row with non-trivial net PnL.

    SOS Analysis pairs cancel to $0 and are omitted.
    Management cost allocations (BUSINESS DEV, Margin Costs) and
    Expired Contract settlements have real PnL and are noted.
    """
    notes: list[str] = []
    for row in rows:
        if abs(row.pnl_dtd) < 1:
            continue
        bucket = _dominant_bucket(row)
        notes.append(
            f"[synthetic] {row.strategy_num} ({row.book}): "
            f"{_fmt(row.pnl_dtd)} | {bucket}"
        )
    return notes


def _dominant_bucket(row: StrategyPnlRow) -> str:
    buckets = {
        "MTM": row.mtm, "Pricing": row.pricing, "Trades": row.trades,
        "Costs": row.costs, "Outturns": row.outturns, "FX": row.fx,
        "Other": row.other, "Residual": row.residual,
    }
    return max(buckets, key=lambda k: abs(buckets[k]))


def _explain(
    row: StrategyPnlRow,
    ctx: StrategyContext | None,
    main_bucket: str,
) -> tuple[str, bool]:
    pnl_str = _fmt(row.pnl_dtd)

    if ctx is None:
        return (
            f"{row.book} / {row.strategy_num}: {pnl_str} ({main_bucket}) — no TPT snapshot",
            True,
        )

    parts: list[str] = []
    instr = ctx.instrument_class or ctx.instrument_type
    cmdty = ctx.commodity
    if instr and cmdty:
        parts.append(f"{cmdty} {instr}")
    elif cmdty:
        parts.append(cmdty)
    elif instr:
        parts.append(instr)

    if ctx.net_direction and ctx.net_qty:
        parts.append(f"{ctx.net_direction} {abs(ctx.net_qty):,.0f} BBL")

    if ctx.counterpart and ctx.counterpart not in ("STSA", "NULL", ""):
        parts.append(f"vs {ctx.counterpart}")

    if ctx.delivery_dt and ctx.delivery_dt not in ("None", "NaT", ""):
        parts.append(f"del. {ctx.delivery_dt}")

    driver = _bucket_label(main_bucket, ctx)
    parts.append(f"→ {pnl_str} ({driver})")

    unclear = (not ctx.instrument_class and not ctx.commodity
               and abs(row.pnl_dtd) > _MIN_ABS_USD * 5)

    return (", ".join(parts) if parts else f"{pnl_str} ({main_bucket})"), unclear


def _bucket_label(bucket: str, ctx: StrategyContext | None) -> str:
    labels = {
        "MTM":      "MtM" + (f" {ctx.pl_type.lower()}" if ctx and ctx.pl_type else ""),
        "Pricing":  "price change",
        "Trades":   "new trades",
        "Costs":    "costs/fees",
        "Outturns": "outturn",
        "FX":       "FX",
        "Other":    "other",
        "Residual": "residual",
    }
    return labels.get(bucket, bucket.lower())


def _fmt(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:+.2f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:+.0f}k"
    return f"${val:+.0f}"
