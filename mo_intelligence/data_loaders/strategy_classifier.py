"""Strategy name classification — determines whether a strategy_num is a
real trading position or a synthetic system-generated entry.

WHY SYNTHETIC ROWS EXIST
-------------------------
Trading systems like TPT generate several types of non-trading strategy entries:

  SOS Analysis pairs  ("SB Analysis", "SB Analysis DTD", "CR 16 Paper SOS Analysis Q1"):
    TPT creates offsetting mirror rows to represent the desk's start-of-season
    (SOS) hedge position vs. the actual book. They ALWAYS come in a pair that
    sums to $0 for the desk. Both rows exist in the TPT position snapshot with
    equal and opposite MTM values. Useful for management analysis; not useful
    for MO commentary since the net impact is zero.

  Expired Contract   ("LNG Trading Book - Expired Contract"):
    When a financial contract expires, TPT parks any remaining settlement PnL
    under a placeholder strategy rather than the original strategy number.
    Real PnL — but the position is closed so no live TPT snapshot rows remain.

  Margin Costs       ("LNG Trading Book - Margin Costs"):
    Initial margin and variation margin payments to exchanges/clearing houses.
    Real cash cost — but NOT a counterpart trade. No TPT snapshot row.

  FX WASH            ("180028 - FX WASH"):
    FX reconciliation entries that net to zero across the book.
    Created by the FX translation process.

  Management allocations ("BUSINESS DEV", "STUK LNG Business Development"):
    Overhead cost allocations from management. Real cost, but not a trade.
    No counterpart, no delivery date.

  ANMA entries       ("ANMA Brent Outright", "ANMA Freight"):
    Rows where TPT could not allocate the PnL to a specific strategy.
    ANMA = likely "Allocation Not Matched Anywhere" or similar.

  ECR VAT entries    ("ECR VAT 2022 Q1"):
    VAT reclaim/adjustment entries for European operations.

TRACKING ACROSS SOURCES
-----------------------
All of these appear in the PnL attribution sheet. The SOS Analysis rows also
exist in TPT position snapshots (cross-referenceable by strategy_num).
The others (BUSINESS DEV, ANMA, Expired Contract, FX WASH) typically do not
have live TPT snapshot rows — they are attribution-only entries.

These rows are KEPT in the system with is_synthetic=True so they can be tracked.
They are EXCLUDED from trading insights generation (no counterpart, no delivery),
but their PnL is included in desk totals since the PnL sheet already counts them.
"""

from __future__ import annotations

_PLACEHOLDER_SUBSTRINGS = (
    " analysis",           # SB Analysis, Paper SOS Analysis, CR 16 Paper SOS Analysis Q1
    "sos analysis",        # ... SOS Analysis Q3  (redundant but explicit)
    "expired contract",    # FO John Old Book - Expired Contract
    "margin costs",        # LNG Trading Book - Margin Costs
    "fx wash",             # 180028 - FX WASH
    "ecr vat",             # ECR VAT 2022 Q1
    "business dev",        # BUSINESS DEV, STUK LNG Business Development
)

_PLACEHOLDER_PREFIXES = (
    "anma ",               # ANMA Brent Outright, ANMA Expired Contract, ANMA Freight
)


def is_synthetic_strategy(strategy_num: str) -> bool:
    """Return True if this strategy_num is a system-generated synthetic entry.

    Synthetic entries are NOT individual trading positions. They are management
    overlays, expired-contract placeholders, margin cost allocations, or
    FX reconciliation entries. They may still carry real PnL.

    Real named strategies — vessel names (AZERBAIJAN-2026064, BAKU-35),
    named books (SB Paper, LPG Active Trading), paper strategies (Paper Cracks,
    Paper Dated), and numbered IDs (215912) — return False.
    """
    s = strategy_num.strip().lower()
    if any(sub in s for sub in _PLACEHOLDER_SUBSTRINGS):
        return True
    if any(s.startswith(pfx) for pfx in _PLACEHOLDER_PREFIXES):
        return True
    return False


# Back-compat alias — used in enricher.py
is_placeholder_strategy = is_synthetic_strategy
