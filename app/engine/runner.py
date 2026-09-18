import asyncio
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any

from app.engine.nodes import NODE_HANDLERS
from app.services.workflow_validator import validate_workflow


@dataclass
class NodeOutcome:
    node_id: str
    node_type: str
    status: str
    attempt: int
    input_data: dict
    output_data: dict | None = None
    error: str | None = None
    duration_ms: int | None = None


@dataclass
class WorkflowRunResult:
    output: dict[str, Any]
    outcomes: list[NodeOutcome] = field(default_factory=list)


class WorkflowExecutionError(RuntimeError):
    def __init__(self, node_id: str, outcomes: list[NodeOutcome], cause: Exception):
        super().__init__(f"Node {node_id} failed: {cause}")
        self.node_id = node_id
        self.outcomes = outcomes
        self.cause = cause


def _edge_is_active(edge: dict, source_output: dict | None) -> bool:
    condition = edge.get("when")
    if condition is None:
        return True
    if source_output is None:
        return False
    return str(source_output.get("branch")).lower() == str(condition).lower()


async def _execute_with_retry(
    node: dict,
    context: dict,
) -> tuple[dict, int, int]:
    handler = NODE_HANDLERS[node["type"]]
    retries = max(0, min(int(node.get("retries", 0)), 5))
    backoff = max(0.05, min(float(node.get("retry_backoff_seconds", 0.25)), 10.0))
    last_error: Exception | None = None

    for attempt in range(1, retries + 2):
        started = perf_counter()
        try:
            output = await handler(node.get("config", {}), context)
            duration_ms = int((perf_counter() - started) * 1000)
            return output, attempt, duration_ms
        except Exception as exc:
            last_error = exc
            if attempt <= retries:
                await asyncio.sleep(backoff * (2 ** (attempt - 1)))

    assert last_error is not None
    raise last_error


async def run_workflow(definition: dict, input_data: dict) -> WorkflowRunResult:
    order = validate_workflow(definition)
    nodes = {node["id"]: node for node in definition["nodes"]}
    edges = definition.get("edges", [])
    incoming: dict[str, list[dict]] = {node_id: [] for node_id in nodes}
    for edge in edges:
        incoming[edge["to"]].append(edge)

    context: dict[str, Any] = {"input": input_data, "steps": {}}
    outcomes: list[NodeOutcome] = []

    for node_id in order:
        node = nodes[node_id]
        predecessors = incoming[node_id]

        if predecessors:
            should_run = any(
                edge["from"] in context["steps"]
                and _edge_is_active(edge, context["steps"].get(edge["from"]))
                for edge in predecessors
            )
            if not should_run:
                outcomes.append(
                    NodeOutcome(
                        node_id=node_id,
                        node_type=node["type"],
                        status="skipped",
                        attempt=0,
                        input_data={},
                    )
                )
                continue

        try:
            output, attempt, duration_ms = await _execute_with_retry(node, context)
        except Exception as exc:
            outcomes.append(
                NodeOutcome(
                    node_id=node_id,
                    node_type=node["type"],
                    status="failed",
                    attempt=max(1, int(node.get("retries", 0)) + 1),
                    input_data={"context": context},
                    error=str(exc),
                )
            )
            raise WorkflowExecutionError(node_id, outcomes, exc) from exc

        context["steps"][node_id] = output
        outcomes.append(
            NodeOutcome(
                node_id=node_id,
                node_type=node["type"],
                status="succeeded",
                attempt=attempt,
                input_data={"config": node.get("config", {})},
                output_data=output,
                duration_ms=duration_ms,
            )
        )

    return WorkflowRunResult(output=context["steps"], outcomes=outcomes)
