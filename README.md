# 🛡️ Sovereign Workbench — On-Premise Agentic AI Console

<p align="center">
  <img src="https://img.shields.io/badge/Status-Production_Ready-success?style=for-the-badge&logo=fastapi" alt="Status Production Ready" />
  <img src="https://img.shields.io/badge/Air--Gap-100%25_On--Premise-blueviolet?style=for-the-badge&logo=shield" alt="100% On-Premise Air-Gapped" />
  <img src="https://img.shields.io/badge/Audit-SHA--256_Hash_Chain_%2B_Ed25519-2ea44f?style=for-the-badge&logo=git" alt="SHA-256 Audit Chain" />
  <img src="https://img.shields.io/badge/Sandbox-Network_Isolated_Docker-0E7C86?style=for-the-badge&logo=docker" alt="Network-Isolated Sandbox" />
  <img src="https://img.shields.io/badge/Tests-54%2F54_Passing-brightgreen?style=for-the-badge&logo=pytest" alt="54/54 Tests Passing" />
</p>

> **The Self-Hosted, Air-Gapped Agentic AI Workbench for Regulated PSUs, Refineries, Defence Units, and Strategic Enterprises.**  
> Complete local intelligence running 100% on internal GPU servers: multi-model auto-selection, universal document OCR, agentic multi-step planning, network-isolated code & math sandboxing, human-in-the-loop authorization, and verifiable cryptographic tamper-evident audit logging. **Zero bytes ever leave your premises.**

---

## 📑 Table of Contents

1. [Problem Statement & Ground Reality](#-problem-statement--ground-reality)
2. [Executive Problem-Solution Mapping](#-executive-problem-solution-mapping)
3. [System Architecture Overview](#-system-architecture-overview)
4. [Core Pillars of Sovereign Workbench](#-core-pillars-of-sovereign-workbench)
   - [Pillar 1: Multi-Model Autonomous Routing (No Vendor Lock-In)](#pillar-1-multi-model-autonomous-routing-no-vendor-lock-in)
   - [Pillar 2: Universal Multi-Format Document Ingestion & Local OCR](#pillar-2-universal-multi-format-document-ingestion--local-ocr)
   - [Pillar 3: Agentic Multi-Step Reasoning & HITL Guardrails](#pillar-3-agentic-multi-step-reasoning--hitl-guardrails)
   - [Pillar 4: Network-Isolated Docker Sandbox (Math & Code Execution)](#pillar-4-network-isolated-docker-sandbox-math--code-execution)
   - [Pillar 5: Tangible Deliverables & Strict Zero-Hallucination RAG](#pillar-5-tangible-deliverables--strict-zero-hallucination-rag)
   - [Pillar 6: Cryptographic Tamper-Evident Ledger (SHA-256 & Ed25519)](#pillar-6-cryptographic-tamper-evident-ledger-sha-256--ed25519)
   - [Pillar 7: Provable Air-Gap Sovereignty & Zero External Network Calls](#pillar-7-provable-air-gap-sovereignty--zero-external-network-calls)
5. [The Visible 8-Stage Defense Pipeline](#-the-visible-8-stage-defense-pipeline)
6. [Hardware Sizing & Demonstration Deployment](#-hardware-sizing--demonstration-deployment)
7. [Step-by-Step Installation & Quickstart](#-step-by-step-installation--quickstart)
8. [End-to-End Demonstration Scenarios](#-end-to-end-demonstration-scenarios)
9. [Automated Verification & Test Suite](#-automated-verification--test-suite)
10. [Repository Structure](#-repository-structure)

---

## 🎯 Problem Statement & Ground Reality

### Background
Refineries, Public Sector Undertakings (PSUs), defence-linked manufacturing units, atomic installations, and government ministries generate massive volumes of routine, high-consequence knowledge work:
- **Board presentations & approval notes** involving capital allocations.
- **Piping & Instrumentation Diagrams (P&IDs)** and engineering drawings.
- **Deterministic thermodynamic calculations** (e.g. boiler/turbine differential pressure, pump efficiencies, ASME safety tolerances).
- **Automation code and scripts** for internal tools and SCADA interfacing.
- **Inspection reports**, scan-damaged equipment manuals, and handwritten maintenance logbooks.

None of this sensitive data can ever be uploaded to commercial cloud AI services (e.g., ChatGPT, Claude, Codex, Copilot) because the underlying files contain proprietary designs, critical infrastructure topologies, trade negotiations, and national security secrets. 

### The Industry Dilemma
Because strict compliance policies prohibit external transmission, personnel face a painful trade-off:
1. **Manual Inefficiency**: Staff manually transcribe, summarize, and compute, causing severe productivity bottlenecks.
2. **Shadow AI Exfiltration**: Frustrated operators quietly paste confidential text into public LLMs, violating corporate policies and exposing enterprise intellectual property.

### The Objective
Open-weight reasoning models (such as Qwen 2.5, DeepSeek Coder, and Qwen2.5-VL) have reached a capability tipping point where an on-premise industrial assistant is realistic. However, **no deployable, turnkey, multi-model agentic system previously existed** that industrial organizations could run out of the box with the fluidity of Claude or Codex while adhering to military-grade SCADA constraints and provable air-gap isolation.

---

## 📊 Executive Problem-Solution Mapping

| Requirement in Problem Statement | Sovereign Workbench Implementation | Codebase Artifacts |
| :--- | :--- | :--- |
| **Self-hosted, air-gapped on organization's GPU** | Completely self-contained stack (FastAPI, Qdrant, PostgreSQL, Docker Sandbox, Nginx). Enforced by `SOVEREIGN_MODE=true` which physically rejects external API calls. | `app/core/config.py`, `app/services/model_provider.py` |
| **No lock-in to one model; multi-model auto-selection** | Dynamic Model Router automatically inspects request context and dispatches to specialized open-weight models: DeepSeek-Coder-V2 for coding, Qwen2.5-VL for vision, Qwen2.5-32B for reasoning/RAG, and Llama-Guard-3 for prompt safety. | `app/services/model_router.py`, `app/services/model_provider.py` |
| **Easily extensible for new models** | Provider-independent abstraction (`ModelProvider` ABC). New open-weight models can be added by updating configuration without rewriting UI or planner logic. | `app/services/model_provider.py`, `app/api/ai.py` |
| **True agentic multi-step planning & tool use** | LangGraph StateGraph engine: multi-turn reasoning loop, automated tool calling (file read/write, vector search, sandbox execution, AST math evaluation), and self-healing error recovery. | `app/services/planner_service.py`, `app/services/coding_agent_service.py` |
| **Human-in-the-Loop (HITL) for sensitive actions** | LangGraph `interrupt()` pause pattern. Critical physical actuator actions (e.g., `open_release_valve`, electrical trips) pause execution and require authenticated cryptographic sign-off. | `app/api/approvals.py`, `app/services/planner_service.py` |
| **Universal OCR & multi-format document handling** | Local RapidOCR engine + PyPDF, python-docx, openpyxl, python-pptx, and CSV/JSON parsers. Ingests scanned PDFs, handwritten maintenance logs, schematics, and photos with zero cloud calls. | `app/services/document_service.py`, `RapidOCR` |
| **Real deliverables (not just chat replies)** | Generates structured Word (`.docx`), Excel spreadsheets, formatted approval notes, and verifiable Python scripts with exact mathematical step derivations. | `app/services/document_service.py`, `app/api/documents.py` |
| **Deterministic calculations (zero math hallucination)** | Network-isolated Docker sandbox and AST evaluator for exact $\Delta p$ pressure drop, efficiency formulas, and tolerance checks with explicit formula readouts. | `sandbox/main.py`, `app/services/calculation_service.py` |
| **Local RAG grounding with page-level citations** | On-premise Qdrant vector store with FastEmbed (`BAAI/bge-small-en-v1.5`). Strict anti-hallucination guardrails: verbatim page/chunk provenance and refusal when data is absent. | `app/services/retrieval_service.py`, `app/services/document_service.py` |
| **Proof of sovereignty (verifiable zero external calls)** | Cryptographic SHA-256 hash-chained tamper-evident audit ledger + Ed25519 digital signatures. Comprehensive security telemetry and live pipeline traces for compliance auditors. | `app/services/audit_service.py`, `app/models/audit.py`, `app/api/audit.py` |

---

## 🏗️ System Architecture Overview

Sovereign Workbench is structured into decoupled, defense-in-depth architectural tiers:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               OPERATOR WORKSTATION UI                                 │
│         Modern High-Contrast Industrial Dark Mode Console (HTML5 / Vanilla CSS3 / JS)    │
│    Chat Composer ── Pipeline Trace Drawer ── Audit Ledger Viewer ── Document Staging   │
└──────────────────────────────────────────┬─────────────────────────────────────────────┘
                                           │ SSE Streaming (/query/stream) & REST APIs
                                           ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                         SOVEREIGN BACKEND GATEWAY (FastAPI)                            │
│                                                                                        │
│  ┌──────────────────────┐   ┌──────────────────────┐   ┌────────────────────────────┐  │
│  │ Rate Limiter         │   │ Prompt Safety Guard  │   │ Role-Based Access Control  │  │
│  │ Token Bucket (60/min)│──▶│ Llama-Guard-3 + Regex│──▶│ SCADA Tiers (L1 / L2 / L3) │  │
│  └──────────────────────┘   └──────────────────────┘   └────────────────────────────┘  │
│                                                                      │                 │
│                                                                      ▼                 │
│                                                        ┌────────────────────────────┐  │
│                                                        │ Dynamic Model Router       │  │
│                                                        │ Task Domain Auto-Detection │  │
│                                                        └─────────────┬──────────────┘  │
│                                                                      │                 │
│         ┌────────────────────────┬───────────────────────────────────┼─────────────────┤
│         ▼                        ▼                                   ▼                 ▼
│  ┌──────────────┐      ┌──────────────────┐               ┌────────────────────┐ ┌─────┴──────┐
│  │ Coding Agent │      │ Vision Analysis  │               │ LangGraph Planner  │ │Universal   │
│  │ DeepSeek     │      │ Qwen2.5-VL /     │               │ Qwen2.5-32B Local  │ │RAG Engine  │
│  │ Coder V2     │      │ RapidOCR Engine  │               │ Multi-Step Reason  │ │Qdrant + BGE│
│  └──────┬───────┘      └────────┬─────────┘               └─────────┬──────────┘ └─────┬──────┘
│         │                       │                                   │                  │
│         ▼                       ▼                                   ▼                  │
│  ┌──────────────────────────────────────────────────────────────────────────┐          │
│  │              NETWORK-ISOLATED COMPUTE SANDBOX (Docker Microservice)      │          │
│  │    • Read-Only Root Filesystem    • Ephemeral in-memory tmpfs (/tmp)     │          │
│  │    • CPU Capped (0.1 Core)        • Memory Capped (64MB)                 │          │
│  │    • Internal Bridge Network      • AST Deterministic Industrial Math    │          │
│  └──────────────────────────────────────┬───────────────────────────────────┘          │
│                                         │                                              │
│                                         ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐          │
│  │                 HUMAN-IN-THE-LOOP (HITL) INTERRUPT GATE                  │          │
│  │    Blocks sensitive actuator commands (e.g. open_release_valve) until    │          │
│  │    dual-operator authorization is submitted and recorded                 │          │
│  └──────────────────────────────────────┬───────────────────────────────────┘          │
│                                         │                                              │
│                                         ▼                                              │
│  ┌──────────────────────────────────────────────────────────────────────────┐          │
│  │        TAMPER-EVIDENT CRYPTOGRAPHIC AUDIT LEDGER (PostgreSQL)            │          │
│  │    SHA-256 Hash Chain: Hi = SHA256(H_{i-1} | canonical_json(event_i))    │          │
│  │    Ed25519 Asymmetric Signed Checkpoints for Irrefutable Compliance      │          │
│  └──────────────────────────────────────────────────────────────────────────┘          │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 🏛️ Core Pillars of Sovereign Workbench

### Pillar 1: Multi-Model Autonomous Routing (No Vendor Lock-In)
The workbench does not force a single generalist model to handle radically different engineering disciplines. A specialized dispatcher inspects prompt syntax, token semantics, and uploaded artifacts to route the request:

```
                          ┌──▶ [Coding / Debugging Task] ──▶ DeepSeek-Coder-V2 + Docker Sandbox
                          │
User Query ──▶ Router ────┼──▶ [Document / SOP Analysis] ──▶ Qwen 2.5 32B/72B + Vector RAG
                          │
                          ├──▶ [Visual Telemetry / Dial] ──▶ Qwen2.5-VL + OpenCV Dial Extractor
                          │
                          └──▶ [Prompt Injection Scan]   ──▶ Llama-Guard-3 + OT Regex Shield
```

- **Pluggable Model Abstraction**: All inference interfaces adhere to the `ModelProvider` abstract base class (`app/services/model_provider.py`).
- **Seamless Model Upgrades**: To introduce a newer open-weight model (e.g., DeepSeek-V3, Llama-4, Mistral-Next), simply configure its model name in `.env` or Ollama/vLLM endpoints. Zero frontend or planner code changes are required.

---

### Pillar 2: Universal Multi-Format Document Ingestion & Local OCR
Industrial documents are rarely clean digital PDFs. Sovereign Workbench integrates a multi-format ingestion pipeline:

```
   ┌──────────────────────────────────────────────────────────────────────────────┐
   │                          SUPPORTED FILE FORMATS                              │
   │  .PDF (Digital & Scanned) │ .DOCX (Word) │ .PPTX (Slides) │ .XLSX (Excel)    │
   │  .CSV / .JSON / .MD       │ .PNG / .JPG (Scanned drawings, Dial Gauges)     │
   └──────────────────────────────────────┬───────────────────────────────────────┘
                                          │
                   Is document scanned / image-only?
                                ┌─────────┴─────────┐
                                │                   │
                            [YES]                [NO]
                                │                   │
                                ▼                   ▼
                   ┌──────────────────────┐  ┌──────────────────────┐
                   │ RapidOCR (On-Device) │  │ Native Text Extract  │
                   │ PaddleOCR Weights    │  │ pdfplumber / docx    │
                   └──────────┬───────────┘  └──────────┬───────────┘
                              │                         │
                              └────────────┬────────────┘
                                           ▼
                   ┌──────────────────────────────────────────────┐
                   │ Recursive Hierarchical Text Chunking         │
                   │ 500 chars, 80 char overlap, page-level tags  │
                   └──────────────────────┬───────────────────────┘
                                          ▼
                   ┌──────────────────────────────────────────────┐
                   │ Local FastEmbed (BAAI/bge-small-en-v1.5)     │
                   │ Cosine similarity indexing in Qdrant         │
                   └──────────────────────────────────────────────┘
```

- **RapidOCR On-Premise Engine**: Runs lightweight OCR models locally on CPU/GPU without contacting external Google Cloud Vision, AWS Textract, or Azure Cognitive Services.
- **Table & Spreadsheet Parsing**: Excel and CSV files are parsed with structural preservation for engineering formulas and tabular figures.

---

### Pillar 3: Agentic Multi-Step Reasoning & HITL Guardrails
Unlike conventional chatbots that respond once and terminate, Sovereign Workbench utilizes **LangGraph** to execute stateful, multi-turn reasoning loops:

1. **State Analysis**: The model inspects operator intent, available plant telemetry, and clearance level.
2. **Tool Execution**: Dynamically executes internal tools (e.g., retrieving manual sections, calculating differential pressure, executing code snippets).
3. **Self-Healing Iteration**: If code fails in the sandbox or telemetry violates bounds, the agent captures the traceback/output and iterates until resolution.
4. **Human-in-the-Loop (HITL) Interruption**:
   - For non-sensitive operations (e.g., querying manuals, reading dials), the agent completes autonomously.
   - For sensitive operational actions (`open_release_valve`, setpoint overrides, electrical switchgear control), the LangGraph workflow triggers an `interrupt()`.
   - Execution suspends in memory and database, generating an approval ticket awaiting an authorized operator's review before physical execution.

---

### Pillar 4: Network-Isolated Docker Sandbox (Math & Code Execution)
Large Language Models cannot be trusted for safety-critical arithmetic or unverified code execution. Sovereign Workbench enforces strict physical isolation:

- **Isolated Docker Container (`sovereign-sandbox`)**:
  - **Read-Only Root Filesystem**: `read_only: true` prevents malware persistence.
  - **In-Memory Tmpfs Execution**: `/tmp` is mounted as temporary RAM; scripts vanish upon completion.
  - **Zero Network Egress**: Assigned strictly to an internal Docker bridge network (`sandbox-net`) with no default gateway. Outbound data exfiltration is mathematically blocked.
  - **Strict Resource Throttling**: Limited to `0.1` CPU cores and `64MB` RAM to prevent Denial-of-Service or infinite loops.
  - **Non-Root Execution**: Runs as unprivileged UID `1001`.
- **Deterministic Industrial Math**:
  - Formulas such as $\Delta p = P_{\text{inlet}} - P_{\text{outlet}}$ are calculated through deterministic arithmetic in the sandbox, checking safe operational limits (e.g. $2.0 - 5.0\text{ bar}$) with full mathematical auditability:
  $$\Delta p = 6.4\text{ bar} - 2.6\text{ bar} = 3.8\text{ bar (NORMAL)}$$

---

### Pillar 5: Tangible Deliverables & Strict Zero-Hallucination RAG
Industrial users need real deliverables, not conversation filler:

- **Anti-Hallucination System Prompting**: If a user asks a question whose answer is not in the uploaded documents, the model is strictly trained and prompted to refuse:
  > *"I could not find that information in the uploaded document."*
- **Verbatim Page Citations**: Every claim is annotated with clickable, auditable citations:
  $$\text{[Report.pdf — Page 2, Chunk #3]}$$
- **File Deliverables**: Outputs complete formatted approval memos, technical reports, and working Python scripts with step-by-step explanations.

---

### Pillar 6: Cryptographic Tamper-Evident Ledger (SHA-256 & Ed25519)
Every action taken across the platform is immutably committed to an append-only audit ledger:

$$H_0 = \text{"0000000000000000000000000000000000000000000000000000000000000000"}$$

$$H_i = \text{SHA256}\Big(H_{i-1} + \text{"\|"} + \text{canonical\_json}(\text{event}_i)\Big)$$

```
  GENESIS BLOCK (H0)
         │
         ▼
  ┌──────────────┐       ┌──────────────┐       ┌──────────────┐
  │   BLOCK #1   │──────▶│   BLOCK #2   │──────▶│   BLOCK #3   │
  │ H1 = SHA256  │       │ H2 = SHA256  │       │ H3 = SHA256  │
  └──────────────┘       └──────────────┘       └──────────────┘
                                                       │
                                        Every N blocks │ Signed with Ed25519
                                                       ▼
                                          ┌───────────────────────────┐
                                          │  SIGNED AUDIT CHECKPOINT  │
                                          │  Head: H3                 │
                                          │  Sig: 3e8b... (Ed25519)   │
                                          └───────────────────────────┘
```

- **Canonical JSON Serialization**: Deterministic key ordering (`sort_keys=True`), compact whitespace, and ISO-8601 UTC timestamps prevent serialization divergence.
- **Tamper Evidence**: Altering a single character, timestamp, or actor ID in block $k$ breaks the hash linkage for all blocks $k+1 \dots N$.
- **Ed25519 Signed Checkpoints**: Periodically signs ledger state using an asymmetric Ed25519 private key stored outside the database. Even an attacker with complete database `root` access cannot forge historical entries without invalidating the cryptographic signature.

---

### Pillar 7: Provable Air-Gap Sovereignty & Zero External Network Calls
The hallmark of a truly sovereign system is verifiable proof that data never leaves the facility:

- **`SOVEREIGN_MODE=true` Enforcement**: The gateway hard-blocks all cloud AI SDKs and external URLs at the application layer. Any outbound attempt raises an immediate `PermissionError` (HTTP 403).
- **Network Isolation Verification**: Docker configurations specify `internal: true` for the computation networks.
- **Audit Ledger Logging**: Every network event, retrieval query, model inference, and code execution is timestamped and logged with origin IP and operator identity.

---

## 🛡️ The Visible 8-Stage Defense Pipeline

Every user prompt traverses an explicit, visible 8-stage defense sequence reflected in real time on the operator console:

```text
 1. Rate Limit Check       ──▶ Token bucket algorithm (60 requests/min capacity)
 2. Prompt Safety Check    ──▶ Dual-engine scan: OT injection regex + Llama-Guard-3
 3. RBAC Verification      ──▶ Verification of operator clearance (Level 1, 2, or 3)
 4. Document Retrieval     ──▶ Local vector search over authorized manuals / uploaded PDFs
 5. Vision Extraction      ──▶ OpenCV dial reading or Qwen2.5-VL visual inspection
 6. Sandboxed Calculation  ──▶ Deterministic industrial calculation in isolated Docker container
 7. Human Approval (HITL)  ──▶ Interruption gate on sensitive actuator actions (open valve, trip)
 8. Audit Log Write        ──▶ Commit SHA-256 Merkle-linked block into immutable audit chain
```

---

## 💻 Hardware Sizing & Demonstration Deployment

Sovereign Workbench is designed to run on common on-premise hardware footprints:

| Tier | Target Hardware | Recommended Open-Weight Models | Typical Deployment Scenario |
| :--- | :--- | :--- | :--- |
| **Edge / Portable Demo** | 1x Workstation GPU (12GB–16GB VRAM, e.g. RTX 4070 / 3060 / Apple M2/M3) | • `qwen2.5:7b-instruct-q4_K_M`<br>• `deepseek-coder-v2:16b-lite-q4`<br>• `qwen2.5-vl:7b-q4`<br>• `llama-guard3:1b` | Hackathon demos, field engineer laptops, emergency operations vehicles. |
| **Mid-Range Production Server** | 1x–2x Enterprise GPU (24GB–48GB VRAM, e.g. RTX 4090 / A5000 / A6000) | • `qwen2.5:14b` or `32b-q4`<br>• `deepseek-coder-v2:16b`<br>• `qwen2.5-vl:7b`<br>• `bge-small-en-v1.5` | Refinery control rooms, PSU zonal offices, defense engineering divisions. |
| **Enterprise Server Cluster** | Multi-GPU Server (80GB+ VRAM, e.g. A100 / H100 / L40S) | • `qwen2.5:72b`<br>• `deepseek-coder-v2:236b` (via vLLM)<br>• `qwen2.5-vl:72b` | Centralized corporate headquarters, national defense data centers. |

---

## 🚀 Step-by-Step Installation & Quickstart

### Prerequisites
- Docker & Docker Compose (v2.20+)
- Python 3.11+
- NVIDIA Container Toolkit (if running local GPU acceleration)

### 1. Clone & Environment Setup
```bash
git clone https://github.com/Suketu-ADT/sovereign-workbench.git
cd sovereign-workbench

# Copy environment configuration
cp .env.example .env
```

Ensure `.env` has your required parameters:
```env
# Enforce 100% Air-Gapped Sovereign Mode (No external cloud calls)
SOVEREIGN_MODE=true

# Local Model Provider Endpoint (Ollama or vLLM)
LOCAL_MODEL_BASE_URL=http://127.0.0.1:11434/v1

# Security Secrets
JWT_SECRET=your_super_secret_64_character_hex_key_here
POSTGRES_PASSWORD=sovereign_secure_password
```

### 2. Launch Local Model Engine (Ollama / vLLM)
If utilizing Ollama on the host:
```bash
# Pull the open-weight model family
ollama pull qwen2.5:7b
ollama pull deepseek-coder-v2:16b
ollama pull qwen2.5-vl
ollama pull llama-guard3:1b
```

### 3. Launch the Sovereign Stack via Docker Compose
```bash
docker compose up -d
```
The stack starts:
- `sovereign-backend`: FastAPI application on port `8000`.
- `sovereign-db`: PostgreSQL database on port `5432`.
- `sovereign-qdrant`: Vector database on port `6333`.
- `sovereign-sandbox`: Network-isolated Docker compute container on port `8081`.
- `sovereign-frontend`: Operator console served on port `80` (or open `index.html` directly).

---

## 🎬 End-to-End Demonstration Scenarios

### Scenario 1: End-to-End Document RAG & Approval Deliverable
**Objective**: Ingest a scanned plant inspection report, extract findings via local OCR, answer questions with page citations, and draft an approval note.

1. In the chat console, upload `boiler_inspection_report.pdf` (or scanned image/Excel sheet).
2. The UI triggers `POST /documents/upload`:
   - RapidOCR scans text layers.
   - Text is split into 500-character chunks with page numbers.
   - Vectors are indexed into Qdrant using FastEmbed.
3. Submit query: *"What are the critical inspection findings and what action is recommended?"*
4. **Result**:
   - The model answers grounded **strictly in the document**:
     > *"Based on Section 3.1 (Page 2), boiler tube wall thinning was detected at 4.2mm (minimum safe limit 5.0mm). Recommendation: Replace tube assembly."*
   - Verbatim clickable source pill: `boiler_inspection_report.pdf — Page 2`.
   - Generates an approval note deliverable for management review.

---

### Scenario 2: Coding Task Verified in Network-Isolated Sandbox
**Objective**: Generate an engineering automation script, execute it in the isolated sandbox, and return verified output.

1. Submit query: *"Write a Python script to compute pump efficiency given 120 kW input and 98 kW hydraulic output."*
2. **Result**:
   - Router detects `coding` task $\to$ dispatches to `DeepSeek-Coder-V2`.
   - Code is generated, transferred to `sovereign-sandbox`, and executed via `POST /execute` in a `tmpfs` RAM disk.
   - Execution succeeds with exit code `0`:
     ```text
     Pump Efficiency: 81.67%
     Status: Acceptable operating performance
     ```
   - Complete working code and terminal execution output are displayed directly in the chat deliverable card.

---

### Scenario 3: Multimodal Vision Dial Reading & Thermodynamic Calculation
**Objective**: Analyze an analog pressure gauge photo, extract inlet pressure, and calculate differential pressure drop deterministically.

1. Upload a dial gauge photo showing `6.4 bar` on `boiler-102`.
2. Submit query: *"Read this gauge and calculate pressure drop across Boiler-102."*
3. **Result**:
   - Stage 5 (Vision Extraction): OpenCV / Qwen2.5-VL extracts needle angle $\to$ `6.4 bar inlet`.
   - Stage 6 (Sandboxed Calculation): Transmits values to the isolated sandbox microservice:
     $$\Delta p = P_{\text{inlet}} - P_{\text{outlet}} = 6.4\text{ bar} - 2.6\text{ bar} = 3.8\text{ bar}$$
   - Tolerance Check: Compares against SOP §4.2 nominal envelope ($2.0 - 5.0\text{ bar}$).
   - Emits readout: **`Δp = 3.8 bar | Range: 2.0 – 5.0 bar | NORMAL`**.

---

### Scenario 4: Sensitive Actuator Command & HITL Authorization
**Objective**: Attempt to open a boiler release valve, observe automated RBAC enforcement and LangGraph interruption.

1. Submit query: *"Open the main release valve on boiler-102 immediately."*
2. **Result**:
   - RBAC checks operator clearance.
   - Planner detects sensitive actuator tool: `open_release_valve`.
   - The LangGraph agent executes `interrupt()`, halting the pipeline.
   - UI modal appears: **"Human-in-the-Loop Approval Required"**.
   - Operator clicks **Approve**.
   - Action executes, and the decision is permanently linked to the SHA-256 hash chain with block hash and actor signature.

---

### Scenario 5: Cryptographic Audit Verification & Proof of Zero Leakage
**Objective**: Verify the integrity of the audit ledger and demonstrate proof that no tampering has occurred.

1. Navigate to the **Audit Ledger** tab in the console.
2. Click **Verify Cryptographic Chain**:
   - Backend traverses from Genesis $H_0$ to current Head.
   - Recomputes SHA-256 for all entries and checks Ed25519 digital signatures.
   - Displays: **`✓ CRYPTOGRAPHIC INTEGRITY VERIFIED (Chain Length: N, Zero Discrepancies)`**.
3. Inspect network egress logs: Demonstrates that **0 external outbound packets** were emitted during the entire workflow.

---

## 🧪 Automated Verification & Test Suite

The repository includes a comprehensive automated test suite covering 100% of the defense pipeline and sovereign guarantees.

```bash
# Activate virtual environment
.\venv\Scripts\activate

# Run all core sovereign test suites (54 comprehensive integration tests)
pytest backend/app/tests/test_sandboxed_calculation_flow.py \
       backend/app/tests/test_multimodal_vision.py \
       backend/app/tests/test_document_rag.py \
       backend/app/tests/test_universal_document_rag.py \
       backend/app/tests/test_audit_ledger.py -v
```

### Test Coverage Highlights:
- **`test_sandboxed_calculation_flow.py`**: Verifies sandboxed calculation is never skipped, evaluates $\Delta p$ formulas correctly, and returns `passed` status.
- **`test_multimodal_vision.py`**: Validates gauge extraction vs. diagram explanation, preventing misrouting.
- **`test_document_rag.py`**: Tests document upload, Qdrant vector retrieval, page-level citations, multi-turn conversation memory, and anti-hallucination refusal.
- **`test_universal_document_rag.py`**: Tests universal multi-format parsing across PDF, DOCX, PPTX, XLSX, CSV, JSON, and images.
- **`test_audit_ledger.py`**: Tests SHA-256 Merkle-style hash chaining, tamper detection on modified payload/timestamps, middle-block deletion detection, and Ed25519 signed checkpoints.

---

## 📂 Repository Structure

```text
.
├── backend/
│   ├── alembic/                  # Database migration scripts (audit logs, checkpoints)
│   ├── app/
│   │   ├── api/                  # FastAPI router endpoints
│   │   │   ├── ai.py             # Model query & task routing endpoints
│   │   │   ├── approvals.py      # Human-in-the-Loop decision endpoints
│   │   │   ├── audit.py          # Cryptographic ledger verification & export
│   │   │   ├── auth.py           # Argon2id password & JWT clearance issuance
│   │   │   ├── documents.py      # Universal document upload & RAG queries
│   │   │   └── query.py          # 8-stage defense pipeline & SSE streaming
│   │   ├── core/                 # Config, security tokens, and DB session
│   │   ├── models/               # SQLAlchemy models (AuditEntry, Checkpoint, User)
│   │   ├── schemas/              # Pydantic schemas (Query, Audit, Document, HITL)
│   │   ├── services/             # Core business & agent logic
│   │   │   ├── audit_service.py  # SHA-256 chaining & Ed25519 signature engine
│   │   │   ├── calculation_service.py # Sandboxed formula & tolerance engine
│   │   │   ├── coding_agent_service.py # DeepSeek self-healing coding runner
│   │   │   ├── document_service.py    # Universal document parser & OCR
│   │   │   ├── model_provider.py      # Abstract model provider (Local/Air-Gap)
│   │   │   ├── model_router.py        # Autonomous task classifier & model selector
│   │   │   ├── planner_service.py     # LangGraph stateful multi-step agent
│   │   │   ├── retrieval_service.py   # Qdrant vector retrieval & BGE embeddings
│   │   │   └── vision_service.py      # OpenCV gauge dial reader & Qwen-VL
│   │   └── tests/                # Automated pytest suite (54+ test cases)
│   └── requirements.txt          # Pinned backend dependencies
├── sandbox/
│   ├── Dockerfile                # Hardened, read-only, non-root sandbox image
│   └── main.py                   # Isolated execution microservice (/execute, /calculate)
├── docker-compose.yml            # Multi-container orchestration (DB, Qdrant, Sandbox, App)
├── index.html                    # Industrial Operator Console UI
├── styles.css                    # Professional dark-mode design system
├── script.js                     # Reactive SSE client, HITL modals, & audit explorer
└── README.md                     # Comprehensive system documentation
```

---

## 📜 License & Compliance

Developed for enterprise, PSU, and strategic industrial installations requiring absolute data sovereignty.  
Designed in compliance with **SCADA IEC 62443**, **ISO 27001**, and **NIST SP 800-82** operational technology security guidelines.
