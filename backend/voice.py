"""
Voice pipeline — Google Cloud Speech-to-Text v1 streaming.
Audio: PCM mono 16-bit 16000 Hz.

Uses Cloud STT for low-latency transcription (~200ms interim, ~1s final).
Gemini is used downstream for understanding/action extraction.
"""
import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable

from google.cloud.speech_v1 import SpeechAsyncClient
from google.cloud.speech_v1.types import cloud_speech

logger = logging.getLogger(__name__)

# Cloud STT streaming has a 5-minute hard limit.
# Reconnect proactively at 4 minutes to avoid hitting it.
_MAX_STREAM_DURATION_S = 240


class VoicePipeline:
    def __init__(self) -> None:
        self._audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue(maxsize=50)
        self._task: asyncio.Task | None = None
        self._ready = asyncio.Event()
        self._running = False

    @property
    def active_stt(self) -> str:
        return "cloud_stt"

    async def start_session(
        self,
        on_transcript: Callable[[str], Awaitable[None]],
        on_interim: Callable[[str], Awaitable[None]] | None = None,
    ) -> None:
        self._running = True
        self._ready.clear()
        self._task = asyncio.create_task(self._run(on_transcript, on_interim))
        try:
            await asyncio.wait_for(self._ready.wait(), timeout=15)
        except asyncio.TimeoutError:
            if self._task.done():
                exc = self._task.exception()
                raise RuntimeError(f"Cloud STT failed to connect: {exc}") from exc
            raise RuntimeError("Cloud STT did not connect within 15 seconds.")
        logger.info("Cloud Speech-to-Text session active.")

    async def _run(
        self,
        on_transcript: Callable[[str], Awaitable[None]],
        on_interim: Callable[[str], Awaitable[None]] | None,
    ) -> None:
        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        client = SpeechAsyncClient()

        recognition_config = cloud_speech.RecognitionConfig(
            encoding=cloud_speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US",
            enable_automatic_punctuation=True,
            model="latest_long",  # continuous recognition for meetings
        )
        streaming_config = cloud_speech.StreamingRecognitionConfig(
            config=recognition_config,
            interim_results=True,  # always get interim for low latency display
        )

        self._ready.set()

        while self._running:
            try:
                stream_start = time.monotonic()
                logger.info("Starting Cloud STT stream...")

                async def request_generator():
                    # First request: config only (no audio)
                    yield cloud_speech.StreamingRecognizeRequest(
                        streaming_config=streaming_config
                    )
                    # Subsequent requests: audio chunks
                    while self._running:
                        try:
                            chunk = await asyncio.wait_for(
                                self._audio_queue.get(), timeout=1.0
                            )
                        except asyncio.TimeoutError:
                            # Check if we should cycle the stream
                            if time.monotonic() - stream_start > _MAX_STREAM_DURATION_S:
                                logger.info(
                                    "Proactive STT stream cycle at %.0fs",
                                    time.monotonic() - stream_start,
                                )
                                return
                            continue
                        if chunk is None:
                            return
                        yield cloud_speech.StreamingRecognizeRequest(
                            audio_content=chunk
                        )
                        if time.monotonic() - stream_start > _MAX_STREAM_DURATION_S:
                            logger.info(
                                "Proactive STT stream cycle at %.0fs",
                                time.monotonic() - stream_start,
                            )
                            return

                response_stream = await client.streaming_recognize(
                    requests=request_generator()
                )

                _resp_count = 0
                async for response in response_stream:
                    if not response.results:
                        continue
                    _resp_count += 1
                    for result in response.results:
                        if not result.alternatives:
                            continue
                        text = result.alternatives[0].transcript
                        if not text.strip():
                            continue
                        if result.is_final:
                            logger.info("STT final: %.80s", text)
                            await on_transcript(text)
                        elif on_interim:
                            await on_interim(text)

                logger.info("STT stream ended after %d responses — reconnecting...", _resp_count)

            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Cloud STT error: %s — reconnecting in 1s...", exc)
                await asyncio.sleep(1.0)

    async def send_audio(self, audio_bytes: bytes) -> None:
        if self._running:
            try:
                self._audio_queue.put_nowait(audio_bytes)
            except asyncio.QueueFull:
                pass  # drop oldest frames if queue is full

    async def wait(self) -> None:
        if self._task:
            await self._task

    async def stop(self) -> None:
        self._running = False
        try:
            self._audio_queue.put_nowait(None)
        except asyncio.QueueFull:
            pass
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
