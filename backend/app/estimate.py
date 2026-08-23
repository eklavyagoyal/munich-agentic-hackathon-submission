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
{digest}{anchors}
Rules:
- Fair market rates for German tradespeople, 2026.
- The total for the WHOLE line (qty x unit rate), gross.
- For upgrades/betterment ("premium", "designer", "upgrade"): give the fair value of a LIKE-FOR-LIKE replacement of the damaged item, not 0 — adjusters approve the standard-quality equivalent.
- Compensation/reimbursement lines can be legitimate: estimate the plausible amount from the damage description.
- Use 0 ONLY when you are confident the item is completely non-claimable (e.g. catering, explicitly double-billed). When unsure, give a moderate positive estimate.
{pcov_rule}- Answer with JSON only: {schema} — one entry per index, all indices present."""

_SCHEMA_PLAIN = '{"items": [{"index": <int>, "fair_total_eur": <number>}, ...]}'
_SCHEMA_PCOV = ('{"items": [{"index": <int>, "fair_total_eur": <number>, '
                '"p_covered": <number 0..1>}, ...]}')
_PCOV_RULE = ("- p_covered: your calibrated probability (0..1) that this item is COVERED "
              "by the policy AND related to the reported damage. Read exclusions literally; "
              "labour or ancillary work on an excluded component is excluded too. Judge "
              "coverage independently of the price estimate.\n")


def build_prompt(case: Case, anchors_block: str = "", digest_block: str = "",
                 ask_p_cov: bool = False, only_idxs: set[int] | None = None) -> str:
    items = [i for i in case.items if only_idxs is None or i.idx in only_idxs]
    items_txt = "\n".join(f"{i.idx} | {i.description} | {i.qty:g} | {i.unit}" for i in items)
    return PROMPT.format(damage=case.damage[:6000], items=items_txt,
                         anchors=anchors_block, digest=digest_block,
                         pcov_rule=_PCOV_RULE if ask_p_cov else "",
                         schema=_SCHEMA_PCOV if ask_p_cov else _SCHEMA_PLAIN)


def _image_b64(case: Case) -> str | None:
    """First case photo, downscaled once via sips (macOS builtin), cached, base64."""
    import base64
    import subprocess
    from pathlib import Path
    if not case.images:
        return None
    src = Path(case.images[0])
    small = src.with_name(src.stem + "_small.jpg")
    if not small.exists():
        r = subprocess.run(["sips", "-Z", "1024", "-s", "format", "jpeg",
                            str(src), "--out", str(small)],
                           capture_output=True, timeout=20)
        if r.returncode != 0 or not small.exists():
            return None
    data = small.read_bytes()
    if len(data) > 900_000:
        return None
    return base64.b64encode(data).decode()


def _call_model(model: str, key: str, case: Case, prompt: str,
                image_b64: str | None = None) -> dict[int, float]:
    if image_b64:
        content = [
            {"type": "text", "text": prompt + "\nA photo of the damage is attached — use it to judge the SCOPE of the damage (size, affected area, severity) and whether items are related."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}", "detail": "low"}},
        ]
    else:
        content = prompt
    body = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_object"},
    }
    r = requests.post("https://api.openai.com/v1/chat/completions",
                      headers={"Authorization": f"Bearer {key}"},
                      json=body, timeout=LLM_TIMEOUT)
    r.raise_for_status()
    content = r.json()["choices"][0]["message"]["content"]
    data = json.loads(content)
    out: dict[int, float] = {}
    pcov: dict[int, float] = {}
    for row in data.get("items", []):
        try:
            idx, v = int(row["index"]), float(row["fair_total_eur"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0 <= v < 10_000_000:
            out[idx] = v
        try:
            pv = float(row["p_covered"])
        except (KeyError, TypeError, ValueError):
            continue
        if 0.0 <= pv <= 1.0:
            pcov[idx] = pv
    return out, pcov


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


def estimate(case: Case, models: tuple[str, ...] | None = None,
             use_anchors: bool = False, use_image: bool = False,
             use_digest: bool = False, ask_p_cov: bool = False,
             use_precedents: bool = False, big_model: str = "",
             big_k: int = 3, big_guard_s: float = 30.0) -> tuple[dict[int, float], dict]:
    """Return (t_hat per index, meta). Median over whatever models answered.
    use_anchors injects proven reference prices from OTHER games (never the
    game being estimated — leave-one-game-out by construction).
    ask_p_cov additionally requests a calibrated P(covered&related) per item
    (median in meta["p_cov"]); use_precedents appends proven outcomes of
    same-scenario/same-wording earlier games to the digest block.
    big_model fires one second-opinion call from a stronger model for the
    big_k most valuable items (by preliminary median) and re-medians their
    votes — skipped entirely once big_guard_s of wall clock have passed."""
    import time as _time
    _t0 = _time.monotonic()
    per_model: dict[str, dict[int, float]] = {}
    per_model_p: dict[str, dict[int, float]] = {}
    errors: dict[str, str] = {}
    anchors_block = ""
    anchors_list: list[dict] = []
    if use_anchors:
        try:
            from .anchors import anchors_for_case_full
            anchors_block, anchors_list = anchors_for_case_full(case, exclude_game=case.game_id)
        except Exception as e:  # noqa: BLE001
            print(f"  anchors unavailable: {type(e).__name__}: {e}")
    digest_block = ""
    if use_digest:
        try:
            from .digest import policy_digest
            digest_block = policy_digest(case)
        except Exception as e:  # noqa: BLE001
            print(f"  digest unavailable: {type(e).__name__}: {e}")
    if use_precedents:
        try:
            from .wording import precedent_block
            digest_block += precedent_block(case)
        except Exception as e:  # noqa: BLE001
            print(f"  precedents unavailable: {type(e).__name__}: {e}")
    prompt = build_prompt(case, anchors_block, digest_block, ask_p_cov=ask_p_cov)
    img = None
    if use_image:
        try:
            img = _image_b64(case)
        except Exception as e:  # noqa: BLE001
            print(f"  image prep failed: {type(e).__name__}: {e}")
    models = models or MODELS
    if _KEYS:
        with cf.ThreadPoolExecutor(max_workers=len(models)) as ex:
            futs = {ex.submit(_call_model, m, _KEYS[i % len(_KEYS)], case, prompt, img): m
                    for i, m in enumerate(models)}
            for fut in cf.as_completed(futs):
                m = futs[fut]
                try:
                    per_model[m], per_model_p[m] = fut.result()
                except Exception as e:  # noqa: BLE001
                    per_model[m], per_model_p[m] = {}, {}
                    errors[m] = f"{type(e).__name__}: {str(e)[:200]}"
                    print(f"  model {m}: {errors[m][:130]}")
    fb = fallback_estimates(case)
    t_hat: dict[int, float] = {}
    source: dict[int, str] = {}
    p_cov: dict[int, float] = {}
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
        pv = sorted(pm[it.idx] for pm in per_model_p.values() if it.idx in pm)
        if pv:
            mid = len(pv) // 2
            p_cov[it.idx] = pv[mid] if len(pv) % 2 else (pv[mid - 1] + pv[mid]) / 2
    big_used: list[int] = []
    if big_model and _KEYS and _time.monotonic() - _t0 < big_guard_s:
        top = sorted((i for i in t_hat if source.get(i, "").startswith("ensemble")),
                     key=lambda i: -t_hat[i])[:max(big_k, 0)]
        if top:
            try:
                big_prompt = build_prompt(case, anchors_block, digest_block,
                                          ask_p_cov=False, only_idxs=set(top))
                big_est, _ = _call_model(big_model, _KEYS[0], case, big_prompt)
                for i in top:
                    if i in big_est:
                        votes = sorted([est[i] for est in per_model.values() if i in est]
                                       + [big_est[i]])
                        mid = len(votes) // 2
                        t_hat[i] = (votes[mid] if len(votes) % 2
                                    else (votes[mid - 1] + votes[mid]) / 2)
                        source[i] = f"{source[i]}+big"
                        big_used.append(i)
            except Exception as e:  # noqa: BLE001
                errors[big_model] = f"{type(e).__name__}: {str(e)[:200]}"
                print(f"  big-ticket {big_model}: {errors[big_model][:130]}")
    meta = {"models_answered": {m: len(v) for m, v in per_model.items()},
            "per_model": {m: v for m, v in per_model.items()}, "source": source,
            "prompt": prompt, "errors": errors, "anchors_used": bool(anchors_block),
            "anchors": anchors_list, "image_used": bool(img),
            "digest_used": bool(digest_block), "digest": digest_block,
            "p_cov": p_cov, "big_used": big_used}
    return t_hat, meta
