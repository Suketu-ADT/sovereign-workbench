# 🛡️ Sovereign Workbench — On-Premise Agentic AI Console

<p align="center">
  <img src="https://img.shields.io/badge/Status-Phase_7_Verified-blue?style=for-the-badge&logo=fastapi" alt="Phase 7 Verified" />
  <img src="https://img.shields.io/badge/Audit-SHA--256_Hash_Chain-2ea44f?style=for-the-badge&logo=git" alt="SHA-256 Audit" />
  <img src="https://img.shields.io/badge/Sandbox-Network_Isolated_Docker-0E7C86?style=for-the-badge&logo=docker" alt="Network Isolated Docker Sandbox" />
</p>

> **Confidential Industrial Operations & Multimodal Safety Workbench**  
> An on-premise, defense-in-depth operator console and backend prototype being engineered for high-consequence operational technology (OT) environments. Enables maintenance operators to query technical manuals, analyze visual gauge telemetry, perform deterministic thermodynamic calculations, and trigger physical actuators under strict Human-in-the-Loop (HITL) authorization and cryptographic tamper-proof logging.

---

## 📑 Table of Contents

- [Phased Implementation Roadmap & Current Status](#-phased-implementation-roadmap--current-status)
- [Key Architectural Features](#-key-architectural-features)
- [Visible 8-Stage Defense Pipeline](#-visible-8-stage-defense-pipeline)
- [SCADA Role-Based Access Control (RBAC)](#-scada-role-based-access-control-rbac)
- [Repository Structure](#-repository-structure)
- [Setup & Deployment](#-setup--deployment)
- [Security Architecture & Known Limitations](#-security-architecture--known-limitations)

---

## 🚦 Phased Implementation Roadmap & Current Status

This repository is being built across 8 deliberate engineering phases:

- [x] **Phase 0 — Environment & Repo Foundation**: FastAPI project skeleton, configuration management, automated health check endpoints (`/health`).
- [x] **Phase 1 — Real Auth, RBAC & Server-Side Audit Trail**: Argon2id password hashing, stateless JWT issuance with `role` + `clearance_level`, deterministic plant capability map (L1/L2/L3 equipment checks), per-user token-bucket rate limiter, Alembic database migrations, and concurrency-locked SHA-256 hash-chained audit ledger.
- [x] **Phase 2 — Prompt Guard (Llama-Guard-3)**: Input safety screening layer situated ahead of RBAC with dual-engine deterministic OT injection scanner and local Llama-Guard-3 client.
- [x] **Phase 3 — Real Document Retrieval**: Qdrant vector database with on-premise FastEmbed local embeddings (`BAAI/bge-small-en-v1.5`), clearance-tagged plant SOP manual chunks, zero-leakage vector pre-filtering (`min_clearance <= user_clearance`).
- [x] **Phase 4 — Vision & Sandboxed Calculation**: Local Qwen2.5-VL gauge-reading extraction from photos, and isolated Docker network sandbox for deterministic $\Delta p$ pressure drop calculation.
- [x] **Phase 5 — Planner & Orchestration**: LangGraph state graph reasoning loop with static capability-map allowlist guardrails, `interrupt()` execution on sensitive actuator commands (`open_release_valve`), and operator authorization endpoints.
- [x] **Phase 6 — HITL Streaming & Frontend Rewiring**: Server-Sent Events (`/query/stream`), live human authorization decision endpoints (`/approvals/{id}/decision`).
- [x] **Phase 7 — Comprehensive Security Review & E2E Validation**: Input validation, photo upload safety, dependency audit, and automated end-to-end integration tests (Boiler-102 flows).
- [ ] **Phase 8 — Final Deployment & Production Verification**: *(Active Phase)* Multi-container Docker Compose deployment verification and documentation.

---

## ⚡ Key Architectural Features

- 💬 **Conversational Operator UX**: Chat layout with progressive SSE updates.
- 🔒 **Server-Side Role-Based Access Control**: Physical equipment access is governed dynamically by the authenticated operator's clearance level.
- 🖼️ **Local Model Inference**: Support for local Qwen2.5-VL and Qwen planners.
- 🤝 **Human-in-the-Loop (HITL) Approval**: Actions triggering physical actuators require explicit operator sign-off by an authorized separate user.
- ⛓️ **SHA-256 Tamper-Evident Audit Chain**: Every action commits an immutable block with parent SHA-256 hash linking, exportable to JSON for compliance review.
- 📦 **Network-Isolated Docker Calculation Sandbox**: Deterministic calculations run in a restricted Docker container on an internal network, with CPU/memory limits and read-only filesystem.

---

## 🛡️ Visible 8-Stage Defense Pipeline

1. **Rate Limit Check**: Token bucket algorithm verifies request cadence.
2. **Prompt Safety Check**: Scans for adversarial injections.
3. **SCADA RBAC Verification**: Verifies if the operator's clearance permits querying or controlling the targeted subsystem.
4. **Document Retrieval**: Retrieves role-filtered maintenance manuals locally.
5. **Multimodal Vision Inspection**: Ingests gauge photos and extracts readings.
6. **Network-Isolated Sandboxed Calculation**: Deterministic calculation in a read-only Docker sandbox.
7. **Human Approval (HITL)**: Requires affirmative human confirmation for sensitive actions.
8. **Audit Log Write**: Computes and appends a SHA-256 Merkle-linked block into the permanent tamper-proof ledger.

---

## 👥 SCADA Role-Based Access Control (RBAC)

| Clearance Tier | Operator Title | Permitted Equipment | Restricted Equipment |
| :--- | :--- | :--- | :--- |
| **Level 1** | Maintenance Engineer | `boiler-102`, `pump-201`, `cooling-loop-c3` | `turbine-gen-4`, `reactor-core-aux` |
| **Level 2** | Systems Specialist | `boiler-102`, `pump-201`, `cooling-loop-c3`, `turbine-gen-4`, Compressors | `reactor-core-aux` |
| **Level 3** | Chief Safety Auditor | **All Units** | None |

---

## 📁 Repository Structure

```
.
├── backend/          # FastAPI application, LangGraph planner, RBAC, Auth
├── sandbox/          # Isolated Docker calculation sandbox
├── docker-compose.yml# Multi-container orchestration
├── .env.example      # Environment configuration templates
├── index.html        # Clean semantic HTML5 markup
├── styles.css        # Vanilla CSS3 design system
├── script.js         # Reactive JavaScript application logic
└── README.md         # Documentation
```

---

## 🚀 Setup & Deployment

### 1. Environment Variables
Copy `.env.example` to `.env` and fill in the required cryptographic secrets:
```bash
cp .env.example .env
```
Ensure `JWT_SECRET` is replaced with a strong 64-character hex key, and the default `POSTGRES_PASSWORD` is changed.

### 2. Multi-Container Stack (Docker Compose)
Launch the backend, persistent PostgreSQL storage, Qdrant vector database, Nginx frontend proxy, and isolated calculation sandbox:
```bash
docker compose up -d
```
Access the operator interface at **`http://localhost`** (or `http://localhost:8080`).

### 3. Database / Qdrant Setup
The Docker Compose stack will automatically run Alembic migrations on startup via the backend container. Qdrant will be available internally for the backend to use.

### 4. Testing Commands
To verify the application integrity and run the full 60-test integration and unit test suite:
```bash
pytest backend/app/tests/ -v
```

### 5. Model Requirements
For local inference, you need Ollama running on your host machine (accessible at `http://127.0.0.1:11434` or configured via `.env`):
- `llama-guard3:1b`
- `qwen2.5:7b` (or preferred planner)
- `qwen2.5-vl` (for vision)

*Note: If models are unavailable, the application gracefully degrades to using mock stubs or fails open/closed depending on the security tier.*

---

## 🛡️ Security Architecture & Known Limitations

### Security Architecture
- **Sandbox Isolation**: The calculation engine runs inside `sovereign-sandbox` with `read_only: true`, a `tmpfs` mount for `/tmp`, rigid CPU (`0.1`) and Memory (`64m`) limits, and operates on an `internal: true` Docker network (`sandbox-net`) to prevent outbound data exfiltration.
- **Audit Cryptography**: All lifecycle decisions, RBAC blocks, and HITL approvals are hashed via SHA-256 and linked sequentially in PostgreSQL.
- **Two-Tier Prompt Guard**: Fast deterministic regex checking followed by semantic LLM safety checking.

### Known Limitations
- **Deployment-Level Air-Gap**: While the Docker containers restrict outbound access where configured, a true air-gap requires physical network isolation of the host machine, which this codebase alone cannot enforce.
- **Ollama / Qwen2.5-VL Cold Starts**: In environments without pre-loaded VRAM, initial multimodal inference can exceed standard HTTP timeouts.
- **Dependency Vulnerabilities**: The pinned `requirements.txt` contains dependencies with known CVEs (e.g., `pypdf`, `werkzeug`, `tornado`). A strategic upgrade cycle is necessary before internet-facing deployment.
- **Model Hallucinations**: Local LLMs may still produce unexpected planner reasoning; the application mitigates this by restricting output to strict capability registries, but cannot eliminate LLM non-determinism entirely.
