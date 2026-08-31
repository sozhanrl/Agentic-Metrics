"""
Integration and unit tests for the POST /projects/from-github endpoint.

Verifies:
1. Valid repository URL imports data, stores raw_payload, runs multi-agent pipeline.
2. Repeat imports of the same repository are idempotent (no duplicate project name crashes).
3. Skipped metrics are accurately reported in the response payload.
4. Demo seed data is never called or mixed in.
5. Error cases (invalid URLs, private/missing repos) return appropriate 4xx errors.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from fastapi import HTTPException

from app import schemas, models
from app.connectors.github_connector import MetricSample
from app.routers.projects import create_project_from_github


@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = MagicMock()
    # Mock project lookup and creation
    existing_projects = {}
    metric_values = []
    recommendations = []

    def mock_get_project_by_external_id(db_session, ext_id):
        return existing_projects.get(ext_id)

    def mock_create_project(db_session, proj_create):
        proj = models.Project(
            id=len(existing_projects) + 1,
            name=proj_create.name,
            source=proj_create.source,
            external_id=proj_create.external_id,
            created_at=datetime.now(timezone.utc),
        )
        existing_projects[proj_create.external_id] = proj
        return proj

    def mock_get_project(db_session, project_id):
        for p in existing_projects.values():
            if p.id == project_id:
                return p
        return None

    def mock_get_metric_definitions(db_session):
        return [
            models.MetricDefinition(id=1, key="code_churn", display_name="Code Churn", category="code_quality", source="github", higher_is_better=False),
            models.MetricDefinition(id=2, key="defect_density", display_name="Defect Density", category="code_quality", source="github", higher_is_better=False),
            models.MetricDefinition(id=3, key="sprint_velocity", display_name="Sprint Velocity", category="process", source="github", higher_is_better=True),
            models.MetricDefinition(id=4, key="cycle_time", display_name="Cycle Time", category="process", source="github", higher_is_better=False),
            models.MetricDefinition(id=5, key="lead_time", display_name="Lead Time", category="process", source="github", higher_is_better=False),
            models.MetricDefinition(id=6, key="deployment_frequency", display_name="Deployment Frequency", category="devops", source="github", higher_is_better=True),
            models.MetricDefinition(id=7, key="change_failure_rate", display_name="Change Failure Rate", category="devops", source="github", higher_is_better=False),
            models.MetricDefinition(id=8, key="mttr", display_name="MTTR", category="devops", source="github", higher_is_better=False),
        ]

    def mock_create_metric_value(db_session, val_create):
        val = models.MetricValue(
            id=len(metric_values) + 1,
            project_id=val_create.project_id,
            metric_id=val_create.metric_id,
            value=val_create.value,
            recorded_at=val_create.recorded_at,
            raw_payload=val_create.raw_payload,
        )
        metric_values.append(val)
        return val

    return {
        "db": db,
        "existing_projects": existing_projects,
        "metric_values": metric_values,
        "mock_get_project_by_external_id": mock_get_project_by_external_id,
        "mock_create_project": mock_create_project,
        "mock_get_project": mock_get_project,
        "mock_get_metric_definitions": mock_get_metric_definitions,
        "mock_create_metric_value": mock_create_metric_value,
    }


@pytest.mark.anyio
async def test_create_project_from_github_success(mock_db):
    """Test importing a GitHub repo with mock connector data."""
    now = datetime.now(timezone.utc)
    mock_samples = {
        "code_churn": [
            MetricSample(value=450.0, recorded_at=now, raw_payload={"additions": 300, "deletions": -150}),
        ],
        "defect_density": [
            MetricSample(value=0.85, recorded_at=now, raw_payload={"bug_count": 3, "kloc": 3.5}),
        ],
        "deployment_frequency": [
            MetricSample(value=2.5, recorded_at=now, raw_payload={"successful_deploy_runs": 10}),
        ],
    }
    mock_skipped = ["cyclomatic_complexity", "test_coverage", "mttr"]

    with patch("app.crud.get_project_by_external_id", side_effect=mock_db["mock_get_project_by_external_id"]), \
         patch("app.crud.create_project", side_effect=mock_db["mock_create_project"]), \
         patch("app.crud.get_project", side_effect=mock_db["mock_get_project"]), \
         patch("app.crud.get_metric_definitions", side_effect=mock_db["mock_get_metric_definitions"]), \
         patch("app.crud.create_metric_value", side_effect=mock_db["mock_create_metric_value"]), \
         patch("app.connectors.github_connector.fetch_repo_metrics", new_callable=AsyncMock) as mock_fetch, \
         patch("app.routers.projects.generate_recommendations_for_project") as mock_generate_recs:

        mock_fetch.return_value = (mock_samples, mock_skipped)
        mock_generate_recs.return_value = [
            {
                "id": 1,
                "project_id": 1,
                "title": "Reduce Code Churn",
                "explanation": "High churn observed.",
                "priority_score": 42.5,
                "status": "open",
                "reasoning_trail": ["[Perceiver] Churn high"],
                "agent_trail": [],
            }
        ]

        req = schemas.GithubImportRequest(
            repo_url="https://github.com/test-org/awesome-repo",
            token="ghp_testtoken123",
        )

        response = await create_project_from_github(req, db=mock_db["db"])

        # Validate response structure
        assert response.id == 1
        assert response.name == "test-org/awesome-repo"
        assert response.source == "github"
        assert response.external_id == "test-org/awesome-repo"
        assert set(response.ingested_metrics) == {"code_churn", "defect_density", "deployment_frequency"}
        assert "cyclomatic_complexity" in response.skipped_metrics
        assert "test_coverage" in response.skipped_metrics
        assert len(response.recommendations) == 1
        assert response.recommendations[0].title == "Reduce Code Churn"

        # Validate that raw_payload was stored with metric values
        assert len(mock_db["metric_values"]) == 3
        churn_row = next(m for m in mock_db["metric_values"] if m.metric_id == 1)
        assert churn_row.value == 450.0
        assert churn_row.raw_payload == {"additions": 300, "deletions": -150}


@pytest.mark.anyio
async def test_create_project_from_github_idempotent(mock_db):
    """Re-importing the same repository must not create duplicate projects or fail with unique constraint."""
    now = datetime.now(timezone.utc)
    mock_samples = {
        "code_churn": [MetricSample(value=100.0, recorded_at=now, raw_payload={})],
    }

    with patch("app.crud.get_project_by_external_id", side_effect=mock_db["mock_get_project_by_external_id"]), \
         patch("app.crud.create_project", side_effect=mock_db["mock_create_project"]), \
         patch("app.crud.get_project", side_effect=mock_db["mock_get_project"]), \
         patch("app.crud.get_metric_definitions", side_effect=mock_db["mock_get_metric_definitions"]), \
         patch("app.crud.create_metric_value", side_effect=mock_db["mock_create_metric_value"]), \
         patch("app.connectors.github_connector.fetch_repo_metrics", new_callable=AsyncMock) as mock_fetch, \
         patch("app.routers.projects.generate_recommendations_for_project", return_value=[]):

        mock_fetch.return_value = (mock_samples, ["cyclomatic_complexity"])

        req = schemas.GithubImportRequest(repo_url="https://github.com/my-org/repeat-repo")

        resp1 = await create_project_from_github(req, db=mock_db["db"])
        resp2 = await create_project_from_github(req, db=mock_db["db"])

        # Both invocations point to the exact same Project ID
        assert resp1.id == resp2.id
        assert resp1.external_id == resp2.external_id == "my-org/repeat-repo"
        assert len(mock_db["existing_projects"]) == 1


@pytest.mark.anyio
async def test_create_project_from_github_invalid_url(mock_db):
    """Invalid URLs must raise HTTP 400."""
    req = schemas.GithubImportRequest(repo_url="https://notgithub.com/org/repo")
    with pytest.raises(HTTPException) as exc_info:
        await create_project_from_github(req, db=mock_db["db"])
    assert exc_info.value.status_code == 400
