from prometheus_client import Counter, Histogram

HTTP_REQUESTS = Counter(
    "flowforge_http_requests_total",
    "HTTP requests processed",
    ["method", "path", "status"],
)
HTTP_LATENCY = Histogram(
    "flowforge_http_request_duration_seconds",
    "HTTP request latency",
    ["method", "path"],
)
EXECUTIONS = Counter(
    "flowforge_executions_total",
    "Workflow executions",
    ["trigger", "status"],
)
