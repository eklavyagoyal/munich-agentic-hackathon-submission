import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture(autouse=True)
def _no_model_backend(monkeypatch):
    """No test may reach a model provider.

    The moment a real key landed in .env and the SDK was installed, the suite went
    from 2.2s to 20s, started billing per run, and one round-trip test began failing
    because the ensemble now answered instead of abstaining. Tests that exercise the
    LLM path must inject their own fake; nothing may depend on ambient credentials.

    Autouse and unconditional: opting in per test is the version of this that stops
    working the first time somebody forgets.
    """
    for var in ("ANTHROPIC_API_KEY", "OPENAI_KEY", "OPENAI_API_KEY", "C2F_BACKEND"):
        monkeypatch.delenv(var, raising=False)
    # llm.backend() memoises, so clearing the environment is not enough on its own.
    try:
        from c2f.estimate import llm
    except ImportError:
        return
    llm.reset()
    yield
    llm.reset()
