"""One schema-constrained JSON call. The ONLY file that knows a model provider.

Backend is picked from whichever key exists, so the same code runs on Anthropic, on
the OPENAI_KEY the QuantCo starter script expects, or on neither — in which case
callers get NoBackend and fall back to the price book.

  C2F_BACKEND   force "anthropic" | "openai" | "none"
  C2F_MODEL     override the model id
  C2F_STORE_LOGS  "0" to stop asking the provider to retain requests
  C2F_LLM_CACHE   a directory: read-through response cache. BACKTESTS ONLY.
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import mimetypes
import os
from pathlib import Path

log = logging.getLogger("c2f")

ANTHROPIC_MODEL = "claude-opus-5"
OPENAI_MODEL = "gpt-4o"

_client = None
_backend: str | None = None


class NoBackend(RuntimeError):
    """No usable model key. Not fatal — the price book still produces numbers."""


def backend() -> str:
    """"anthropic" | "openai" | "none". Resolved once, then cached."""
    global _backend
    if _backend is None:
        forced = os.environ.get("C2F_BACKEND", "").strip().lower()
        if forced:
            _backend = forced
        elif os.environ.get("ANTHROPIC_API_KEY"):
            _backend = "anthropic"
        elif os.environ.get("OPENAI_KEY") or os.environ.get("OPENAI_API_KEY"):
            _backend = "openai"
        else:
            _backend = "none"
        # Retention is reported on the SAME line, once, rather than as its own
        # message: it is a privacy-relevant default that is ON, and a setting
        # nothing announces is a setting nobody can verify took effect.
        if _backend == "openai":
            log.warning("llm backend: %s (request retention %s)", _backend,
                        "ON" if store_logs() else "off")
        else:
            log.warning("llm backend: %s", _backend)
    return _backend


def reset() -> None:
    """Re-resolve the backend. Tests only — never during a round."""
    global _backend, _client
    _backend, _client = None, None


def model_id() -> str:
    return os.environ.get("C2F_MODEL") or (
        ANTHROPIC_MODEL if backend() == "anthropic" else OPENAI_MODEL
    )


def store_logs() -> bool:
    """Ask the provider to RETAIN each request, so it appears in the dashboard Logs.

    Retention is opt-in per request and defaults OFF at the API. That is why our Logs
    view read empty through the first 27 rounds while Usage was billing normally --
    nothing was misconfigured, we simply never asked. It is now explicit.

    The tradeoff is one-directional and worth naming at the call site: retention means
    the prompt PERSISTS in a browsable dashboard, and our item prompts carry invoice
    line text. We already transmit that text to get a price; this keeps a copy. Set
    C2F_STORE_LOGS=0 to switch it off without a deploy.
    """
    v = os.environ.get("C2F_STORE_LOGS", "1").strip().lower()
    return v not in {"0", "false", "no", "off", ""}


def _b64(path: Path) -> tuple[str, str]:
    return (
        mimetypes.guess_type(path.name)[0] or "image/png",
        base64.standard_b64encode(path.read_bytes()).decode(),
    )


def cache_dir() -> Path | None:
    """Where to cache responses, or None. Unset means NO caching, which is the default
    and what the live daemon must always see -- a cached answer in a live round would be
    stale by a whole game."""
    raw = os.environ.get("C2F_LLM_CACHE", "").strip()
    return Path(raw) if raw else None


def _cache_key(prompt: str, schema: dict, fast: bool, system: str | None,
               images: list) -> str:
    """Hash everything that can change the answer, and nothing that cannot.

    Includes the model id: a cache shared across models would silently serve gpt-4o
    answers for a different model and the swap would look like a null result.
    """
    payload = json.dumps({
        "model": model_id(),
        "prompt": prompt,
        "schema": schema,
        "fast": fast,
        "system": system,
        "images": sorted(str(p) for p in images),
    }, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# Counters, so a backtest can PROVE it replayed rather than re-sampled. A run reporting
# 0 hits is a run that spent money and measured fresh noise.
hits = 0
misses = 0

# Per-key draw counter. The ensemble sends the SAME prompt N times to get N independent
# samples, and its spread IS the sigma the decision rules use. A cache keyed on the
# prompt alone would return one identical answer N times, collapsing the ensemble to a
# single sample and silently changing sigma -- observed dropping 0.450 to 0.366. So each
# key stores a LIST of responses and successive calls draw successive entries. A replay
# therefore reproduces the same MULTISET of samples, which is what the median and the
# spread depend on, without needing the caller to pass a sample index or the concurrent
# gather to preserve order.
_draws: dict[str, int] = {}


def reset_draws() -> None:
    """Start a fresh pass over the cache. Call between replays."""
    _draws.clear()


def cache_stats() -> tuple[int, int]:
    return hits, misses


async def ask_json(
    prompt: str,
    *,
    schema: dict,
    fast: bool,
    timeout: float,
    system: str | None = None,
    images: tuple[str, ...] = (),
) -> dict:
    """Schema-constrained JSON. Raises on any failure — callers own the fallback.

    With C2F_LLM_CACHE set, identical requests replay from disk instead of resampling.
    That exists because model non-determinism was larger than the effects we were trying
    to measure: two replays of the same 12 games differed by 31,886 EUR of provable
    income, which is an order of magnitude above the ~2,000/game changes under test.
    Every A/B on a model-dependent rule was measuring noise. Off by default, so the live
    daemon is never served a stale answer.
    """
    global hits, misses
    b = backend()
    paths = [Path(p) for p in images if Path(p).exists()]

    cdir = cache_dir()
    key = None
    stored: list = []
    if cdir is not None:
        key = _cache_key(prompt, schema, fast, system, paths)
        path = cdir / f"{key}.json"
        if path.is_file():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                stored = loaded if isinstance(loaded, list) else [loaded]
            except ValueError:
                stored = []          # truncated by an interrupted run; refetch
        n = _draws.get(key, 0)
        if n < len(stored):
            _draws[key] = n + 1
            hits += 1
            return stored[n]
        misses += 1

    if b == "anthropic":
        out = await _anthropic(prompt, schema, fast, timeout, system, paths)
    elif b == "openai":
        out = await _openai(prompt, schema, fast, timeout, system, paths)
    else:
        raise NoBackend("no ANTHROPIC_API_KEY or OPENAI_KEY in the environment")

    if cdir is not None and key is not None:
        try:
            cdir.mkdir(parents=True, exist_ok=True)
            stored.append(out)
            _draws[key] = len(stored)
            # Write via a temp file so a crash mid-write cannot leave a half entry that
            # a later run would treat as authoritative.
            tmp = cdir / f".{key}.tmp"
            tmp.write_text(json.dumps(stored, ensure_ascii=False), encoding="utf-8")
            tmp.replace(cdir / f"{key}.json")
        except OSError:
            pass          # caching is a convenience; never fail a call over it
    return out


async def _anthropic(prompt, schema, fast, timeout, system, images) -> dict:
    global _client
    import anthropic

    if _client is None:
        # One retry only: inside a 60s round a second retry costs more than it saves.
        _client = anthropic.AsyncAnthropic(max_retries=1)

    content: list[dict] = []
    for p in images:
        media, data = _b64(p)
        content.append(
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}}
        )
    content.append({"type": "text", "text": prompt})

    kwargs: dict = {}
    if system:
        # Identical across every item in a round and every round in the tournament,
        # so it earns a cache breakpoint.
        kwargs["system"] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]

    r = await _client.with_options(timeout=timeout).messages.create(
        model=model_id(),
        max_tokens=8000,
        output_config={
            "effort": "low" if fast else "high",
            "format": {"type": "json_schema", "schema": schema},
        },
        messages=[{"role": "user", "content": content}],
        **kwargs,
    )
    if r.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {getattr(r.stop_details, 'category', None)}")
    if r.stop_reason == "max_tokens":
        raise RuntimeError("hit max_tokens — JSON is truncated")
    text = next((blk.text for blk in r.content if blk.type == "text"), None)
    if not text:
        raise RuntimeError(f"no text block (stop_reason={r.stop_reason})")
    return json.loads(text)


async def _openai(prompt, schema, fast, timeout, system, images) -> dict:
    global _client
    from openai import AsyncOpenAI

    if _client is None:
        _client = AsyncOpenAI(
            api_key=os.environ.get("OPENAI_KEY") or os.environ.get("OPENAI_API_KEY"),
            max_retries=1,
        )

    content: list[dict] = []
    for p in images:
        media, data = _b64(p)
        content.append({"type": "image_url", "image_url": {"url": f"data:{media};base64,{data}"}})
    content.append({"type": "text", "text": prompt})

    messages: list[dict] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": content})

    # Built as kwargs rather than passed as None: with logging off the request is
    # byte-identical to what shipped for 27 rounds, so this cannot change behaviour.
    extra: dict = {}
    if store_logs():
        extra = {"store": True, "metadata": {"app": "c2f"}}

    r = await _client.with_options(timeout=timeout).chat.completions.create(
        model=model_id(),
        messages=messages,
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "result", "schema": schema, "strict": True},
        },
        **extra,
    )
    choice = r.choices[0]
    if choice.finish_reason == "length":
        raise RuntimeError("hit token limit — JSON is truncated")
    if getattr(choice.message, "refusal", None):
        raise RuntimeError(f"model refused: {choice.message.refusal[:120]}")
    if not choice.message.content:
        raise RuntimeError(f"empty response (finish_reason={choice.finish_reason})")
    return json.loads(choice.message.content)
