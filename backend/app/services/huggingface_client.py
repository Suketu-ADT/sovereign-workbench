"""
Hugging Face Inference Providers Client.
Uses OpenAI-compatible API interface via the OpenAI Python SDK for development & testing.
CRITICAL: Never leak HF_TOKEN in exceptions, logs, or error responses.
"""

import logging
import os
from typing import Optional
from dotenv import load_dotenv
from openai import OpenAI, OpenAIError, APIConnectionError, RateLimitError, APIError, APITimeoutError

from app.core.config import settings

load_dotenv()
load_dotenv("backend/.env")

logger = logging.getLogger(__name__)

HF_TOKEN = os.getenv("HF_TOKEN") or getattr(settings, "HF_TOKEN", None)
HF_BASE_URL = os.getenv("HF_BASE_URL") or getattr(settings, "HF_BASE_URL", "https://router.huggingface.co/v1")

_client: Optional[OpenAI] = None


def get_client() -> OpenAI:
    """Returns initialized OpenAI client configured for Hugging Face inference router."""
    global _client, HF_TOKEN, HF_BASE_URL
    token = os.getenv("HF_TOKEN") or getattr(settings, "HF_TOKEN", None)
    base_url = os.getenv("HF_BASE_URL") or getattr(settings, "HF_BASE_URL", "https://router.huggingface.co/v1")

    if not token:
        raise RuntimeError("HF_TOKEN is not configured. External Hugging Face provider is unavailable.")

    if _client is None or getattr(_client, "api_key", None) != token or str(_client.base_url).rstrip("/") != base_url.rstrip("/"):
        _client = OpenAI(
            base_url=base_url,
            api_key=token,
            timeout=30.0,
            max_retries=2,
        )
    return _client


# Eager initialization if token is present at import time
if HF_TOKEN:
    try:
        client = OpenAI(
            base_url=HF_BASE_URL,
            api_key=HF_TOKEN,
            timeout=30.0,
            max_retries=2,
        )
        _client = client
    except Exception as _init_err:
        logger.warning("Could not eagerly initialize HuggingFace OpenAI client: %s", _init_err)
        client = None
else:
    client = None


def _sanitize(msg: str) -> str:
    s = str(msg)
    import re
    active_token = os.getenv("HF_TOKEN") or getattr(settings, "HF_TOKEN", None) or HF_TOKEN
    if active_token and active_token in s:
        s = s.replace(active_token, "[REDACTED_HF_TOKEN]")
    s = re.sub(r"hf_[A-Za-z0-9_-]{10,}", "[REDACTED_HF_TOKEN]", s)
    return s


def call_huggingface(
    model: str,
    user_prompt: str | list[dict],
    system_prompt: str = "You are a helpful AI assistant.",
    timeout: float = 45.0,
) -> str:
    """
    Calls a model via Hugging Face Inference Providers OpenAI-compatible endpoint.
    Handles timeouts, connection retries, and sanitizes all error messages to ensure zero credential leakage.
    Supports both text queries and multimodal content blocks.
    """
    active_client = get_client()

    logger.info("Dispatching request to Hugging Face model router for model: %s", model)
    try:
        response = active_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0.2,
            max_tokens=4096,
            timeout=timeout,
        )

        if not response.choices or not response.choices[0].message:
            raise RuntimeError("Hugging Face provider returned empty response choices.")

        content = response.choices[0].message.content or ""
        return content

    except APITimeoutError as e:
        logger.error("Hugging Face API request timed out for model %s after %ss", model, timeout)
        raise TimeoutError(f"Hugging Face model inference timed out after {timeout}s.") from None

    except RateLimitError as e:
        logger.error("Hugging Face rate limit reached for model %s", model)
        raise RuntimeError("Hugging Face rate limit exceeded. Please wait or retry later.") from None

    except APIConnectionError as e:
        logger.error("Failed to connect to Hugging Face provider endpoint: %s", HF_BASE_URL)
        raise ConnectionError("Unable to establish connection to Hugging Face model provider.") from None

    except APIError as e:
        logger.error("Hugging Face API error (status %s): %s", getattr(e, "status_code", "unknown"), getattr(e, "message", str(e)))
        clean_msg = _sanitize(getattr(e, "message", "Inference provider returned an API error."))
        raise RuntimeError(f"Hugging Face provider error: {clean_msg}") from None

    except OpenAIError as e:
        logger.error("OpenAI SDK error while invoking Hugging Face model: %s", e)
        clean_msg = _sanitize(str(e))
        raise RuntimeError(f"Model provider communication error: {clean_msg}") from None

    except Exception as e:
        logger.error("Unexpected error in call_huggingface: %s", e)
        clean_msg = _sanitize(str(e))
        raise RuntimeError(f"Safe model inference failure: {clean_msg}") from None


def call_huggingface_vision(
    model: str,
    prompt: str,
    image_b64: str,
    system_prompt: str = "You are an expert multimodal visual analyst.",
    timeout: float = 45.0,
) -> str:
    """
    Multimodal visual inference helper dispatching image + text prompt to vision-language models.
    """
    data_url = image_b64 if image_b64.startswith("data:") else f"data:image/png;base64,{image_b64}"
    content_blocks = [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    return call_huggingface(
        model=model,
        user_prompt=content_blocks,
        system_prompt=system_prompt,
        timeout=timeout,
    )
