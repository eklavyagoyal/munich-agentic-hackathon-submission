"""Claim to Fame."""

# Load .env before anything reads os.environ, so a key placed in that file actually
# takes effect no matter which entrypoint runs. See c2f/core/env.py.
from c2f.core.env import load as _load_env

_load_env()
