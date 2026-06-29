"""Strategy detail fetcher — deep-reads T and T1 snapshots for one strategy.

This is the data layer behind the LLM writer tools. Given a strategy_num,
it pulls all position rows from both snapshots and computes the evolution:
  - trade price, market price, quantity, counterpart, delivery (from each row)
  - price change between T and T1 per instrument
  - net position and MTM change

The LLM writer calls fetch_strategy_rows() as a tool when it needs to explain
a strategy in detail (counterpart, price move, cargo size, delivery tenor).

Future: fetch_strategy_trade_logs() will call the TPT REST API to return
trade booking events (NEW/AMEND/CANCEL) for the strategy on a given day.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

_C = {
    "strat":       "Strategy Num",
    "book":        "Book Cd",
    "lob":         "Lob Cd",
    "instr_type":  "Instrument Type Cd",
    "instr_class": "Instrument Class Cd",
    "trade_type":  "Trade Type Cd",
    "cmdty":       "Cmdty Cd",
    "counterpart": "Counterpart Company Num",
    "pl_type":     "Pl Type Ind",
    "buy_sell":    "Buy Sell Ind",
    "qty":         "Risk Qty",
    "delivery":    "Delivery Dt",
    "trade_price": "Trade Price",
    "mkt_price":   "Market Price",
    "mtm":         "Total Risk Mtm",
    "grade":       "Grade Cd",
}

_RELEVANT_COLS = list(_C.values())


# ---------------------------------------------------------------------------
# Public API — called by LangGraph tools
# ---------------------------------------------------------------------------

def fetch_strategy_rows(
    strategy_num: str,
    file_t: str | Path,
    file_t1: str | Path,
    cob_date: date,
    top_n: int = 30,
) -> str:
    """Return a structured text block with position detail for one strategy.

    Compares T vs T1 to show price evolution, position, counterparts, delivery.
    This is what the LLM writer reads to explain a strategy's PnL contribution.
    """
    df_t  = _read_strat(file_t,  strategy_num)
    df_t1 = _read_strat(file_t1, strategy_num)

    if df_t.empty and df_t1.empty:
        return f"Strategy {strategy_num}: no rows found in T or T1 snapshots."

    lines: list[str] = [f"STRATEGY: {strategy_num}"]

    # Header info from T (or T1 if T is empty)
    ref = df_t if not df_t.empty else df_t1
    lines.append(_header_line(ref))
    lines.append("")

    # T snapshot
    if not df_t.empty:
        lines.append(f"T SNAPSHOT ({cob_date}):")
        lines += _format_rows(df_t.head(top_n))
        net_t = _net(df_t)
        lines.append(f"  → Net: {net_t['direction']} {net_t['qty']:,.0f} BBL | "
                     f"Avg market price: {net_t['avg_mkt']:,.2f} | "
                     f"Net MTM: {_fmt(net_t['mtm'])}")
    else:
        lines.append(f"T SNAPSHOT ({cob_date}): no rows")

    lines.append("")

    # T1 snapshot
    if not df_t1.empty:
        lines.append(f"T1 SNAPSHOT (previous COB):")
        lines += _format_rows(df_t1.head(top_n))
        net_t1 = _net(df_t1)
        lines.append(f"  → Net: {net_t1['direction']} {net_t1['qty']:,.0f} BBL | "
                     f"Avg market price: {net_t1['avg_mkt']:,.2f} | "
                     f"Net MTM: {_fmt(net_t1['mtm'])}")
    else:
        lines.append("T1 SNAPSHOT (previous COB): no rows")

    lines.append("")

    # Evolution: what changed between T1 and T
    if not df_t.empty and not df_t1.empty:
        net_t  = _net(df_t)
        net_t1 = _net(df_t1)
        mtm_change   = net_t["mtm"]  - net_t1["mtm"]
        price_change = net_t["avg_mkt"] - net_t1["avg_mkt"]
        qty_change   = net_t["qty"]  - net_t1["qty"]

        lines.append("EVOLUTION (T vs T1):")
        lines.append(f"  MTM change     : {_fmt(mtm_change)}")
        lines.append(f"  Price change   : {price_change:+,.3f} (mkt price per unit)")
        if abs(qty_change) > 0.5:
            lines.append(f"  Position change: {qty_change:+,.0f} BBL "
                         f"({'added' if qty_change > 0 else 'reduced'})")
        else:
            lines.append("  Position       : unchanged")
        # Counterpart changes
        cps_t  = set(df_t[_C["counterpart"]].dropna().unique())
        cps_t1 = set(df_t1[_C["counterpart"]].dropna().unique())
        new_cps = cps_t - cps_t1
        if new_cps:
            lines.append(f"  New counterparts: {', '.join(sorted(new_cps))}")

    return "\n".join(lines)


def fetch_strategy_trade_logs(
    strategy_num: str,
    cob_date: date,
    api_base_url: str = "",
    api_key: str = "",
) -> str:
    """Return trade events (NEW/AMEND/CANCEL) for a strategy on a given date.

    NOT YET CONNECTED — the TPT REST API endpoint and credentials are not
    yet available. Returns a placeholder so the LLM knows to use snapshot
    data instead.

    When the API is wired:
      GET {api_base_url}/trades?strategy={strategy_num}&date={cob_date}
    Expected response: list of trade events with trade_id, action, price,
    quantity, counterpart, timestamp.
    """
    if not api_base_url:
        return (
            f"[TPT_LOG] Strategy {strategy_num} | Date {cob_date} | "
            "Trade log API not yet connected. "
            "Use T/T1 snapshot comparison to infer new trades "
            "(positions that appear in T but not in T1 are new today)."
        )
    # Future implementation:
    # resp = requests.get(f"{api_base_url}/trades",
    #     params={"strategy": strategy_num, "date": cob_date.isoformat()},
    #     headers={"X-API-Key": api_key})
    # return _format_trade_logs(resp.json())
    return "[TPT_LOG] Not yet implemented"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _read_strat(path: str | Path, strategy_num: str) -> pd.DataFrame:
    df = pd.read_excel(path, engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    col = _C["strat"]
    if col not in df.columns:
        return pd.DataFrame()
    mask = df[col].astype(str).str.strip() == str(strategy_num).strip()
    subset = df[mask].copy()
    # Only keep columns we care about
    keep = [c for c in _RELEVANT_COLS if c in subset.columns]
    return subset[keep].reset_index(drop=True)


def _header_line(df: pd.DataFrame) -> str:
    parts = []
    for key in ("lob", "book", "instr_class", "instr_type", "cmdty", "grade"):
        col = _C.get(key, "")
        if col in df.columns:
            val = _s(df[col].iloc[0])
            if val:
                parts.append(val)
    return "  " + " | ".join(parts) if parts else ""


def _format_rows(df: pd.DataFrame) -> list[str]:
    lines = []
    for _, row in df.iterrows():
        bs    = _s(row.get(_C["buy_sell"]))
        qty   = _f(row.get(_C["qty"]))
        tp    = _f(row.get(_C["trade_price"]))
        mp    = _f(row.get(_C["mkt_price"]))
        mtm   = _f(row.get(_C["mtm"]))
        cp    = _s(row.get(_C["counterpart"]))
        deliv = _s(row.get(_C["delivery"]))
        pl    = _s(row.get(_C["pl_type"]))

        parts = [f"  {'Buy' if bs == 'B' else 'Sell' if bs == 'S' else bs}"]
        if qty:   parts.append(f"{qty:,.0f} BBL")
        if tp:    parts.append(f"@ trade {tp:,.2f}")
        if mp:    parts.append(f"mkt {mp:,.2f}")
        if mtm:   parts.append(f"MTM {_fmt(mtm)}")
        if cp:    parts.append(f"vs {cp}")
        if deliv: parts.append(f"del.{deliv}")
        if pl:    parts.append(f"[{pl}]")
        lines.append(" | ".join(parts))
    return lines


def _net(df: pd.DataFrame) -> dict:
    long_qty  = df[df[_C["buy_sell"]] == "B"][_C["qty"]].apply(_f).sum() if _C["buy_sell"] in df.columns else 0
    short_qty = df[df[_C["buy_sell"]] == "S"][_C["qty"]].apply(_f).sum() if _C["buy_sell"] in df.columns else 0
    net_qty   = long_qty - short_qty
    total_mtm = df[_C["mtm"]].apply(_f).sum() if _C["mtm"] in df.columns else 0
    # Weighted avg market price (long-side for physical)
    mkt_prices = df[_C["mkt_price"]].apply(_f) if _C["mkt_price"] in df.columns else pd.Series([0.0])
    avg_mkt = mkt_prices[mkt_prices > 0].mean() if len(mkt_prices[mkt_prices > 0]) else 0.0
    return {
        "direction": "long" if net_qty >= 0 else "short",
        "qty": abs(net_qty),
        "avg_mkt": avg_mkt,
        "mtm": total_mtm,
    }


def _s(val) -> str:
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


def _fmt(val: float) -> str:
    if abs(val) >= 1_000_000:
        return f"${val/1_000_000:+.2f}M"
    if abs(val) >= 1_000:
        return f"${val/1_000:+.0f}k"
    return f"${val:+.0f}"
