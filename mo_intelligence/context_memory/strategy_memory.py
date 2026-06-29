"""Persistent strategy memory — survives across runs.

Stores what we know about each strategy (instrument, commodity, counterpart,
direction, typical PnL drivers) in a JSON file. Grows richer every run as
new TPT data is observed.

Usage:
    memory = StrategyMemory()
    ctx = memory.get("215895")           # lookup
    memory.upsert(strategy_context)      # update
    memory.save()                        # persist to disk
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from mo_intelligence.shared.models import StrategyContext

_DEFAULT_PATH = Path(__file__).parent / "strategy_index.json"

_EMPTY_STR_SENTINELS = {"nan", "none", "null", "nat", ""}


def _is_meaningful(val) -> bool:
    """True if val is non-empty and not a garbage sentinel string/number."""
    if isinstance(val, str):
        return val.strip().lower() not in _EMPTY_STR_SENTINELS
    if isinstance(val, (int, float)):
        return val not in (0, 0.0)
    return val is not None


def _empty_for(val):
    """Return the correct 'empty' for a value's type."""
    if isinstance(val, (int, float)):
        return 0.0
    return ""


class StrategyMemory:
    def __init__(self, path: Path | str = _DEFAULT_PATH) -> None:
        self._path = Path(path)
        self._store: dict[str, StrategyContext] = {}
        self._load()

 
    # Public API
 
    def get(self, strategy_num: str) -> StrategyContext | None:
        return self._store.get(str(strategy_num))

    def upsert(self, ctx: StrategyContext) -> None:
        """Insert or update, always keeping the richest version.

        A field value is considered "known" if it is non-empty AND is not a
        sentinel string like "nan"/"none"/"null" left over from earlier runs.
        """
        key = str(ctx.strategy_num)
        existing = self._store.get(key)
        if existing is None:
            # Ensure we store a clean context on first insert
            self._store[key] = StrategyContext.model_validate({
                k: (v if _is_meaningful(v) else _empty_for(v)) for k, v in ctx.model_dump().items()
            })
            return
        # Merge: prefer the newer value when it's meaningful
        merged = existing.model_dump()
        for field, new_val in ctx.model_dump().items():
            if _is_meaningful(new_val):
                merged[field] = new_val
            elif not _is_meaningful(merged[field]):
                # Both old and new are empty/garbage — normalise to empty
                merged[field] = _empty_for(new_val)
        self._store[key] = StrategyContext(**merged)

    def upsert_many(self, contexts: list[StrategyContext]) -> None:
        for ctx in contexts:
            self.upsert(ctx)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        data = {k: v.model_dump() for k, v in self._store.items()}
        self._path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def __len__(self) -> int:
        return len(self._store)

 
    # Internal
 
    def clean_nan_values(self) -> int:
        """Scrub any 'nan' sentinel strings that snuck in from earlier runs."""
        count = 0
        for key, ctx in list(self._store.items()):
            d = ctx.model_dump()
            cleaned = {k: (_empty_for(v) if not _is_meaningful(v) else v) for k, v in d.items()}
            if cleaned != d:
                self._store[key] = StrategyContext.model_validate(cleaned)
                count += 1
        return count

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            self._store = {k: StrategyContext(**v) for k, v in raw.items()}
            self.clean_nan_values()  # scrub any stale "nan" strings from prior runs
        except Exception:
            self._store = {}
