"""
OBD2 AI Backend  v2.0
─────────────────────
Replaces local Tesseract OCR with OpenAI Vision so the service can be
deployed on Render / Railway without any native system dependencies.

Flow:
  POST /upload  →  read image bytes  →  resize in memory  →
  base64-encode  →  GPT-4o Vision analysis  →  return JSON
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
import sys
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import OpenAI, OpenAIError
from PIL import Image

# ── Environment ────────────────────────────────────────────────────────────────

load_dotenv()  # loads .env when running locally; env vars win on the cloud

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o")   # override via env var
MAX_IMAGE_PX   = int(os.getenv("MAX_IMAGE_PX", "1024")) # resize long edge to this

if not OPENAI_API_KEY:
    print("FATAL: OPENAI_API_KEY is not set. Set it in .env or as an environment variable.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("obd2ai")

# ── FastAPI app ────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OBD2 AI Backend",
    description="Analyse vehicle dashboard images using OpenAI Vision",
    version="2.0.0",
)

# CORS — allow all origins so Android, iOS and Web clients can connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Prompts ────────────────────────────────────────────────────────────────────

_SYSTEM = (
    "You are an expert automotive diagnostic AI. "
    "You specialise in reading vehicle dashboards, warning lights, "
    "and OBD/DTC diagnostic codes. "
    "You always respond in Hebrew and return ONLY valid JSON — no prose, "
    "no markdown fences."
)

_USER_PROMPT = """Carefully examine this vehicle dashboard image.

Your tasks:
1. Read ALL visible text (Hebrew, English, numbers, warning messages)
2. Identify every warning light that is ON (by icon, colour, or label)
3. Extract any OBD/DTC codes visible (format: P/C/B/U + 4 digits, e.g. P0420)
4. Diagnose the vehicle problems based on what you observe
5. Provide clear safety guidance

Return ONLY a valid JSON object — no extra text, no code fences.
Use EXACTLY these keys:

{
  "problem": "main problem description in Hebrew (2-3 sentences)",
  "severity": "one of exactly: קריטי | גבוה | בינוני | נמוך",
  "can_drive": "כן or לא followed by a brief Hebrew explanation",
  "actions": ["action 1 in Hebrew", "action 2 in Hebrew"],
  "possible_causes": ["cause 1 in Hebrew", "cause 2 in Hebrew"],
  "need_garage": "כן or לא followed by a brief Hebrew explanation",
  "estimated_cost": "estimated NIS cost range or explanation in Hebrew",
  "emergency": "כן or לא",
  "detected_text": "all text you can read from the image (preserve original language)",
  "possible_obd_codes": ["P0420", "P0171"]
}

Rules:
- If the image is blurry or hard to read, still try your best and note it in "problem".
- If no problems are detected, set "problem" to "לא זוהו בעיות ברורות בתמונה".
- "possible_obd_codes" must be a list of strings; empty list [] if none found.
- "actions" and "possible_causes" must be lists; at least one item each.
- All string values must be in Hebrew except for OBD code strings and "detected_text".
"""

# ── Image helpers ──────────────────────────────────────────────────────────────

def _image_to_base64(raw_bytes: bytes) -> str:
    """
    Open an image from bytes, resize it so the longest edge ≤ MAX_IMAGE_PX,
    convert to JPEG, and return a base64-encoded string.
    Keeps everything in memory — no disk I/O.
    """
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


# ── JSON extraction ────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any]:
    """
    Parse a JSON object from the model response.
    Handles cases where the model accidentally wraps output in ```json fences.
    """
    # 1. Direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 2. Strip markdown code fences then retry
    cleaned = re.sub(r"```(?:json)?\s*", "", text, flags=re.I).strip().strip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # 3. Grab the outermost { … } block
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON in model response (first 400 chars): {text[:400]}")


def _safe_defaults(result: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure every field the Flutter app expects is present.
    Guards against partial or malformed model output.
    """
    def _str(key: str, default: str = "") -> None:
        if not isinstance(result.get(key), str):
            result[key] = default

    def _list(key: str) -> None:
        val = result.get(key)
        if not isinstance(val, list):
            result[key] = [str(val)] if val else []

    _str("problem",        "לא זוהו בעיות")
    _str("severity",       "נמוך")
    _str("can_drive",      "כן")
    _str("need_garage",    "לא")
    _str("estimated_cost", "לא ידוע")
    _str("emergency",      "לא")
    _str("detected_text",  "")
    _list("actions")
    _list("possible_causes")
    _list("possible_obd_codes")

    # Normalise emergency to Hebrew string that isEmergency() can read
    emerg = result["emergency"]
    if isinstance(emerg, bool):
        result["emergency"] = "כן" if emerg else "לא"
    elif str(emerg).lower() in ("true", "1", "yes"):
        result["emergency"] = "כן"
    elif str(emerg).lower() in ("false", "0", "no"):
        result["emergency"] = "לא"

    return result


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root() -> dict[str, str]:
    return {"message": "OBD2 AI Backend Running", "version": "2.0.0"}


@app.get("/health")
def health() -> dict[str, str]:
    """Health-check endpoint used by Render / Railway / load balancers."""
    return {"status": "ok", "model": OPENAI_MODEL}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Accept a vehicle dashboard image, analyse it with OpenAI Vision,
    and return structured JSON compatible with the Flutter frontend.
    """
    log.info("Upload received: filename=%s content_type=%s", file.filename, file.content_type)

    # ── 1. Read bytes ─────────────────────────────────────────────────────
    try:
        raw = await file.read()
    except Exception as exc:
        log.error("File read error: %s", exc)
        raise HTTPException(status_code=400, detail="Cannot read uploaded file") from exc

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    log.info("File size: %d bytes", len(raw))

    # ── 2. Prepare image (in-memory resize + base64) ──────────────────────
    try:
        b64 = _image_to_base64(raw)
    except Exception as exc:
        log.error("Image processing error: %s", exc)
        raise HTTPException(status_code=422, detail="Invalid or unsupported image") from exc

    # ── 3. OpenAI Vision call ─────────────────────────────────────────────
    try:
        log.info("Calling OpenAI Vision: model=%s", OPENAI_MODEL)
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[
                {"role": "system", "content": _SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64}",
                                "detail": "high",  # high-res analysis of dashboard details
                            },
                        },
                        {"type": "text", "text": _USER_PROMPT},
                    ],
                },
            ],
            max_tokens=1500,
            temperature=0.1,  # low temp for consistent, factual output
        )
        ai_text: str = response.choices[0].message.content or ""
        log.info(
            "OpenAI response: %d chars | finish_reason=%s | tokens=%s",
            len(ai_text),
            response.choices[0].finish_reason,
            response.usage,
        )
    except OpenAIError as exc:
        log.error("OpenAI API error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc
    except Exception as exc:
        log.error("Unexpected error calling OpenAI: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    # ── 4. Parse JSON ─────────────────────────────────────────────────────
    try:
        result = _extract_json(ai_text)
    except ValueError as exc:
        log.error("JSON parse failed: %s", exc)
        # Fallback — never let a bad model response crash the Flutter app
        result = {
            "problem": "שגיאה בניתוח התמונה. נסה שוב עם תמונה ברורה יותר.",
            "severity": "נמוך",
            "can_drive": "לא ידוע",
            "actions": ["נסה להעלות תמונה ברורה יותר של לוח המחוונים"],
            "possible_causes": ["תמונה לא ברורה או אינה מציגה לוח מחוונים"],
            "need_garage": "לא ידוע",
            "estimated_cost": "לא ידוע",
            "emergency": "לא",
            "detected_text": ai_text[:500],
            "possible_obd_codes": [],
        }

    # ── 5. Normalise and guarantee all fields ─────────────────────────────
    result = _safe_defaults(result)

    log.info(
        "Analysis complete: problem=%r severity=%s emergency=%s",
        result["problem"][:60],
        result["severity"],
        result["emergency"],
    )
    return result
