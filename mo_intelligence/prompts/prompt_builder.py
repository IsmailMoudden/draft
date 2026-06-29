"""Prompt builder — assembles the full LLM prompt for each desk.

Two prompt formats are produced for each desk:
  build_desk_prompt()     → returns (system_msg, user_msg) for the chat API
  build_context_block()   → returns a plain-text context block for debugging
                            or for embedding into a single-turn prompt

Usage (when LLM is wired in writer.py):

    from mo_intelligence.prompts.prompt_builder import build_desk_prompt
    from mo_intelligence.shared.models import EnrichedDeskContext

    system, user = build_desk_prompt(enriched)
    response = await openai_client.chat.completions.create(
        model=settings.azure_openai_deployment,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": user},
        ],
        max_tokens=300,
        temperature=0.3,  # low temp for factual commentary
    )
    comment = response.choices[0].message.content.strip()
"""

from __future__ import annotations

from mo_intelligence.prompts.examples import get_examples_for_desk
from mo_intelligence.prompts.system_prompt import SYSTEM_PROMPT
from mo_intelligence.shared.models import EnrichedDeskContext, RunType


def build_desk_prompt(
    enriched: EnrichedDeskContext,
    run_type: RunType = RunType.DAILY,
) -> tuple[str, str]:
    """Return (system_message, user_message) for the desk commentary LLM call.

    The system message is the fixed MO analyst persona.
    The user message contains all the enriched context and asks for the comment.
    """
    user_msg = _build_user_message(enriched, run_type)
    return SYSTEM_PROMPT, user_msg


def build_context_block(
    enriched: EnrichedDeskContext,
    run_type: RunType = RunType.DAILY,
) -> str:
    """Return a plain-text version of the full prompt (system + user) for debugging."""
    system, user = build_desk_prompt(enriched, run_type)
    return f"=== SYSTEM ===\n{system}\n\n=== USER ===\n{user}"



# Internal helpers


def _build_user_message(enriched: EnrichedDeskContext, run_type: RunType) -> str:
    parts: list[str] = []

    # --- Header ---
    parts.append(
        f"Write the {run_type.value} PnL comment for desk: {enriched.desk}\n"
        f"COB date: {enriched.cob}\n"
        f"Run type: {run_type.value.upper()}"
    )

    # --- Attribution summary ---
    pnl = enriched.pnl
    parts.append("\n--- ATTRIBUTION ---")
    parts.append(f"DTD P&L : {_fmt(pnl.pnl_dtd)}")
    parts.append(f"YTD P&L : {_fmt(pnl.pnl_ytd)}")
    attr_lines = [
        f"  MTM      : {_fmt(pnl.mtm)}",
        f"  Pricing  : {_fmt(pnl.pricing)}",
        f"  Trades   : {_fmt(pnl.trades)}",
        f"  Costs    : {_fmt(pnl.costs)}",
        f"  Outturns : {_fmt(pnl.outturns)}",
        f"  FX       : {_fmt(pnl.fx)}",
        f"  Other    : {_fmt(pnl.other)}",
        f"  Residual : {_fmt(pnl.residual)}",
    ]
    # Only show non-zero buckets
    parts.append("\n".join(l for l in attr_lines if not l.endswith(": $+0")))

    # --- Book breakdown ---
    if pnl.book_breakdown:
        parts.append("\n--- BOOK / LOB BREAKDOWN (top contributors) ---")
        top = sorted(pnl.book_breakdown.items(), key=lambda x: abs(x[1]), reverse=True)[:8]
        for k, v in top:
            if abs(v) >= 1:
                parts.append(f"  {k}: {_fmt(v)}")

    # --- Strategy-level insights from TPT snapshots ---
    explained = [i for i in enriched.insights if not i.unclear and i.context]
    unclear   = [i for i in enriched.insights if i.unclear]

    if explained:
        parts.append("\n--- STRATEGY CONTEXT (from TPT position snapshots) ---")
        parts.append(
            "Each entry: [strategy_num | instrument | commodity | direction | qty | counterpart | "
            "delivery | pnl_dtd | primary_driver]"
        )
        for ins in explained:
            ctx = ins.context
            delivery = f"del.{ctx.delivery_dt}" if ctx and ctx.delivery_dt else ""
            counterpart = f"vs {ctx.counterpart}" if ctx and ctx.counterpart not in ("STSA", "") else ""
            direction = f"{ctx.net_direction} {abs(ctx.net_qty):,.0f} BBL" if ctx and ctx.net_direction and ctx.net_qty else ""
            instr = ctx.instrument_class or ctx.instrument_type if ctx else ""
            parts.append(
                f"  [{ins.strategy_num}] {ctx.commodity if ctx else ''} {instr} "
                f"{direction} {counterpart} {delivery} "
                f"| {_fmt(ins.pnl_dtd)} | driver: {ins.main_bucket}"
            )

    # --- TPT trade logs (future, not yet available) ---
    # When wired, TPT trade logs would appear here as:
    #
    # --- TRADE LOGS (from TPT API) [FUTURE] ---
    # [TPT_LOG] 2026-06-26 | NEW | trade_id=T123456 | Brent Crude Physical |
    #   Buy 100kb @ $85.50/bbl | counterpart=BP | delivery=Aug-26 | book=Azeri SB
    # [TPT_LOG] 2026-06-26 | AMEND | trade_id=T123400 | price updated $84.00→$85.20
    #   | impact: +$120k Pricing
    #
    # For now this section is intentionally empty — add when TPT API is connected.

    if unclear:
        parts.append("\n--- STRATEGIES WITHOUT TPT CONTEXT ---")
        parts.append(
            "These trading strategies contributed to P&L but have no TPT snapshot "
            "data available (desk may not yet have a T/T1 file, or the strategy "
            "name doesn't match the snapshot — use book and bucket to infer):"
        )
        for ins in unclear:
            parts.append(
                f"  [{ins.strategy_num}] book={ins.book} | {_fmt(ins.pnl_dtd)} | "
                f"driver: {ins.main_bucket}"
            )

    # --- Synthetic rows (SOS Analysis, management allocations, etc.) ---
    if enriched.synthetic_notes:
        parts.append("\n--- SYNTHETIC / MANAGEMENT ENTRIES ---")
        parts.append(
            "These are system-generated rows (SOS Analysis pairs, FX WASH, "
            "management cost allocations, expired contract settlements). "
            "SOS Analysis pairs always cancel to $0. Others may have real PnL "
            "(e.g. management cost, expired settlement):"
        )
        for note in enriched.synthetic_notes:
            parts.append(f"  {note}")

    # --- Prior comment (style reference) ---
    if enriched.prior_comment:
        parts.append("\n--- PRIOR COMMENT (style reference only — do NOT copy) ---")
        parts.append(f'  "{enriched.prior_comment}"')

    # --- Few-shot examples ---
    examples = get_examples_for_desk(enriched.desk, n=2)
    if examples:
        parts.append("\n--- STYLE EXAMPLES (from Desk Comments sheet) ---")
        for ex in examples:
            parts.append(
                f"  [{ex['desk']} | {ex['cob']} | DTD {ex['dtd']}]\n"
                f"  Attribution: {ex['attribution']}\n"
                f"  Comment: {ex['comment']}\n"
                f"  Why this is good: {ex['notes']}"
            )

    # --- Instruction ---
    parts.append(
        "\n--- YOUR TASK ---\n"
        "Write the PnL comment for this desk using the data above.\n"
        "Rules:\n"
        "  - Organise by commodity/product, not by attribution bucket.\n"
        "  - Lead with the most significant driver.\n"
        "  - Include counterpart, volume, and delivery when available from TPT context.\n"
        "  - If the P&L is driven mainly by unclear strategies, say so briefly "
        "    and note which buckets drove it.\n"
        "  - Match the style of the examples above.\n"
        "  - Max ~150 words. No headers, no bullets, no greetings.\n"
        "Output the comment text only."
    )

    return "\n".join(parts)


def _fmt(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:+.2f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:+.0f}k"
    return f"${val:+.0f}"
