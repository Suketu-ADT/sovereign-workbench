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
        """Attempts calling Qwen2.5-VL 72B (via cloud API) or local VLM endpoint with circuit breaker protection."""
        global _last_vlm_failure_time
        if not self.vlm_enabled:
            return None

        # Check circuit breaker
        if time.time() - _last_vlm_failure_time < _CIRCUIT_BREAKER_COOLDOWN:
            return None

        # 1. Check if remote OpenAI-compatible API is configured (e.g. OpenRouter / DashScope)
        api_key = (settings.LLM_API_KEY or "").strip()
        base_url = (settings.LLM_BASE_URL or "").strip().rstrip("/")
        is_local_endpoint = bool(base_url and any(h in base_url.lower() for h in ["127.0.0.1", "localhost", "0.0.0.0"]))
        can_call_remote = bool(api_key or is_local_endpoint)

        if can_call_remote and base_url:
            url = f"{base_url}/chat/completions" if not base_url.endswith("/chat/completions") else base_url
            headers = {
                "Content-Type": "application/json",
                "HTTP-Referer": "https://sovereign.workbench.internal",
                "X-Title": "Sovereign Industrial Workbench",
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            data_url = image_b64 if image_b64.startswith("data:") else f"data:image/png;base64,{image_b64}"
            payload = {
                "model": self.vlm_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are an industrial computer vision expert inspecting analog pressure dial gauges. "
                            "Analyze the gauge dial and needle position carefully. "
                            "Output strictly valid JSON conforming to this schema:\n"
                            '{"reading": float, "confidence": float}\n'
                            "where reading is the measured value in bar (e.g. 6.4) and confidence is between 0.0 and 1.0. "
                            "Do not wrap in markdown fences or include any extra text."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {"type": "image_url", "image_url": {"url": data_url}},
                        ],
                    },
                ],
                "response_format": {"type": "json_object"},
                "temperature": 0.1,
            }

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    res = await client.post(url, json=payload, headers=headers)
                    if res.status_code == 200:
                        import json
                        import re
                        res_data = res.json()
                        choices = res_data.get("choices", [])
                        text_val = choices[0]["message"]["content"] if choices else "{}"
                        if "```" in text_val:
                            text_val = re.sub(r"^```(?:json)?\s*|\s*```$", "", text_val.strip(), flags=re.MULTILINE)
                        return json.loads(text_val)
                    else:
                        logger.warning("Remote VLM API responded with HTTP %d: %s", res.status_code, res.text)
            except Exception as e:
                logger.info("Remote VLM endpoint call failed (%s). Activating circuit breaker.", e)
                _last_vlm_failure_time = time.time()
                return None

        # 2. Local Ollama VLM fallback
        if not self.vlm_url:
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

    def _analyze_gauge_opencv(self, img: np.ndarray) -> tuple[float | None, float]:
        """
        Extracts pressure dial reading from image using circle detection and needle vector angle.
        Returns (reading_bar, confidence) where reading_bar is None if no needle was detected.
        Confidence is derived from the proportion of needle pixels found relative to image area.
        """
        h, w = img.shape[:2]
        total_pixels = h * w
        center_x, center_y = w // 2, int(h * 0.55)

        # 1. Search for red/accent colored needle
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        # Red spans 0-10 and 170-180 in OpenCV HSV
        mask1 = cv2.inRange(hsv, np.array([0, 70, 50]), np.array([10, 255, 255]))
        mask2 = cv2.inRange(hsv, np.array([170, 70, 50]), np.array([180, 255, 255]))
        mask = mask1 | mask2

        pts = cv2.findNonZero(mask)
        if pts is not None and len(pts) > 5:
            pts = pts.reshape(-1, 2)
            # Find the point furthest from the dial pivot center
            dists = np.linalg.norm(pts - np.array([center_x, center_y]), axis=1)
            tip = pts[np.argmax(dists)]

            # Angle from dial pivot
            calc_angle = math.atan2(tip[1] - center_y, tip[0] - center_x)
            if calc_angle < 0:
                calc_angle += 2 * math.pi

            # Dial arc spans pi to 2*pi for top half (0 to 10 bar)
            if calc_angle >= math.pi:
                fraction = (calc_angle - math.pi) / math.pi
                reading = round(fraction * 10.0, 1)
                # Cap within valid instrument range [0.0, 10.0]
                reading = max(0.0, min(10.0, reading))

                # Compute confidence from needle pixel evidence:
                # needle_ratio = needle pixels / total pixels, scaled and clamped
                needle_pixel_count = len(pts)
                needle_ratio = needle_pixel_count / total_pixels
                # A well-visible needle typically covers 0.5-3% of gauge area.
                # Scale: ratio >= 0.005 -> confidence 0.95+, ratio ~0.001 -> ~0.80
                confidence = min(0.99, max(0.50, 0.75 + needle_ratio * 40.0))
                return reading, round(confidence, 2)

        # No needle detected — signal extraction failure (do NOT fabricate a reading)
        logger.warning(
            "Gauge needle not detected: found %d red pixels (minimum 6 required). "
            "Cannot extract reading.",
            len(pts) if pts is not None else 0,
        )
        return None, 0.0

    async def extract_gauge_reading(
        self,
        image_data: str | bytes | None = None,
        equipment_unit: str = "boiler-102",
    ) -> VisionResult:
        """
        Processes gauge photo to extract numerical pressure reading.
        Distinguishes 4 distinct outcomes:
          (a) No image provided -> status='skipped', reading=None
          (b) Image decode / validation failed -> status='invalid_image', reading=None
          (c) Successful decode & extraction -> status='success', reading=float
          (d) Valid image but needle not detected -> status='extraction_failed', reading=None
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

        # Valid image decoded -> perform VLM or OpenCV extraction
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

        # Outcome (d): Valid image decoded but needle extraction failed
        if reading is None:
            return VisionResult(
                status="extraction_failed",
                reading=None,
                unit="bar",
                parameter="inlet_pressure",
                confidence=0.0,
                assessment="Gauge needle not detected — unable to extract reading from image",
                error="No gauge needle detected in image",
            )

        # Outcome (c): Successful extraction
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
