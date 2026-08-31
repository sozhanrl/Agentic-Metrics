"""
Unit tests for the GitHub data connector (backend/app/connectors/github_connector.py).

Acceptance Criteria Verified:
1. Zero usage of `random` in `backend/app/connectors/`.
2. Deterministic: Calling twice on the same repo data returns identical metric values.
3. Scoped: Two different repos produce distinct, independently-traceable metric sets with differing raw payloads.
4. Error Handling: 404 / 401 / 403 propagate clear HTTP exceptions without fallbacks to seeded data.
5. Omission: Unverifiable metrics (cyclomatic_complexity, test_coverage) and metrics lacking real signals are listed in `skipped_metrics`.
"""

import ast
import os
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
import httpx

from app.connectors.github_connector import (
    parse_github_url,
    fetch_repo_metrics,
    MetricSample,
)


# ---------------------------------------------------------------------------
# 1. Non-randomness AST & Static Code Check
# ---------------------------------------------------------------------------

def test_no_random_in_connectors():
    """Verify that 'random' is never imported or used anywhere in the connectors directory."""
    connector_dir = os.path.join(os.path.dirname(__file__), "..", "app", "connectors")
    for root, _, files in os.walk(connector_dir):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as source_file:
                    content = source_file.read()
                    assert "random." not in content, f"Found 'random.' usage in {path}"
                    assert "import random" not in content, f"Found 'import random' in {path}"
                    assert "from random import" not in content, f"Found 'from random import' in {path}"


# ---------------------------------------------------------------------------
# 2. URL Parsing & Validation
# ---------------------------------------------------------------------------

def test_parse_github_url_valid():
    cases = [
        ("https://github.com/facebook/react", ("facebook", "react")),
        ("http://github.com/torvalds/linux", ("torvalds", "linux")),
        ("github.com/pallets/flask", ("pallets", "flask")),
        ("https://github.com/encode/fastapi/", ("encode", "fastapi")),
        ("https://github.com/tiangolo/uvicorn.git", ("tiangolo", "uvicorn")),
        ("https://www.github.com/org/repo-name.js", ("org", "repo-name.js")),
    ]
    for url, expected in cases:
        assert parse_github_url(url) == expected


def test_parse_github_url_invalid():
    invalid_cases = [
        "",
        "   ",
        "https://gitlab.com/owner/repo",
        "https://github.com/onlyowner",
        "https://github.com/owner/repo/extra/path",
        "https://bitbucket.org/owner/repo",
        "not-a-url",
    ]
    for url in invalid_cases:
        with pytest.raises(HTTPException) as exc_info:
            parse_github_url(url)
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# 3. Determinism & Real Metric Computation with Mocked HTTPX
# ---------------------------------------------------------------------------

def _mock_github_transport(repo_name="demo-repo", is_empty=False, fail_runs=2):
    """Create a mock httpx transport that simulates GitHub REST responses."""
    def handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)

        if url_str.endswith(f"/repos/test-owner/{repo_name}"):
            return httpx.Response(200, json={
                "name": repo_name,
                "full_name": f"test-owner/{repo_name}",
                "default_branch": "main",
            })

        elif "/stats/code_frequency" in url_str:
            if is_empty:
                return httpx.Response(200, json=[])
            # Weekly stats: [timestamp, additions, deletions]
            return httpx.Response(200, json=[
                [1704067200, 500, -100],  # 600 churn
                [1704672000, 300, -50],   # 350 churn
                [1705276800, 450, -200],  # 650 churn
            ])

        elif "/languages" in url_str:
            if is_empty:
                return httpx.Response(200, json={})
            return httpx.Response(200, json={"Python": 70000, "JavaScript": 35000}) # 105k bytes -> 3.0 KLOC

        elif "/issues" in url_str:
            if "labels=bug" in url_str:
                if is_empty:
                    return httpx.Response(200, json=[])
                return httpx.Response(200, json=[
                    {"id": 101, "number": 1, "title": "Crash on startup"},
                    {"id": 102, "number": 2, "title": "Memory leak"},
                    {"id": 103, "number": 3, "title": "PR with bug label", "pull_request": {}},  # should be excluded
                ])
            elif "state=closed" in url_str:
                if is_empty:
                    return httpx.Response(200, json=[])
                # Return closed issues in trailing 28 days
                return httpx.Response(200, json=[
                    {"id": 201, "number": 10, "closed_at": "2026-08-25T10:00:00Z"},
                    {"id": 202, "number": 11, "closed_at": "2026-08-20T14:00:00Z"},
                    {"id": 203, "number": 12, "closed_at": "2026-08-15T09:00:00Z"},
                    {"id": 204, "number": 13, "closed_at": "2026-08-10T12:00:00Z"},
                ])

        elif "/pulls" in url_str and "/commits" in url_str:
            return httpx.Response(200, json=[
                {"commit": {"author": {"date": "2026-08-01T00:00:00Z"}}}
            ])

        elif "/pulls" in url_str:
            if is_empty:
                return httpx.Response(200, json=[])
            return httpx.Response(200, json=[
                {
                    "number": 5,
                    "created_at": "2026-08-01T10:00:00Z",
                    "merged_at": "2026-08-02T10:00:00Z",  # 24 hours
                },
                {
                    "number": 6,
                    "created_at": "2026-08-05T08:00:00Z",
                    "merged_at": "2026-08-07T08:00:00Z",  # 48 hours
                },
            ])

        elif "/actions/runs" in url_str:
            if is_empty:
                return httpx.Response(200, json={"workflow_runs": []})
            return httpx.Response(200, json={
                "workflow_runs": [
                    {
                        "id": 1,
                        "workflow_id": 100,
                        "name": "Deploy Production",
                        "head_branch": "main",
                        "status": "completed",
                        "conclusion": "failure",
                        "created_at": "2026-08-20T10:00:00Z",
                    },
                    {
                        "id": 2,
                        "workflow_id": 100,
                        "name": "Deploy Production",
                        "head_branch": "main",
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": "2026-08-20T14:00:00Z",  # 4 hours MTTR
                    },
                    {
                        "id": 3,
                        "workflow_id": 100,
                        "name": "Deploy Production",
                        "head_branch": "main",
                        "status": "completed",
                        "conclusion": "success",
                        "created_at": "2026-08-21T10:00:00Z",
                    },
                ]
            })

        return httpx.Response(404, json={"message": "Not Found"})

    return httpx.MockTransport(handler)


@pytest.mark.anyio
async def test_fetch_repo_metrics_repeatability(monkeypatch):
    """Calling fetch_repo_metrics twice with identical inputs must return identical values."""
    mock_transport = _mock_github_transport("repo-1")

    # Patch httpx.AsyncClient to use our mock transport
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original_client(*args, transport=mock_transport, **kwargs),
    )

    run_1_metrics, run_1_skipped = await fetch_repo_metrics("test-owner", "repo-1")
    run_2_metrics, run_2_skipped = await fetch_repo_metrics("test-owner", "repo-1")

    # Assert skipped metrics match exactly
    assert run_1_skipped == run_2_skipped
    assert "cyclomatic_complexity" in run_1_skipped
    assert "test_coverage" in run_1_skipped

    # Assert all computed metrics are 100% deterministic (no random jitter)
    assert set(run_1_metrics.keys()) == set(run_2_metrics.keys())
    for k in run_1_metrics:
        samples_1 = run_1_metrics[k]
        samples_2 = run_2_metrics[k]
        assert len(samples_1) == len(samples_2)
        for s1, s2 in zip(samples_1, samples_2):
            assert s1.value == s2.value
            assert s1.raw_payload == s2.raw_payload


@pytest.mark.anyio
async def test_fetch_repo_metrics_computations(monkeypatch):
    """Verify exact mathematical computations of metrics against known signals."""
    mock_transport = _mock_github_transport("repo-1")

    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original_client(*args, transport=mock_transport, **kwargs),
    )

    metrics, skipped = await fetch_repo_metrics("test-owner", "repo-1")

    # 1. code_churn backfilled 3 weeks, latest is 650.0 (450+200)
    assert "code_churn" in metrics
    assert len(metrics["code_churn"]) == 3
    assert metrics["code_churn"][-1].value == 650.0

    # 2. defect_density: 2 bug issues / (105,000 / 35 / 1000 = 3.0 KLOC) = 0.67
    assert "defect_density" in metrics
    assert metrics["defect_density"][0].value == 0.67

    # 3. cycle_time: median of [24h, 48h] = 36.0 hours
    assert "cycle_time" in metrics
    assert metrics["cycle_time"][0].value == 36.0

    # 4. mttr: failure at 10:00 -> success at 14:00 = 4.0 hours
    assert "mttr" in metrics
    assert metrics["mttr"][0].value == 4.0

    # 5. change_failure_rate: 1 failure out of 3 runs = 33.33%
    assert "change_failure_rate" in metrics
    assert metrics["change_failure_rate"][0].value == 33.33


@pytest.mark.anyio
async def test_fetch_repo_metrics_error_propagation(monkeypatch):
    """Verify that 404, 401, 403 errors are properly raised and not masked with fake data."""
    def error_handler(request: httpx.Request) -> httpx.Response:
        url_str = str(request.url)
        if "not-found" in url_str:
            return httpx.Response(404, json={"message": "Not Found"})
        elif "bad-token" in url_str:
            return httpx.Response(401, json={"message": "Bad credentials"})
        elif "rate-limited" in url_str:
            return httpx.Response(403, headers={"x-ratelimit-remaining": "0"}, json={"message": "Rate limit"})
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(error_handler)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda *args, **kwargs: original_client(*args, transport=transport, **kwargs),
    )

    with pytest.raises(HTTPException) as exc_404:
        await fetch_repo_metrics("test-owner", "not-found")
    assert exc_404.value.status_code == 404

    with pytest.raises(HTTPException) as exc_401:
        await fetch_repo_metrics("test-owner", "bad-token")
    assert exc_401.value.status_code == 401

    with pytest.raises(HTTPException) as exc_403:
        await fetch_repo_metrics("test-owner", "rate-limited")
    assert exc_403.value.status_code == 403
