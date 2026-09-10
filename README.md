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
To verify the application integrity and run the full test suite:
```bash
# Run model routing & sovereign mode test suite (7 tests)
pytest backend/app/tests/test_model_routing.py -v

# Run entire integration test suite
pytest backend/app/tests/ -v
```

### 5. Model Requirements
For local inference, you need Ollama or vLLM running on your host machine (accessible at `http://127.0.0.1:11434` or configured via `.env`):
- `llama-guard3:1b`
- `qwen2.5:7b` (or preferred planner)
- `qwen2.5-vl` (for vision)
- `deepseek-coder-v2` (for local sovereign coding)

*Note: If local model servers are offline during development or test execution, the application gracefully degrades to deterministic safety synthesizers.*

---

## 🤖 Multi-Model Routing & Sovereign AI Architecture

> [!IMPORTANT]
> **Hugging Face Inference Providers are used ONLY for development/testing.**  
> **They are NOT part of the final air-gapped sovereign deployment.**  
> **In production Sovereign Mode, all AI inference must run locally.**

The Sovereign Workbench features an autonomous multi-model routing layer that inspects incoming queries and dispatches them to specialized neural models or deterministic engines according to task domain and air-gap policy.

```text
React Frontend (Operator Console)
       ↓
FastAPI Backend (/api/ai/query)
       ↓
Prompt Guard (Llama-Guard-3 + Regex Scanner)
       ↓
Task Classifier (Deterministic Pattern & Domain Extractor)
       ↓
Model Router (Config-Driven Registry & Sovereign Policy)
       ↓
Provider Abstraction Layer (ModelProvider)
       ┌───────────────────────────┬───────────────────────────┐
       │ Hugging Face Provider     │ Local Model Provider      │
       │ (Development / Testing)   │ (Ollama / vLLM / Air-Gap) │
       └───────────────────────────┴───────────────────────────┘
       ↓
LangGraph Agent / Coding Agent
       ↓
Network-Isolated Docker Sandbox (/execute, /calculate)
       ↓
Immutable SHA-256 Hash-Chained Audit Ledger
```

### 1. Model Architecture
- **Provider-Independent Abstraction**: The backend interacts exclusively via `ModelProvider` abstract base classes (`HuggingFaceProvider` and `LocalProvider` in `app/services/model_provider.py`). The core agent, LangGraph planner, and UI are completely decoupled from external vendor SDKs.
- **Backend Isolation**: The React frontend **never** communicates with model APIs directly. All model communications originate from the hardened FastAPI backend.
- **Zero-Trust Token Management**: Model API tokens (`HF_TOKEN`) are never sent to the browser, never returned in health/status responses, and sanitized through strict regex pattern redaction before committing to logs or audit blocks.

### 2. Model Routing Logic
The model router (`app/services/model_router.py`) maps user requests to specialized models via `select_model(task_type)`:

| Task Type | Target Model | Default Provider (Dev) | Sovereign Mode (Air-Gap) | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Coding / Debugging** | `deepseek-ai/DeepSeek-Coder-V2-Instruct` | Hugging Face | Local (vLLM / Ollama) | Code synthesis, script debugging, unit test creation |
| **Vision / OCR** | `qwen2.5-vl` | Local | Local (Ollama) | Dial gauge reading, valve position, visual telemetry |
| **Document / Reasoning / Planning** | `qwen/qwen2.5-32b-instruct` | Hugging Face | Local (Ollama) | Manual analysis, multi-step maintenance planning |
| **Calculation** | Deterministic Sandbox Tool | Local Sandbox | Local Sandbox | Thermodynamic calculations, $\Delta p$ pressure drop |

### 3. Hugging Face Development Setup
During development, the workbench uses Hugging Face's OpenAI-compatible router (`https://router.huggingface.co/v1`) to access cutting-edge open weights models without local GPU overhead.

1. Obtain an API token from [Hugging Face Settings](https://huggingface.co/settings/tokens).
2. Configure `.env`:
```env
HF_TOKEN=hf_your_token_here
HF_BASE_URL=https://router.huggingface.co/v1
```
The OpenAI Python SDK is utilized under the hood (`app/services/huggingface_client.py`) with comprehensive timeout, logging, and token redaction guardrails.

### 4. Environment Configuration (`.env`)
```env
# Development Model Provider
HF_TOKEN=hf_your_token_here
HF_BASE_URL=https://router.huggingface.co/v1

# Sovereign Air-Gapped Deployment Flag
SOVEREIGN_MODE=false

# Local Model Server (Ollama / vLLM / LocalAI)
LOCAL_MODEL_BASE_URL=http://localhost:8000/v1
PLANNER_MODEL_URL=http://127.0.0.1:11434
VISION_MODEL_URL=http://127.0.0.1:11434

# Sandbox URL
SANDBOX_URL=http://sandbox:8080
```

### 5. Running the Coding Model & Agent Workflow
When a coding task is dispatched, the autonomous `CodingAgentService` (`app/services/coding_agent_service.py`) executes a closed-loop generation and verification cycle:

```text
User coding request
       ↓
Task classification (coding)
       ↓
DeepSeek-Coder-V2 selected
       ↓
Generate code via Provider
       ↓
Save code to temporary workspace
       ↓
Execute inside Docker sandbox (POST /execute)
       ↓
Validate exit code & stderr
       ├── If Success → Return verified code + execution output
       └── If Failure → Send error traceback back to Coding Model
                            ↓
                        Generate corrected code (Self-Healing Retry Loop)
                            ↓
                        Maximum retry limit (default: 3)
```

### 6. Sandbox Security Controls
All Python code execution occurs inside the `sovereign-sandbox` Docker container with rigorous defense-in-depth isolation:
- **Read-Only Root Filesystem**: The root filesystem is mounted read-only (`read_only: true`).
- **Tmpfs Workspace**: Ephemeral scripts are executed strictly in `/tmp` using in-memory tmpfs.
- **Resource Constraints**: Capped at `0.1` CPU cores and `64MB` RAM to prevent denial-of-service.
- **Network Isolation**: The sandbox container operates on an internal Docker bridge network (`sandbox-net`) with default gateway disabled to prevent data exfiltration.
- **Non-Root Execution**: Runs as unprivileged UID `1001`.

### 7. Sovereign Mode (Air-Gap Enforcement)
To enforce strict air-gap compliance:
```env
SOVEREIGN_MODE=true
```
When `SOVEREIGN_MODE=true`:
- All external cloud providers (Hugging Face, OpenRouter, etc.) are **hard blocked** at the provider abstraction layer (`app/services/model_provider.py`).
- Attempting to route to an external provider raises a `PermissionError` (HTTP 403) with the message:
  ```
  External AI providers are disabled in Sovereign Mode. Use a local model provider.
  ```
- The Model Router automatically redirects requests to local models running on on-premise infrastructure (Ollama or vLLM).

### 8. Local Model Migration (Production Air-Gap)
To transition from development to a fully air-gapped sovereign production deployment:
1. Deploy Ollama or vLLM on an on-premise GPU workstation.
2. Pull the local equivalents:
   ```bash
   ollama pull deepseek-coder-v2:16b
   ollama pull qwen2.5:32b
   ollama pull qwen2.5-vl
   ```
3. Update production configuration:
   ```env
   SOVEREIGN_MODE=true
   LOCAL_MODEL_BASE_URL=http://127.0.0.1:11434/v1
   ```
4. No backend or frontend code changes are required; the configuration-driven model registry handles the provider swap seamlessly.

### 9. Security & Auditing Considerations
- **Cryptographic Audit Ledger**: Every model routing event is appended to the PostgreSQL SHA-256 hash-chained audit ledger with action `MODEL_ROUTER`, recording timestamp, operator, task type, provider, model, execution status, and latency.
- **Zero Token Leakage**: The token sanitizer intercepts exceptions and responses, preventing `HF_TOKEN` from appearing in audit logs, system exceptions, or API payloads.
- **Input Guardrails**: All queries undergo two-tier Prompt Guard validation (heuristic regex injection scanner + semantic Llama-Guard-3 screening) prior to reaching any model router.

### 10. Demo Commands
Verify the multi-model routing layer with the following scenarios:

#### Scenario 1: Coding Request (Auto-routes to DeepSeek-Coder-V2 + Docker Sandbox)
```bash
curl -X POST http://localhost:8000/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Write Python code to calculate pump efficiency when input power is 100 kW and output power is 85 kW."}'
```
*Expected Output:* Task detected as `coding`, model selected as `DeepSeek-Coder-V2`, execution verified in Docker sandbox, efficiency calculated as `85.0%`.

#### Scenario 2: Document / Reasoning Request (Auto-routes to Qwen2.5-32B)
```bash
curl -X POST http://localhost:8000/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Summarize this engineering inspection report and identify key maintenance risks."}'
```
*Expected Output:* Task detected as `document`, model selected as `qwen/qwen2.5-32b-instruct`.

#### Scenario 3: Vision Request (Auto-routes to Qwen2.5-VL)
```bash
curl -X POST http://localhost:8000/api/ai/query \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Analyze this inspection image and extract the dial gauge reading."}'
```
*Expected Output:* Task detected as `vision`, model selected as `qwen2.5-vl`.

#### Check Model & Sovereign Status:
```bash
curl -X GET http://localhost:8000/api/models/status
```

### 11. Automated Test Suite
```bash
# Run model routing tests:
pytest backend/app/tests/test_model_routing.py -v

# Verification covers:
# Test 1: Coding task routing to DeepSeek-Coder-V2
# Test 2: Vision task routing to Qwen2.5-VL
# Test 3: Document/Reasoning routing to Qwen2.5-32B
# Test 4: Sovereign Mode air-gap enforcement (blocks external providers)
# Test 5: Provider failure resilience & zero secret leakage
# Test 6: Docker sandbox code execution (/execute tmpfs isolation)
# Test 7: /api/models/status and /api/ai/query end-to-end integration
```

---

## 🛡️ Security Architecture & Known Limitations

### Security Architecture
- **Sandbox Isolation**: The calculation engine runs inside `sovereign-sandbox` with `read_only: true`, a `tmpfs` mount for `/tmp`, rigid CPU (`0.1`) and Memory (`64m`) limits, and operates on an `internal: true` Docker network (`sandbox-net`) to prevent outbound data exfiltration.
- **Audit Cryptography**: All lifecycle decisions, RBAC blocks, and HITL approvals are hashed via SHA-256 and linked sequentially in PostgreSQL.
- **Two-Tier Prompt Guard**: Fast deterministic regex checking followed by semantic LLM safety checking.
- **Centralized Provider Policy**: In air-gapped Sovereign Mode (`SOVEREIGN_MODE=true`), all outbound AI provider connections are forbidden at the application level.

### Known Limitations
- **Deployment-Level Air-Gap**: While the Docker containers restrict outbound access where configured, a true air-gap requires physical network isolation of the host machine, which this codebase alone cannot enforce.
- **Ollama / Qwen2.5-VL Cold Starts**: In environments without pre-loaded VRAM, initial multimodal inference can exceed standard HTTP timeouts.
- **Dependency Vulnerabilities**: The pinned `requirements.txt` contains dependencies with known CVEs (e.g., `pypdf`, `werkzeug`, `tornado`). A strategic upgrade cycle is necessary before internet-facing deployment.
- **Model Hallucinations**: Local LLMs may still produce unexpected planner reasoning; the application mitigates this by restricting output to strict capability registries, but cannot eliminate LLM non-determinism entirely.

