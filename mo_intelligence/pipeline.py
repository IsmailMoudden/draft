"""Entry point — run the full pipeline from the command line.

Usage (minimum — no LLM, structured output only):
    python -m mo_intelligence.pipeline \
        --date 2025-06-27 \
        --pnl  "path/to/PnlAttr_comments.xlsx" \
        --tpt  "path/to/ST-DESK-PM-PNL Oil BBL T.xlsx" \
        --tpt1 "path/to/ST-DESK-PM-PNL Oil BBL T1.xlsx"

With LLM (once Azure creds are in .env):
    Same command — the writer auto-detects credentials and switches to LLM mode.

Output is printed to stdout. Set --out to also write a text file.
"""

from __future__ import annotations

import argparse
import asyncio
from datetime import date, datetime

from mo_intelligence.shared.config import settings
from mo_intelligence.shared.logging import configure_logging, get_logger
from mo_intelligence.shared.models import RunType
from mo_intelligence.orchestrator.graph import run_pipeline

log = get_logger(__name__)


async def main(
    trade_date: date,
    pnl_attr_file: str,
    tpt_file_t: str,
    tpt_file_t1: str,
    run_type: RunType,
    out: str,
) -> None:
    configure_logging()

    log.info(
        "pipeline_start",
        date=str(trade_date),
        run_type=run_type.value,
        pnl_file=pnl_attr_file or "NOT PROVIDED",
        tpt_t=tpt_file_t or "NOT PROVIDED",
        tpt_t1=tpt_file_t1 or "NOT PROVIDED",
        llm_enabled=bool(settings.azure_openai_api_key),
    )

    state = await run_pipeline(
        run_type=run_type,
        trade_date=trade_date,
        pnl_attr_file=pnl_attr_file,
        tpt_file_t=tpt_file_t,
        tpt_file_t1=tpt_file_t1,
    )

    # Print results
    print("\n" + state.summary_detailed)

    if state.generated_comments:
        print(f"\n{'='*60}")
        print(f"  {len(state.generated_comments)} desk comment(s) generated")
        print(f"{'='*60}")
        for c in state.generated_comments:
            print(f"\n[{c.desk}]")
            print(c.comment)

    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(state.summary_detailed + "\n\n")
            for c in state.generated_comments:
                f.write(f"\n[{c.desk}]\n{c.comment}\n")
        print(f"\nOutput written to: {out}")

    log.info(
        "pipeline_done",
        run_id=str(state.run_id),
        desks=len(state.generated_comments),
        enriched=len(state.enriched_desks),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MO Intelligence pipeline")
    parser.add_argument("--date",  default=date.today().isoformat(),
                        help="COB date YYYY-MM-DD (default: today)")
    parser.add_argument("--pnl",   default="", help="Path to PnlAttr_comments.xlsx")
    parser.add_argument("--tpt",   default="", help="Path to TPT snapshot T (today)")
    parser.add_argument("--tpt1",  default="", help="Path to TPT snapshot T-1 (yesterday)")
    parser.add_argument("--run-type", default="daily",
                        choices=[r.value for r in RunType])
    parser.add_argument("--out",   default="", help="Optional output text file path")
    args = parser.parse_args()

    asyncio.run(main(
        trade_date=date.fromisoformat(args.date),
        pnl_attr_file=args.pnl,
        tpt_file_t=args.tpt,
        tpt_file_t1=args.tpt1,
        run_type=RunType(args.run_type),
        out=args.out,
    ))
