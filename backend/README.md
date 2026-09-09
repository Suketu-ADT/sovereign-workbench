# Sovereign Workbench — Backend (Phase 0/1)

FastAPI service providing authentication, RBAC, rate limiting, and a
hash-chained audit trail for the Sovereign On-Premise Agentic AI Workbench.

## Quick Start

### Prerequisites
- Docker and Docker Compose

### Run

```bash
cd backend
cp .env.example .env        # Edit JWT_SECRET for production
docker compose up --build
```

The API will be available at **http://localhost:8000**.  
Interactive docs (Swagger UI) at **http://localhost:8000/docs**.

### Seed Accounts

Three demo operators are seeded automatically on first run:

| Name             | Email                        | Role                   | Clearance | Password       |
|-----------------|------------------------------|------------------------|-----------|----------------|
| Suketu Patel     | suketu.2005@gmail.com        | Chief_Safety_Auditor   | Level 3   | `changeme123`  |
| John Morrison    | j.morrison@plant.internal    | Maintenance_Engineer   | Level 1   | `changeme123`  |
| Dr. Elena Vance  | elena.vance@plant.internal   | Systems_Specialist     | Level 2   | `changeme123`  |

## API Endpoints

### Authentication
| Method | Path             | Description                     | Auth     |
|--------|------------------|---------------------------------|----------|
| POST   | `/auth/register` | Register a new operator         | None     |
| POST   | `/auth/login`    | Login, receive JWT              | None     |
| GET    | `/auth/me`       | Get current user profile        | Bearer   |

### Query Pipeline
| Method | Path     | Description                     | Auth     |
|--------|----------|---------------------------------|----------|
| POST   | `/query` | Submit query through pipeline   | Bearer   |

Pipeline steps (each writes an audit entry):
1. **Rate limit** — 60 req / 10 min per user → 429 if exceeded
2. **RBAC check** — clearance vs. capability map → 403 if insufficient
3. **Stub response** — retrieval/vision/calculation are Phases 3-5

### Audit Log
| Method | Path             | Description                     | Auth     |
|--------|------------------|---------------------------------|----------|
| GET    | `/audit`         | List entries (paginated)        | Bearer   |
| GET    | `/audit/verify`  | Verify hash chain integrity     | Bearer   |
| GET    | `/audit/export`  | Export full ledger               | Bearer   |

### System
| Method | Path      | Description         | Auth |
|--------|-----------|---------------------|------|
| GET    | `/health` | Health check        | None |

## RBAC Capability Map

| Unit                | Required Clearance |
|--------------------|--------------------|
| boiler-102          | ≥ 1                |
| pump-201            | ≥ 1                |
| cooling-loop-c3     | ≥ 1                |
| turbine-gen-4       | ≥ 2                |
| compressor          | ≥ 2                |
| reactor-core-aux    | ≥ 3                |

## Environment Variables

| Variable           | Description                    | Default                          |
|-------------------|--------------------------------|----------------------------------|
| `DATABASE_URL`     | Async Postgres connection URL  | `postgresql+asyncpg://...`       |
| `JWT_SECRET`       | JWT signing secret             | ⚠️ Must change in production     |
| `JWT_ALGORITHM`    | JWT algorithm                  | `HS256`                          |
| `JWT_EXPIRE_HOURS` | Token expiry in hours          | `8`                              |
| `SEED_PASSWORD`    | Password for demo operators    | `changeme123`                    |

## Verification

```bash
# Health check
curl http://localhost:8000/health

# Login as Morrison
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"j.morrison@plant.internal","password":"changeme123"}'

# Query turbine (should fail with 403 for Morrison)
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{"text":"check turbine-gen-4 status"}'

# Verify audit chain
curl -H "Authorization: Bearer <TOKEN>" \
  http://localhost:8000/audit/verify
```
