"""Data models for the MO PnL commentary pipeline.

Three data sources feed into the system:

1. PnlAttr_comments.xlsx — PnL broken down by strategy and attribution bucket
   (MTM, Pricing, Trades, Costs, Outturns, FX, Residual). Primary source.

2. TPT position snapshots (T and T-1 Excel files) — daily end-of-day positions.
   Used to enrich each strategy with instrument type, commodity, counterpart,
   direction, quantity, and delivery date.

3. TPT trade log API (not yet connected) — transaction events (NEW/AMEND/CANCEL).
   Will explain the Trades attribution bucket when wired up.

Note on strategy_num: it can be a number ("215912") or a name ("SB Paper",
"BLUE LAKE STAR-35"). Both are valid TPT identifiers.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class RunType(str, Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"



# Source 1 — PnL Attribution file


class StrategyPnlRow(BaseModel):
    """One row from the PNL sheet, per strategy."""

    strategy_num: str
    desk: str
    book: str
    lob: str
    cob: date
    pnl_dtd: float = 0.0
    pnl_ytd: float = 0.0
    mtm: float = 0.0
    pricing: float = 0.0
    trades: float = 0.0
    costs: float = 0.0
    outturns: float = 0.0
    fx: float = 0.0
    other: float = 0.0
    residual: float = 0.0
    # True for system rows like SOS Analysis pairs, FX WASH, management allocations
    is_synthetic: bool = False


class DeskPnlRow(BaseModel):
    """All strategies for a desk summed into one row."""

    desk: str
    cob: date
    pnl_dtd: float = 0.0
    pnl_ytd: float = 0.0
    mtm: float = 0.0
    pricing: float = 0.0
    trades: float = 0.0
    costs: float = 0.0
    outturns: float = 0.0
    fx: float = 0.0
    other: float = 0.0
    residual: float = 0.0
    currency: str = "USD"
    book_breakdown: dict[str, float] = Field(default_factory=dict)


class DeskComment(BaseModel):
    """An existing comment from the Desk Comments sheet. Used as style reference only."""

    desk: str
    cob: date
    comment_type: str
    comment: str
    user: str = ""



# Source 2 — TPT position snapshots


class StrategyContext(BaseModel):
    """What we know about a strategy from the TPT snapshot files.

    Built once from T and T-1 Excel files, then stored in strategy_index.json
    so future runs can reuse it without re-reading the files.
    """

    strategy_num: str
    desk: str
    book: str
    instrument_type: str = ""
    instrument_class: str = ""
    trade_type: str = ""
    commodity: str = ""
    counterpart: str = ""
    pl_type: str = ""
    net_direction: str = ""
    net_qty: float = 0.0
    delivery_dt: str = ""
    last_seen: str = ""



# Source 3 — TPT trade log API (not yet connected)


class TptTradeLog(BaseModel):
    """A single trade event from the TPT API (NEW/AMEND/CANCEL).

    Not the same as a snapshot row — this is a timestamped event that explains
    why the Trades attribution bucket moved. API credentials TBD.
    """

    trade_id: str
    strategy_num: str
    desk: str
    book: str
    cob: date
    event_time: datetime | None = None
    action: str = ""
    instrument_type: str = ""
    commodity: str = ""
    counterpart: str = ""
    buy_sell: str = ""
    quantity: float = 0.0
    price: float = 0.0
    prev_price: float | None = None
    delivery_dt: str = ""
    pnl_impact: float = 0.0
    notes: str = ""



# Enrichment — one per strategy, one per desk


class StrategyInsight(BaseModel):
    """One strategy's PnL contribution, enriched with TPT context."""

    strategy_num: str
    desk: str
    book: str
    pnl_dtd: float
    main_bucket: str
    context: StrategyContext | None = None
    trade_logs: list[TptTradeLog] = Field(default_factory=list)
    explanation: str = ""
    unclear: bool = False


class EnrichedDeskContext(BaseModel):
    """Everything the writer needs for one desk on one COB date."""

    desk: str
    cob: date
    pnl: DeskPnlRow
    insights: list[StrategyInsight] = Field(default_factory=list)
    synthetic_notes: list[str] = Field(default_factory=list)
    prior_comment: str = ""
    unclear_items: list[str] = Field(default_factory=list)



# Output


class GeneratedComment(BaseModel):
    """The LLM-generated comment for one desk."""

    desk: str
    run_type: RunType
    period_end: date
    comment: str
    sources_used: list[str] = Field(default_factory=list)



# Orchestrator state — flows through the LangGraph nodes


class OrchestratorState(BaseModel):
    """State object passed between retrieve → enrich → write."""

    run_id: UUID = Field(default_factory=uuid4)
    run_type: RunType
    trade_date: date

    # input file paths
    pnl_attr_file: str = ""
    tpt_file_t: str = ""
    tpt_file_t1: str = ""

    # populated by retrieve
    strategy_rows: list[StrategyPnlRow] = Field(default_factory=list)
    desk_pnl: list[DeskPnlRow] = Field(default_factory=list)
    prior_comments: list[DeskComment] = Field(default_factory=list)

    # populated by a future fetch_logs node
    tpt_trade_logs: list[TptTradeLog] = Field(default_factory=list)

    # populated by enrich
    enriched_desks: list[EnrichedDeskContext] = Field(default_factory=list)
    enrich_retries: int = 0

    # populated by write
    generated_comments: list[GeneratedComment] = Field(default_factory=list)
    summary_short: str = ""
    summary_detailed: str = ""


__all__ = [
    "RunType",
    "StrategyPnlRow",
    "DeskPnlRow",
    "DeskComment",
    "StrategyContext",
    "TptTradeLog",
    "StrategyInsight",
    "EnrichedDeskContext",
    "GeneratedComment",
    "OrchestratorState",
]
