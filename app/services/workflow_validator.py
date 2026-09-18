import hashlib
import json
from collections import defaultdict, deque


ALLOWED_NODE_TYPES = {"transform", "condition", "http", "ai"}


class WorkflowValidationError(ValueError):
    pass


def canonical_checksum(definition: dict) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(canonical).hexdigest()


def validate_workflow(definition: dict) -> list[str]:
    nodes = definition.get("nodes")
    edges = definition.get("edges", [])

    if not isinstance(nodes, list) or not nodes:
        raise WorkflowValidationError("Workflow requires a non-empty nodes list")
    if not isinstance(edges, list):
        raise WorkflowValidationError("edges must be a list")

    node_ids: set[str] = set()
    for node in nodes:
        node_id = node.get("id")
        node_type = node.get("type")
        if not node_id or not isinstance(node_id, str):
            raise WorkflowValidationError("Every node requires a string id")
        if node_id in node_ids:
            raise WorkflowValidationError(f"Duplicate node id: {node_id}")
        if node_type not in ALLOWED_NODE_TYPES:
            raise WorkflowValidationError(f"Unsupported node type: {node_type}")
        node_ids.add(node_id)

    indegree = {node_id: 0 for node_id in node_ids}
    outgoing: dict[str, list[str]] = defaultdict(list)

    for edge in edges:
        source = edge.get("from")
        target = edge.get("to")
        if source not in node_ids or target not in node_ids:
            raise WorkflowValidationError("Every edge must reference existing nodes")
        outgoing[source].append(target)
        indegree[target] += 1

    queue = deque([node_id for node_id, degree in indegree.items() if degree == 0])
    order: list[str] = []
    while queue:
        current = queue.popleft()
        order.append(current)
        for target in outgoing[current]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)

    if len(order) != len(node_ids):
        raise WorkflowValidationError("Workflow graph must be acyclic")

    return order
