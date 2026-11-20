from contextlib import asynccontextmanager
import logging
import time
from typing import Optional

from fastapi import FastAPI, Header, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.db import (
    check_db_healthy,
    get_session_messages,
    get_session_system_prompt,
    init_db,
    list_sessions,
    save_turn_transaction,
    upsert_session_system_prompt,
)
from app.llm import AllProvidersUnavailableException, execute_chat
from app.schemas import (
    ChatMetadata,
    ChatRequest,
    ChatResponse,
    HealthResponse,
    MessageItem,
    SessionHistoryResponse,
)

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Initializing database...")
    await init_db()
    keys_count = len(settings.api_keys)
    if keys_count < 2:
        logger.warning(
            "Fewer than 2 LLM API keys configured (%d found). At least 2 recommended for full failover.",
            keys_count
        )
    else:
        logger.info("%d LLM API keys loaded in pool.", keys_count)
    yield
    # Shutdown
    logger.info("Shutting down application...")


app = FastAPI(
    title="LLM Chatbot with Key Failover and Response Caching",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Exception Handlers
@app.exception_handler(AllProvidersUnavailableException)
async def all_providers_unavailable_handler(request: Request, exc: AllProvidersUnavailableException):
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={"detail": "all providers unavailable"}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": jsonable_encoder(exc.errors())}
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # Treat 400 JSON decoding errors as 422 for strict contract compliance
    if exc.status_code == 400 and "json" in str(exc.detail).lower():
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": "Malformed JSON in request body"}
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled internal server error: %s", exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "internal server error"}
    )


# -------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    db_ok = await check_db_healthy()
    if not db_ok:
        raise HTTPException(status_code=500, detail="Database unreachable")
    return HealthResponse(
        status="ok",
        keys_configured=len(settings.api_keys),
        cache_enabled=True
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    x_simulate_failure: Optional[str] = Header(default=None, alias="X-Simulate-Failure")
):
    start_time = time.perf_counter()
    session_id = payload.session_id
    user_message = payload.message

    # 1. Resolve system prompt
    if payload.system_prompt is not None:
        sys_prompt = payload.system_prompt.strip()
        await upsert_session_system_prompt(session_id, sys_prompt)
    else:
        saved_prompt = await get_session_system_prompt(session_id)
        sys_prompt = saved_prompt if saved_prompt is not None else settings.DEFAULT_SYSTEM_PROMPT

    # 2. Load session history from SQLite (oldest first, without system prompt)
    history_items = await get_session_messages(session_id)

    # 3. Build messages list: [system prompt] + history + [new user message]
    messages = [{"role": "system", "content": sys_prompt}]
    for item in history_items:
        messages.append({"role": item["role"], "content": item["content"]})
    messages.append({"role": "user", "content": user_message})

    # 4. Execute chat with LLM gateway (checks cache, key loop, failover)
    reply_text, metadata_dict = await execute_chat(
        messages=messages,
        simulate_header=x_simulate_failure
    )

    # 5. Measure latency
    latency_ms = int((time.perf_counter() - start_time) * 1000)
    metadata_dict["latency_ms"] = latency_ms

    # 6. Save turn atomically to SQLite
    await save_turn_transaction(
        session_id=session_id,
        user_message=user_message,
        assistant_reply=reply_text,
        assistant_metadata=metadata_dict
    )

    # 7. Construct and return response
    return ChatResponse(
        session_id=session_id,
        reply=reply_text,
        metadata=ChatMetadata(**metadata_dict)
    )


@app.get("/sessions")
async def get_all_sessions():
    return await list_sessions()


@app.get("/sessions/{session_id}/messages", response_model=SessionHistoryResponse)
async def get_history(session_id: str):
    messages_data = await get_session_messages(session_id)
    if not messages_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="session not found"
        )

    formatted_messages = []
    for item in messages_data:
        formatted_messages.append(MessageItem(**item))

    return SessionHistoryResponse(
        session_id=session_id,
        messages=formatted_messages
    )
