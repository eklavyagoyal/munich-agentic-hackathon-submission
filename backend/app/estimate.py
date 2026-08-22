"""Fair-value estimation: 3-model LLM ensemble, median, text-only.

v1's benchmark (analysis/luis-1725) on 272 proven intervals: median of
[gpt-4.1-mini, gpt-5.4-mini, gpt-5.6-terra] with description+invoice ONLY beat
every single model and every extra-context variant (+policy/+photo made models
bolder, not better). Wall clock is the slowest call (~6s of the 60s window).

Every failure degrades, never zeroes: missing model -> median of the rest;
all missing -> per-unit fallback rates learned from proven t_lo bounds.
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import re

import requests

from .parse import Case

MODELS = tuple(os.environ.get("C2F_MODELS", "gpt-4.1-mini,gpt-5.4-mini,gpt-5.6-terra").split(","))
LLM_TIMEOUT = float(os.environ.get("C2F_LLM_TIMEOUT", "25"))

_KEYS = [k for k in (os.environ.get("OPENAI_API_KEY_1"), os.environ.get("OPENAI_API_KEY_2"),
                     os.environ.get("OPENAI_API_KEY_3"), os.environ.get("OPENAI_API_KEY")) if k]

PROMPT = """You are a senior German insurance claims adjuster. For each invoice line item, estimate the FAIR GROSS TOTAL price in EUR (quantity x unit price, including 19% VAT) that a claims expert would approve for this damage case.

Damage description:
{damage}

Invoice line items (index | description | qty | unit):
{items}

Rules:
- Fair market rates for German tradespeople, 2026.
- The total for the WHOLE line (qty x unit rate), gross.
- Items unrelated to the described damage, pure betterment/upgrades ("entire", "all", "undamaged", "upgrade"), luxury extras, or non-claimable costs (catering, double-billed) get a LOW value or 0.
- Answer with JSON only: {{"items": [{{"index": <int>, "fair_total_eur": <number>}}, ...]}} — one entry per index, all indices present."""


def build_prompt(case: Case) -> str:
    items_txt = "\n".join(f"{i.idx} | {i.description} | {i.qty:g} | {i.unit}" for i in case.items)
    return PROMPT.format(damage=case.damage[:6000], items=items_txt)


def _call_model(model: str, key: str, case: Case, prompt: str) -> dict[int, float]:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
    }
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers={"Authorization": f"Bearer {key}"},
                      json=body, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    out: dict[int, float] = {}
    for row in data.get("items", []):
        try:
            idx, v = int(row["index"]), float(row["fair_total_eur"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= v < 10_000_000:
            out[idx] = v
    return out


# Fallback per-unit-class gross rates, learned from proven t_lo bounds of 41 games
# (see calibrate.py output); deliberately on the low side of proven-fair.
FALLBACK_RATES = {"m2": 40.0, "m": 25.0, "h": 90.0, "pcs": 150.0, "pauschal": 250.0, "kwh": 0.5}


def _unit_class(unit: str) -> str:
    u = unit.lower().rstrip(".")
    if u in ("m2", "m²", "sqm", "qm"):
        return "m2"
    if u in ("h", "hour", "hours", "std", "stunden"):
        return "h"
    if u in ("m", "lfm", "meter"):
        return "m"
    if u in ("kwh",):
        return "kwh"
    if u in ("pauschal", "flat rate", "flatrate", "lump sum", "psch") or "pausch" in u or "flat" in u:
        return "pauschal"
    return "pcs"


def fallback_estimates(case: Case) -> dict[int, float]:
    return {i.idx: max(i.qty, 1.0) * FALLBACK_RATES[_unit_class(i.unit)] for i in case.items}


def estimate(case: Case, models: tuple[str, ...] | None = None) -> tuple[dict[int, float], dict]:
    """Return (t_hat per index, meta). Median over whatever models answered."""
    per_model: dict[str, dict[int, float]] = {}
    errors: dict[str, str] = {}
    prompt = build_prompt(case)
    models = models or MODELS
    if _KEYS:
        with cf.ThreadPoolExecutor(max_workers=len(models)) as ex:
            futs = {ex.submit(_call_model, m, _KEYS[i % len(_KEYS)], case, prompt): m
                    for i, m in enumerate(models)}
            for fut in cf.as_completed(futs):
                m = futs[fut]
                try:
                    per_model[m] = fut.result()
                except Exception as e:  # noqa: BLE001
                    per_model[m] = {}
                    errors[m] = f"{type(e).__name__}: {str(e)[:200]}"
                    print(f"  model {m}: {errors[m][:130]}")
    fb = fallback_estimates(case)
    t_hat: dict[int, float] = {}
    source: dict[int, str] = {}
    for it in case.items:
        votes = sorted(est[it.idx] for est in per_model.values() if it.idx in est)
        if votes:
            mid = len(votes) // 2
            med = votes[mid] if len(votes) % 2 else (votes[mid - 1] + votes[mid]) / 2
            t_hat[it.idx] = med
            source[it.idx] = f"ensemble{len(votes)}"
        else:
            t_hat[it.idx] = fb[it.idx]
            source[it.idx] = "fallback"
    meta = {"models_answered": {m: len(v) for m, v in per_model.items()},
            "per_model": {m: v for m, v in per_model.items()}, "source": source,
            "prompt": prompt if _KEYS else build_prompt(case), "errors": errors}
    return t_hat, meta
