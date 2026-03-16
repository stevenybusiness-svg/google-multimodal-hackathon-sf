from __future__ import annotations

import asyncio

from backend.contracts import empty_understanding
from backend.understanding import TranscriptBuffer, _strip_json_fences
import backend.understanding as understanding


def test_strip_json_fences_handles_wrapped_payload() -> None:
    wrapped = "```json\n{\"sentiment\": \"neutral\"}\n```"
    assert _strip_json_fences(wrapped) == '{"sentiment": "neutral"}'


def test_transcript_buffer_force_flush_preserves_final_utterance(monkeypatch) -> None:
    async def fake_understand(transcript: str, face_sentiment=None):
        result = empty_understanding()
        result["commitments"] = [{"owner": "sam", "what": transcript}]
        return result

    monkeypatch.setattr(understanding, "understand_transcript", fake_understand)
    buffer = TranscriptBuffer()

    first = asyncio.run(buffer.process("I will send the update", None))
    final = asyncio.run(buffer.flush(None))

    assert first is None
    assert final is not None
    assert final["commitments"][0]["what"] == "I will send the update"


def test_transcript_buffer_flushes_on_sentence_boundary(monkeypatch) -> None:
    async def fake_understand(transcript: str, face_sentiment=None):
        result = empty_understanding()
        result["agreements"] = [{"summary": transcript}]
        return result

    monkeypatch.setattr(understanding, "understand_transcript", fake_understand)
    buffer = TranscriptBuffer()

    result = asyncio.run(buffer.process("We agreed to launch next week.", None))

    assert result is not None
    assert result["agreements"][0]["summary"] == "We agreed to launch next week."
