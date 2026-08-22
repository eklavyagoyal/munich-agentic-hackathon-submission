"""`.env` must actually be read.

submit/client.py instructs the operator to put the team key in `.env`. Nothing was
reading that file, so the key would have been silently ignored -- at 03:00, with no
round submitted and nothing in the logs pointing at the cause.
"""
import os

VARS = ("TEAM_API_KEY", "OPENAI_KEY", "ANTHROPIC_API_KEY")


def test_dotenv_is_actually_read(tmp_path, monkeypatch):
    from c2f.core.env import load

    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "# a comment line",
                "TEAM_API_KEY=plain-value",
                'export OPENAI_KEY="double-quoted"',
                "ANTHROPIC_API_KEY='single-quoted'",
                "MALFORMED LINE WITHOUT EQUALS",
                "",
            ]
        )
    )
    for v in VARS:
        monkeypatch.delenv(v, raising=False)

    names = load(tmp_path / ".env")

    assert set(names) == set(VARS)
    assert os.environ["TEAM_API_KEY"] == "plain-value"
    assert os.environ["OPENAI_KEY"] == "double-quoted"      # quotes stripped
    assert os.environ["ANTHROPIC_API_KEY"] == "single-quoted"


def test_real_env_wins_over_the_file(tmp_path, monkeypatch):
    """So an inline override works, and CI never picks up local secrets."""
    from c2f.core.env import load

    (tmp_path / ".env").write_text("TEAM_API_KEY=from-file\n")
    monkeypatch.setenv("TEAM_API_KEY", "from-real-env")

    assert load(tmp_path / ".env") == []
    assert os.environ["TEAM_API_KEY"] == "from-real-env"


def test_missing_file_is_not_an_error(tmp_path):
    from c2f.core.env import load

    assert load(tmp_path / "does-not-exist") == []


def test_returns_names_never_values(tmp_path, monkeypatch):
    """The return value is meant to be loggable, so it must not carry secrets."""
    from c2f.core.env import load

    marker = "zz-should-never-be-logged-zz"
    (tmp_path / ".env").write_text(f"TEAM_API_KEY={marker}\n")
    monkeypatch.delenv("TEAM_API_KEY", raising=False)

    assert marker not in str(load(tmp_path / ".env"))


def test_dotenv_is_gitignored():
    """A committed key is unrecoverable -- the guard belongs in the test suite."""
    import subprocess

    r = subprocess.run(
        ["git", "check-ignore", "-q", ".env"], capture_output=True, timeout=10
    )
    assert r.returncode == 0, ".env is NOT gitignored"
