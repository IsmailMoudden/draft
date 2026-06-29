"""Loader for PnlAttr_comments.xlsx (or SQL equivalent).

PNL sheet       → strategy-level rows (all rows, synthetic ones marked)
                → desk-level aggregates (include synthetic so totals match)
Desk Comments   → existing PNL comments as style/context reference

Synthetic rows (SOS Analysis pairs, FX WASH, management allocations) are
marked with is_synthetic=True rather than dropped. Their PnL is included in
desk aggregates because the attribution file already counts them. The enricher
separates them from trading-position insights at analysis time.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from mo_intelligence.data_loaders.strategy_classifier import is_synthetic_strategy
from mo_intelligence.shared.models import DeskComment, DeskPnlRow, StrategyPnlRow


def load_strategy_rows(
    file_path: str | Path,
    cob_date: date,
) -> list[StrategyPnlRow]:
    """Return one StrategyPnlRow per row in the PNL sheet for the given COB date.

    All rows are returned, including synthetic ones (is_synthetic=True).
    Empty or completely-zero rows are dropped.
    """
    df = _read_pnl_sheet(file_path)
    df["_cob"] = df["COB"].apply(_parse_date)
    subset = df[df["_cob"] == cob_date]
    if subset.empty:
        return []

    rows: list[StrategyPnlRow] = []
    for _, r in subset.iterrows():
        strat_num = str(r.get("Strategy Num", "") or "").strip()
        if not strat_num or strat_num.lower() in ("nan", "none"):
            continue
        rows.append(StrategyPnlRow(
            strategy_num=strat_num,
            desk=str(r.get("DESK", "") or ""),
            book=str(r.get("Book Cd", "") or ""),
            lob=str(r.get("Lob Cd", "") or ""),
            cob=cob_date,
            pnl_dtd=_f(r.get("PNL DTD")),
            pnl_ytd=_f(r.get("PNL YTD")),
            mtm=_f(r.get("MTM")),
            pricing=_f(r.get("PRICING")),
            trades=_f(r.get("TRADES")),
            costs=_f(r.get("COSTS")),
            outturns=_f(r.get("OUTTURNS")),
            fx=_f(r.get("FX")),
            other=_f(r.get("OTHER")),
            residual=_f(r.get("RESIDUAL")),
            is_synthetic=is_synthetic_strategy(strat_num),
        ))
    return rows


def load_desk_pnl(
    file_path: str | Path,
    cob_date: date,
) -> list[DeskPnlRow]:
    """Aggregate all strategy rows (including synthetic) to desk level.

    Synthetic rows are included so the desk total matches what the attribution
    file shows. The book_breakdown only includes non-synthetic rows (to avoid
    showing SOS Analysis pairs in the top-contributor list).
    """
    strategy_rows = load_strategy_rows(file_path, cob_date)
    desk_map: dict[str, dict] = defaultdict(lambda: {
        "pnl_dtd": 0.0, "pnl_ytd": 0.0, "mtm": 0.0, "pricing": 0.0,
        "trades": 0.0, "costs": 0.0, "outturns": 0.0, "fx": 0.0,
        "other": 0.0, "residual": 0.0,
        "book_breakdown": defaultdict(float),
    })

    for row in strategy_rows:
        d = desk_map[row.desk]
        for bucket in ["pnl_dtd", "pnl_ytd", "mtm", "pricing", "trades",
                       "costs", "outturns", "fx", "other", "residual"]:
            d[bucket] += getattr(row, bucket)
        # Book breakdown: only real trading rows (synthetic pairs cancel anyway)
        if not row.is_synthetic:
            key = f"{row.lob}/{row.book}" if row.lob else row.book
            if key.strip("/"):
                d["book_breakdown"][key] += row.pnl_dtd

    result: list[DeskPnlRow] = []
    for desk, d in desk_map.items():
        top_books = dict(
            sorted(d["book_breakdown"].items(), key=lambda x: abs(x[1]), reverse=True)[:10]
        )
        result.append(DeskPnlRow(
            desk=desk, cob=cob_date,
            pnl_dtd=d["pnl_dtd"], pnl_ytd=d["pnl_ytd"],
            mtm=d["mtm"], pricing=d["pricing"], trades=d["trades"],
            costs=d["costs"], outturns=d["outturns"], fx=d["fx"],
            other=d["other"], residual=d["residual"],
            book_breakdown=top_books,
        ))
    return result


def load_prior_comments(
    file_path: str | Path,
    cob_date: date,
    comment_type: str = "PNL",
) -> list[DeskComment]:
    df = pd.read_excel(file_path, sheet_name="Desk Comments", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    df["_cob"] = df["COB"].apply(_parse_date)
    subset = df[
        (df["_cob"] == cob_date) &
        (df["Type"].str.upper() == comment_type.upper())
    ]
    results: list[DeskComment] = []
    for _, row in subset.iterrows():
        text = str(row.get("Comment", "") or "").strip()
        if not text or text.lower() in ("nan", "none", "null"):
            continue
        results.append(DeskComment(
            desk=str(row.get("DESK", "")),
            cob=cob_date,
            comment_type=str(row.get("Type", comment_type)),
            comment=text,
            user=str(row.get("USER", "")),
        ))
    return results


def _read_pnl_sheet(file_path: str | Path) -> pd.DataFrame:
    df = pd.read_excel(file_path, sheet_name="PNL", engine="openpyxl")
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _parse_date(val) -> date | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, (datetime, pd.Timestamp)):
        return val.date()
    if isinstance(val, date):
        return val
    s = str(val).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:19], fmt[:len(s)]).date()
        except (ValueError, IndexError):
            continue
    return None


def _f(val) -> float:
    try:
        v = float(val)
        return 0.0 if v != v else v
    except (TypeError, ValueError):
        return 0.0
