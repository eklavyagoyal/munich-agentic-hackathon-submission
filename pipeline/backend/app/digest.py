"""Policy digest: one fast pre-call that turns the case's policy text into a
short list of pricing-relevant limits and exclusions.

Why: anchors pin MARKET rates, but coverage is per case — game 48 priced pool
equipment at market rates under an 'Ancillary Plant Edition' policy that
capped exactly those items (18/27 charges burned). The digest is the missing
per-case signal. Cached per game under data/digests/.
"""
from __future__ import annotations

import json
import os

import requests

from .config import DATA
from .parse import Case

DIGEST_DIR = DATA / "digests"
DIGEST_MODEL = os.environ.get("C2F_DIGEST_MODEL", "gpt-4.1-mini")
_KEY = (os.environ.get("OPENAI_API_KEY_2") or os.environ.get("OPENAI_API_KEY") or "")

PROMPT = """Extract ONLY the pricing-relevant rules from this insurance policy for a claims adjuster. Focus on: coverage limits/caps (with amounts), excluded categories (e.g. ancillary plant, pool equipment, contents, outbuildings), betterment/upgrade rules, deductibles, and anything capping specific line items. Ignore boilerplate.

POLICY:
{policy}

Answer with JSON: {{"digest": ["<rule 1>", ...]}} — at most 10 short bullet strings, each naming concrete items/amounts where possible."""


def policy_digest(case: Case) -> str:
    """Cached digest text block for the estimator prompt ('' on any failure)."""
    if not case.policy.strip() or not _KEY:
        return ""
    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    cache = DIGEST_DIR / f"game_{case.game_id:03d}.json"
    if cache.exists():
        try:
            lines = json.loads(cache.read_text())["digest"]
        except (OSError, KeyError, json.JSONDecodeError):
            lines = []
    else:
        try:
            r = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {_KEY}"},
                json={"model": DIGEST_MODEL,
                      "messages": [{"role": "user",
                                    "content": PROMPT.format(policy=case.policy[:24000])}],
                      "response_format": {"type": "json_object"}},
                timeout=18)
            r.raise_for_status()
            lines = json.loads(r.json()["choices"][0]["message"]["content"]).get("digest", [])
            lines = [str(x)[:300] for x in lines][:10]
            cache.write_text(json.dumps({"digest": lines}))
        except Exception as e:  # noqa: BLE001
            print(f"  digest failed: {type(e).__name__}: {str(e)[:120]}")
            return ""
    if not lines:
        return ""
    return ("\nTHIS case's policy limits (override general market rates and the "
            "reference prices when they conflict — items outside coverage or over "
            "a cap have a LOW or zero approved value):\n"
            + "\n".join(f"- {x}" for x in lines) + "\n")
