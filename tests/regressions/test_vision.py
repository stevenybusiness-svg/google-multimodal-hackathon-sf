from __future__ import annotations

from types import SimpleNamespace

from backend.session_state import VisionState
from backend.vision import _norm, _parse_vision_response


def test_parse_vision_response_is_safe_when_no_face_exists() -> None:
    response = SimpleNamespace(
        label_annotations=[SimpleNamespace(description="team"), SimpleNamespace(description="meeting")],
        face_annotations=[],
    )

    result = _parse_vision_response(response)

    assert result["sentiment"] is None
    assert result["face_box"] is None
    assert result["labels"] == ["team", "meeting"]


def test_norm_maps_likelihood_range_to_fraction() -> None:
    assert _norm(0) == 0.0
    assert _norm(5) == 1.0


def test_vision_state_is_session_scoped() -> None:
    session_a = VisionState()
    session_b = VisionState()

    session_a.update({"sentiment": "anger"})
    session_b.update({"sentiment": "neutral"})

    assert session_a.latest_sentiment() == {"sentiment": "anger"}
    assert session_b.latest_sentiment() == {"sentiment": "neutral"}
