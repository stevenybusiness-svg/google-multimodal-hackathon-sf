"""Railtracks agentic framework integration for the meeting agent.

Wraps understanding + action pipeline as a Railtracks multi-agent Flow with
specialist nodes and sentiment-gated routing.  If railtracks cannot import
(Python <3.10), a simulation provides the identical public API.
"""
from __future__ import annotations

import asyncio, logging, time
from typing import Any, Callable

logger = logging.getLogger(__name__)

# -- Probe for native railtracks -------------------------------------------
_RT_AVAILABLE = False
try:
    import railtracks as rt
    _RT_AVAILABLE = True
    logger.info("railtracks %s loaded (native)", rt.__version__)
except Exception:
    logger.info("railtracks unavailable — simulation mode")

def railtracks_available() -> bool:
    """Return True if railtracks can be imported."""
    return _RT_AVAILABLE

# -- Shared flow state (singleton) -----------------------------------------
_NEGATIVE_FACES = {"anger", "sadness"}
_state_lock = asyncio.Lock()
_flow_state: dict[str, Any] = {
    "mode": "native" if _RT_AVAILABLE else "simulation",
    "nodes_active": set(), "actions_dispatched": 0,
    "routing_decisions": [], "last_run_ms": 0.0, "total_runs": 0,
}

async def _record(node: str, decision: str, ms: float) -> None:
    async with _state_lock:
        decs = _flow_state["routing_decisions"]
        decs.append({"node": node, "decision": decision, "elapsed_ms": round(ms, 1)})
        if len(decs) > 50:
            _flow_state["routing_decisions"] = decs[-50:]

# -- Specialist nodes -------------------------------------------------------
class TranscriptAnalyzer:
    """Takes transcript text, returns structured extraction via understand_fn."""
    name = "TranscriptAnalyzer"
    def __init__(self, fn: Callable) -> None:
        self._fn = fn
    async def run(self, transcript: str, face_sentiment: dict | None = None) -> dict:
        t0 = time.monotonic()
        result = await self._fn(transcript, face_sentiment)
        await _record(self.name, "extracted", (time.monotonic() - t0) * 1000)
        return result

class SentimentMonitor:
    """Classifies face+text sentiment; decides proceed / risk_flag / block."""
    name = "SentimentMonitor"
    async def run(self, face_sentiment: dict | None = None,
                  text_sentiment: str = "neutral") -> dict:
        t0 = time.monotonic()
        face = (face_sentiment or {}).get("sentiment", "neutral")
        risk = text_sentiment in ("negative", "uncertain") or face in _NEGATIVE_FACES
        blocked = (text_sentiment == "negative"
                   or (text_sentiment == "uncertain" and face in _NEGATIVE_FACES))
        decision = "block" if blocked else ("risk_flag" if risk else "proceed")
        await _record(self.name, decision, (time.monotonic() - t0) * 1000)
        return {"face": face, "text": text_sentiment, "risk": risk,
                "blocked": blocked, "decision": decision}

class ActionExecutor:
    """Dispatches understanding to Slack/Calendar/tasks via dispatch_fn."""
    name = "ActionExecutor"
    def __init__(self, fn: Callable) -> None:
        self._fn = fn
    async def run(self, understanding: dict, blocked: bool = False) -> list[dict]:
        t0 = time.monotonic()
        if blocked:
            await _record(self.name, "blocked_by_sentiment", (time.monotonic() - t0) * 1000)
            return []
        actions = await self._fn(understanding)
        count = len(actions) if isinstance(actions, list) else 0
        await _record(self.name, f"dispatched_{count}", (time.monotonic() - t0) * 1000)
        async with _state_lock:
            _flow_state["actions_dispatched"] += count
        return actions if isinstance(actions, list) else []

class MeetingMemory:
    """Accumulates context across the meeting session."""
    name = "MeetingMemory"
    _KEYS = ("commitments", "agreements", "meeting_requests",
             "document_revisions", "infrastructure_requests")
    def __init__(self) -> None:
        self._history: list[dict] = []
    async def run(self, understanding: dict, sentiment: dict,
                  actions: list[dict]) -> dict:
        t0 = time.monotonic()
        entry = {
            "ts": time.time(),
            "sentiment": sentiment.get("decision", "unknown"),
            "items_extracted": sum(len(understanding.get(k, [])) for k in self._KEYS),
            "actions_fired": len(actions),
        }
        self._history.append(entry)
        if len(self._history) > 100:
            self._history = self._history[-100:]
        await _record(self.name, "stored", (time.monotonic() - t0) * 1000)
        return {"history_len": len(self._history), "latest": entry}

# -- Flow -------------------------------------------------------------------
_flow_instance: _MeetingFlow | None = None

class _MeetingFlow:
    """Multi-agent flow (simulated or native railtracks wrapper)."""
    def __init__(self, understand_fn: Callable, dispatch_fn: Callable) -> None:
        self.analyzer = TranscriptAnalyzer(understand_fn)
        self.sentiment = SentimentMonitor()
        self.executor = ActionExecutor(dispatch_fn)
        self.memory = MeetingMemory()
        nodes = [self.analyzer, self.sentiment, self.executor, self.memory]
        logger.info("MeetingFlow created (%s): %s", _flow_state["mode"],
                     ", ".join(n.name for n in nodes))

def create_meeting_flow(understand_fn: Callable | None = None,
                        dispatch_fn: Callable | None = None) -> _MeetingFlow:
    """Create (or return cached) meeting agent flow."""
    global _flow_instance
    if _flow_instance is not None:
        return _flow_instance
    if understand_fn is None or dispatch_fn is None:
        raise ValueError("understand_fn and dispatch_fn required on first call")
    _flow_instance = _MeetingFlow(understand_fn, dispatch_fn)
    return _flow_instance

async def run_meeting_flow(transcript: str,
                           face_sentiment: dict | None = None,
                           understand_fn: Callable | None = None,
                           dispatch_fn: Callable | None = None) -> dict:
    """Execute the flow end-to-end. Returns understanding, sentiment,
    actions, memory, and timing metadata for the UI / visualizer."""
    flow = create_meeting_flow(understand_fn, dispatch_fn)
    t0 = time.monotonic()
    # Step 1 — analyse transcript
    understanding = await flow.analyzer.run(transcript=transcript,
                                            face_sentiment=face_sentiment)
    # Step 2 — sentiment gate
    text_sent = understanding.get("sentiment", "neutral") if understanding else "neutral"
    sentiment = await flow.sentiment.run(face_sentiment=face_sentiment,
                                         text_sentiment=text_sent)
    # Step 3 — execute actions (skip if blocked)
    actions = await flow.executor.run(understanding=understanding,
                                      blocked=sentiment["blocked"])
    # Step 4 — store in memory
    mem = await flow.memory.run(understanding=understanding,
                                sentiment=sentiment, actions=actions)
    elapsed = (time.monotonic() - t0) * 1000
    async with _state_lock:
        _flow_state["last_run_ms"] = round(elapsed, 1)
        _flow_state["total_runs"] += 1
    return {"understanding": understanding, "sentiment": sentiment,
            "actions": actions, "memory": mem,
            "timing_ms": round(elapsed, 1), "mode": _flow_state["mode"]}

def get_flow_status() -> dict:
    """Current flow state for UI: active nodes, action count, routing."""
    return {
        "mode": _flow_state["mode"],
        "nodes_active": list(_flow_state["nodes_active"]),
        "actions_dispatched": _flow_state["actions_dispatched"],
        "total_runs": _flow_state["total_runs"],
        "last_run_ms": _flow_state["last_run_ms"],
        "routing_decisions": list(_flow_state["routing_decisions"][-10:]),
    }
