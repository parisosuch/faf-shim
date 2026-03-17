# TODO

## Performance / Reliability

- **Cache TTL / expiry** — the slug cache is unbounded and only invalidated on writes; add a TTL to protect against stale data if the DB is modified outside the app
- **Retry logic in `_forward_and_log`** — retry transient forward failures (e.g. 5xx, connection errors) with exponential backoff before writing the error log
- **Dead letter queue** — store permanently failed forwards for later inspection and replay via the API

## Observability

- **Metrics** — expose request counts, forward latency, cache hit/miss rate (e.g. via a `/metrics` endpoint or Prometheus integration)

## Security

- **Rate limiting on `POST /in/{slug}`** — prevent abuse from high-volume or malicious senders
