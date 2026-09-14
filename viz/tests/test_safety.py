from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock

from viz.case_worker import _inside, _validate_archive_members
from viz.server import Handler, MAX_QUERY_FIELDS


class ArchiveSafetyTests(unittest.TestCase):
    def test_safe_synthetic_archive_passes(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            archive = Path(raw) / "synthetic.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("documents/invoice.pdf", b"synthetic-not-a-real-pdf")
            _validate_archive_members(archive)

    def test_traversal_archive_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            archive = Path(raw) / "synthetic.zip"
            with zipfile.ZipFile(archive, "w") as handle:
                handle.writestr("../escape.txt", b"synthetic")
            with self.assertRaises(ValueError):
                _validate_archive_members(archive)

    def test_path_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw) / "runtime"
            parent.mkdir()
            self.assertTrue(_inside(parent / "case" / "file.pdf", parent))
            self.assertFalse(_inside(parent.parent / "outside.pdf", parent))


class SourceBoundaryTests(unittest.TestCase):
    def test_all_runtime_python_stays_out_of_submit_and_dotenv_paths(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = "\n".join(
            path.read_text() for path in sorted(root.glob("*.py"))
        )
        for forbidden in (
            "c2f.submit", "LiveApi", "play_once", "load_dotenv(",
            "dotenv_values(", "find_dotenv(",
        ):
            self.assertNotIn(forbidden, source)

    def test_case_worker_moves_to_runtime_before_importing_c2f(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "case_worker.py").read_text()
        self.assertLess(source.index("os.chdir(runtime)"),
                        source.index("from c2f.ingest.decrypt import extract"))
        self.assertLess(source.index("os.chdir(runtime)"),
                        source.index("from c2f.ingest.parse import build_case"))

    def test_excess_query_fields_receive_explicit_client_error(self) -> None:
        handler = object.__new__(Handler)
        handler.path = "/?" + "&".join(
            f"field{index}=synthetic" for index in range(MAX_QUERY_FIELDS + 1)
        )
        handler._problem = Mock()
        handler.do_GET()
        handler._problem.assert_called_once_with(
            400,
            "Invalid query",
            f"The request exceeds the {MAX_QUERY_FIELDS}-field local safety limit.",
            failure_class="InputLimit",
        )

    def test_server_has_no_submission_client_reference(self) -> None:
        server_source = (Path(__file__).resolve().parents[1] / "server.py").read_text()
        self.assertNotIn("LiveApi", server_source)
        self.assertNotIn("play_once", server_source)
        self.assertNotIn("c2f.submit", server_source)

    def test_frontend_never_uses_dynamic_inner_html(self) -> None:
        app_source = (Path(__file__).resolve().parents[1] / "static" / "app.js").read_text()
        self.assertNotIn("innerHTML", app_source)


if __name__ == "__main__":
    unittest.main()
