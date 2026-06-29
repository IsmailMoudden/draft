"""Data models — desk-centric PnL commentary system.

DATA SOURCES (important distinction):

  1. PnL Attribution file (PnlAttr_comments.xlsx → future SQL table):
       Daily PnL broken down by strategy_num, book, attribution bucket.
       This is the PRIMARY source: it tells us HOW MUCH each strategy made/lost
       and in which bucket (MTM, Pricing, Trades, Costs, Outturns, FX, Residual).

  2. TPT POSITION SNAPSHOTS (ST-DESK-PM-PNL Oil BBL T.xlsx / T1.xlsx):
       End-of-day snapshots of all open positions in TPT (trade processing tool).
       T = today's snapshot, T-1 = yesterday's snapshot.
       One row per position (not per trade event). PnL = MTM(T) - MTM(T-1).
       Used to ENRICH each strategy_num with: instrument type, commodity,
       counterpart, direction (buy/sell), quantity, delivery date.
       Source for StrategyContext objects stored in the persistent memory.

  3. TPT TRADE LOGS (future — via TPT REST API):
       Transaction-level event stream: new trades booked, amendments, cancellations.
       NOT the same as snapshots. A log event has: trade_id, action (NEW/AMEND/CANCEL),
       timestamp, price, quantity, counterpart.
       Used to explain the TRADES attribution bucket — a new deal booked today
       at an off-market price creates immediate P&L that appears in "Trades".
       API format and credentials TBD. Model is defined here for forward compatibility.

STRATEGY NUMBER FORMAT:
  strategy_num is a string, not always a number. Valid forms:
    - "215912"             → numeric system ID (most common)
    - "SB Paper"           → named strategy alias (user-defined in TPT)
    - "LPG Active Trading" → named book-level strategy
    - "BLUE LAKE STAR-35"  → vessel name (Shipping desk)
    - "DANICA-31"          → vessel name (Shipping desk)
  Text strategy names are NOT data errors. They are legitimate TPT strategy
  identifiers used by desks that prefer named strategies over system IDs.
  The cross-reference (PnL strategy_num → TPT snapshot row) works the same
  way for text and numeric IDs: exact string match.
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


# ---------------------------------------------------------------------------
# Source 1: PnL Attribution file
# ---------------------------------------------------------------------------

class StrategyPnlRow(BaseModel):
    """One row from the PNL attribution sheet — per strategy, not aggregated.

    Keeps strategy_num intact so it can be cross-referenced with TPT snapshots.
    strategy_num may be numeric or a text name — both are valid (see models.py
    module docstring for the full taxonomy).

    is_synthetic: True for system-generated overlay rows (SOS Analysis pairs,
        FX WASH, management allocations, expired contract placeholders).
        These ARE included in desk aggregates and ARE cross-referenceable in
        TPT snapshots, but they are NOT individual trading positions.
        SOS Analysis / SB Analysis rows always come in offsetting pairs that
        net to $0 for the desk.
    """
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
    is_synthetic: bool = False   # True for overlay/analysis/management rows


class DeskPnlRow(BaseModel):
    """Aggregated PnL for one desk on one COB date — sum of all StrategyPnlRow."""
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
    """Existing human-written comment from the Desk Comments sheet.

    Used as STYLE REFERENCE for the LLM — not as facts for the current run.
    """
    desk: str
    cob: date
    comment_type: str   # "PNL", "POS", "PXG"
    comment: str
    user: str = ""


# ---------------------------------------------------------------------------
# Source 2: TPT Position Snapshots → persistent context memory
# ---------------------------------------------------------------------------

class StrategyContext(BaseModel):
    """What we know about a strategy from TPT position snapshot data.

    Built by reading T and T-1 snapshot files. Stored in the persistent
    strategy memory (strategy_index.json) and enriched across runs.

    snapshot_source = "tpt_snapshot" — these come from the daily Excel files.
    Do NOT confuse with TptTradeLog which comes from the future TPT API.
    """
    strategy_num: str       # exact string from the PNL sheet — may be text or numeric
    desk: str
    book: str
    instrument_type: str = ""     # e.g. "Physical Index", "Financial Swap", "Future"
    instrument_class: str = ""    # e.g. "Physical", "Swap", "Option"
    trade_type: str = ""          # TPT trade type code
    commodity: str = ""           # e.g. "Azeri Crude Oil", "Brent Crude Oil", "LNG"
    counterpart: str = ""         # e.g. "BP", "STOV", "Trafigura"
    pl_type: str = ""             # "Realized" / "Unrealized"
    net_direction: str = ""       # "long" / "short" (net across all rows for this strategy)
    net_qty: float = 0.0          # net position in BBL (or native unit)
    delivery_dt: str = ""         # delivery / expiry date
    last_seen: str = ""           # ISO date of last COB where this strategy appeared


# ---------------------------------------------------------------------------
# Source 3: TPT Trade Logs (future — TPT REST API)
# ---------------------------------------------------------------------------

class TptTradeLog(BaseModel):
    """A single trade event from the TPT transaction log API.

    IMPORTANT: This is NOT a snapshot row. It is a timestamped event
    (new trade, amendment, cancellation) that explains why the TRADES
    attribution bucket moved on a given day.

    Status: not yet connected. API endpoint and auth are TBD.
    The TPT API base URL and key are stored in config.py (tpt_api_base_url,
    tpt_api_key) for when this becomes available.
    """
    trade_id: str
    strategy_num: str           # links to StrategyContext.strategy_num
    desk: str
    book: str
    cob: date
    event_time: datetime | None = None
    action: str = ""            # "NEW", "AMEND", "CANCEL", "CONFIRM"
    instrument_type: str = ""
    commodity: str = ""
    counterpart: str = ""
    buy_sell: str = ""          # "B" / "S"
    quantity: float = 0.0
    price: float = 0.0
    prev_price: float | None = None   # for AMEND: the old price
    delivery_dt: str = ""
    pnl_impact: float = 0.0    # estimated P&L impact of this event
    notes: str = ""


# ---------------------------------------------------------------------------
# Enrichment outputs — per desk, per run
# ---------------------------------------------------------------------------

class StrategyInsight(BaseModel):
    """One strategy's contribution to desk PnL, enriched with TPT snapshot context."""
    strategy_num: str
    desk: str
    book: str
    pnl_dtd: float
    main_bucket: str            # which attribution bucket drove the PnL
    context: StrategyContext | None = None
    trade_logs: list[TptTradeLog] = Field(default_factory=list)
    explanation: str = ""       # MO-style explanation, or "" if unclear
    unclear: bool = False       # True if we couldn't explain this strategy


class EnrichedDeskContext(BaseModel):
    """Everything we know about a desk for the current run — used by the writer."""
    desk: str
    cob: date
    pnl: DeskPnlRow
    insights: list[StrategyInsight] = Field(default_factory=list)
    synthetic_notes: list[str] = Field(default_factory=list)
    prior_comment: str = ""
    unclear_items: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

class GeneratedComment(BaseModel):
    """Generated PnL comment for one desk."""
    desk: str
    run_type: RunType
    period_end: date
    comment: str
    sources_used: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Orchestrator state
# ---------------------------------------------------------------------------

class OrchestratorState(BaseModel):
    """State flowing through the LangGraph pipeline.

    Input fields (set before running):
      pnl_attr_file    → PnL attribution Excel / future SQL query
      tpt_file_t       → TPT position snapshot for today (T)
      tpt_file_t1      → TPT position snapshot for yesterday (T-1)
      [future] tpt_trade_logs are fetched from the TPT API by a future
               'fetch_logs' node — they are NOT in the input files.
    """
    run_id: UUID = Field(default_factory=uuid4)
    run_type: RunType
    trade_date: date

    # --- Input paths ---
    pnl_attr_file: str = ""
    tpt_file_t: str = ""      # TPT snapshot: today's positions
    tpt_file_t1: str = ""     # TPT snapshot: yesterday's positions

    # --- Populated by retrieve ---
    strategy_rows: list[StrategyPnlRow] = Field(default_factory=list)
    desk_pnl: list[DeskPnlRow] = Field(default_factory=list)
    prior_comments: list[DeskComment] = Field(default_factory=list)

    # --- Populated by fetch_logs (future TPT API node) ---
    tpt_trade_logs: list[TptTradeLog] = Field(default_factory=list)

    # --- Populated by enrich ---
    enriched_desks: list[EnrichedDeskContext] = Field(default_factory=list)
    enrich_retries: int = 0

    # --- Populated by write ---
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
