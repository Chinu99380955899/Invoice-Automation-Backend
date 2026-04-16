# Invoice Automation Platform

A **production-grade**, scalable invoice processing platform that ingests invoice
documents, extracts structured data with dual OCR engines, validates
confidence and business rules, and either auto-approves or sends the invoice
to a human reviewer before posting to downstream systems (SAP / Salesforce).

Designed to process **40,000+ documents/day** with fault-tolerant async
pipelines, circuit breakers, and graceful degradation — never crashes on
bad input or upstream outages.

---

## Architecture overview

```
┌──────────────┐  upload   ┌─────────────────┐      ┌──────────────┐
│  React SPA   │──────────▶│  FastAPI (API)  │─────▶│  PostgreSQL  │
└──────────────┘           │                 │◀────▶│              │
        ▲                  │   JWT · CORS    │      └──────────────┘
        │ SSE/polling      │   Prometheus    │
        │                  └────────┬────────┘
        │                           │ publishes task
        │                           ▼
        │                  ┌─────────────────┐      ┌──────────────┐
        │                  │  Redis (broker) │◀────▶│ Celery Worker│
        │                  └─────────────────┘      │  (pipeline)  │
        │                                           └──────┬───────┘
        │                                                  │
        │                       ┌──────────────────────────┼─────────────┐
        │                       ▼                          ▼             ▼
        │            ┌─────────────────┐    ┌──────────────────┐   ┌─────────┐
        │            │ Preprocessing   │    │ Champ (Azure DI) │   │ SAP/SF  │
        │            │ (OpenCV)        │    │ + Challenger     │   │ posting │
        │            └─────────────────┘    │ (PaddleOCR)      │   └─────────┘
        │                                   │ + Validation     │
        │                                   └──────────────────┘
        │
        └─────────────── reviewer UI, status updates, audit trail
```

### Agent pipeline (5 stages)

| # | Agent                      | Responsibility                                      |
|---|----------------------------|-----------------------------------------------------|
| 1 | **Preprocessing**          | Rasterize PDFs, denoise, deskew, CLAHE enhance     |
| 2 | **Champ OCR** (Azure DI)   | Prebuilt-invoice model, structured fields & items  |
| 3 | **Challenger OCR** (Paddle)| Independent extraction via OCR + regex            |
| 4 | **Validation**             | Compare outputs, run math check, decide status    |
| 5 | **Integration**            | Salesforce vendor/PO validation + SAP final post  |

Every agent returns a uniform `AgentResult` with `success`, timing, and
error info — a failure in one agent **never** crashes the pipeline, it
degrades gracefully and the invoice is routed to review.

---

## Repository layout

```
invoice/
├── backend/                    FastAPI application
│   ├── app/
│   │   ├── api/                HTTP routes + middleware + exception handlers
│   │   │   ├── v1/             Versioned endpoints (auth, invoices, review, health)
│   │   │   ├── deps.py         Auth & DB dependencies
│   │   │   ├── middleware.py   Request ID, logging context
│   │   │   └── exception_handlers.py
│   │   ├── agents/             5-stage processing pipeline
│   │   ├── core/               Config, logging, security
│   │   ├── db/                 SQLAlchemy models + session
│   │   ├── schemas/            Pydantic DTOs
│   │   ├── services/           Business logic (user, invoice, storage)
│   │   ├── utils/              Exceptions, circuit breaker, hashing
│   │   ├── workers/            Celery app + tasks + DLQ
│   │   └── main.py             ASGI app factory
│   ├── alembic/                Migrations
│   ├── scripts/                Seed sample data
│   ├── tests/                  pytest suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                   React + Vite + Redux Toolkit
│   ├── src/
│   │   ├── components/         Layout + common + invoice widgets
│   │   ├── pages/              Dashboard, List, Detail, Review, Login, 404
│   │   ├── services/api.js     Axios client w/ JWT refresh
│   │   ├── store/              Redux slices (auth, invoices, ui)
│   │   └── styles/             Design-system CSS
│   ├── Dockerfile              Multi-stage → nginx
│   └── nginx.conf              SPA + API reverse proxy
└── docker-compose.yml          Full stack (pg + redis + api + workers + UI)
```

---

## Quickstart — Docker

```bash
cp .env.example .env
cp backend/.env.example backend/.env

docker compose up --build
```

Services:

- **UI**: http://localhost:3000
- **API docs**: http://localhost:8000/docs
- **Flower (Celery UI)**: http://localhost:5555
- **Prometheus metrics**: http://localhost:8000/metrics

Default dev admin user (auto-seeded):

```
email:    admin@invoice.local
password: Admin@12345
```

### Seed sample invoices

```bash
docker compose exec backend python -m scripts.seed_sample_data
```

---

## Quickstart — local (no Docker)

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Postgres + Redis must be running locally
alembic upgrade head
uvicorn app.main:app --reload

# In a second shell:
celery -A app.workers.celery_app.celery_app worker --loglevel=info -Q invoices
celery -A app.workers.celery_app.celery_app worker --loglevel=info -Q invoices.dlq
```

### Frontend

```bash
cd frontend
cp .env.example .env
npm install
npm run dev                  # http://localhost:5173
```

---

## API surface

All endpoints are under `/api/v1`. Full interactive docs at `/docs`.

| Method | Path                               | Purpose                          |
|--------|------------------------------------|----------------------------------|
| POST   | `/auth/register`                   | Create a user                    |
| POST   | `/auth/login`                      | Exchange credentials for JWT     |
| POST   | `/auth/refresh`                    | Refresh access token             |
| GET    | `/auth/me`                         | Current user                     |
| POST   | `/invoices/upload`                 | Upload an invoice (multipart)    |
| GET    | `/invoices`                        | Paginated list + filters         |
| GET    | `/invoices/{id}`                   | Full detail incl. logs & OCR A/B |
| GET    | `/invoices/stats`                  | Dashboard aggregates             |
| POST   | `/review/{id}/action`              | APPROVE / REJECT / REPROCESS     |
| GET    | `/health`, `/ready`, `/metrics`    | Ops endpoints                    |

Every error response uses a consistent JSON envelope:

```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": { "errors": [...] },
  "request_id": "b4e1f6ac...",
  "timestamp": "2026-04-16T10:02:47Z"
}
```

---

## Production-readiness features

| Concern                | Implementation                                                 |
|------------------------|----------------------------------------------------------------|
| Scalability            | Celery workers scale horizontally; stateless API; pooled DB    |
| Fault tolerance        | Retries with exponential backoff, DLQ for terminal failures   |
| Never crashes          | Global exception handler + `BaseAgent.execute` wraps errors   |
| Idempotency            | SHA-256 file hash prevents duplicate uploads                  |
| Circuit breakers       | `pybreaker` around Azure DI, SAP, Salesforce                   |
| Rate limiting          | Upload size + extension whitelist + Celery prefetch=1          |
| Graceful OCR degradation | Validation agent tolerates a missing engine                   |
| Observability          | Structured JSON logs (`structlog`), Prometheus, Flower         |
| Security               | JWT access/refresh, bcrypt, CORS allowlist, path-traversal guards |
| ACID                   | PostgreSQL with constraints, status-machine enforcement        |
| Audit trail            | `processing_logs` appended every stage, reviewer tracking      |
| Config                 | All env-driven via `pydantic-settings`; no hardcoded values    |
| Containerization       | Multi-stage Dockerfiles; non-root runtime user; healthchecks   |

---

## Configuration

All behaviour is environment-driven. Key toggles (see `backend/.env.example`):

| Variable                    | Purpose                                        |
|-----------------------------|------------------------------------------------|
| `USE_MOCK_AZURE_OCR`        | Deterministic mock instead of calling Azure DI |
| `USE_MOCK_PADDLE_OCR`       | Use mock instead of running PaddleOCR          |
| `USE_MOCK_INTEGRATIONS`     | Mock SAP/Salesforce (default in dev)           |
| `STORAGE_BACKEND`           | `local` or `azure`                             |
| `CELERY_TASK_MAX_RETRIES`   | Per-task retry ceiling before DLQ             |
| `CONFIDENCE_THRESHOLD`      | Auto-approval floor                            |
| `FIELD_MATCH_THRESHOLD`     | Champ/Challenger agreement ratio floor        |
| `AMOUNT_TOLERANCE`          | Fractional tolerance for totals comparison     |

---

## Testing

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

The backend suite covers:

- Health & readiness probes
- Auth flow (register → login → `me`, bad password, missing token)
- Security primitives (bcrypt, JWT round-trip, tampered tokens)
- Storage backend (round-trip, path-traversal rejection)
- Invoice service (dedup, status machine, filters)
- Validation agent (auto-approve, mismatch, one-engine-down, math check)

---

## Workflow

1. User uploads invoice in the UI.
2. API validates extension/size, stores the file (hash-keyed for dedup), and
   enqueues a Celery task.
3. Worker runs preprocessing → Champ & Challenger OCR → validation.
4. If `AUTO_APPROVED`, Salesforce vendor check runs and the invoice is
   auto-posted to SAP.
5. If `REVIEW_REQUIRED`, the reviewer opens the detail page and sees
   side-by-side Champ vs Challenger output with highlighted mismatches.
   They can edit fields and Approve / Reject / Reprocess.
6. Approved invoices post to SAP; rejected ones close out with an audit entry.

---

## License

MIT
