import asyncio
import json
import logging
import os
import uuid

from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

import backend.actions as _actions_module
from backend.actions import ActionSession, get_calendar_service
from backend.email_summary import init_gmail_creds, send_meeting_summary
from backend.contracts import (
    StatusPayload,
    SentimentPayload,
    TranscriptPayload,
    UnderstandingResult,
    has_action_items,
    make_ws_message,
)
from backend.documents import MARKETING_BRIEF, REVISION_MODEL
from backend.infra import provision_container, provision_infrastructure
from backend.understanding import TranscriptBuffer, UNDERSTANDING_MODEL
from backend.session_state import session_registry
from backend.vision import analyze_frame
from backend.voice import VoicePipeline
from backend.sponsor_digitalocean import do_available, do_archive_meeting, kb_stats
from backend.sponsor_railtracks import get_flow_status, run_meeting_flow
from backend.bigquery import bq_available, generate_report, get_report, setup_dataset, run_query, nl_to_sql

app = FastAPI(title="Meeting Agent")


class NoCacheMiddleware(BaseHTTPMiddleware):
    """Prevent browsers from serving stale static files after deploys."""
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.url.path in ("/", "/chat") or request.url.path.startswith("/static"):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheMiddleware)
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.on_event("startup")
async def _validate_models():
    """Fail fast at startup if Gemini models are unreachable (uses models.get, no RPM cost)."""
    from google import genai
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        logger.warning("GOOGLE_API_KEY not set — skipping model validation")
        return
    client = genai.Client(api_key=api_key)
    for model_name in {UNDERSTANDING_MODEL, REVISION_MODEL}:
        try:
            model_info = await client.aio.models.get(model=model_name)
            logger.info("Model validated: %s ✓ (display: %s)", model_name, model_info.display_name)
        except Exception as exc:
            logger.error("MODEL_VALIDATION_FAIL: %s — %s", model_name, exc)
            raise SystemExit(f"Model {model_name} is not available: {exc}")

# Calendar service — initialized once at startup from env; None if not configured
calendar_service = None
_token_json = os.getenv("GOOGLE_CALENDAR_TOKEN_JSON")
if _token_json:
    try:
        calendar_service = get_calendar_service(json.loads(_token_json))
        logger.info("Google Calendar service initialized.")
        if _actions_module._calendar_creds:
            init_gmail_creds(_actions_module._calendar_creds)
            logger.info("Gmail credentials initialized (shared with Calendar).")
    except Exception as exc:
        logger.warning("Calendar service init failed (continuing without it): %s", exc)


@app.get("/health")
async def health():
    return JSONResponse({"status": "ok"})


@app.get("/")
async def index():
    return FileResponse(
        "static/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.get("/chat")
async def chat_page():
    return FileResponse(
        "static/chat.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        },
    )


@app.post("/api/chat")
async def api_chat(request: Request):
    """Query the DigitalOcean Knowledge Base about past meeting data."""
    body = await request.json()
    message = body.get("message", "").strip()
    if not message:
        return JSONResponse({"error": "message is required"}, status_code=400)

    if not do_available():
        return JSONResponse({
            "response": (
                "The DigitalOcean Knowledge Base is not configured. "
                "Please set DO_AGENT_ENDPOINT and DO_AGENT_ACCESS_KEY "
                "environment variables to enable meeting memory."
            )
        })

    from backend.sponsor_digitalocean import _get_client
    client = _get_client()
    if client is None:
        return JSONResponse({
            "response": "Unable to connect to the knowledge base. Please check your configuration."
        })

    try:
        response = await client.chat.completions.create(
            model="n/a",
            messages=[{"role": "user", "content": message}],
        )
        answer = response.choices[0].message.content or "No relevant information found."
        return JSONResponse({"response": answer})
    except Exception as exc:
        logger.error("Chat API error: %s", exc)
        return JSONResponse(
            {"error": "Failed to query knowledge base. Please try again."},
            status_code=500,
        )


@app.websocket("/ws/audio")
async def websocket_audio(ws: WebSocket):
    await ws.accept()
    session_id = ws.query_params.get("session_id") or str(uuid.uuid4())
    sid = session_id[:8]  # short ID for log readability
    logger.info("[%s] WebSocket session started", sid)
    session_state = session_registry.ensure(session_id)
    session_state.ws_send = None  # set after send() is defined
    pipeline = VoicePipeline()
    buf      = TranscriptBuffer()
    session  = ActionSession(session_id=session_id)
    _transcript_segments: list[str] = []
    _all_actions: list[dict] = []
    _session_start = asyncio.get_event_loop().time()

    async def send(msg: dict) -> bool:
        """Send JSON to client. Returns False if client is gone."""
        try:
            await ws.send_text(json.dumps(msg))
            return True
        except Exception:
            return False

    session_state.ws_send = send

    _bg_tasks: set[asyncio.Task] = set()  # strong refs prevent GC before completion

    async def _dispatch(understanding: UnderstandingResult) -> None:
        try:
            face = session_state.vision.latest_sentiment()

            async def _on_action(action: dict) -> None:
                if action["type"] == "document":
                    payload = action["payload"]
                    if isinstance(payload, dict) and payload.get("content"):
                        session_state.document_content = payload["content"]
                await send(make_ws_message("action", action))
                await send(make_ws_message("pipeline", {"event": "action_dispatched", "action_type": action["type"]}))

            actions = await session.dispatch(
                understanding,
                has_calendar=calendar_service is not None,
                face_sentiment=face,
                on_action=_on_action,
            )
            _all_actions.extend(actions)

            # After actions are dispatched, update Railtracks flow status
            flow_status = get_flow_status()
            flow_status["actions_dispatched"] = len(actions)
            await send(make_ws_message("flow_status", {"agents": {
                "TranscriptAnalyzer": "running" if understanding else "idle",
                "SentimentMonitor": "running",
                "ActionExecutor": "running" if actions else "idle",
                "MeetingMemory": "running",
            }}))

            # Infrastructure provisioning — fire-and-forget per D-04
            for infra_req in understanding.get("infrastructure_requests", []):
                if infra_req.get("sentiment") == "positive":
                    async def _provision_and_report(req):
                        result = await provision_infrastructure(req, on_action=_on_action)
                        if result:
                            await _on_action(result)
                    t = asyncio.create_task(_provision_and_report(infra_req))
                    _bg_tasks.add(t)
                    t.add_done_callback(_bg_tasks.discard)
                else:
                    logger.info("[%s] Infra request blocked (sentiment=%s): %s",
                                sid, infra_req.get("sentiment"), infra_req.get("name", "?"))
        except Exception as exc:
            logger.error("[%s] _dispatch failed: %s", sid, exc)

    async def on_interim(text: str) -> None:
        """Send interim (partial) transcript to client for low-latency display."""
        await send(make_ws_message("pipeline", {"event": "stt_start"}))
        await send(make_ws_message("interim", {"text": text}))

    async def on_transcript(text: str) -> None:
        """Send final transcript to client and process through understanding."""
        _transcript_segments.append(text)
        await send(make_ws_message("pipeline", {"event": "stt_result", "stats": {"words": len(text.split())}}))
        transcript_payload: TranscriptPayload = {"text": text}
        if not await send(make_ws_message("transcript", transcript_payload)):
            return
        status_payload: StatusPayload = {"text": f"STT: {pipeline.active_stt}"}
        await send(make_ws_message("status", status_payload))

        async def _handle_understanding(understanding: UnderstandingResult) -> None:
            await send(make_ws_message("pipeline", {"event": "understanding_result", "stats": {
                "sentiment": understanding.get("sentiment", "neutral"),
                "actions": sum(len(understanding.get(k, [])) for k in ("commitments", "agreements", "meeting_requests", "document_revisions", "infrastructure_requests"))
            }}))
            logger.info("[%s] Understanding result: %s", sid, json.dumps(understanding)[:300])
            sentiment_payload: SentimentPayload = {"value": understanding.get("sentiment", "neutral")}
            await send(make_ws_message("sentiment", sentiment_payload))
            if has_action_items(understanding):
                logger.info("Dispatching actions for: %s", [k for k in ("commitments", "agreements", "meeting_requests", "document_revisions") if understanding.get(k)])
                t = asyncio.create_task(_dispatch(understanding))
                _bg_tasks.add(t)
                t.add_done_callback(_bg_tasks.discard)

        face = session_state.vision.latest_sentiment()
        await send(make_ws_message("pipeline", {"event": "understanding_start"}))
        await send(make_ws_message("flow_status", {"agents": {
            "TranscriptAnalyzer": "running",
            "SentimentMonitor": "running",
            "ActionExecutor": "idle",
            "MeetingMemory": "idle",
        }}))
        understanding = await buf.process(text, face, on_result=_handle_understanding)
        if understanding is None:  # None = still buffering or cooldown pending
            return
        await _handle_understanding(understanding)

    async def _watch_session() -> None:
        """Notify client and close connection if Gemini Live session dies unexpectedly.
        Closing the WS triggers ws.onclose on the client → stopMeeting() → UI resets."""
        try:
            await pipeline.wait()
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Gemini Live session died unexpectedly: %s", exc)
            await send(make_ws_message("status", {"text": "Voice error — reload to reconnect"}))
            try:
                await ws.close(code=1011, reason="Voice pipeline error")
            except Exception:
                pass

    _watcher: asyncio.Task | None = None
    client_disconnected = False
    try:
        try:
            await pipeline.start_session(on_transcript, on_interim=on_interim)
        except Exception as exc:
            logger.error("Voice pipeline failed to start: %s", exc)
            await send(make_ws_message("status", {"text": f"Voice error: {exc}"}))
            await ws.close(code=1011, reason="Voice pipeline startup failed")
            return
        await send(make_ws_message("status", {"text": f"STT: {pipeline.active_stt}"}))
        _watcher = asyncio.create_task(_watch_session())

        # Receive loop: binary = audio, text = JSON commands (e.g. {"type":"stop"})
        while True:
            data = await ws.receive()
            if data["type"] == "websocket.disconnect":
                client_disconnected = True
                break
            if "bytes" in data and data["bytes"]:
                await pipeline.send_audio(data["bytes"])
            elif "text" in data and data["text"]:
                try:
                    cmd = json.loads(data["text"])
                    if cmd.get("type") == "stop":
                        logger.info("Client requested meeting stop — finishing actions...")
                        break
                except json.JSONDecodeError:
                    pass
    except WebSocketDisconnect:
        logger.info("Client disconnected.")
        client_disconnected = True
    finally:
        if _watcher and not _watcher.done():
            _watcher.cancel()
            try:
                await _watcher
            except asyncio.CancelledError:
                pass

        # Stop pipeline first to prevent Gemini reconnection attempts
        await pipeline.stop()

        # Force-flush any remaining transcript so short meetings still get actions
        try:
            face = session_state.vision.latest_sentiment()
            logger.info("[%s] Force-flushing buffer at meeting end...", sid)
            understanding = await buf.flush(face)
            if understanding is not None:
                logger.info("[%s] Force-flush result: %s", sid, json.dumps(understanding)[:500])
                sentiment_payload: SentimentPayload = {"value": understanding.get("sentiment", "neutral")}
                await send(make_ws_message("sentiment", sentiment_payload))
                if has_action_items(understanding):
                    logger.info("[%s] Dispatching actions from force-flush", sid)
                    await _dispatch(understanding)
                else:
                    logger.warning("[%s] Force-flush returned understanding but NO action items", sid)
            else:
                logger.info("[%s] Force-flush returned None (buffer was empty — cooldown may have already flushed)", sid)
        except Exception as exc:
            logger.error("[%s] Final flush/dispatch failed: %s", sid, exc)

        buf.reset()

        # Wait for pending action dispatches (Slack, Calendar) to complete.
        # The WS is still open (unless client disconnected), so action results
        # will be sent to the client and appear on the summary screen.
        if _bg_tasks:
            await asyncio.gather(*_bg_tasks, return_exceptions=True)

        # Archive meeting to DigitalOcean Knowledge Base
        if _transcript_segments and do_available():
            try:
                transcript_docs = [{"text": seg} for seg in _transcript_segments]
                archive_result = await do_archive_meeting(session_id, transcript_docs, _all_actions)
                if archive_result:
                    logger.info("[%s] Meeting archived to DO Knowledge Base", sid)
                    if not client_disconnected:
                        await send(make_ws_message("memory_status", {"status": "archived", "session_id": session_id}))
            except Exception as exc:
                logger.error("[%s] DO archive failed: %s", sid, exc)

        # Send meeting summary email
        if _transcript_segments:
            duration_s = asyncio.get_event_loop().time() - _session_start
            try:
                email_result = await send_meeting_summary(
                    duration_s=duration_s,
                    transcript_segments=_transcript_segments,
                    task_log=session.task_log,
                    action_results=_all_actions,
                )
                if not client_disconnected:
                    await send(make_ws_message("action", email_result))
            except Exception as exc:
                logger.error("[%s] Summary email failed: %s", sid, exc)

        # Signal client that all background work is done
        if not client_disconnected:
            await send(make_ws_message("done"))

        logger.info("[%s] Session cleaned up. Tasks logged: %d", sid, len(session.task_log))
        session_state.ws_send = None
        session_registry.discard(session_id)


_MAX_FRAME_BYTES = 5 * 1024 * 1024  # 5 MB


@app.get("/api/document")
async def api_document(request: Request):
    session_id = request.query_params.get("session_id")
    session_state = session_registry.get(session_id)
    return JSONResponse({
        "title": session_state.document_title if session_state else "Product Launch Marketing Brief",
        "content": session_state.document_content if session_state else MARKETING_BRIEF,
        "status": session_state.document_status if session_state else "DRAFT",
    })


@app.post("/api/frame")
async def api_frame(request: Request):
    session_id = request.query_params.get("session_id")
    session_state = session_registry.get(session_id)
    content_length = int(request.headers.get("content-length", 0))
    if content_length > _MAX_FRAME_BYTES:
        return JSONResponse({"error": "frame too large"}, status_code=413)
    frame_bytes = await request.body()
    if len(frame_bytes) > _MAX_FRAME_BYTES:
        return JSONResponse({"error": "frame too large"}, status_code=413)
    result = await analyze_frame(frame_bytes, session_state.vision if session_state else None)
    if result and session_state and session_state.ws_send:
        try:
            await session_state.ws_send(make_ws_message("pipeline", {
                "event": "vision_result",
                "stats": {
                    "sentiment": result.get("sentiment", "neutral"),
                    "score": round(result.get("engagement", 0) or 0, 2)
                }
            }))
        except Exception:
            pass  # WS may be closed; vision result still returned via REST
    return JSONResponse(result or {})


@app.post("/api/provision-container")
async def api_provision_container(request: Request):
    """Provision a Cloud Run container via Terraform. Accepts JSON body with container config."""
    body = await request.json()
    req = {
        "name": body.get("name", "container"),
        "image": body.get("image", "us-docker.pkg.dev/cloudrun/container/hello"),
        "region": body.get("region", "us-central1"),
        "port": body.get("port", 8080),
        "memory": body.get("memory", "512Mi"),
        "cpu": body.get("cpu", "1"),
        "min_instances": body.get("min_instances", 0),
        "max_instances": body.get("max_instances", 1),
        "sentiment": "positive",
    }
    result = await provision_container(req)
    return JSONResponse(result)


# -- Sponsor integration endpoints ------------------------------------------

@app.get("/api/sponsors/status")
async def sponsors_status():
    """Return which sponsor integrations are active."""
    return JSONResponse({
        "assistant_ui": True,
        "digitalocean": do_available(),
        "railtracks": True,  # always available (uses existing GOOGLE_API_KEY)
        "bigquery": bq_available(),
    })


@app.post("/api/chat")
async def api_chat(request: Request):
    """Chat with meeting knowledge base via DO Agent."""
    body = await request.json()
    message = body.get("message", "")
    if not message:
        return JSONResponse({"error": "message required"}, status_code=400)

    from backend.sponsor_digitalocean import do_chat
    if not do_available():
        return JSONResponse({"error": "Knowledge base not configured"}, status_code=503)

    response = await do_chat(message)
    return JSONResponse({"response": response})


@app.get("/api/kb/status")
async def kb_status():
    """Get Knowledge Base status — documents loaded, availability."""
    return JSONResponse(kb_stats())


@app.get("/api/railtracks/status")
async def railtracks_status():
    """Get Railtracks agent flow status for the visualizer."""
    return JSONResponse(get_flow_status())


# -- BigQuery / Report endpoints -----------------------------------------------


@app.post("/api/bigquery/setup")
async def bigquery_setup():
    """Create BigQuery dataset, table, and seed sample marketing data."""
    if not bq_available():
        return JSONResponse({"error": "GOOGLE_CLOUD_PROJECT not set"}, status_code=503)
    try:
        status = await setup_dataset()
        return JSONResponse({"status": status})
    except Exception as exc:
        logger.error("BigQuery setup failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.post("/api/bigquery/query")
async def bigquery_query(request: Request):
    """Run a natural-language query against BigQuery marketing data."""
    if not bq_available():
        return JSONResponse({"error": "GOOGLE_CLOUD_PROJECT not set"}, status_code=503)
    body = await request.json()
    query = body.get("query", "").strip()
    if not query:
        return JSONResponse({"error": "query is required"}, status_code=400)
    try:
        report = await generate_report(query)
        # Build report URL relative to current host
        report_id = report["report_id"]
        report["report_url"] = f"/report/{report_id}"
        return JSONResponse(report)
    except Exception as exc:
        logger.error("BigQuery query failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@app.get("/report/{report_id}")
async def view_report(report_id: str):
    """Serve an LLM-generated HTML report with charts."""
    from fastapi.responses import HTMLResponse
    report = get_report(report_id)
    if not report:
        return HTMLResponse("<h1>Report not found</h1><p>This report may have expired.</p>", status_code=404)
    return HTMLResponse(report["html"])


@app.post("/api/bigquery/sql")
async def bigquery_sql(request: Request):
    """Execute raw SQL against BigQuery (for advanced users / testing)."""
    if not bq_available():
        return JSONResponse({"error": "GOOGLE_CLOUD_PROJECT not set"}, status_code=503)
    body = await request.json()
    sql = body.get("sql", "").strip()
    if not sql:
        return JSONResponse({"error": "sql is required"}, status_code=400)
    try:
        results = await run_query(sql)
        return JSONResponse({"results": results, "row_count": len(results)})
    except Exception as exc:
        logger.error("BigQuery SQL failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)
