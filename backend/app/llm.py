import asyncio
import hashlib
import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import litellm
from litellm import (
    APIConnectionError,
    AuthenticationError,
    BadGatewayError,
    BadRequestError,
    InternalServerError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServiceUnavailableError,
    Timeout,
)

from app.config import settings

logger = logging.getLogger("llm_gateway")
litellm.suppress_debug_info = True
litellm.set_verbose = False
logging.getLogger("LiteLLM").setLevel(logging.WARNING)


class AllProvidersUnavailableException(Exception):
    """Raised when all configured LLM providers/keys have failed."""
    pass


class CacheManager:
    """
    Manages deterministic response caching independent of API keys and session IDs.
    Uses LiteLLM cache where available, with an in-memory/disk store to guarantee
    exact retrieval and metadata consistency.
    """
    def __init__(self, cache_type: str = "local", cache_dir: Optional[str] = None):
        self.cache_type = cache_type
        self.cache_dir = cache_dir
        self._local_store: Dict[str, dict] = {}
        self._init_litellm_cache()

    def _init_litellm_cache(self) -> None:
        try:
            if hasattr(litellm, "Cache"):
                if self.cache_type == "disk" and self.cache_dir:
                    litellm.cache = litellm.Cache(type="disk", disk_cache_dir=self.cache_dir)
                else:
                    litellm.cache = litellm.Cache(type="local")
        except Exception as e:
            logger.warning("Could not initialize litellm.Cache: %s. Using internal cache.", e)

    @staticmethod
    def compute_cache_key(
        messages: List[Dict[str, str]],
        primary_model: str,
        temperature: float,
        max_tokens: int
    ) -> str:
        key_data = {
            "model": primary_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        serialized = json.dumps(key_data, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    async def get(self, cache_key: str) -> Optional[dict]:
        return self._local_store.get(cache_key)

    async def set(self, cache_key: str, data: dict) -> None:
        self._local_store[cache_key] = data


# Global cache manager instance
cache_manager = CacheManager(cache_type=settings.CACHE_TYPE, cache_dir=settings.CACHE_DIR)

# Real 429 cooldown tracker: key_id -> expiry_epoch (seconds)
# Simulated failures NEVER update this
_key_cooldowns: Dict[str, float] = {}


def parse_simulation_header(header_val: Optional[str]) -> Dict[str, int]:
    """
    Parses X-Simulate-Failure header value.
    Format: comma-separated <key_id>=<status> pairs; '*' means every key.
    Allowed statuses: 429, 500, 502, 503.
    """
    if not header_val:
        return {}
    result = {}
    valid_statuses = {429, 500, 502, 503}
    parts = header_val.split(",")
    for part in parts:
        part = part.strip()
        if not part or "=" not in part:
            continue
        k_id, status_str = part.split("=", 1)
        k_id = k_id.strip()
        status_str = status_str.strip()
        try:
            status_code = int(status_str)
            if status_code in valid_statuses:
                result[k_id] = status_code
        except ValueError:
            continue
    return result


def _raise_simulated_error(status: int, model: str) -> None:
    if status == 429:
        raise RateLimitError(
            message="Simulated 429 RateLimitError",
            llm_provider="simulated",
            model=model
        )
    elif status == 500:
        raise InternalServerError(
            message="Simulated 500 InternalServerError",
            llm_provider="simulated",
            model=model
        )
    elif status == 502:
        raise BadGatewayError(
            message="Simulated 502 BadGatewayError",
            llm_provider="simulated",
            model=model
        )
    elif status == 503:
        raise ServiceUnavailableError(
            message="Simulated 503 ServiceUnavailableError",
            llm_provider="simulated",
            model=model
        )


def _get_ordered_pool(key_pool: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    """
    Sort keys so healthy keys come before keys in active real-429 cooldown.
    Preserves relative order within groups.
    """
    now = time.time()
    healthy = []
    cooling = []
    for item in key_pool:
        k_id = item[0]
        cooldown_until = _key_cooldowns.get(k_id, 0.0)
        if cooldown_until > now:
            cooling.append(item)
        else:
            healthy.append(item)
    return healthy + cooling


async def execute_chat(
    messages: List[Dict[str, str]],
    simulate_header: Optional[str] = None
) -> Tuple[str, dict]:
    """
    Executes a chat completion following the strict failover and caching contract.
    Returns: (reply_text, metadata_dict)
    """
    key_pool = settings.key_pool
    primary_model = settings.primary_model
    temp = settings.LLM_TEMPERATURE
    max_tok = settings.LLM_MAX_TOKENS
    timeout_sec = settings.LLM_TIMEOUT_SECONDS

    # 1. Parse simulation header if enabled
    is_sim_enabled = settings.is_failure_simulation_enabled
    sim_map = parse_simulation_header(simulate_header) if is_sim_enabled else {}
    has_simulation = bool(sim_map)

    # 2. Cache lookup (skipped if failure simulation is active)
    cache_key = CacheManager.compute_cache_key(messages, primary_model, temp, max_tok)
    if not has_simulation:
        cached_entry = await cache_manager.get(cache_key)
        if cached_entry:
            meta = {
                "resolution_source": "LLM_CACHE",
                "model": cached_entry.get("model", primary_model),
                "input_tokens": cached_entry.get("input_tokens", 0),
                "output_tokens": cached_entry.get("output_tokens", 0),
                "key_id": None,
                "fallback_attempts": 0,
            }
            return cached_entry["reply"], meta

    # 3. Key loop if cache miss or simulation
    if not key_pool:
        logger.warning("No API keys configured")
        raise AllProvidersUnavailableException("all providers unavailable")

    ordered_keys = _get_ordered_pool(key_pool)
    fallback_attempts = 0

    for key_id, api_key, model in ordered_keys:
        is_simulated = False
        try:
            # Check for simulated failure on this key
            if has_simulation:
                sim_status = sim_map.get(key_id, sim_map.get("*"))
                if sim_status:
                    is_simulated = True
                    _raise_simulated_error(sim_status, model)

            # Live LiteLLM call
            response = await litellm.acompletion(
                model=model,
                messages=messages,
                api_key=api_key,
                temperature=temp,
                max_tokens=max_tok,
                timeout=timeout_sec,
                num_retries=0
            )

            # Extract reply content
            choices = getattr(response, "choices", None)
            if not choices or len(choices) == 0:
                raise ValueError("No choices returned by model")

            msg = getattr(choices[0], "message", None)
            reply_text = getattr(msg, "content", "") if msg else ""
            if not reply_text or not reply_text.strip():
                raise ValueError("Empty reply returned by model")

            # Extract token counts
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None) if usage else None
            completion_tokens = getattr(usage, "completion_tokens", None) if usage else None

            if prompt_tokens is None or prompt_tokens <= 0:
                try:
                    prompt_tokens = litellm.token_counter(model=model, messages=messages)
                except Exception:
                    prompt_tokens = sum(len(m.get("content", "").split()) for m in messages)

            if completion_tokens is None or completion_tokens <= 0:
                try:
                    completion_tokens = litellm.token_counter(model=model, text=reply_text)
                except Exception:
                    completion_tokens = max(1, len(reply_text.split()))

            # Record healthy key (remove cooldown if any)
            _key_cooldowns.pop(key_id, None)

            # Store in cache
            cache_payload = {
                "reply": reply_text,
                "model": model,
                "input_tokens": int(prompt_tokens),
                "output_tokens": int(completion_tokens),
            }
            await cache_manager.set(cache_key, cache_payload)

            meta = {
                "resolution_source": "LIVE_INFERENCE",
                "model": model,
                "input_tokens": int(prompt_tokens),
                "output_tokens": int(completion_tokens),
                "key_id": key_id,
                "fallback_attempts": fallback_attempts,
            }
            return reply_text, meta

        except (
            RateLimitError,
            InternalServerError,
            ServiceUnavailableError,
            BadGatewayError,
            APIConnectionError,
            Timeout,
            AuthenticationError,
            PermissionDeniedError,
            NotFoundError,
            BadRequestError,
            Exception
        ) as err:
            logger.warning(
                "Attempt failed for key %s (model: %s): %s",
                key_id,
                model,
                type(err).__name__
            )
            # Track real 429 for cooldown (never simulated)
            if not is_simulated and isinstance(err, RateLimitError):
                _key_cooldowns[key_id] = time.time() + 45.0

            fallback_attempts += 1
            continue

    # If all keys failed
    raise AllProvidersUnavailableException("all providers unavailable")
