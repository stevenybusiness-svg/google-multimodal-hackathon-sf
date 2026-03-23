from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine
import time

from backend.documents import MARKETING_BRIEF


@dataclass
class VisionState:
    last_call_time: float = 0.0
    latest_result: dict | None = None

    def should_process(self, debounce_seconds: int, now: float | None = None) -> bool:
        current_time = time.monotonic() if now is None else now
        if current_time - self.last_call_time < debounce_seconds:
            return False
        self.last_call_time = current_time
        return True

    def update(self, result: dict | None) -> dict | None:
        if result is not None:
            self.latest_result = result
        return result

    def latest_sentiment(self) -> dict | None:
        return self.latest_result


@dataclass
class MeetingSessionState:
    document_content: str = MARKETING_BRIEF
    document_title: str = "Product Launch Marketing Brief"
    document_status: str = "DRAFT"
    vision: VisionState = field(default_factory=VisionState)
    ws_send: Callable[..., Coroutine[Any, Any, bool]] | None = None


class SessionRegistry:
    def __init__(self) -> None:
        self._sessions: dict[str, MeetingSessionState] = {}

    def ensure(self, session_id: str) -> MeetingSessionState:
        if session_id not in self._sessions:
            self._sessions[session_id] = MeetingSessionState()
        return self._sessions[session_id]

    def get(self, session_id: str | None) -> MeetingSessionState | None:
        if not session_id:
            return None
        return self._sessions.get(session_id)

    def discard(self, session_id: str | None) -> None:
        if session_id:
            self._sessions.pop(session_id, None)


session_registry = SessionRegistry()
