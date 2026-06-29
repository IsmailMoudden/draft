"""Few-shot examples — real PnL comments from the Desk Comments sheet.

These are authentic comments written by MO analysts. They are grouped by desk
type / commodity profile so the prompt builder can select the most relevant
examples for each desk being commented.

Each example shows what a GOOD comment looks like for that context. The LLM
should match this style, not copy the content.

Format of each entry:
  {
      "desk": str,
      "cob": str,          # YYYY-MM-DD
      "dtd": str,          # formatted total DTD P&L
      "attribution": str,  # which bucket drove the P&L (summary)
      "comment": str,      # the actual comment text
      "notes": str,        # explanation of what makes this a good example
  }
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Examples grouped by desk type
# ---------------------------------------------------------------------------

# --- Crude physical desks ---
CRUDE_PHYSICAL_EXAMPLES = [
    {
        "desk": "CASPIAN",
        "cob": "2026-06-25",
        "dtd": "-$457k",
        "attribution": "MTM -$484k, Pricing +$84k, Other -$120k, Costs -$1k",
        "comment": (
            "MTM: -$3k BFOE, +$3k Brent Flat Price, +$19k Brent Timing, "
            "-$485k BTC (diff -$0.350/bbl), -$53k DFL "
            "Pricing & Hedges: +$84k "
            "Costs: -$1k Inspection "
            "Other: -$120k Backwardation play (250k Mar27 unwound)"
        ),
        "notes": (
            "Excellent: leads with commodity/origin breakdown inside MTM. "
            "Shows price differential (diff -$0.350/bbl) — key for crude. "
            "Distinguishes MTM from Pricing (physical pricing lines) from Costs. "
            "Names the specific trade in Other (backwardation play, notional 250k)."
        ),
    },
    {
        "desk": "CASPIAN",
        "cob": "2026-06-24",
        "dtd": "+$1.58M",
        "attribution": "MTM -$95k, Pricing +$33k, Trades +$1.28M, Costs +$357k",
        "comment": (
            "MTM: -$279k BFOE, -$6k Brent Flat Price, +$182k Brent Timing, "
            "+$7k BTC (diff +$0.005/bbl), +$183k DFL "
            "Pricing & Hedges: +$33k "
            "New purchase: +$1,283k New Jul Condensate from Heritage (3x75 kb) "
            "Costs: -$25k Demurrage, +$382k Freight (new cargo)"
        ),
        "notes": (
            "New trade drives most of the P&L: names the seller (Heritage), "
            "volume (3x75 kb), and product (Jul Condensate). "
            "Freight is positive (income) vs demurrage (cost) — clearly separated."
        ),
    },
    {
        "desk": "GPTEUPHY",
        "cob": "2026-06-24",
        "dtd": "+$1.74M",
        "attribution": "Trades +$1.74M, MTM -$13k",
        "comment": (
            "Azeri New Trade Exxon sold Repsol +695k$. "
            "Kazakh: New Trades CPC Suez KMG sold Petroineos (-566k$), "
            "Afra Petroineos sold ORL +615k$. "
            "Libya Es Sider Conoc/STIR Freight +69k$. "
            "North Sea Paper: Spec MTM Long 180kb 24-26 Jun v Cal Jul (-13k$)."
        ),
        "notes": (
            "Physical trades: always buyer/seller pair (e.g., KMG sold Petroineos). "
            "Origin-based grouping: Azeri / Kazakh / Libya / North Sea. "
            "Paper position stated as direction + size + tenor."
        ),
    },
]

# --- Physical specialty products (chemicals, refined) ---
SPECIALTY_PRODUCTS_EXAMPLES = [
    {
        "desk": "AZERISP",
        "cob": "2026-06-26",
        "dtd": "-$798k",
        "attribution": "MTM -$712k, Trades +$753, Costs -$51k, Other -$35k",
        "comment": (
            "Methanol: -$759k (-$709k MtM, -$50k Costs), "
            "MOGAS: -$62k MtM, "
            "HPR: +$60k MtM, "
            "Urea: -$35k Qty Adjustments"
        ),
        "notes": (
            "Organises by product. Sub-breakdown shown in parentheses only when "
            "more than one bucket contributes. Qty Adjustment = outturn/physical quantity update."
        ),
    },
    {
        "desk": "AZERISP",
        "cob": "2026-06-25",
        "dtd": "-$109k",
        "attribution": "MTM -$283k, Trades +$226k, Costs -$52k",
        "comment": (
            "Urea +$308k: -$54k MtM, +$226k New trades, +$136k Costs "
            "Mogas +$62k: +$63k MtM "
            "HPR -$36k: -$36k MtM "
            "Pygas -$44k: -$33k MtM, -$11k Costs "
            "Methanol -$339k: -$339k MtM and physical updates, -$3k New trade"
        ),
        "notes": (
            "Each product leads with its total, then sub-breakdown follows. "
            "Urea has opposite-sign buckets that partially offset (worth showing)."
        ),
    },
    {
        "desk": "AZERISP",
        "cob": "2026-06-23",
        "dtd": "-$340k",
        "attribution": "MTM -$83k, Costs -$280k, Trades -$58k, Other +$81k",
        "comment": (
            "HPR +$13k: MtM "
            "Pygas -$41k: MtM "
            "Methanol -$156k: +$121k MtM, -$277k costs (-$263k Freight, -$15k Demurrage, +$1k Inspection) "
            "Urea -$167k: -$115k MtM, -$58k New physical trades and qty updates, +$6k Insurance costs"
        ),
        "notes": (
            "When Costs are large (>10% of desk P&L) always break them down: "
            "Freight, Demurrage, Inspection, Insurance as sub-items."
        ),
    },
]

# --- LPG / Light products ---
LIGHTS_EXAMPLES = [
    {
        "desk": "LIGHTS",
        "cob": "2026-06-26",
        "dtd": "+$240k",
        "attribution": "MTM +$220k, Pricing +$3k, Trades +$14k, FX +$2k",
        "comment": "LPG: +$236k MtM gains mainly from C3 NEW",
        "notes": (
            "Very short — that's fine when one product dominates. "
            "C3 = propane (common LPG abbreviation). "
            "NEW = new cargo or new forward position."
        ),
    },
    {
        "desk": "LIGHTS",
        "cob": "2026-06-25",
        "dtd": "+$57k",
        "attribution": "MTM +$51k, Trades +$6k",
        "comment": "LPG: $-73k MtM losses mainly driven by Mt Belv  Naphtha: +$100k MtM gain  Mogas: +$30k MtM gain",
        "notes": (
            "Multiple products separated by spaces (desk style). "
            "Mt Belv = Mont Belvieu, US propane hub. "
            "Negative LPG offset by positive Naphtha and Mogas — comment shows the offset."
        ),
    },
    {
        "desk": "LIGHTS",
        "cob": "2026-06-24",
        "dtd": "-$426k",
        "attribution": "MTM -$426k",
        "comment": "LPG: $-455k MtM losses mainly driven by C3 CP & FEI  Mogas: $29k mtm gain",
        "notes": (
            "C3 CP = propane Contract Price (monthly CP pricing). "
            "FEI = Far East Index. Specifying the pricing basis explains WHY it moved."
        ),
    },
]

# --- Distillates / Middles ---
MIDDLES_EXAMPLES = [
    {
        "desk": "MIDDLES",
        "cob": "2026-06-26",
        "dtd": "+$107k",
        "attribution": "MTM +$71k, Trades +$32k, Costs +$4k",
        "comment": "+$53k paper gain, +$43k new Ulsd deal, +$7k mtm & pricing, +$6k loan interest, -$4k Density escalation",
        "notes": (
            "Simple driver list: paper book, a specific new deal (Ulsd), "
            "MTM+pricing combined, cost type (loan interest), outturn type (density escalation). "
            "No product headers needed when it's all one product family (distillates)."
        ),
    },
    {
        "desk": "MIDDLES",
        "cob": "2026-06-25",
        "dtd": "-$8k",
        "attribution": "MTM -$19k, Trades +$7k, Costs +$4k",
        "comment": "-$19k MTM pricing, +$7k paper gain, +$4k density escalation",
        "notes": "Minimal when P&L is small. Correct — no need to elaborate on a -$8k day.",
    },
    {
        "desk": "MIDDLES",
        "cob": "2026-06-24",
        "dtd": "-$53k",
        "attribution": "MTM -$75k, Trades -$12k, Costs +$34k",
        "comment": "-$75k paper loss, +$25k bank charges, +$9k loan interest, -$12k mtm & pricing",
        "notes": (
            "Bank charges = positive here (income from letter of credit fees charged to counterpart). "
            "Sign convention is always from the desk's P&L perspective."
        ),
    },
]

# --- Shipping / Freight ---
SHIPPING_EXAMPLES = [
    {
        "desk": "SHIPPING",
        "cob": "2026-06-26",
        "dtd": "+$66k",
        "attribution": "MTM +$60k, Costs +$865",
        "comment": "Short 90kt USGC-UKC, Short 120kt TD3 Cal27, TD20 long 60kt Cal27",
        "notes": (
            "Shipping comments describe the POSITION, not just the P&L. "
            "Route format: USGC-UKC (US Gulf Coast to UK Continent). "
            "TD3 = dirty tanker route 3 (Middle East Gulf to Japan). "
            "Size in kt. Tenor: Cal27 = Calendar year 2027 FFA position."
        ),
    },
    {
        "desk": "SHIPPING",
        "cob": "2026-06-25",
        "dtd": "+$66k",
        "attribution": "MTM +$60k, Costs +$865",
        "comment": "Short 105kt USGC-UKC, Short 120kt TD3 Cal27, TD20 long 60kt Cal27",
        "notes": "Position slightly changed from yesterday — cargo loaded/discharged.",
    },
]

# --- Paper / Financial derivatives ---
PAPER_EXAMPLES = [
    {
        "desk": "GPTPAPER",
        "cob": "2026-06-26",
        "dtd": "-$85k",
        "attribution": "Trades -$85k",
        "comment": "Ldn (ROFR): Spec New Trades Short 175kb Dec/Dec & 253kb Mar/Apr Brent Spreads (-85k$).",
        "notes": (
            "ROFR = Right of First Refusal. Spec = speculative (not a hedge). "
            "Dec/Dec, Mar/Apr = spread between those delivery months. "
            "Brent Spreads = inter-month calendar spread position."
        ),
    },
    {
        "desk": "GPTPAPER",
        "cob": "2026-06-24",
        "dtd": "-$3k",
        "attribution": "Trades -$3k",
        "comment": "Ldn (ROFR): Spec Closed 50kb Brent/WTI Box (-3k$).",
        "notes": "Box = Brent/WTI location spread. Closed = trade unwound, realising the loss.",
    },
    {
        "desk": "CUSHING",
        "cob": "2026-06-26",
        "dtd": "+$2k",
        "attribution": "Trades +$2k",
        "comment": "KICH: Spec Closed Short WTI Spreads, MTM Long 360kb Aug, 100kb Sep HTT & Short 15kt Jul Freight +2k$.",
        "notes": (
            "KICH = desk sub-book or strategy name. "
            "WTI Spreads = inter-month WTI position. "
            "HTT = Houston-to-TankTank storage play. "
            "Multiple positions mentioned even when total P&L is small."
        ),
    },
]

# --- LNG ---
LNG_EXAMPLES = [
    {
        "desk": "LNG",
        "cob": "2026-06-25",
        "dtd": "-$270k",
        "attribution": "MTM -$270k",
        "comment": "Loss coming from FFA as prices went down, losing on 360 days Cal-27 FFA Length @ -$1,750/day. FFA LTD -$270k",
        "notes": (
            "LNG freight: FFA (Forward Freight Agreement). "
            "Rate shown: $/day. Length = long position. "
            "LTD = life-to-date, showing total position P&L for context."
        ),
    },
    {
        "desk": "LNG",
        "cob": "2026-06-24",
        "dtd": "+$2.2M",
        "attribution": "Trades +$2.2M",
        "comment": (
            "+$1.1m coming from new FOB US strip of 4 cargoes purchased from Total "
            "and marked to NWE. +$1.1m coming from sale into Egypt to Trafi."
        ),
        "notes": (
            "Two new deals, each explained: origin (FOB US), seller (Total), "
            "marked-to (NWE = Northwest Europe price benchmark). "
            "And the sale: destination (Egypt), buyer (Trafigura)."
        ),
    },
]

# --- Carbon / Emissions ---
CARBON_EXAMPLES = [
    {
        "desk": "CARBON",
        "cob": "2026-06-26",
        "dtd": "+$2k",
        "attribution": "MTM +$2k",
        "comment": "Spec: -$4.5k, New trades -$9k",
        "notes": "Carbon comments are very brief — often just spec book + new trades. Acceptable.",
    },
    {
        "desk": "CARBON",
        "cob": "2026-06-23",
        "dtd": "+$21k",
        "attribution": "MTM +$21k",
        "comment": "Spec: +$21k : 213024 : +$6k",
        "notes": (
            "Strategy number called out explicitly when it's a notable mover. "
            "Strategy 213024 is referenced directly."
        ),
    },
]

# --- Gas ---
GAS_EXAMPLES = [
    {
        "desk": "GAS",
        "cob": "2026-06-23",
        "dtd": "-$250k",
        "attribution": "MTM -$250k",
        "comment": "Spec: Q3'26 MGP/CEGH spread updated to -0.5 eur/mwh -$250k",
        "notes": (
            "Gas price quoted in EUR/MWh even though P&L is USD. "
            "MGP = Italian gas hub. CEGH = Central European Gas Hub (Vienna). "
            "Q3'26 = quarterly tenor."
        ),
    },
]

# ---------------------------------------------------------------------------
# Desk-type classification — maps desk names to their example set
# ---------------------------------------------------------------------------

DESK_TYPE_MAP: dict[str, str] = {
    # Key: desk name in PNL sheet, Value: example group name
    "AZERISB":    "crude_physical",
    "CASPIAN":    "crude_physical",
    "GPTEUPHY":   "crude_physical",
    "GPTPAPER":   "paper",
    "CUSHING":    "paper",
    "AZERISP":    "specialty_products",
    "LIGHTS":     "lights",
    "MIDDLES":    "middles",
    "SHIPPING":   "shipping",
    "CARBON":     "carbon",
    "LNG":        "lng",
    "GAS":        "gas",
    "MALTA":      "lng",         # LNG adjacent
    "LEGACY":     "specialty_products",
    "STAR":       "crude_physical",
    "PAPER":      "paper",
    "XBOOKJV":    "specialty_products",
    "MGMT":       "specialty_products",
    "BIOFUELS":   "specialty_products",
}

EXAMPLES_BY_TYPE: dict[str, list[dict]] = {
    "crude_physical":    CRUDE_PHYSICAL_EXAMPLES,
    "specialty_products": SPECIALTY_PRODUCTS_EXAMPLES,
    "lights":            LIGHTS_EXAMPLES,
    "middles":           MIDDLES_EXAMPLES,
    "shipping":          SHIPPING_EXAMPLES,
    "paper":             PAPER_EXAMPLES,
    "lng":               LNG_EXAMPLES,
    "carbon":            CARBON_EXAMPLES,
    "gas":               GAS_EXAMPLES,
}


def get_examples_for_desk(desk: str, n: int = 2) -> list[dict]:
    """Return up to n few-shot examples for the given desk type."""
    desk_type = DESK_TYPE_MAP.get(desk.upper(), "crude_physical")
    pool = EXAMPLES_BY_TYPE.get(desk_type, CRUDE_PHYSICAL_EXAMPLES)
    return pool[:n]
