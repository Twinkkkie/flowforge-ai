import pytest

from app.services.workflow_validator import WorkflowValidationError, validate_workflow


def test_validate_workflow_returns_topological_order() -> None:
    definition = {
        "nodes": [
            {"id": "a", "type": "transform", "config": {}},
            {"id": "b", "type": "condition", "config": {}},
            {"id": "c", "type": "transform", "config": {}},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "c"},
        ],
    }

    assert validate_workflow(definition) == ["a", "b", "c"]


def test_validate_workflow_rejects_cycles() -> None:
    definition = {
        "nodes": [
            {"id": "a", "type": "transform"},
            {"id": "b", "type": "transform"},
        ],
        "edges": [
            {"from": "a", "to": "b"},
            {"from": "b", "to": "a"},
        ],
    }

    with pytest.raises(WorkflowValidationError, match="acyclic"):
        validate_workflow(definition)
