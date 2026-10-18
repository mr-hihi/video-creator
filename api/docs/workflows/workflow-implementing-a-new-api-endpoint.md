# Workflow — implementing an API endpoint

Template: [template-api-endpoint.md](../templates/template-api-endpoint.md).

1. Service method first: rules + domain errors, no HTTP types.
2. Route in `router.py`: parse input, call one service method, wrap the result in a response DTO. Nothing else.
3. New error → add its class to `errors.py` and its status to `STATUS_CODES_BY_ERROR` in `http_errors.py`.
4. Public mutation (anything a stranger could spam) → `dependencies=[Depends(require_captcha)]`.
5. Tests: service unit tests + a `TestClient` test for status code, JSON shape and error mapping.
6. Contract moved → update [../../../docs/dependency-graph.md](../../../docs/dependency-graph.md) and the frontend types in the same change.
