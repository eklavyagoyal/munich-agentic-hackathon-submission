"""One Claude call, JSON out, bounded. The only file that knows about a model provider.

Two profiles, because the round is 60s and we submit twice (GAMEPLAN §4):
  fast=True   low effort  — feeds submission #1, the safety net
  fast=False  high effort — feeds submission #2, the real answer
"""

from __future__ import annotations

import base64
import json
import logging
import mimetypes
from pathlib import Path

import anthropic

MODEL = "claude-opus-5"

log = logging.getLogger("c2f")

_client: anthropic.AsyncAnthropic | None = None


def client() -> anthropic.AsyncAnthropic:
    global _client
    if _client is None:
        # One retry only: inside a 60s round a second retry costs more than it saves.
        _client = anthropic.AsyncAnthropic(max_retries=1)
    return _client


def _image_block(path: Path) -> dict:
    media = mimetypes.guess_type(path.name)[0] or "image/png"
    return {
        "type": "image",
        "source": {
            "type": "base64",
            "media_type": media,
            "data": base64.standard_b64encode(path.read_bytes()).decode(),
        },
    }


async def ask_json(
    prompt: str,
    *,
    schema: dict,
    fast: bool,
    timeout: float,
    system: str | None = None,
    images: list[Path] | None = None,
) -> dict:
    """Schema-constrained JSON. Raises on failure — callers own the fallback."""
    content: list[dict] = [_image_block(p) for p in (images or [])]
    content.append({"type": "text", "text": prompt})

    kwargs: dict = {}
    if system:
        # Stable across every item in a round and every round in the tournament,
        # so it is worth a cache breakpoint.
        kwargs["system"] = [
            {"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}
        ]

    r = await client().with_options(timeout=timeout).messages.create(
        model=MODEL,
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

    text = next((b.text for b in r.content if b.type == "text"), None)
    if not text:
        raise RuntimeError(f"no text block in response (stop_reason={r.stop_reason})")
    return json.loads(text)
