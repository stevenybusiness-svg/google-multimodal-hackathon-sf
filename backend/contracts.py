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
ActionType = Literal["slack", "calendar", "task", "document", "email", "infra"]
WsMessageType = Literal["transcript", "interim", "status", "sentiment", "action", "done", "pipeline"]

UNDERSTANDING_KEYS = (
    "commitments",
    "agreements",
    "meeting_requests",
    "document_revisions",
    "infrastructure_requests",
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


class InfraRequest(TypedDict, total=False):
    name: str                # slug for resource, e.g. "demo-server"
    machine_type: str        # e.g. "e2-medium", "n2-standard-4"
    zone: str                # e.g. "us-central1-a"
    disk_size_gb: int        # default 20
    ports: list[str]         # e.g. ["80", "443", "22"]
    description: str
    sentiment: str           # gate: only provision on "positive"


class ContainerRequest(TypedDict, total=False):
    name: str                # service name, e.g. "web-api"
    image: str               # container image, e.g. "gcr.io/project/image:tag"
    region: str              # e.g. "us-central1"
    port: int                # container port, default 8080
    memory: str              # e.g. "512Mi", "1Gi"
    cpu: str                 # e.g. "1", "2"
    min_instances: int       # default 0
    max_instances: int       # default 1
    description: str
    sentiment: str           # gate: only provision on "positive"


class UnderstandingResult(TypedDict):
    commitments: list[Commitment]
    agreements: list[Agreement]
    meeting_requests: list[MeetingRequest]
    document_revisions: list[DocumentRevision]
    infrastructure_requests: list[InfraRequest]
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
        "infrastructure_requests": [],
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
