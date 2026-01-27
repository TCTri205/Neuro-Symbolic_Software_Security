import os
import shutil
import pytest
from unittest.mock import patch
from src.report.manager import ReportManager
from src.report.markdown import MarkdownReporter
from src.report.sarif import SarifReporter
from src.report.ir import IRReporter


@pytest.fixture
def temp_report_dir():
    dir_path = "tests/temp_reports"
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)
    yield dir_path
    if os.path.exists(dir_path):
        shutil.rmtree(dir_path)


@pytest.fixture
def mock_results():
    return {"file.py": {"data": "test"}}


def test_generate_all_success(temp_report_dir, mock_results):
    manager = ReportManager(temp_report_dir)

    # Mock reporters to avoid actual file writing logic in unit test
    # But we want to verify the manager logic
    with (
        patch.object(MarkdownReporter, "generate") as mock_md,
        patch.object(SarifReporter, "generate") as mock_sarif,
        patch.object(IRReporter, "generate") as mock_ir,
    ):
        generated = manager.generate_all(mock_results)

        assert len(generated) == 3
        assert os.path.join(temp_report_dir, "nsss_report.md") in generated
        assert os.path.join(temp_report_dir, "nsss_report.sarif") in generated
        assert os.path.join(temp_report_dir, "nsss_report.ir.json") in generated

        mock_md.assert_called_once()
        mock_sarif.assert_called_once()
        mock_ir.assert_called_once()

        # Verify dir was created
        assert os.path.exists(temp_report_dir)


def test_generate_all_create_dir_failure(temp_report_dir, mock_results):
    # Simulate permission error or similar
    with patch("os.makedirs", side_effect=OSError("Perm denied")):
        manager = ReportManager(temp_report_dir)
        generated = manager.generate_all(mock_results)
        assert len(generated) == 0


def test_reporter_failure_resilience(temp_report_dir, mock_results):
    manager = ReportManager(temp_report_dir)

    with (
        patch.object(
            MarkdownReporter, "generate", side_effect=Exception("MD Failed")
        ) as mock_md,
        patch.object(SarifReporter, "generate") as mock_sarif,
        patch.object(IRReporter, "generate") as mock_ir,
    ):
        generated = manager.generate_all(mock_results)

        # Should still generate SARIF + IR even if MD fails
        assert len(generated) == 2
        assert any(path.endswith(".sarif") for path in generated)
        assert any(path.endswith(".ir.json") for path in generated)

        mock_md.assert_called_once()
        mock_sarif.assert_called_once()
        mock_ir.assert_called_once()


def test_report_type_filtering(temp_report_dir, mock_results):
    manager = ReportManager(temp_report_dir, report_types=["markdown"])

    with (
        patch.object(MarkdownReporter, "generate") as mock_md,
        patch.object(SarifReporter, "generate") as mock_sarif,
    ):
        generated = manager.generate_all(mock_results)

        assert len(generated) == 1
        assert generated[0].endswith(".md")

        mock_md.assert_called_once()
        mock_sarif.assert_not_called()
