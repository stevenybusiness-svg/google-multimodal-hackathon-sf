from __future__ import annotations

from typing import Literal, TypedDict

try:
    from typing import NotRequired
except ImportError:  # pragma: no cover - Python <3.11 fallback
    from typing_extensions import NotRequired

SentimentValue = Literal[
    "positive",
    "neutral",
    "negative",
    "uncertain",
    "happiness",
    "sadness",
    "anger",
    "surprise",
]
ActionStatus = Literal["sent", "failed", "skipped", "logged", "blocked"]
ActionType = Literal["slack", "calendar", "task", "document", "email"]
WsMessageType = Literal["transcript", "interim", "status", "sentiment", "action", "done", "pipeline"]

UNDERSTANDING_KEYS = (
    "commitments",
    "agreements",
    "meeting_requests",
    "document_revisions",
)


class Commitment(TypedDict, total=False):
    owner: str
    what: str
    by_when: str | None
    sentiment: str
    note: str


class Agreement(TypedDict, total=False):
    summary: str
    sentiment: str


class MeetingRequest(TypedDict, total=False):
    summary: str
    attendees: list[str]
    when: str | None
    sentiment: str


class DocumentRevision(TypedDict, total=False):
    change: str
    section: str


class UnderstandingResult(TypedDict):
    commitments: list[Commitment]
    agreements: list[Agreement]
    meeting_requests: list[MeetingRequest]
    document_revisions: list[DocumentRevision]
    sentiment: str


class ActionResult(TypedDict):
    type: ActionType
    payload: object
    status: ActionStatus
    error: NotRequired[str]
    sentiment: NotRequired[str]


class TranscriptPayload(TypedDict):
    text: str


class StatusPayload(TypedDict, total=False):
    text: str


class SentimentPayload(TypedDict):
    value: str


class WsServerMessage(TypedDict, total=False):
    type: WsMessageType
    data: object


def empty_understanding() -> UnderstandingResult:
    return {
        "commitments": [],
        "agreements": [],
        "meeting_requests": [],
        "document_revisions": [],
        "sentiment": "neutral",
    }


def has_action_items(result: UnderstandingResult) -> bool:
    return any(result.get(key) for key in UNDERSTANDING_KEYS)


def make_action_result(
    action_type: ActionType,
    payload: object,
    status: ActionStatus,
    error: str | None = None,
    sentiment: str | None = None,
) -> ActionResult:
    result: ActionResult = {
        "type": action_type,
        "payload": payload,
        "status": status,
    }
    if error:
        result["error"] = error
    if sentiment:
        result["sentiment"] = sentiment
    return result


def make_ws_message(message_type: WsMessageType, data: object | None = None) -> WsServerMessage:
    message: WsServerMessage = {"type": message_type}
    if data is not None:
        message["data"] = data
    return message
