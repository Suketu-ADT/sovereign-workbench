# Sovereign Workbench — On-Premise Agentic AI Console

> **Confidential Industrial Operations & Multimodal Safety Workbench**  
> Built for the Smart India Hackathon (SIH) — Confidential on-premise industrial query processing with verified defense pipeline, human-in-the-loop authorization, and hash-chain audit logging.

---

## Overview

Sovereign Workbench is an air-gapped operator console for high-consequence operational technology (OT) environments (e.g., thermal power plants, manufacturing units, and chemical processing loops). Maintenance engineers can query equipment manuals, extract gauge values from visual inspection photos, run deterministic calculations, and request physical actuator actions (such as opening relief valves) under strict safety policies.

### Key Capabilities

1. **Conversational Operator Interface**: Clean, ChatGPT/Claude-style conversational UX with collapsible chat history, past conversation recall, auto-resizing input, and file attachment handling.
2. **Visible Defense Pipeline**: Every operator prompt passes through a defense sequence:
   - **Rate Limit Check**: Token bucket usage verification.
   - **Prompt Safety Check**: Adversarial injection heuristics scan.
   - **SCADA RBAC Verification**: Enforces hardware clearances by operator tier.
   - **Role-Filtered Document Retrieval**: Local manual lookup without outbound egress.
   - **Multimodal Vision Inspection**: Extracts live gauge readings and confidence metrics.
   - **Sandboxed Calculation**: Isolated compute for thermal and pressure differentials.
   - **Human Approval (HITL)**: Secondary authorization required before physical actuator commands execute.
   - **Audit Log Write**: SHA-256 Merkle-linked tamper-proof block commitment.
3. **Dynamic Role-Based Access Control (RBAC)**:
   - **Level 1 — Maintenance Engineer** (`boiler-102` and basic telemetry).
   - **Level 2 — Systems Specialist** (Turbines, Compressors, Boilers & Pumps).
   - **Level 3 — Chief Safety Auditor** (Facility-wide clearance & emergency audits).
4. **User Profile & Navigation**:
   - Bottom-of-sidebar profile pill with avatar, name, and tier (`Suketu · Pro ⌄`).
   - Upward popup card featuring Settings (`Ctrl ,`), Language switcher, SOP 4.2.1 Emergency Guide, Clearances Matrix, CLI snippets with JSON audit export, Sovereign Academy (`New` badge), and Logout.
5. **Zero External Build Step**: Pure HTML5, CSS3, and JavaScript — runs by opening `index.html` directly in any web browser (`file:///` compatible).

---

## Quick Start

No installation, npm dependencies, or server setup required.

1. Clone or download this repository:
   ```bash
   git clone <YOUR-GITHUB-REPO-URL>
   cd SIH
   ```
2. Double-click or open `index.html` in any modern browser:
   ```bash
   # Windows PowerShell:
   Start-Process index.html
   ```

---

## Repository Structure

```
.
├── index.html        # Semantic markup (sidebar, chat console, dialogs, modals)
├── styles.css        # Vanilla CSS design system (light/dark themes, components)
├── script.js         # Interactivity, defense pipeline simulator, audit hash chain, auth
└── README.md         # Project documentation
```

---

## Industrial Safety Protocol

All physical actuations strictly conform to **SOP 4.2.1**:
- Pressure relief valve operations require dual-key Human-in-the-Loop (HITL) authorization by a Senior Engineer.
- Every event is committed to a continuous SHA-256 Merkle hash chain ensuring legal non-repudiation and offline verification.
