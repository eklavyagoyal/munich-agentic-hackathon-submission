"""One schema-constrained JSON call. The ONLY file that knows a model provider.

Backend is picked from whichever key exists, so the same code runs on Anthropic, on
the OPENAI_KEY the QuantCo starter script expects, or on neither — in which case
callers get NoBackend and fall back to the price book.

  C2F_BACKEND   force "anthropic" | "openai" | "none"
  C2F_MODEL     override the model id
  C2F_STORE_LOGS  "0" to stop asking the provider to retain requests
"""
from __future__ import annotations

import base64
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


async def ask_json(
    prompt: str,
    *,
    schema: dict,
    fast: bool,
    timeout: float,
    system: str | None = None,
    images: tuple[str, ...] = (),
) -> dict:
    """Schema-constrained JSON. Raises on any failure — callers own the fallback."""
    b = backend()
    paths = [Path(p) for p in images if Path(p).exists()]
    if b == "anthropic":
        return await _anthropic(prompt, schema, fast, timeout, system, paths)
    if b == "openai":
        return await _openai(prompt, schema, fast, timeout, system, paths)
    raise NoBackend("no ANTHROPIC_API_KEY or OPENAI_KEY in the environment")


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
