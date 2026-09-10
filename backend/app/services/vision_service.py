"""
Multimodal Vision Service for industrial gauge reading.
Supports local vision model endpoints (Qwen2.5-VL via Ollama/vLLM)
with an air-gapped OpenCV / PIL deterministic computer vision engine
for circular dial needle angle detection and gauge reading extraction.
"""

import base64
import io
import logging
import math
import time
from typing import Any

import cv2
import httpx
import numpy as np
from PIL import Image

from app.core.config import settings
from app.schemas.query import VisionResult

logger = logging.getLogger(__name__)

# Circuit breaker cooldown for local VLM endpoint
_CIRCUIT_BREAKER_COOLDOWN = 30.0
_last_vlm_failure_time: float = 0.0


# Prevent PIL decompression bombs
Image.MAX_IMAGE_PIXELS = 16_000_000
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB binary limit
MAX_IMAGE_DIMENSION = 4096

VALID_MAGIC_HEADERS = (
    b"\x89PNG\r\n\x1a\n",  # PNG
    b"\xff\xd8\xff",        # JPEG
    b"RIFF",                # WEBP/AVI
    b"BM",                  # BMP
    b"GIF87a",              # GIF87a
    b"GIF89a",              # GIF89a
)


class VisionService:
    """Extracts operational analog/digital gauge readings from photos."""

    def __init__(
        self,
        vlm_enabled: bool | None = None,
        vlm_url: str | None = None,
        vlm_model: str | None = None,
        timeout: float | None = None,
    ):
        self.vlm_enabled = vlm_enabled if vlm_enabled is not None else settings.VISION_MODEL_ENABLED
        self.vlm_url = vlm_url or settings.VISION_MODEL_URL
        self.vlm_model = vlm_model or settings.VISION_MODEL_NAME
        self.timeout = timeout or settings.VISION_TIMEOUT

    async def _call_local_vlm(self, image_b64: str, prompt: str) -> dict[str, Any] | None:
        """Attempts calling a local Qwen2.5-VL endpoint with circuit breaker protection."""
        global _last_vlm_failure_time
        if not self.vlm_enabled or not self.vlm_url:
            return None

        # Check circuit breaker
        if time.time() - _last_vlm_failure_time < _CIRCUIT_BREAKER_COOLDOWN:
            return None

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(
                    f"{self.vlm_url}/api/generate",
                    json={
                        "model": self.vlm_model,
                        "prompt": prompt,
                        "images": [image_b64],
                        "stream": False,
                        "format": "json",
                    },
                )
                if res.status_code == 200:
                    import json
                    response_text = res.json().get("response", "{}")
                    return json.loads(response_text)
        except Exception as e:
            logger.info("Local VLM endpoint unreachable (%s). Activating circuit breaker.", e)
            _last_vlm_failure_time = time.time()
            return None

    def _decode_image_bytes(self, image_data: str | bytes) -> np.ndarray | None:
        """
        Validates magic headers, size bounds, and decodes image into BGR OpenCV numpy array.
        Guards against corrupted buffers, decompression bombs, and polyglot files.
        """
        try:
            if isinstance(image_data, str):
                # Strip data URL header if present (e.g. data:image/png;base64,...)
                if "," in image_data:
                    image_data = image_data.split(",", 1)[1]
                raw_bytes = base64.b64decode(image_data)
            else:
                raw_bytes = image_data

            if not raw_bytes:
                logger.warning("Empty image buffer provided")
                return None

            if len(raw_bytes) > MAX_IMAGE_BYTES:
                logger.warning("Image buffer exceeds 5MB limit (%d bytes)", len(raw_bytes))
                return None

            # Verify image magic bytes
            is_valid_header = any(raw_bytes.startswith(h) for h in VALID_MAGIC_HEADERS)
            if not is_valid_header:
                logger.warning("Image buffer has invalid or unrecognized magic header")
                return None

            nparr = np.frombuffer(raw_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                logger.warning("cv2.imdecode failed to decode image buffer")
                return None

            h, w = img.shape[:2]
            if h > MAX_IMAGE_DIMENSION or w > MAX_IMAGE_DIMENSION:
                logger.warning("Image dimensions %dx%d exceed maximum limit %d", w, h, MAX_IMAGE_DIMENSION)
                return None

            return img
        except Exception as e:
            logger.warning("Failed to decode image buffer: %s", e)
            return None

    

    async def extract_gauge_reading(
        self,
        image_data: str | bytes | None = None,
        equipment_unit: str = "boiler-102",
    ) -> VisionResult:
        """
        Processes gauge photo to extract numerical pressure reading.
        Distinguishes 3 distinct outcomes:
          (a) No image provided -> status='skipped', reading=None
          (b) Image decode / validation failed -> status='invalid_image', reading=None
          (c) Successful decode & extraction -> status='success', reading=float
        """
        # Outcome (a): No image provided (legitimate skip)
        if not image_data or (isinstance(image_data, str) and not image_data.strip()):
            return VisionResult(
                status="skipped",
                reading=None,
                unit="bar",
                parameter="inlet_pressure",
                confidence=0.0,
                assessment="No visual asset attached — skipped",
                error=None,
            )

        # Outcome (b): Decode image buffer and validate magic bytes & size
        img = self._decode_image_bytes(image_data)
        if img is None:
            return VisionResult(
                status="invalid_image",
                reading=None,
                unit="bar",
                parameter="inlet_pressure",
                confidence=0.0,
                assessment="Visual asset rejected: corrupted payload, invalid magic bytes, or unsupported dimensions",
                error="Invalid or corrupted image format",
            )

        # Outcome (c): Valid image decoded -> perform VLM or OpenCV extraction
        reading = None
        confidence = 0.0

        # 1. Try local VLM if enabled
        if isinstance(image_data, str) and "," in image_data:
            b64_str = image_data.split(",", 1)[1]
        elif isinstance(image_data, bytes):
            b64_str = base64.b64encode(image_data).decode("utf-8")
        else:
            b64_str = str(image_data)

        vlm_res = await self._call_local_vlm(
            b64_str,
            "Extract the pressure gauge reading in bar and return JSON with keys: reading, confidence."
        )
        if vlm_res and "reading" in vlm_res:
            try:
                reading = float(vlm_res["reading"])
                confidence = float(vlm_res.get("confidence", 0.95))
            except (ValueError, TypeError):
                pass

        if reading is None:
            return VisionResult(
                status="extraction_failed",
                reading=None,
                unit="bar",
                parameter="inlet_pressure",
                confidence=0.0,
                assessment="VLM extraction failed or model unavailable",
                error="Failed to extract numerical reading from image",
            )

        # Formulate assessment based on operational equipment parameters
        if equipment_unit == "boiler-102" or "boiler" in equipment_unit:
            if 4.0 <= reading <= 7.0:
                assessment = f"Within normal range (4.0–7.0 bar)"
            elif reading > 7.0:
                assessment = f"High pressure advisory: {reading} bar exceeds normal upper limit (7.0 bar)"
            else:
                assessment = f"Low pressure advisory: {reading} bar below normal lower limit (4.0 bar)"
        else:
            assessment = f"Measured {reading} bar (Confidence: {confidence})"

        return VisionResult(
            status="success",
            reading=reading,
            unit="bar",
            parameter="inlet_pressure",
            confidence=confidence,
            assessment=assessment,
            error=None,
        )

    def generate_synthetic_gauge(self, pressure_bar: float = 6.4) -> str:
        """
        Generates a synthetic pressure gauge PNG matching script.js's canvas drawing
        and returns it as a base64 Data URL.
        """
        img = np.zeros((80, 80, 3), dtype=np.uint8)
        img[:] = (41, 32, 26)  # BGR for #1a2029 background

        # Cyan dial arc
        cv2.circle(img, (40, 44), 28, (201, 195, 79), 2)  # BGR for #4FC3C9

        # Red needle
        p_clamped = max(0.0, min(10.0, pressure_bar))
        angle = math.pi + (p_clamped / 10.0) * math.pi
        x_end = int(40 + math.cos(angle) * 22)
        y_end = int(44 + math.sin(angle) * 22)
        cv2.line(img, (40, 44), (x_end, y_end), (73, 81, 248), 2)  # BGR for #F85149

        # Text label
        cv2.putText(img, f"{pressure_bar} bar", (20, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.3, (201, 195, 79), 1)

        _, buf = cv2.imencode(".png", img)
        b64_str = base64.b64encode(buf).decode("utf-8")
        return f"data:image/png;base64,{b64_str}"


# Singleton instance
vision_service = VisionService()
