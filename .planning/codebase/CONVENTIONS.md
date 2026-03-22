# Coding Conventions

**Analysis Date:** 2026-03-22

## Naming Patterns

**Files:**
- Python modules: `snake_case.py` (e.g., `understanding.py`, `actions.py`)
- Private/internal modules: prefix underscore (e.g., `_helpers.py` not seen but convention clear from functions)
- JavaScript/Frontend: `camelCase.js` (e.g., `core.js`, `documents.js`, `session.js`)

**Functions:**
- Python functions/methods: `snake_case` (e.g., `understand_transcript()`, `create_calendar_event()`, `send_audio()`)
- Private functions: prefix underscore (e.g., `_get_client()`, `_post_slack()`, `_dispatch()`, `_watch_session()`)
- Async functions: same naming convention, just prefix `async` keyword (e.g., `async def process()`)
- JavaScript functions: `camelCase` (e.g., `timeStr()`, `float32ToInt16()`, `generateSessionId()`)

**Variables:**
- Module-level state/constants: `SCREAMING_SNAKE_CASE` for constants (e.g., `UNDERSTANDING_MODEL`, `SLACK_CHANNEL`, `DEBOUNCE_SECONDS`, `_MAX_STREAM_DURATION_S`)
- Local variables: `snake_case` (e.g., `text`, `face_sentiment`, `understanding`)
- Private/module-local state: prefix underscore (e.g., `_client`, `_slack`, `_calendar_creds`, `_gemini_sem`)
- JavaScript state objects: camelCase properties (e.g., `state.ws`, `state.micStream`, `state.currentScreen`)

**Types:**
- TypedDict classes: `PascalCase` (e.g., `UnderstandingResult`, `ActionResult`, `TranscriptPayload`)
- Type aliases (Literal): `PascalCase` (e.g., `SentimentValue`, `ActionStatus`, `WsMessageType`)
- Custom semaphore/lock variables: prefix underscore, descriptive (e.g., `_gemini_sem`, `_vision_sem`, `_doc_lock`)

## Code Style

**Formatting:**
- Python: Uses standard PEP 8 style
- Import grouping order observed: stdlib → third-party → local imports
- Line wrapping: Imports and long lines broken to ~100 chars
- No explicit formatter config found (Prettier/Black not in requirements)

**Linting:**
- Python linting: No ESLint/Pylint config found
- Uses standard Python type hints (`str | None` syntax for union types, `async/await` for async)
- Type annotations on function signatures required for clarity: `async def process(text: str, face_sentiment: dict | None = None)`

**Docstring Style:**
- Module-level docstrings present (e.g., `voice.py` has module docstring explaining STT)
- Class docstrings: `TranscriptBuffer` has docstring explaining behavior and constants
- Function docstrings: Brief description with parameters noted in code (e.g., `send()` has "Returns False if client is gone")
- No JSDoc/TSDoc observed; inline comments used instead

## Import Organization

**Order (observed in main.py):**
1. Future imports: `from __future__ import annotations`
2. Python stdlib: `import asyncio`, `import json`, `import logging`, `import os`, `import uuid`
3. Third-party: `from dotenv import load_dotenv`, `from fastapi import ...`, `from google import ...`
4. Local imports: `import backend.actions as _actions_module`, `from backend.understanding import ...`

**Path Aliases:**
- No path aliases (`@` paths, `~` paths) detected
- Relative imports avoided; absolute imports from `backend.*` package used throughout
- Module re-imports with aliases for clarity: `import backend.actions as _actions_module` (to avoid naming conflicts)
- Local imports as `import re as _re` (disambiguate standard library from local helpers)

## Error Handling

**Patterns:**
- Explicit exception catching by type: `except json.JSONDecodeError as e:` then `except Exception as e:`
- Rate-limit detection by string inspection: `"429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)`
- Graceful degradation: Missing API keys → warning log + feature skipped (e.g., `_get_slack()` returns `None`)
- try/except/finally for cleanup: WS close in finally block; pipeline stop guaranteed
- Retries with exponential backoff (Gemini): 3 attempts, parse `retryDelay` from error, cap at 35s
- Fire-and-forget dispatch with callback for exception handling: `asyncio.create_task(_dispatch())` wrapped in try/except
- Silent failures on websocket/streaming operations: `except Exception: pass` when closing or cancelling tasks

## Logging

**Framework:** Python `logging` stdlib

**Patterns:**
- Initialize per-module: `logger = logging.getLogger(__name__)` at module top
- Baseline config in `main.py`: `logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")`
- Log levels:
  - `INFO` for major events (session started, STT connected, model validated, actions dispatched)
  - `DEBUG` for detailed state (buffer held, cooldown fired, token refreshed)
  - `WARNING` for degradation (model unavailable, calendar service init failed, feature skipped)
  - `ERROR` for failures (API errors, voice pipeline died, dispatch failed)
- Session tracking: Short ID in brackets `[%s]` for readability (e.g., `[abc1234f]`)
- Sensitive data: Text/token contents truncated to first 80 chars or first 300 JSON chars
- Structured logging: Use `%s` % formatting, not f-strings (legacy but consistent)
- Inline debug via logger: `logger.debug("buffer held"), logger.info("flushing buffer (%d chars)")

## Comments

**When to Comment:**
- Complex logic blocks: Async task lifecycle, cooldown cancellation logic explained inline
- API quirks documented: "googleapiclient Resource is not thread-safe" (comment in `_build_calendar_service`)
- Business rules explained: "Primary gate: text sentiment. Face is supplemental" in `_should_block()`
- Configuration magic numbers justified: "_MAX_STREAM_DURATION_S = 240 # Cloud STT streaming has a 5-minute hard limit"
- Workarounds noted: Mutable list pattern `[_send_ref]` exposes outer scope variable (mentioned in MEMORY)

**No JSDoc/TSDoc:** JavaScript code uses minimal comments; configuration objects are self-explanatory (e.g., `sentimentConfig` object with explicit keys)

## Function Design

**Size:**
- Small focused functions preferred: `_norm()` is 1 line, `timeStr()` is 1 line
- Medium functions (20-40 lines): `understand_transcript()`, `_post_slack()`, `analyze_frame()`
- Larger methods acceptable for async orchestration: `dispatch()` ~40 lines, `_run()` ~60 lines (streaming loop)
- Nested async tasks: `_dispatch()`, `_watch_session()`, `on_transcript()` defined inline when session-scoped

**Parameters:**
- Type hints required: `def process(text: str, face_sentiment: dict | None = None) -> UnderstandingResult | None`
- Optional params use `None` defaults: `face_sentiment: dict | None = None`
- Sentinel pattern avoided; explicit `None` checks used: `if understanding is None:` (not `if not understanding:`)
- Keyword-only after required: `async def dispatch(self, understanding: UnderstandingResult, has_calendar: bool = False, face_sentiment: dict | None = None)`

**Return Values:**
- Explicit return types: All async functions annotated with return type
- Union returns allowed: `UnderstandingResult | None`, `list[ActionResult]`
- Consistent payload shapes: `ActionResult` TypedDict enforces `type`, `payload`, `status` fields
- None return for "no result": Polling/cooldown functions return `None` (not empty list/dict)

## Module Design

**Exports:**
- No `__all__` observed; exports implicit from module imports
- Public API functions: `understand_transcript()`, `TranscriptBuffer` class, `analyze_frame()`
- Private helpers: prefixed underscore, not imported externally
- Lazy initialization globals: `_client`, `_slack`, `_calendar_creds` (module-level singletons)

**Barrel Files:**
- No barrel files (`__init__.py` is empty in `backend/`)
- Direct imports from leaf modules: `from backend.understanding import TranscriptBuffer`
- Type-only exports: `backend.contracts` holds TypedDict definitions for type hints

## JavaScript/Frontend Conventions

**File Structure:**
- IIFE pattern: `(() => { ... })()` wraps module code for scope isolation
- Namespace: `window.MeetingAgent.moduleName` for module registration
- State encapsulation: `const state = { ... }` as local variable (not global)

**Naming (JavaScript):**
- DOM element cache: `const dom = { screens: {...}, startBtn, ... }` (object literal with shorthand props)
- Configuration objects: `sentimentConfig`, `actionBadge`, `overlayColors` (lowercase keys, PascalCase values)
- Event handlers: `addEventListener` with arrow functions
- Private functions: `function timeStr()`, `function float32ToInt16()` (no prefix, scope-private via IIFE)

**String Operations:**
- XSS prevention: `textContent` used instead of `innerHTML` (observed: `chevron.textContent = 'expand_more'`)
- URL encoding: `encodeURIComponent()` for query params
- No string concatenation for SQL/commands (not applicable, but note: no injection vectors in static code)

---

*Convention analysis: 2026-03-22*
