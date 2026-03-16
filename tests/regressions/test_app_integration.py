from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient

from backend.contracts import empty_understanding
import backend.main as main
import backend.understanding as understanding


class FakeVoicePipeline:
    def __init__(self) -> None:
        self._on_transcript = None
        self._sent_audio = False

    @property
    def active_stt(self) -> str:
        return "gemini_live"

    async def start_session(self, on_transcript):
        self._on_transcript = on_transcript

    async def send_audio(self, audio_bytes: bytes) -> None:
        if self._sent_audio or self._on_transcript is None:
            return
        self._sent_audio = True
        await self._on_transcript("I will send the launch plan")

    async def wait(self) -> None:
        return None

    async def stop(self) -> None:
        return None


def test_websocket_flow_emits_contract_messages(monkeypatch) -> None:
    async def fake_understand(transcript: str, face_sentiment=None):
        result = empty_understanding()
        result["commitments"] = [{"owner": "alice", "what": transcript, "sentiment": "neutral"}]
        return result

    async def fake_post_slack(text: str):
        return {"type": "slack", "payload": {"text": text}, "status": "sent"}

    monkeypatch.setattr(main, "VoicePipeline", FakeVoicePipeline)
    monkeypatch.setattr(understanding, "understand_transcript", fake_understand)
    monkeypatch.setattr(main, "calendar_service", None)
    import backend.actions as actions
    monkeypatch.setattr(actions, "_post_slack", fake_post_slack)

    client = TestClient(main.app)

    with client.websocket_connect("/ws/audio?session_id=test-session") as websocket:
        websocket.send_bytes(b"\x00\x00" * 64)
        websocket.send_text('{"type":"stop"}')

        messages = []
        while True:
            payload = websocket.receive_json()
            messages.append(payload)
            if payload["type"] == "done":
                break

    message_types = [message["type"] for message in messages]
    assert "transcript" in message_types
    assert "status" in message_types
    assert "sentiment" in message_types
    assert "action" in message_types
    assert message_types[-1] == "done"

    action_message = next(message for message in messages if message["type"] == "action")
    assert action_message["data"]["type"] in {"slack", "task"}
    assert action_message["data"]["status"] in {"sent", "logged"}
