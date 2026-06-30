# Pipeline Documentation

The goal of the system is to read daily MO files, understand what drove each desk's PnL, and produce a written comment per desk using an LLM — exactly like an MO analyst would write it, but automated.

---

## How the pipeline runs

```
pipeline.py
    └── orchestrator/graph.py       builds and runs the LangGraph graph
            ├── nodes.retrieve()    reads the 3 input files
            ├── nodes.enrich()      links strategies to TPT context
            └── nodes.write()       calls the LLM, saves output
```

You trigger it from the command line:

```bash
python -m mo_intelligence.pipeline \
  --date 2025-06-27 \
  --pnl  PnlAttr_comments.xlsx \
  --tpt  "ST-DESK-PM-PNL Oil BBL T.xlsx" \
  --tpt1 "ST-DESK-PM-PNL Oil BBL T1.xlsx"
```

---

## File by file

### `pipeline.py`
Entry point. Parses CLI arguments (date, file paths, run type), calls `run_pipeline()`, and prints the result to stdout. Nothing else.

---

### `shared/models.py`
All data types used across the pipeline. If you want to know what shape a piece of data has, look here.

Key types:
- `StrategyPnlRow` — one row from the PNL sheet (one strategy, one day)
- `DeskPnlRow` — all strategies for a desk summed up
- `StrategyContext` — what we know about a strategy from TPT snapshots (commodity, counterpart, direction, etc.)
- `EnrichedDeskContext` — everything the LLM needs for one desk: PnL + strategy insights + prior comment
- `OrchestratorState` — the state object that travels through the graph, picking up data at each node

---

### `shared/config.py`
Reads the `.env` file and exposes a `settings` object. All credentials and tuning parameters live here. If you need to change the LLM deployment name or temperature, do it in `.env` — not in the code.

---

### `orchestrator/graph.py`
Defines the LangGraph graph: which nodes exist, what order they run in, and the conditional retry logic for enrich. This is where you'd add a new node (e.g., a `fetch_logs` node for the TPT API).

The retry logic: if enrich finds unclear strategies and TPT data is available, it loops back once to try again before going to write.

---

### `orchestrator/nodes.py`
The actual implementation of each node. Three async functions: `retrieve`, `enrich`, `write`. Each takes the current state, does its work, and returns a dict of fields to update on the state.

---

### `data_loaders/pnl_attr_loader.py`
Reads `PnlAttr_comments.xlsx`. Three functions:
- `load_strategy_rows()` — returns one `StrategyPnlRow` per row in the PNL sheet
- `load_desk_pnl()` — aggregates those rows to desk level → `DeskPnlRow` list
- `load_prior_comments()` — reads the Desk Comments sheet → `DeskComment` list (used as style reference by the LLM)

---

### `data_loaders/tpt_loader.py`
Reads the two TPT snapshot files (T and T-1). Builds one `StrategyContext` per strategy, with the MTM change computed as `MTM(T) - MTM(T-1)`. These contexts are passed to `StrategyMemory` for storage.

The column mapping (`_C` dict at the top) maps canonical field names to the actual Excel column headers. If the headers change, update `_C`.

---

### `data_loaders/enricher.py`
Takes the list of `StrategyPnlRow` objects and looks up each strategy in `StrategyMemory`. For each significant strategy (above a minimum PnL threshold), it produces a `StrategyInsight` with a plain-text explanation. If a strategy can't be found in memory and its PnL is large, it's flagged as `unclear=True` so the LLM mentions it.

"Significant" means: PnL > $5k absolute, or > 5% of the desk's total DTD.

---

### `data_loaders/strategy_classifier.py`
One function: `is_synthetic_strategy(strategy_num)`. Returns True for system-generated entries like SOS Analysis pairs, FX WASH, management cost allocations. These rows are kept in the data but excluded from strategy insights because they're not real trading positions.

---

### `context_memory/strategy_memory.py`
A persistent JSON store (`strategy_index.json`) that remembers what we know about each strategy across runs. Every time TPT files are loaded, the memory is updated. If the same strategy appears again tomorrow, we already know its commodity, counterpart, direction, etc. — no need to re-read the files.

Key methods:
- `get(strategy_num)` — returns a `StrategyContext` or None
- `upsert(ctx)` — adds or updates, always keeping the richest version
- `save()` — writes to disk

---

### `ai_writer/writer.py`
Calls Azure OpenAI once per desk. Takes each `EnrichedDeskContext`, builds the prompt via `prompt_builder.py`, sends it to GPT-4o, and returns the comment text. The LLM is only given structured data — not raw Excel files. This is what prevents hallucination.

---

### `prompts/prompt_builder.py`
Assembles the user message sent to the LLM for each desk. It includes:
- Attribution bucket breakdown (MTM, Pricing, Trades, etc.)
- Strategy insights from TPT snapshots (commodity, counterpart, direction, delivery)
- Prior comment as style reference
- Two few-shot examples from `examples.py`
- The instruction: write like an MO analyst, lead with commodity not with bucket names, max ~150 words

---

### `prompts/system_prompt.py`
The fixed system message sent to the LLM on every call. Defines the MO analyst persona, the comment style rules, what each attribution bucket means, and how to handle unclear strategies. You shouldn't need to change this often.

---

### `prompts/examples.py`
Real PnL comments from the Desk Comments sheet, grouped by desk type (crude physical, LPG, shipping, LNG, paper, etc.). The prompt builder picks the 2 most relevant examples for the desk being commented. These exist so the LLM matches the actual style used by the team.

---

## Data sources summary

| File | What it contains | Used by |
|------|-----------------|---------|
| `PnlAttr_comments.xlsx` — sheet "PNL" | PnL per strategy, all buckets | `pnl_attr_loader` |
| `PnlAttr_comments.xlsx` — sheet "Desk Comments" | Prior human-written comments | `pnl_attr_loader` |
| `ST-DESK-PM-PNL Oil BBL T.xlsx` | Today's TPT position snapshot | `tpt_loader` |
| `ST-DESK-PM-PNL Oil BBL T1.xlsx` | Yesterday's TPT position snapshot | `tpt_loader` |
| `strategy_index.json` (generated) | Persistent strategy memory | `strategy_memory` |

---

## What's not yet connected

| Component | Status |
|-----------|--------|
| TPT trade log API | Model defined (`TptTradeLog`), API credentials TBD |
| PostgreSQL | Config field exists, currently using Excel files directly |
| Teams notifications | Webhook URL in config, delivery not yet implemented |
| Weekly / monthly runs | Run types defined, aggregation logic not yet built |
