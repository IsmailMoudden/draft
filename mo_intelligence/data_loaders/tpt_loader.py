"""TPT snapshot loader — builds StrategyContext objects from T and T1 files.

Each strategy in the TPT file gets a StrategyContext that captures:
  instrument type, commodity, counterpart, direction, qty, MTM change.

These are merged into the persistent StrategyMemory so every run
accumulates richer knowledge about each strategy.

LOB → DESK mapping must be extended when new desk files become available.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd

from mo_intelligence.shared.models import StrategyContext

_LOB_TO_DESK: dict[str, str] = {
    "AZERI SB": "AZERISB",
    "ASSETS": "AZERISB",
    # Extend as other desks' TPT files become available
}

# Column names
_C = {
    "lob":         "Lob Cd",
    "book":        "Book Cd",
    "strat":       "Strategy Num",
    "instr_type":  "Instrument Type Cd",
    "instr_class": "Instrument Class Cd",
    "trade_type":  "Trade Type Cd",
    "cmdty":       "Cmdty Cd",
    "counterpart": "Counterpart Company Num",
    "pl_type":     "Pl Type Ind",
    "buy_sell":    "Buy Sell Ind",
    "qty":         "Risk Qty",
    "delivery":    "Delivery Dt",
    "mtm":         "Total Risk Mtm",
}


def build_strategy_contexts(
    file_t: str | Path,
    file_t1: str | Path,
    cob_date: date,
) -> list[StrategyContext]:
    """Build one StrategyContext per strategy from the T and T1 snapshots.

    MTM change (T - T1) per strategy is stored so the enricher can reconcile
    with PnL attribution figures.
    """
    df_t  = _read(file_t)
    df_t1 = _read(file_t1)

    # Aggregate MTM by strategy for each snapshot
    mtm_t  = _agg_mtm(df_t)
    mtm_t1 = _agg_mtm(df_t1)

    # Build contexts from the T snapshot (most current)
    contexts: list[StrategyContext] = []
    seen: set[str] = set()

    for _, row in df_t.iterrows():
        strat = str(row.get(_C["strat"], "") or "")
        if not strat or strat in seen:
            continue
        seen.add(strat)

        lob  = str(row.get(_C["lob"], "") or "")
        desk = _LOB_TO_DESK.get(lob, "")
        book = str(row.get(_C["book"], "") or "")

        qty   = _f(row.get(_C["qty"]))
        bs    = str(row.get(_C["buy_sell"], "") or "").upper()
        mtm_change = mtm_t.get(strat, 0.0) - mtm_t1.get(strat, 0.0)

        delivery = row.get(_C["delivery"])
        delivery_str = str(delivery) if delivery and not pd.isna(delivery) else ""

        contexts.append(StrategyContext(
            strategy_num=strat,
            desk=desk,
            book=book,
            instrument_type=_s(row.get(_C["instr_type"])),
            instrument_class=_s(row.get(_C["instr_class"])),
            trade_type=_s(row.get(_C["trade_type"])),
            commodity=_s(row.get(_C["cmdty"])),
            counterpart=_s(row.get(_C["counterpart"])),
            pl_type=_s(row.get(_C["pl_type"])),
            net_direction="long" if bs == "B" else ("short" if bs == "S" else ""),
            net_qty=qty,
            delivery_dt=delivery_str,
            last_seen=cob_date.isoformat(),
        ))

    return contexts


def _read(path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _agg_mtm(df: pd.DataFrame) -> dict[str, float]:
    col_strat = _C["strat"]
    col_mtm   = _C["mtm"]
    if col_strat not in df.columns or col_mtm not in df.columns:
        return {}
    agg = df.groupby(col_strat)[col_mtm].sum()
    return {str(k): float(v) for k, v in agg.items()}


def _s(val) -> str:
    """Convert a cell value to string, returning '' for None/NaN/nan."""
    if val is None:
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    s = str(val).strip()
    return "" if s.lower() in ("nan", "none", "null", "nat") else s


def _f(val) -> float:
    try:
        v = float(val)
        return 0.0 if v != v else v
    except (TypeError, ValueError):
        return 0.0
