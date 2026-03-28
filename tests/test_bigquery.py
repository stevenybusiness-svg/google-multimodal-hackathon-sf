"""Tests for BigQuery report generation pipeline."""

from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


def test_bq_available_true():
    with patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
        from backend.bigquery import bq_available
        assert bq_available() is True


def test_bq_available_false():
    with patch.dict(os.environ, {}, clear=True):
        from backend.bigquery import bq_available
        # Need to reimport to pick up env change
        import importlib
        import backend.bigquery as bq_mod
        importlib.reload(bq_mod)
        assert bq_mod.bq_available() is False


def test_sample_data_generation():
    from backend.bigquery import _generate_sample_rows
    rows = _generate_sample_rows(num_days=7)
    # 7 days * 6 channels = 42 rows
    assert len(rows) == 42
    # Check all required fields
    for row in rows:
        assert "date" in row
        assert "channel" in row
        assert "segment" in row
        assert "spend" in row
        assert "conversions" in row
        assert "revenue" in row
        assert "cac" in row
        assert "impression_count" in row
        assert "click_count" in row
        assert "roi" in row
    # Check channels are valid
    channels = {r["channel"] for r in rows}
    assert channels == {"organic_search", "paid_search", "paid_social", "email", "direct", "referral"}
    # Check segments are valid
    segments = {r["segment"] for r in rows}
    assert segments <= {"enterprise", "mid_market", "smb", "startup"}


def test_sample_data_deterministic():
    from backend.bigquery import _generate_sample_rows
    rows1 = _generate_sample_rows(num_days=5)
    rows2 = _generate_sample_rows(num_days=5)
    assert rows1 == rows2


def test_looker_studio_url():
    from backend.bigquery import looker_studio_url
    url = looker_studio_url("my-project", "marketing_data", "campaigns")
    assert "lookerstudio.google.com" in url
    assert "my-project" in url
    assert "marketing_data" in url
    assert "campaigns" in url
    assert "bigQuery" in url


def test_report_request_contract():
    from backend.contracts import ReportRequest, empty_understanding
    result = empty_understanding()
    assert "report_requests" in result
    assert result["report_requests"] == []


def test_understanding_keys_includes_reports():
    from backend.contracts import UNDERSTANDING_KEYS
    assert "report_requests" in UNDERSTANDING_KEYS


@pytest.mark.asyncio
async def test_nl_to_sql_calls_gemini():
    """Verify NL-to-SQL calls Gemini and strips fences."""
    mock_resp = MagicMock()
    mock_resp.text = "SELECT channel, SUM(revenue) FROM `p.marketing_data.campaigns` GROUP BY channel"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("backend.bigquery._get_genai", return_value=mock_client), \
         patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
        from backend.bigquery import nl_to_sql
        sql = await nl_to_sql("show revenue by channel")
        assert "SELECT" in sql
        assert "channel" in sql


@pytest.mark.asyncio
async def test_generate_report_end_to_end():
    """Full pipeline: NL → SQL → results → summary."""
    mock_genai = MagicMock()
    # First call: NL to SQL
    sql_resp = MagicMock()
    sql_resp.text = "SELECT channel, SUM(revenue) as total FROM `p.marketing_data.campaigns` GROUP BY channel"
    # Second call: summary
    summary_resp = MagicMock()
    summary_resp.text = "Paid search drives the most revenue at $50K."
    mock_genai.models.generate_content.side_effect = [sql_resp, summary_resp]

    mock_bq = MagicMock()
    mock_query_job = MagicMock()
    mock_row = MagicMock()
    mock_row.items.return_value = [("channel", "paid_search"), ("total", 50000.0)]
    mock_query_job.result.return_value = [mock_row]
    mock_bq.query.return_value = mock_query_job
    mock_bq.project = "test-project"

    with patch("backend.bigquery._get_genai", return_value=mock_genai), \
         patch("backend.bigquery._get_bq", return_value=mock_bq), \
         patch.dict(os.environ, {"GOOGLE_CLOUD_PROJECT": "test-project"}):
        from backend.bigquery import generate_report
        report = await generate_report("show revenue by channel")
        assert "sql" in report
        assert "results" in report
        assert "looker_url" in report
        assert "summary" in report
        assert len(report["results"]) == 1
        assert "lookerstudio" in report["looker_url"]
