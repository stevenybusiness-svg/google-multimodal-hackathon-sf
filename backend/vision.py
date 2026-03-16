from google.cloud import vision
from google.api_core import client_options as client_options_lib
import asyncio, logging, os, time

from backend.session_state import VisionState

logger = logging.getLogger(__name__)

DEBOUNCE_SECONDS = 2
_vision_sem = asyncio.Semaphore(3)

try:
    vision_opts = client_options_lib.ClientOptions(
        quota_project_id=os.getenv("GOOGLE_CLOUD_PROJECT")
    )
    vision_client = vision.ImageAnnotatorClient(client_options=vision_opts)
except Exception as e:
    logger.warning(f"Vision client init failed: {e}")
    vision_client = None


async def analyze_frame(frame_bytes: bytes, session_state: VisionState | None = None) -> dict | None:
    state = session_state or VisionState()
    now = time.monotonic()
    if not state.should_process(DEBOUNCE_SECONDS, now=now):
        return None
    if not vision_client:
        return None
    try:
        request = vision.AnnotateImageRequest(
            image=vision.Image(content=frame_bytes),
            features=[
                vision.Feature(type_=vision.Feature.Type.FACE_DETECTION, max_results=1),
                vision.Feature(type_=vision.Feature.Type.LABEL_DETECTION, max_results=5),
            ],
        )
        async with _vision_sem:
            batch = await asyncio.to_thread(
                vision_client.batch_annotate_images,
                requests=[request],
            )
        result = _parse_vision_response(batch.responses[0])
        return state.update(result)
    except Exception as e:
        logger.error("Vision API error: %s", e)
        return None


def _parse_vision_response(response) -> dict:
    result = {"sentiment": None, "engagement": None, "labels": [], "face_box": None}
    result["labels"] = [l.description for l in response.label_annotations[:5]]
    if response.face_annotations:  # ALWAYS guard
        face = response.face_annotations[0]
        # Use the same scale for all emotions — no artificial boost for negatives.
        # Cloud Vision likelihoods: 1=VERY_UNLIKELY … 5=VERY_LIKELY.
        # VERY_UNLIKELY/UNLIKELY genuinely mean the emotion is absent.
        emotions = {
            "happiness": _norm(face.joy_likelihood),
            "sadness":   _norm(face.sorrow_likelihood),
            "anger":     _norm(face.anger_likelihood),
            "surprise":  _norm(face.surprise_likelihood),
        }
        logger.info("Vision emotions: joy=%d→%.2f, sorrow=%d→%.2f, anger=%d→%.2f, surprise=%d→%.2f",
                     face.joy_likelihood, emotions["happiness"],
                     face.sorrow_likelihood, emotions["sadness"],
                     face.anger_likelihood, emotions["anger"],
                     face.surprise_likelihood, emotions["surprise"])
        dominant, score = max(emotions.items(), key=lambda x: x[1])
        # Require POSSIBLE (0.4) or higher to declare an emotion — anything below is noise.
        result["sentiment"] = dominant if score >= 0.4 else "neutral"
        result["engagement"] = score
        verts = face.bounding_poly.vertices
        if verts:
            result["face_box"] = {
                "x": verts[0].x, "y": verts[0].y,
                "w": verts[2].x - verts[0].x,
                "h": verts[2].y - verts[0].y,
                "coords": "pixel",
            }
    return result


_NORM_MAP = {0: 0.0, 1: 0.1, 2: 0.4, 3: 0.7, 4: 0.9, 5: 1.0}


def _norm(likelihood_enum: int) -> float:
    return _NORM_MAP.get(likelihood_enum, 0.0)
