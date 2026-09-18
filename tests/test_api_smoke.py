from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_auth_org_workflow_versioning_smoke() -> None:
    email = f"alina-{uuid4()}@example.com"
    password = "portfolio-password-123"

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        registered = await client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
        )
        assert registered.status_code == 201

        logged_in = await client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": password},
        )
        assert logged_in.status_code == 200
        headers = {"Authorization": f"Bearer {logged_in.json()['access_token']}"}

        org = await client.post(
            "/api/v1/organizations",
            json={"name": "Portfolio Org"},
            headers=headers,
        )
        assert org.status_code == 201
        org_id = org.json()["id"]

        workflow = await client.post(
            f"/api/v1/organizations/{org_id}/workflows",
            json={"name": "Lead Triage"},
            headers=headers,
        )
        assert workflow.status_code == 201
        workflow_id = workflow.json()["id"]

        definition = {
            "nodes": [
                {
                    "id": "prepare",
                    "type": "transform",
                    "config": {"set": {"lead": "{{input.name}}"}},
                },
                {
                    "id": "classify",
                    "type": "condition",
                    "config": {"path": "input.score", "operator": "gte", "value": 80},
                },
            ],
            "edges": [{"from": "prepare", "to": "classify"}],
        }
        version = await client.post(
            f"/api/v1/workflows/{workflow_id}/versions",
            json={"definition": definition},
            headers=headers,
        )
        assert version.status_code == 201
        assert version.json()["version"] == 1

        activated = await client.post(
            f"/api/v1/workflows/{workflow_id}/versions/1/activate",
            headers=headers,
        )
        assert activated.status_code == 200
        assert activated.json()["active_version"] == 1

        secret = await client.post(
            f"/api/v1/organizations/{org_id}/secrets",
            json={"name": "CRM_TOKEN", "value": "super-secret-value"},
            headers=headers,
        )
        assert secret.status_code == 201
        assert "value" not in secret.json()
