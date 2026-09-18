import pytest

from app.engine.runner import run_workflow


@pytest.mark.asyncio
async def test_engine_runs_only_matching_condition_branch() -> None:
    definition = {
        "nodes": [
            {
                "id": "prepare",
                "type": "transform",
                "config": {"set": {"score": "{{input.score}}"}},
            },
            {
                "id": "decide",
                "type": "condition",
                "config": {
                    "path": "steps.prepare.values.score",
                    "operator": "gte",
                    "value": 80,
                },
            },
            {
                "id": "accepted",
                "type": "transform",
                "config": {"set": {"decision": "accepted"}},
            },
            {
                "id": "rejected",
                "type": "transform",
                "config": {"set": {"decision": "rejected"}},
            },
        ],
        "edges": [
            {"from": "prepare", "to": "decide"},
            {"from": "decide", "to": "accepted", "when": "true"},
            {"from": "decide", "to": "rejected", "when": "false"},
        ],
    }

    result = await run_workflow(definition, {"score": 92})

    assert result.output["prepare"]["values"]["score"] == 92
    assert result.output["decide"]["branch"] == "true"
    assert result.output["accepted"]["values"]["decision"] == "accepted"
    assert "rejected" not in result.output
    skipped = [item for item in result.outcomes if item.node_id == "rejected"][0]
    assert skipped.status == "skipped"
