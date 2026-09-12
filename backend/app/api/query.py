"""
Query route — the defense pipeline entry point.

Pipeline steps (in order):
  1. Rate limit check
  2. RBAC check
  3. If both pass → stub response (retrieval/vision/calculation
     are Phases 3-5)

Each step writes an audit_log entry via the centralized audit service.
"""

import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import get_current_user
from app.db.session import get_db
from app.models.approval import PendingApproval
from app.schemas.query import DocumentCitation, HITLApprovalDetails, QueryRequest, QueryResponse
from app.services import (
    audit_service,
    calculation_service,
    planner_service,
    prompt_guard,
    rate_limiter,
    rbac_service,
    retrieval_service,
    vision_service,
)
from app.services.document_service import document_service
from app.services.model_provider import get_provider
from app.services.model_router import route_request




router = APIRouter(tags=["Query"])


@router.get(
    "/query/models",
    summary="Get active inference models and API status",
)
async def get_active_models(
    current_user: dict = Depends(get_current_user),
):
    return {
        "planner_model": settings.PLANNER_MODEL_NAME,
        "vision_model": settings.VISION_MODEL_NAME,
        "has_api_key": bool(settings.LLM_API_KEY),
        "base_url": settings.LLM_BASE_URL,
    }


def is_gauge_query(query_text: str) -> bool:
    """Determines whether visual query is targeting operational gauge reading vs diagram explanation."""
    q = (query_text or "").lower().strip()
    explanation_keywords = [
        "explain", "describe", "what is", "diagram", "pipeline", "flowchart",
        "architecture", "infographic", "overview", "summarize", "walkthrough", "stages", "steps", "chart",
    ]
    if any(w in q for w in explanation_keywords) and not any(p in q for p in ["gauge reading", "dial reading", "measure pressure", "gauge pressure"]):
        return False

    gauge_keywords = [
        "gauge", "dial", "needle", "inlet", "outlet", "pressure", "vent",
        "bar", "psi", "delta-p", "delta p", "drop", "reading", "value",
    ]
    return any(w in q for w in gauge_keywords) or not q


@router.post(
    "/query",
    response_model=QueryResponse,
    summary="Submit a query through the defense pipeline",
)
async def submit_query(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    x_model_api_key: str | None = Header(None, alias="X-Model-Api-Key"),
    x_model_base_url: str | None = Header(None, alias="X-Model-Base-Url"),
):
    if x_model_api_key:
        settings.LLM_API_KEY = x_model_api_key
    if x_model_base_url:
        settings.LLM_BASE_URL = x_model_base_url

    query_text = body.get_query_text()
    user_id = uuid.UUID(current_user["sub"])
    clearance = current_user["clearance_level"]
    has_image_requested = bool(body.has_image or (body.image_data and str(body.image_data).strip()))
    routing = route_request(query_text, has_image=has_image_requested)

    # ── Step 1: Rate limit check ──────────────────────────────
    allowed, retry_after = rate_limiter.check_rate_limit(user_id)

    if not allowed:
        async with audit_service.audit_transaction(db):
            await audit_service.append_entry(
                db=db,
                event_type="RATE_LIMIT_BLOCK",
                detail=f"Rate limit exceeded for user {current_user['email']}",
                actor_user_id=user_id,
            )
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "retry_after_s": retry_after,
            },
        )

    # ── Step 2: Prompt safety check (PromptGuard) ─────────────
    safe, reason = await prompt_guard.is_safe(query_text)

    if not safe:
        async with audit_service.audit_transaction(db):
            await audit_service.append_entry(
                db=db,
                event_type="PROMPT_SAFETY_BLOCK",
                detail=f"Prompt rejected by PromptGuard: {reason}",
                actor_user_id=user_id,
            )
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "Prompt blocked by safety screening",
                "reason": reason,
            },
        )

    # ── Step 3: RBAC check ────────────────────────────────────
    rbac_allowed, required_level = rbac_service.check_access(query_text, clearance)

    if not rbac_allowed:
        async with audit_service.audit_transaction(db):
            await audit_service.append_entry(
                db=db,
                event_type="RBAC_BLOCK",
                detail=(
                    f"Insufficient clearance: required level {required_level}, "
                    f"user {current_user['email']} has level {clearance}"
                ),
                actor_user_id=user_id,
            )
            await db.commit()

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Insufficient clearance",
                "required_level": required_level,
                "current_level": clearance,
            },
        )

    # ── Check for Active Document Scope (Document Grounding RAG) ─
    active_doc_ids = list(body.document_ids or [])
    if not active_doc_ids and body.conversation_id:
        active_doc_ids = document_service.get_conversation_documents(body.conversation_id)
    elif active_doc_ids and body.conversation_id:
        document_service.set_conversation_document(body.conversation_id, active_doc_ids)

    if active_doc_ids:
        # Document Grounding RAG Pipeline
        doc_chunks = retrieval_service.retrieve_document_chunks(
            query=query_text,
            user_id=str(user_id),
            document_ids=active_doc_ids,
            top_k=5,
        )

        citations = [
            DocumentCitation(
                filename=c.filename,
                page=c.page_number,
                chunk_id=c.chunk_id,
                snippet=c.text[:200],
            )
            for c in doc_chunks
        ]
        seen_sources = set()
        sources = []
        for c in doc_chunks:
            s = f"{c.filename} — Page {c.page_number}"
            if s not in seen_sources:
                seen_sources.add(s)
                sources.append(s)

        system_prompt, user_prompt = document_service.build_grounded_prompt(
            query=query_text,
            chunks=doc_chunks,
        )

        doc_routing = route_request(query_text, task_type="document")
        selected_model = body.model or doc_routing["model"]
        provider = get_provider(doc_routing["provider"])
        answer = await provider.generate_async(
            model=selected_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
        )

        calc_result = await calculation_service.evaluate_operational_calculation(
            query=query_text,
            doc_chunks=doc_chunks,
            equipment_unit="boiler-102",
        )

        async with audit_service.audit_transaction(db):
            await audit_service.append_entry(
                db=db,
                event_type="DOCUMENT_RETRIEVED",
                detail=f"Retrieved {len(doc_chunks)} chunks for documents {active_doc_ids}",
                actor_user_id=user_id,
            )
            await audit_service.append_entry(
                db=db,
                event_type="DOCUMENT_QUERY",
                detail=f"Document query processed: {query_text[:120]} (chunks: {len(doc_chunks)})",
                actor_user_id=user_id,
            )
            await audit_service.append_entry(
                db=db,
                event_type="CALCULATION_RESULT",
                detail=(
                    f"Sandboxed formula '{calc_result.formula}' evaluated to "
                    f"{calc_result.pressure_drop} {calc_result.unit} "
                    f"(nominal range: {calc_result.normal_range}) — Status: {calc_result.status}"
                ),
                actor_user_id=user_id,
            )
            await audit_service.append_entry(
                db=db,
                event_type="QUERY_COMPLETE",
                detail=f"Document grounded query completed: {len(doc_chunks)} chunks retrieved, model={selected_model}",
                actor_user_id=user_id,
            )
            await db.commit()

        return QueryResponse(
            status="accepted_stub",
            note=f"Grounded response generated using {len(doc_chunks)} document chunks",
            retrieved_chunks=[],
            citations=citations,
            sources=sources,
            calculation_result=calc_result,
            final_synthesis=answer,
            model_routing=doc_routing,
        )

    # ── Step 4: Plant Manual Retrieval & Query Acceptance ──────
    lower_text = query_text.lower()
    is_plant_related = any(k in lower_text for k in [
        "boiler", "turbine", "reactor", "pump", "valve", "pipe", "plant",
        "sop", "manual", "pressure", "temperature", "drum", "bms", "feedwater",
        "clearance", "actuator", "flange", "gauge", "telemetry"
    ])
    is_coding_task = routing.get("task_type") in ("coding", "debugging")
    if is_coding_task:
        retrieved_chunks = []
    elif has_image_requested and not is_gauge_query(query_text) and not is_plant_related:
        retrieved_chunks = []
    elif is_plant_related or any(k in lower_text for k in ["sop", "manual", "procedure", "spec", "standard"]):
        retrieved_chunks = retrieval_service.retrieve(
            query=query_text,
            operator_clearance=clearance,
        )
    else:
        retrieved_chunks = []


    # Determine equipment unit from query context
    if "reactor" in lower_text:
        unit = "reactor-core-aux"
    elif "turbine" in lower_text:
        unit = "turbine-gen-4"
    elif has_image_requested and not is_gauge_query(body.text):
        unit = "visual-asset"
    elif is_coding_task:
        unit = "sandbox-compute"
    elif routing.get("task_type") == "reasoning" and not is_plant_related:
        unit = "reasoning-core"
    else:
        unit = "boiler-102"

    # ── Step 5: Vision Processing (multimodal asset analysis or dial gauge) ─
    vision_result = None
    vision_analysis = None
    if has_image_requested:
        if is_gauge_query(body.text):
            vision_result = await vision_service.extract_gauge_reading(
                image_data=body.image_data,
                equipment_unit=unit,
            )
        else:
            vision_analysis = await vision_service.analyze_visual_asset(
                image_data=body.image_data,
                prompt=body.text or "Explain what is shown in this image in detail.",
            )

    # ── Step 6: Sandboxed Calculation (deterministic delta-p) ─
    calc_result = None
    if vision_result and vision_result.status == "success" and vision_result.reading is not None:
        calc_result = await calculation_service.compute_differential_pressure(
            inlet_pressure=vision_result.reading,
            outlet_pressure=2.6,
            equipment_unit=unit,
        )
    elif not (has_image_requested and not is_gauge_query(query_text)):
        calc_result = await calculation_service.evaluate_operational_calculation(
            query=query_text,
            equipment_unit=unit,
        )

    # ── Step 7: LangGraph Reasoning Loop & HITL Interruption ─
    plan_result = await planner_service.run_plan(
        query=body.text,
        user_id=str(user_id),
        operator_email=current_user.get("email", ""),
        clearance_level=clearance,
        unit=unit,
        retrieved_docs=[c.model_dump() for c in retrieved_chunks],
        vision_reading=vision_result.reading if (vision_result and vision_result.status == "success") else None,
        pressure_drop=calc_result.pressure_drop if calc_result else None,
        vision_analysis=vision_analysis,
        vision_explanation=vision_analysis.get("explanation") if vision_analysis else None,
        task_type=routing.get("task_type"),
    )

    is_awaiting_approval = bool(plan_result.get("approval_required"))
    thread_id = plan_result.get("thread_id")
    approval_details_dict = plan_result.get("approval_details")

    async with audit_service.audit_transaction(db):
        await audit_service.append_entry(
            db=db,
            event_type="QUERY_SUBMITTED",
            detail=f"Query accepted: {body.text[:200]}",
            actor_user_id=user_id,
        )

        # Audit retrieval chunks accessed with security clearance ratings
        if retrieved_chunks:
            chunk_summary = ", ".join(
                f"[{c.sop_id} {c.unit} L{c.min_clearance}]"
                for c in retrieved_chunks
            )
            audit_detail = (
                f"Retrieved {len(retrieved_chunks)} chunks for clearance {clearance}: "
                f"{chunk_summary}"
            )
        else:
            audit_detail = f"Zero document chunks accessible for clearance {clearance}"

        await audit_service.append_entry(
            db=db,
            event_type="RETRIEVAL_EXECUTED",
            detail=audit_detail,
            actor_user_id=user_id,
        )

        # Step 5 Audit: Vision extraction
        if vision_result:
            if vision_result.status == "success":
                audit_vis_detail = (
                    f"Extracted {vision_result.reading} {vision_result.unit} "
                    f"({vision_result.parameter}, confidence {vision_result.confidence}) "
                    f"— {vision_result.assessment}"
                )
            elif vision_result.status == "invalid_image":
                audit_vis_detail = f"Visual asset rejected: {vision_result.error} — {vision_result.assessment}"
            elif vision_result.status == "extraction_failed":
                audit_vis_detail = f"Extraction failed: {vision_result.error} — {vision_result.assessment}"
            else:
                audit_vis_detail = "No visual asset attached — skipped"

            await audit_service.append_entry(
                db=db,
                event_type="VISION_EXTRACTION",
                detail=audit_vis_detail,
                actor_user_id=user_id,
            )

        # Step 6 Audit: Sandboxed calculation
        if calc_result:
            await audit_service.append_entry(
                db=db,
                event_type="CALCULATION_RESULT",
                detail=(
                    f"Sandboxed formula '{calc_result.formula}' evaluated to "
                    f"{calc_result.pressure_drop} {calc_result.unit} "
                    f"(nominal range: {calc_result.normal_range}) — Status: {calc_result.status}"
                ),
                actor_user_id=user_id,
            )

        # Step 7 Audit: Plan and HITL gate
        if is_awaiting_approval and approval_details_dict:
            await audit_service.append_entry(
                db=db,
                event_type="HITL_REQUIRED",
                detail=(
                    f"Sensitive action '{approval_details_dict['action']}' on target "
                    f"'{approval_details_dict['target']}' requires operator authorization. "
                    f"LangGraph thread {thread_id} paused at HITL gate."
                ),
                actor_user_id=user_id,
            )
            pending_record = PendingApproval(
                thread_id=thread_id,
                requestor_user_id=user_id,
                operator_email=current_user.get("email", ""),
                clearance_level=clearance,
                unit=unit,
                authority=approval_details_dict.get(
                    "authority", "Senior_Engineer (HITL Required)"
                ),
                action=approval_details_dict.get("action", "unknown"),
                target=approval_details_dict.get("target", unit),
                approval_details=approval_details_dict,
                status="PENDING",
            )
            db.add(pending_record)
        else:
            await audit_service.append_entry(
                db=db,
                event_type="PLAN_GENERATED",
                detail=(
                    f"Reasoning loop executed for {unit}: "
                    f"{plan_result.get('action_status', 'COMPLETED')}"
                ),
                actor_user_id=user_id,
            )

        # Query complete
        complete_status = "Awaiting HITL Authorization" if is_awaiting_approval else "Completed"
        detail_items = [f"Query defense pipeline verified ({complete_status}): {len(retrieved_chunks)} docs retrieved"]
        if vision_result:
            if vision_result.status == "success":
                detail_items.append(f"gauge: {vision_result.reading} bar")
            elif vision_result.status == "invalid_image":
                detail_items.append(f"gauge: rejected ({vision_result.error})")
            elif vision_result.status == "extraction_failed":
                detail_items.append(f"gauge: extraction failed ({vision_result.error})")
        if calc_result:
            detail_items.append(f"delta-p: {calc_result.pressure_drop} bar")
        await audit_service.append_entry(
            db=db,
            event_type="QUERY_COMPLETE",
            detail=", ".join(detail_items),
            actor_user_id=user_id,
        )

        await db.commit()

    approval_details_obj = (
        HITLApprovalDetails(**approval_details_dict)
        if approval_details_dict
        else None
    )

    response_status = "awaiting_approval" if is_awaiting_approval else "accepted_stub"
    if is_awaiting_approval:
        response_note = "Sensitive actuator action proposed — workflow paused at HITL gate"
    else:
        note_parts = [f"Retrieved {len(retrieved_chunks)} role-filtered manual chunks"]
        if vision_result:
            if vision_result.status == "success":
                note_parts.append(f"vision reading: {vision_result.reading} bar")
            elif vision_result.status == "invalid_image":
                note_parts.append(f"vision error: {vision_result.error}")
            elif vision_result.status == "extraction_failed":
                note_parts.append(f"vision extraction failed: {vision_result.error}")
        if calc_result:
            note_parts.append(f"calculated delta-p: {calc_result.pressure_drop} bar ({calc_result.status})")
        response_note = ", ".join(note_parts)

    return QueryResponse(
        status=response_status,
        note=response_note,
        retrieved_chunks=retrieved_chunks,
        vision_analysis=vision_result,
        calculation_result=calc_result,
        approval_required=is_awaiting_approval,
        approval_details=approval_details_obj,
        thread_id=thread_id,
        final_synthesis=plan_result.get("synthesis"),
        model_routing=routing,
    )


# ── Server-Sent Events (SSE) Streaming Pipeline ──────────────

import asyncio
import json
import time
from fastapi.responses import StreamingResponse
from app.db.session import async_session_factory


def _sse_event(event_type: str, data: dict) -> str:
    return f"event: {event_type}\ndata: {json.dumps(data)}\n\n"


@router.post(
    "/query/stream",
    summary="Stream defense pipeline execution events via Server-Sent Events (SSE)",
)
async def stream_query(
    body: QueryRequest,
    current_user: dict = Depends(get_current_user),
    x_model_api_key: str | None = Header(None, alias="X-Model-Api-Key"),
    x_model_base_url: str | None = Header(None, alias="X-Model-Base-Url"),
):
    """
    Executes the 8-stage defense pipeline progressively, yielding SSE messages
    for each layer (rate limit, prompt safety, RBAC, retrieval, vision, calculation,
    planner HITL gate, and hash-chain audit write).
    """
    if x_model_api_key:
        settings.LLM_API_KEY = x_model_api_key
    if x_model_base_url:
        settings.LLM_BASE_URL = x_model_base_url

    async def event_generator():
        t0 = time.time()
        query_text = body.get_query_text()
        user_id = uuid.UUID(current_user["sub"])
        clearance = current_user["clearance_level"]
        operator_email = current_user.get("email", "")
        has_image = bool(body.has_image or (body.image_data and str(body.image_data).strip()))

        active_doc_ids = list(body.document_ids or [])
        if not active_doc_ids and body.conversation_id:
            active_doc_ids = document_service.get_conversation_documents(body.conversation_id)
        elif active_doc_ids and body.conversation_id:
            document_service.set_conversation_document(body.conversation_id, active_doc_ids)

        yield _sse_event("init", {
            "query": query_text,
            "clearance": clearance,
            "user": operator_email,
            "has_image": has_image,
            "document_ids": active_doc_ids,
        })
        await asyncio.sleep(0.04)

        # ── Step 1: Rate Limit ─────────────────────────────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "rate-limit",
            "label": "Rate Limit Check",
            "desc": "Token bucket verification",
        })
        allowed, retry_after = rate_limiter.check_rate_limit(user_id)
        if not allowed:
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    entry = await audit_service.append_entry(
                        db=db,
                        event_type="RATE_LIMIT_BLOCK",
                        detail=f"Rate limit exceeded for user {operator_email}",
                        actor_user_id=user_id,
                    )
                    await db.commit()
            block_data = {
                "step": "rate-limit",
                "error": "Rate limit exceeded",
                "reason": f"Retry after {retry_after}s",
                "audit_entry": {"index": entry.idx, "hash": entry.hash, "prev_hash": entry.prev_hash},
            }
            yield _sse_event("step_blocked", block_data)
            yield _sse_event("blocked", block_data)
            return

        elapsed = int((time.time() - t_step) * 1000)
        yield _sse_event("step_complete", {
            "step": "rate-limit",
            "status": "passed",
            "readout": "Token bucket verification: OK",
            "elapsed_ms": elapsed,
        })
        await asyncio.sleep(0.04)

        # ── Step 2: Prompt Safety (PromptGuard) ───────────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "prompt-safety",
            "label": "Prompt Safety Check",
            "desc": "Injection & adversarial scan",
        })
        safe, reason = await prompt_guard.is_safe(query_text)
        if not safe:
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    entry = await audit_service.append_entry(
                        db=db,
                        event_type="PROMPT_SAFETY_BLOCK",
                        detail=f"Prompt rejected by PromptGuard: {reason}",
                        actor_user_id=user_id,
                    )
                    await db.commit()
            block_data = {
                "step": "prompt-safety",
                "error": "Prompt blocked by safety screening",
                "reason": reason,
                "audit_entry": {"index": entry.idx, "hash": entry.hash, "prev_hash": entry.prev_hash},
            }
            yield _sse_event("step_blocked", block_data)
            yield _sse_event("blocked", block_data)
            return

        elapsed = int((time.time() - t_step) * 1000)
        yield _sse_event("step_complete", {
            "step": "prompt-safety",
            "status": "passed",
            "readout": "0 injection patterns detected — CLEAR",
            "elapsed_ms": elapsed,
        })
        await asyncio.sleep(0.04)

        # ── Step 2b: Dynamic Model Routing & Task Classification ──
        if active_doc_ids:
            routing = route_request(query_text, task_type="document")
        else:
            routing = route_request(query_text, has_image=has_image)
        selected_model = body.model or routing["model"]
        yield _sse_event("model_routing", {
            "task_type": routing["task_type"],
            "provider": routing["provider"],
            "model": selected_model,
            "sandboxed": routing.get("sandboxed", False),
            "sovereign_mode": settings.SOVEREIGN_MODE,
        })
        await asyncio.sleep(0.04)

        # ── Step 3: RBAC Clearance Check ──────────────────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "rbac",
            "label": "RBAC Verification",
            "desc": "Role-capability authorization",
        })
        rbac_allowed, required_level = rbac_service.check_access(query_text, clearance)
        if not rbac_allowed:
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    entry = await audit_service.append_entry(
                        db=db,
                        event_type="RBAC_BLOCK",
                        detail=(
                            f"Insufficient clearance: required level {required_level}, "
                            f"user {operator_email} has level {clearance}"
                        ),
                        actor_user_id=user_id,
                    )
                    await db.commit()
            block_data = {
                "step": "rbac",
                "error": "Insufficient clearance",
                "required_level": required_level,
                "current_level": clearance,
                "reason": f"Required clearance Level {required_level}, but operator has Level {clearance}",
                "audit_entry": {"index": entry.idx, "hash": entry.hash, "prev_hash": entry.prev_hash},
            }
            yield _sse_event("step_blocked", block_data)
            yield _sse_event("blocked", block_data)
            return

        elapsed = int((time.time() - t_step) * 1000)
        role_name = current_user.get("role", "Operator")
        yield _sse_event("step_complete", {
            "step": "rbac",
            "status": "passed",
            "readout": f"Clearance: Level {clearance} ✔ Role: {role_name}",
            "elapsed_ms": elapsed,
        })
        await asyncio.sleep(0.04)

        # ── Dedicated Document Grounding RAG Execution Path ─────
        if active_doc_ids:
            t_doc = time.time()
            yield _sse_event("step_start", {
                "step": "doc-retrieval",
                "label": "Document Vector Retrieval",
                "desc": f"Semantic search over {len(active_doc_ids)} document(s) in Qdrant",
            })
            doc_chunks = retrieval_service.retrieve_document_chunks(
                query=query_text,
                user_id=str(user_id),
                document_ids=active_doc_ids,
                top_k=5,
            )
            citations = [
                DocumentCitation(
                    filename=c.filename,
                    page=c.page_number,
                    chunk_id=c.chunk_id,
                    snippet=c.text[:200],
                )
                for c in doc_chunks
            ]
            seen_sources = set()
            sources = []
            for c in doc_chunks:
                s = f"{c.filename} — Page {c.page_number}"
                if s not in seen_sources:
                    seen_sources.add(s)
                    sources.append(s)

            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    await audit_service.append_entry(
                        db=db,
                        event_type="DOCUMENT_RETRIEVED",
                        detail=f"Retrieved {len(doc_chunks)} chunks for documents {active_doc_ids}",
                        actor_user_id=user_id,
                    )
                    await audit_service.append_entry(
                        db=db,
                        event_type="DOCUMENT_QUERY",
                        detail=f"Document query processed: {query_text[:120]} (chunks: {len(doc_chunks)})",
                        actor_user_id=user_id,
                    )
                    await db.commit()

            elapsed_doc = int((time.time() - t_doc) * 1000)
            yield _sse_event("step_complete", {
                "step": "doc-retrieval",
                "status": "passed",
                "readout": f"{len(doc_chunks)} chunks retrieved from {len(active_doc_ids)} active document(s)",
                "chunks": [
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "filename": c.filename,
                        "page_number": c.page_number,
                        "text": c.text,
                        "score": c.score,
                    }
                    for c in doc_chunks
                ],
                "citations": [c.model_dump() for c in citations],
                "sources": sources,
                "elapsed_ms": elapsed_doc,
            })
            await asyncio.sleep(0.04)

            yield _sse_event("step_complete", {
                "step": "vision",
                "status": "skipped",
                "readout": "Document query — vision telemetry skipped",
                "elapsed_ms": 0,
            })
            await asyncio.sleep(0.02)

            # ── Step 6: Sandboxed Calculation ─────────────────────
            t_calc = time.time()
            yield _sse_event("step_start", {
                "step": "calculation",
                "label": "Sandboxed Calculation",
                "desc": "Isolated compute environment",
            })
            calc_result = await calculation_service.evaluate_operational_calculation(
                query=query_text,
                doc_chunks=doc_chunks,
                equipment_unit="boiler-102",
            )
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    await audit_service.append_entry(
                        db=db,
                        event_type="CALCULATION_RESULT",
                        detail=(
                            f"Sandboxed formula '{calc_result.formula}' evaluated to "
                            f"{calc_result.pressure_drop} {calc_result.unit} "
                            f"(nominal range: {calc_result.normal_range}) — Status: {calc_result.status}"
                        ),
                        actor_user_id=user_id,
                    )
                    await db.commit()
            elapsed_calc = max(1, int((time.time() - t_calc) * 1000))
            yield _sse_event("step_complete", {
                "step": "calculation",
                "status": "passed",
                "readout": f"Δp = {calc_result.pressure_drop} bar | Range: {calc_result.normal_range} | {calc_result.status}",
                "calculation": calc_result.model_dump(),
                "elapsed_ms": elapsed_calc,
            })
            await asyncio.sleep(0.04)

            t_infer = time.time()
            yield _sse_event("step_start", {
                "step": "approval",
                "label": "Grounded Model Inference",
                "desc": f"Executing inference via {selected_model}",
            })
            system_prompt, user_prompt = document_service.build_grounded_prompt(
                query=query_text,
                chunks=doc_chunks,
            )
            provider = get_provider(routing["provider"])
            answer = await provider.generate_async(
                model=selected_model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
            elapsed_infer = int((time.time() - t_infer) * 1000)
            yield _sse_event("step_complete", {
                "step": "approval",
                "status": "passed",
                "readout": f"Grounded response generated via {selected_model}",
                "elapsed_ms": elapsed_infer,
            })
            await asyncio.sleep(0.04)

            t_audit = time.time()
            yield _sse_event("step_start", {
                "step": "audit-write",
                "label": "Audit Log Write",
                "desc": "Hash-chain entry commitment",
            })
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    entry = await audit_service.append_entry(
                        db=db,
                        event_type="QUERY_COMPLETE",
                        detail=f"Document grounded query completed: {len(doc_chunks)} chunks retrieved, model={selected_model}",
                        actor_user_id=user_id,
                    )
                    await db.commit()

            elapsed_audit = int((time.time() - t_audit) * 1000)
            audit_payload = {
                "index": entry.idx,
                "hash": entry.hash,
                "prev_hash": entry.prev_hash,
                "timestamp": entry.timestamp.isoformat(),
                "event": entry.event_type,
                "detail": entry.detail,
            }
            yield _sse_event("step_complete", {
                "step": "audit-write",
                "status": "passed",
                "readout": f"Committed to tamper-proof block #{entry.idx} (SHA-256 verified)",
                "entry": audit_payload,
                "elapsed_ms": elapsed_audit,
            })

            yield _sse_event("complete", {
                "status": "completed",
                "retrieved_chunks": [],
                "document_chunks": [
                    {
                        "chunk_id": c.chunk_id,
                        "document_id": c.document_id,
                        "filename": c.filename,
                        "page_number": c.page_number,
                        "text": c.text,
                        "score": c.score,
                    }
                    for c in doc_chunks
                ],
                "citations": [c.model_dump() for c in citations],
                "sources": sources,
                "calculation_result": calc_result.model_dump() if calc_result else None,
                "final_synthesis": answer,
                "model_routing": routing,
                "audit_entry": audit_payload,
                "total_elapsed_ms": int((time.time() - t0) * 1000),
            })
            return

        # ── Step 4: Plant Manual Retrieval ────────────────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "doc-retrieval",
            "label": "Document Retrieval",
            "desc": "Role-filtered manual lookup",
        })

        lower_text = body.text.lower()
        is_plant_related = any(k in lower_text for k in [
            "boiler", "turbine", "reactor", "pump", "valve", "pipe", "plant",
            "sop", "manual", "pressure", "temperature", "drum", "bms", "feedwater",
            "clearance", "actuator", "flange", "gauge", "telemetry"
        ])
        is_coding_task = routing.get("task_type") in ("coding", "debugging")
        if is_coding_task:
            retrieved_chunks = []
        elif has_image and not is_gauge_query(body.text) and not is_plant_related:
            retrieved_chunks = []
        elif is_plant_related or any(k in lower_text for k in ["sop", "manual", "procedure", "spec", "standard"]):
            retrieved_chunks = retrieval_service.retrieve(
                query=body.text,
                operator_clearance=clearance,
            )
        else:
            retrieved_chunks = []

        if "reactor" in lower_text:
            unit = "reactor-core-aux"
        elif "turbine" in lower_text:
            unit = "turbine-gen-4"
        elif is_coding_task:
            unit = "sandbox-compute"
        elif has_image and not is_gauge_query(body.text):
            unit = "visual-asset"
        elif routing.get("task_type") == "reasoning" and not is_plant_related:
            unit = "reasoning-core"
        else:
            unit = "boiler-102"

        async with async_session_factory() as db:
            async with audit_service.audit_transaction(db):
                await audit_service.append_entry(
                    db=db,
                    event_type="QUERY_SUBMITTED",
                    detail=f"Query accepted: {body.text[:200]}",
                    actor_user_id=user_id,
                )
                chunk_summary = ", ".join(
                    f"[{c.sop_id} {c.unit} L{c.min_clearance}]"
                    for c in retrieved_chunks
                )
                await audit_service.append_entry(
                    db=db,
                    event_type="RETRIEVAL_EXECUTED",
                    detail=f"Retrieved {len(retrieved_chunks)} chunks for clearance {clearance}: {chunk_summary}",
                    actor_user_id=user_id,
                )
                await db.commit()

        elapsed = int((time.time() - t_step) * 1000)
        if retrieved_chunks:
            top_chunk = retrieved_chunks[0]
            top_title = top_chunk.title
            top_sop = top_chunk.sop_id
            readout_text = f"{len(retrieved_chunks)} docs matched → Top: {top_sop} {top_title}"
        elif is_coding_task:
            readout_text = "0 plant manuals required (routed to code intelligence sandbox)"
        else:
            readout_text = "0 plant manuals required (general query prompt)"

        yield _sse_event("step_complete", {
            "step": "doc-retrieval",
            "status": "passed",
            "readout": readout_text,
            "chunks": [c.model_dump() for c in retrieved_chunks],
            "elapsed_ms": elapsed,
        })
        await asyncio.sleep(0.04)

        # ── Step 5: Vision Processing (multimodal asset analysis or dial gauge) ─
        t_step = time.time()
        vision_result = None
        vision_analysis = None
        if has_image:
            is_gauge = is_gauge_query(body.text)
            if is_gauge:
                yield _sse_event("step_start", {
                    "step": "vision",
                    "label": "Vision Extraction",
                    "desc": "Multimodal gauge reading",
                })
                vision_result = await vision_service.extract_gauge_reading(
                    image_data=body.image_data,
                    equipment_unit=unit,
                )
                elapsed = int((time.time() - t_step) * 1000)
                if vision_result.status == "success":
                    async with async_session_factory() as db:
                        async with audit_service.audit_transaction(db):
                            await audit_service.append_entry(
                                db=db,
                                event_type="VISION_EXTRACTION",
                                detail=(
                                    f"Extracted {vision_result.reading} {vision_result.unit} "
                                    f"({vision_result.parameter}, confidence {vision_result.confidence}) "
                                    f"— {vision_result.assessment}"
                                ),
                                actor_user_id=user_id,
                            )
                            await db.commit()
                    yield _sse_event("step_complete", {
                        "step": "vision",
                        "status": "passed",
                        "readout": f"Gauge: {vision_result.reading} bar inlet | Confidence: {vision_result.confidence}",
                        "vision": vision_result.model_dump(),
                        "elapsed_ms": elapsed,
                    })
                elif vision_result.status == "invalid_image":
                    async with async_session_factory() as db:
                        async with audit_service.audit_transaction(db):
                            await audit_service.append_entry(
                                db=db,
                                event_type="VISION_EXTRACTION",
                                detail=f"Visual asset rejected: {vision_result.error} — {vision_result.assessment}",
                                actor_user_id=user_id,
                            )
                            await db.commit()
                    yield _sse_event("step_complete", {
                        "step": "vision",
                        "status": "failed",
                        "readout": f"Image rejected: {vision_result.error}",
                        "vision": vision_result.model_dump(),
                        "elapsed_ms": elapsed,
                    })
                elif vision_result.status == "extraction_failed":
                    async with async_session_factory() as db:
                        async with audit_service.audit_transaction(db):
                            await audit_service.append_entry(
                                db=db,
                                event_type="VISION_EXTRACTION",
                                detail=f"Extraction failed: {vision_result.error} — {vision_result.assessment}",
                                actor_user_id=user_id,
                            )
                            await db.commit()
                    yield _sse_event("step_complete", {
                        "step": "vision",
                        "status": "failed",
                        "readout": f"Extraction failed: {vision_result.error}",
                        "vision": vision_result.model_dump(),
                        "elapsed_ms": elapsed,
                    })
                else:
                    yield _sse_event("step_complete", {
                        "step": "vision",
                        "status": "skipped",
                        "readout": "No visual asset attached — skipped",
                        "vision": vision_result.model_dump(),
                        "elapsed_ms": elapsed,
                    })
            else:
                # General Multimodal Visual Asset Analysis (Qwen2.5-VL)
                yield _sse_event("step_start", {
                    "step": "vision",
                    "label": "Multimodal Visual Analysis",
                    "desc": "Qwen2.5-VL visual asset breakdown",
                })
                vision_analysis = await vision_service.analyze_visual_asset(
                    image_data=body.image_data,
                    prompt=body.text or "Explain what is shown in this image in detail.",
                )
                elapsed = int((time.time() - t_step) * 1000)
                if vision_analysis.get("status") == "success":
                    doc_type = vision_analysis.get("doc_type", "image")
                    doc_label = (
                        "PDF Document" if doc_type == "pdf_document"
                        else "PDF Visual Diagram" if doc_type == "pdf_diagram"
                        else "Structured Document" if doc_type == "text_document"
                        else "Multimodal Visual Asset"
                    )
                    model_label = vision_analysis.get("model", "Qwen2.5-VL")

                    async with async_session_factory() as db:
                        async with audit_service.audit_transaction(db):
                            await audit_service.append_entry(
                                db=db,
                                event_type="VISION_ANALYSIS",
                                detail=f"{doc_label} analysis complete ({model_label})",
                                actor_user_id=user_id,
                            )
                            await db.commit()

                    expl = vision_analysis.get("explanation") or ""
                    first_line = next((line.strip("#* -") for line in expl.split("\n") if line.strip()), f"{doc_label} analyzed")
                    preview = (first_line[:75] + "...") if len(first_line) > 75 else first_line

                    yield _sse_event("step_complete", {
                        "step": "vision",
                        "status": "passed",
                        "readout": f"{doc_label} analyzed ({model_label.split('/')[-1]}) — {preview}",
                        "vision_analysis": vision_analysis,
                        "elapsed_ms": elapsed,
                    })
                else:
                    err_msg = vision_analysis.get("error", "Failed to analyze visual asset")
                    yield _sse_event("step_complete", {
                        "step": "vision",
                        "status": "failed",
                        "readout": f"Visual analysis error: {err_msg}",
                        "vision_analysis": vision_analysis,
                        "elapsed_ms": elapsed,
                    })
        else:
            yield _sse_event("step_complete", {
                "step": "vision",
                "status": "skipped",
                "readout": "No visual asset attached — skipped",
                "elapsed_ms": 0,
            })
        await asyncio.sleep(0.04)

        # ── Step 6: Sandboxed Calculation ─────────────────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "calculation",
            "label": "Sandboxed Calculation",
            "desc": "Isolated compute environment",
        })
        calc_result = None
        if vision_result and vision_result.status == "success" and vision_result.reading is not None:
            calc_result = await calculation_service.compute_differential_pressure(
                inlet_pressure=vision_result.reading,
                outlet_pressure=2.6,
                equipment_unit=unit,
            )
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    await audit_service.append_entry(
                        db=db,
                        event_type="CALCULATION_RESULT",
                        detail=(
                            f"Sandboxed formula '{calc_result.formula}' evaluated to "
                            f"{calc_result.pressure_drop} {calc_result.unit} "
                            f"(nominal range: {calc_result.normal_range}) — Status: {calc_result.status}"
                        ),
                        actor_user_id=user_id,
                    )
                    await db.commit()
            elapsed = int((time.time() - t_step) * 1000)
            yield _sse_event("step_complete", {
                "step": "calculation",
                "status": "passed",
                "readout": f"Δp = {calc_result.pressure_drop} bar | Range: {calc_result.normal_range} | {calc_result.status}",
                "calculation": calc_result.model_dump(),
                "elapsed_ms": elapsed,
            })
        elif has_image and not is_gauge_query(body.text):
            elapsed = int((time.time() - t_step) * 1000)
            calc_msg = "Calculation skipped: visual asset is a conceptual diagram/workflow, not an operational pressure gauge"
            yield _sse_event("step_complete", {
                "step": "calculation",
                "status": "skipped",
                "readout": calc_msg,
                "calculation": None,
                "elapsed_ms": elapsed,
            })
        else:
            calc_result = await calculation_service.evaluate_operational_calculation(
                query=body.text,
                equipment_unit=unit,
            )
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    await audit_service.append_entry(
                        db=db,
                        event_type="CALCULATION_RESULT",
                        detail=(
                            f"Sandboxed formula '{calc_result.formula}' evaluated to "
                            f"{calc_result.pressure_drop} {calc_result.unit} "
                            f"(nominal range: {calc_result.normal_range}) — Status: {calc_result.status}"
                        ),
                        actor_user_id=user_id,
                    )
                    await db.commit()
            elapsed = max(1, int((time.time() - t_step) * 1000))
            yield _sse_event("step_complete", {
                "step": "calculation",
                "status": "passed",
                "readout": f"Δp = {calc_result.pressure_drop} bar | Range: {calc_result.normal_range} | {calc_result.status}",
                "calculation": calc_result.model_dump(),
                "elapsed_ms": elapsed,
            })
        await asyncio.sleep(0.04)

        # ── Step 7: Reasoning Loop & HITL Interruption ────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "approval",
            "label": "Human Approval (HITL)",
            "desc": "Sensitive action authorization",
        })
        plan_result = await planner_service.run_plan(
            query=body.text,
            user_id=str(user_id),
            operator_email=operator_email,
            clearance_level=clearance,
            unit=unit,
            retrieved_docs=[c.model_dump() for c in retrieved_chunks],
            vision_reading=vision_result.reading if (vision_result and vision_result.status == "success") else None,
            pressure_drop=calc_result.pressure_drop if calc_result else None,
            vision_analysis=vision_analysis,
            vision_explanation=vision_analysis.get("explanation") if vision_analysis else None,
            task_type=routing.get("task_type"),
        )

        is_awaiting = bool(plan_result.get("approval_required"))
        thread_id = plan_result.get("thread_id")
        approval_details = plan_result.get("approval_details")

        if is_awaiting and approval_details:
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    entry = await audit_service.append_entry(
                        db=db,
                        event_type="HITL_REQUIRED",
                        detail=(
                            f"Sensitive action '{approval_details['action']}' on target "
                            f"'{approval_details['target']}' requires operator authorization. "
                            f"LangGraph thread {thread_id} paused at HITL gate."
                        ),
                        actor_user_id=user_id,
                    )
                    pending_record = PendingApproval(
                        thread_id=thread_id,
                        requestor_user_id=user_id,
                        operator_email=operator_email,
                        clearance_level=clearance,
                        unit=unit,
                        authority=approval_details.get(
                            "authority", "Senior_Engineer (HITL Required)"
                        ),
                        action=approval_details.get("action", "unknown"),
                        target=approval_details.get("target", unit),
                        approval_details=approval_details,
                        status="PENDING",
                    )
                    db.add(pending_record)
                    await db.commit()
            elapsed = int((time.time() - t_step) * 1000)
            yield _sse_event("step_complete", {
                "step": "approval",
                "status": "awaiting",
                "readout": "Awaiting Human-in-the-Loop authorization...",
                "thread_id": thread_id,
                "approval_details": approval_details,
                "elapsed_ms": elapsed,
            })
            yield _sse_event("approval_required", {
                "step": "approval",
                "status": "awaiting_approval",
                "thread_id": thread_id,
                "approval_details": approval_details,
                "retrieved_chunks": [c.model_dump() for c in retrieved_chunks],
                "vision_analysis": vision_result.model_dump() if vision_result else None,
                "calculation_result": calc_result.model_dump() if calc_result else None,
                "model_routing": routing,
                "audit_entry": {"index": entry.idx, "hash": entry.hash, "prev_hash": entry.prev_hash},
            })
            return
        else:
            async with async_session_factory() as db:
                async with audit_service.audit_transaction(db):
                    await audit_service.append_entry(
                        db=db,
                        event_type="PLAN_GENERATED",
                        detail=(
                            f"Reasoning loop executed for {unit}: "
                            f"{plan_result.get('action_status', 'COMPLETED')}"
                        ),
                        actor_user_id=user_id,
                    )
                    await db.commit()
            elapsed = int((time.time() - t_step) * 1000)
            yield _sse_event("step_complete", {
                "step": "approval",
                "status": "skipped",
                "readout": "No sensitive actions — auto-cleared",
                "elapsed_ms": elapsed,
            })
            await asyncio.sleep(0.04)

        # ── Step 8: Audit Log Write ───────────────────────────
        t_step = time.time()
        yield _sse_event("step_start", {
            "step": "audit-write",
            "label": "Audit Log Write",
            "desc": "Hash-chain entry commitment",
        })
        async with async_session_factory() as db:
            async with audit_service.audit_transaction(db):
                entry = await audit_service.append_entry(
                    db=db,
                    event_type="QUERY_COMPLETE",
                    detail=(
                        f"Query defense pipeline verified (Completed): {len(retrieved_chunks)} docs retrieved"
                        + (f", gauge: {vision_result.reading} bar" if (vision_result and vision_result.status == "success") else "")
                        + (f", delta-p: {calc_result.pressure_drop} bar" if calc_result else "")
                    ),
                    actor_user_id=user_id,
                )
                await db.commit()

        elapsed = int((time.time() - t_step) * 1000)
        audit_payload = {
            "index": entry.idx,
            "hash": entry.hash,
            "prev_hash": entry.prev_hash,
            "timestamp": entry.timestamp.isoformat(),
            "event": entry.event_type,
            "detail": entry.detail,
        }
        yield _sse_event("step_complete", {
            "step": "audit-write",
            "status": "passed",
            "readout": f"Committed to tamper-proof block #{entry.idx} (SHA-256 verified)",
            "entry": audit_payload,
            "elapsed_ms": elapsed,
        })

        # ── Complete Event ────────────────────────────────────
        code_exec = plan_result.get("code_execution") or {}
        code_str = code_exec.get("code")
        output_str = code_exec.get("output")
        yield _sse_event("complete", {
            "status": "completed",
            "retrieved_chunks": [c.model_dump() for c in retrieved_chunks],
            "vision_analysis": vision_result.model_dump() if vision_result else vision_analysis,
            "calculation_result": calc_result.model_dump() if calc_result else None,
            "approval_required": False,
            "thread_id": thread_id,
            "final_synthesis": plan_result.get("synthesis"),
            "code": code_str,
            "execution_result": output_str,
            "code_execution": code_exec if code_str else None,
            "model_routing": routing,
            "audit_entry": audit_payload,
            "total_elapsed_ms": int((time.time() - t0) * 1000),
        })

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )




