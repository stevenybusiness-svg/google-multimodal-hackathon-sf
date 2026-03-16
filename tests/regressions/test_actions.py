from __future__ import annotations

import asyncio
from datetime import datetime

import backend.actions as actions
from backend.contracts import empty_understanding
from backend.documents import _strip_markdown_fences


def test_strip_markdown_fences_handles_wrapped_document() -> None:
    wrapped = "```markdown\n# Title\n```"
    assert _strip_markdown_fences(wrapped) == "# Title"


def test_action_dispatch_returns_stable_shapes(monkeypatch) -> None:
    async def fake_post_slack(text: str):
        return {"type": "slack", "payload": {"text": text}, "status": "sent"}

    async def fake_create_calendar_event(summary, when, attendees=None, sentiment="neutral"):
        return {"summary": summary, "start": {"dateTime": when or "now"}}

    async def fake_revise_document(original: str, revisions: list[dict]) -> str:
        return original + "\n## Updated"

    async def fake_upload(content: str, filename: str, title: str, comment: str):
        return {"type": "document", "payload": {"filename": filename, "title": title}, "status": "sent"}

    monkeypatch.setattr(actions, "_post_slack", fake_post_slack)
    monkeypatch.setattr(actions, "create_calendar_event", fake_create_calendar_event)
    monkeypatch.setattr(actions, "revise_document", fake_revise_document)
    monkeypatch.setattr(actions, "_upload_slack_file", fake_upload)
    monkeypatch.setattr(actions, "_calendar_creds", object())

    understanding = empty_understanding()
    understanding["commitments"] = [{"owner": "alice", "what": "ship backend", "sentiment": "neutral"}]
    understanding["meeting_requests"] = [{"summary": "Launch sync", "when": "2026-03-16T15:00:00+00:00", "sentiment": "neutral"}]
    understanding["document_revisions"] = [{"change": "Update the timeline", "section": "Timeline"}]

    result = asyncio.run(actions.ActionSession().dispatch(understanding, has_calendar=True))

    assert {item["type"] for item in result} == {"slack", "task", "calendar", "document"}
    assert all("status" in item for item in result)
    document_action = next(item for item in result if item["type"] == "document")
    assert document_action["payload"]["content"].endswith("## Updated")


def test_calendar_event_invalid_datetime_falls_back_to_now(monkeypatch) -> None:
    captured: dict = {}

    class DummyExecute:
        def execute(self):
            return captured["body"]

    class DummyEvents:
        def insert(self, calendarId: str, body: dict):
            captured["calendarId"] = calendarId
            captured["body"] = body
            return DummyExecute()

    class DummyService:
        def events(self):
            return DummyEvents()

    monkeypatch.setattr(actions, "_build_calendar_service", lambda: DummyService())

    result = asyncio.run(
        actions.create_calendar_event("Sync", "not-a-date", attendees=["a@example.com"], sentiment="negative")
    )

    start = datetime.fromisoformat(result["start"]["dateTime"])
    assert captured["calendarId"] == "primary"
    assert result["attendees"] == [{"email": "a@example.com"}]
    assert start.tzinfo is not None
    assert "Sentiment flagged" in result["description"]
