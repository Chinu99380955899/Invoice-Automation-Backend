# Architecture

This document explains the architectural choices behind the Invoice
Automation platform and the boundaries that keep it maintainable at scale.

## Design principles

1. **Separation of concerns.** Four backend layers with strict dependencies
   pointing inward:

   ```
   api  →  services  →  db / integrations
               ↑
            agents (pipeline)
   ```

   - **API layer** handles HTTP, auth, validation, and shaping the error
     envelope. It does no business logic.
   - **Service layer** owns domain operations (dedup, status transitions,
     dashboard stats). It's the only layer that writes to the DB.
   - **Agent layer** executes the async pipeline, delegating persistence
     back to services.
   - **Utilities / infrastructure** (storage, circuit breaker, hashing)
     are injected — nothing in the domain code knows whether storage is
     local FS or Azure Blob.

2. **Fail-safe by default.** A bug or upstream outage must never take
   down the service or crash the worker. Every agent returns a uniform
   `AgentResult(success=…)`; the pipeline degrades gracefully (e.g.
   challenger OCR down → route to REVIEW with a single-engine flag).

3. **Idempotency everywhere.** Uploads are keyed by SHA-256 content
   hash; re-uploading the same file is a no-op. Celery tasks are keyed
   by invoice id and can safely be re-run.

4. **No hidden state.** All configuration flows through `pydantic-settings`
   from environment variables. No hardcoded URLs, secrets, or thresholds.

## Status state machine

```
UPLOADED ─► PROCESSING ─► AUTO_APPROVED ─► POSTED
                      │
                      ├─► REVIEW_REQUIRED ─► APPROVED ─► POSTED
                      │                 └─► REJECTED
                      └─► FAILED (retry) ─► PROCESSING
```

Every transition is enforced by `InvoiceService.transition_status` so
the DB can never reach a nonsensical state (e.g. UPLOADED → POSTED).

## Why two OCR engines?

Running Champ (Azure Document Intelligence) **and** Challenger (PaddleOCR)
independently on the same invoice gives us an automated second opinion.
The Validation agent compares outputs field-by-field; agreement above
the threshold with sufficient confidence auto-approves, while any
disagreement routes to a human reviewer with the mismatches highlighted.

Over time, audit data from this dual-engine setup feeds back into
threshold tuning and gives us a credible A/B signal when evaluating new
OCR models — the fundamental reason for naming them "Champ" (incumbent)
and "Challenger" (contender).

## Queueing & back-pressure

- Celery with Redis broker — simple, fast, battle-tested.
- `worker_prefetch_multiplier=1` ensures fair scheduling when tasks
  have highly variable durations (OCR can take 5–30s).
- `worker_max_tasks_per_child=100` recycles workers to bound memory
  growth from PaddleOCR / OpenCV.
- `task_acks_late` + `task_reject_on_worker_lost` guarantees tasks are
  re-queued if a worker dies mid-processing.
- A dedicated **dead-letter queue** (`invoices.dlq`) receives tasks that
  exceed `CELERY_TASK_MAX_RETRIES`; a separate worker logs them to the
  audit trail for human follow-up rather than silently dropping them.

## Why circuit breakers?

Azure DI, SAP, and Salesforce are external services. A 30-second timeout
multiplied by thousands of queued invoices is an outage amplifier.
`pybreaker` wraps each integration so after `fail_max=5` failures the
breaker opens and fast-fails for `reset_timeout=60s` — giving the
upstream time to recover without draining our worker pool.

## Scaling to 40k+ documents

- **Horizontal workers.** `docker compose up --scale worker=N` to add
  parallelism. The bottleneck is usually OCR latency, not the DB.
- **DB indexes.** Composite indexes on `(status, created_at)` and
  `(vendor_name, invoice_number)` keep list queries fast at scale.
- **Streaming uploads.** File hashing uses `sha256_of_stream` so 25 MB
  PDFs never land in RAM twice.
- **Stateless API.** Put N FastAPI containers behind a load balancer;
  JWT means no session affinity required.

## Frontend architecture

- **Vite + React 18 + Redux Toolkit.** Code-split per route + vendor
  chunks for fast TTI.
- **Thin Redux slices** (auth, invoices, ui) — one async thunk per
  backend endpoint; the components only bind to selectors.
- **Axios interceptor** handles JWT attachment, a single refresh-on-401
  (de-duplicated by a shared promise), and toasts for network errors.
- **Error boundary + 404 route** — user never sees a blank screen.
- **Skeleton loaders** on every data-fetching page for perceived
  performance.
- **Design tokens** in `src/styles/index.css` — no component library
  dependency, minimal bundle size, easy to theme.
