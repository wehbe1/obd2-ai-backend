"""
OBD2 AI Backend  v3.0
─────────────────────
Production-grade automotive diagnostic AI.

Uses OpenAI Vision with the strongest available model (gpt-4o default).
Supports fallback models so deployment never breaks on model deprecations.

Analysable inputs:
  • Car dashboards / instrument clusters
  • OBD / DTC scanner screens
  • Warning-light arrays (icons only)
  • Mechanic report photos
  • Error-message screens

Endpoint: POST /upload → rich structured JSON
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

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_IMAGE_PX   = int(os.getenv("MAX_IMAGE_PX", "1536"))  # longer edge limit

if not OPENAI_API_KEY:
    print("FATAL: OPENAI_API_KEY is not set. "
          "Set it in .env or as a cloud environment variable.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

# Model priority list — strongest vision-capable model first.
# Override the primary with the OPENAI_MODEL environment variable.
_PRIMARY = os.getenv("OPENAI_MODEL", "gpt-4o")
_FALLBACK_CHAIN = ["gpt-4o", "gpt-4-turbo", "gpt-4o-mini"]

_seen: set[str] = set()
MODEL_LIST: list[str] = []
for _m in [_PRIMARY] + _FALLBACK_CHAIN:
    if _m not in _seen:
        _seen.add(_m)
        MODEL_LIST.append(_m)

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("obd2ai")

# ── FastAPI ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OBD2 AI Backend",
    description="Production automotive diagnostic AI — OpenAI Vision",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── System prompt ──────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a professional automotive diagnostic AI with expert mechanic knowledge.
You perform precise visual inspections of vehicle images.

ABSOLUTE RULES:
1. Return ONLY valid JSON — no prose, no markdown, no code fences.
2. NEVER hallucinate. If a value is not clearly visible, write exactly: "not_visible"
3. All explanatory text fields must be written in Hebrew (עברית).
4. OBD codes: standard format — one letter + 4 digits (P0420, C1234, B0100, U0100).
5. severity must be exactly one of: קריטי | גבוה | בינוני | נמוך
6. safety_recommendation must be exactly one of: stop_immediately | drive_to_garage | safe_to_drive
7. confidence: decimal between 0.0 and 1.0 (your certainty about the analysis).
8. Images may be blurry or partial — do your best and report uncertainty honestly.\
"""

# ── User prompt ────────────────────────────────────────────────────────────────

_USER_PROMPT = """\
Perform a comprehensive automotive diagnostic inspection of this image.

The image may show: a car dashboard, instrument cluster, OBD/DTC scanner screen,
warning-light panel, mechanic report, or vehicle error messages.

INSPECT ALL OF THE FOLLOWING:
• Every warning light that is ON — identify by icon shape, color, and label
• All text visible on the dashboard or scanner (Hebrew, English, numbers)
• Any OBD / DTC diagnostic codes displayed
• Instrument readings: RPM, speed, coolant temperature, fuel level, battery voltage
• Overall vehicle state and urgency

Return EXACTLY this JSON structure — no extra keys, no missing keys:

{
  "problem": "Main problem summary in Hebrew, 2-3 sentences. If no problems: 'לא זוהו בעיות ברורות בתמונה'",
  "simple_explanation": "Non-technical explanation for the car owner in Hebrew. What does this mean for them? What should they do right now?",
  "mechanic_explanation": "Technical explanation at professional mechanic level in Hebrew. Specify: affected system, likely root cause, diagnostic steps.",
  "severity": "Exactly one of: קריטי | גבוה | בינוני | נמוך",
  "safety_recommendation": "Exactly one of: stop_immediately | drive_to_garage | safe_to_drive",
  "can_drive": "'כן' or 'לא' followed by a short Hebrew explanation",
  "need_garage": "'כן' or 'לא' followed by a short Hebrew explanation",
  "emergency": "'כן' or 'לא'",
  "confidence": 0.90,
  "uncertainty": "Empty string '' if image is clear. Otherwise describe the image quality issue in Hebrew.",
  "detected_warning_lights": [
    {
      "name": "Warning light name in Hebrew (e.g. 'בדוק מנוע', 'לחץ שמן נמוך')",
      "color": "Exactly one of: red | orange | yellow | blue | green | white",
      "severity": "Exactly one of: קריטי | גבוה | בינוני | נמוך",
      "description": "What this warning light means and why it activates, in Hebrew"
    }
  ],
  "detected_dashboard_text": "All readable text from the image verbatim. Preserve original language (Hebrew/English/numbers). Empty string if none.",
  "detected_obd_codes": [
    {
      "code": "P0420",
      "description": "Plain-Hebrew description of what this code means and which system it affects",
      "severity": "Exactly one of: קריטי | גבוה | בינוני | נמוך"
    }
  ],
  "detected_vehicle_state": {
    "rpm": "Numeric RPM reading, or 'not_visible'",
    "speed": "Speed with unit (e.g. '80 km/h'), or 'not_visible'",
    "temperature": "Coolant temperature with unit (e.g. '95°C'), or 'not_visible'",
    "fuel": "Fuel level (e.g. '1/4', '25%', 'נמוך'), or 'not_visible'",
    "battery": "Battery voltage or indicator (e.g. '12.4V', 'נמוכה'), or 'not_visible'"
  },
  "possible_causes": [
    "Probable cause 1 in Hebrew",
    "Probable cause 2 in Hebrew"
  ],
  "recommended_steps": [
    "Immediate action step 1 in Hebrew",
    "Action step 2 in Hebrew"
  ],
  "estimated_cost": "Realistic repair cost range in Israel in NIS (₪), with brief Hebrew explanation. Example: '500-1,500 ₪ לתיקון חיישן חמצן'",
  "detected_text": "Same as detected_dashboard_text (kept for compatibility)",
  "possible_obd_codes": ["P0420"],
  "actions": ["Same content as recommended_steps, kept for compatibility"]
}

FINAL RULES:
- detected_warning_lights: [] if no warning lights are visible. Do NOT guess.
- detected_obd_codes: [] if no codes visible. Do NOT guess codes.
- possible_obd_codes: flat string list of codes from detected_obd_codes.
- actions must equal recommended_steps content.
- detected_text must equal detected_dashboard_text.
- If image is blurry or unclear: set confidence < 0.5 and describe in uncertainty field.
- If no problems found: severity='נמוך', safety_recommendation='safe_to_drive', emergency='לא'.
"""

# ── Image processing ───────────────────────────────────────────────────────────

def _image_to_base64(raw_bytes: bytes) -> str:
    """Resize image to MAX_IMAGE_PX on longest edge, convert to JPEG, base64-encode."""
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


# ── JSON extraction ────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any]:
    """Robustly parse JSON from the model response."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    cleaned = re.sub(r"```(?:json)?\s*", "", text, flags=re.I).strip().strip("`")
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass

    raise ValueError(f"No valid JSON in model response: {text[:400]}")


# ── Field normalisation ────────────────────────────────────────────────────────

def _safe_defaults(result: dict[str, Any]) -> dict[str, Any]:
    """Guarantee every field the Flutter app expects is present and correctly typed."""

    def _str(key: str, default: str = "") -> None:
        if not isinstance(result.get(key), str):
            result[key] = default

    def _list(key: str) -> None:
        val = result.get(key)
        if not isinstance(val, list):
            result[key] = [str(val)] if val else []

    def _float_field(key: str, default: float) -> None:
        try:
            result[key] = float(result.get(key, default))
        except (TypeError, ValueError):
            result[key] = default

    def _dict_field(key: str, default: dict) -> None:
        if not isinstance(result.get(key), dict):
            result[key] = default

    # ── Legacy fields (required by existing Flutter clients) ──────────────────
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

    # ── v3 enhanced fields ────────────────────────────────────────────────────
    _str("simple_explanation",      "")
    _str("mechanic_explanation",    "")
    _str("safety_recommendation",   "safe_to_drive")
    _str("detected_dashboard_text", result.get("detected_text", ""))
    _str("uncertainty",             "")
    _float_field("confidence",      0.7)
    _list("recommended_steps")
    _list("detected_warning_lights")
    _list("detected_obd_codes")
    _dict_field("detected_vehicle_state", {
        "rpm": "not_visible", "speed": "not_visible",
        "temperature": "not_visible", "fuel": "not_visible",
        "battery": "not_visible",
    })

    # ── Cross-field sync ──────────────────────────────────────────────────────

    # Sync recommended_steps ↔ actions
    if result["recommended_steps"] and not result["actions"]:
        result["actions"] = result["recommended_steps"]
    elif result["actions"] and not result["recommended_steps"]:
        result["recommended_steps"] = result["actions"]

    # Sync detected_dashboard_text ↔ detected_text
    if result["detected_dashboard_text"] and not result["detected_text"]:
        result["detected_text"] = result["detected_dashboard_text"]
    elif result["detected_text"] and not result["detected_dashboard_text"]:
        result["detected_dashboard_text"] = result["detected_text"]

    # Populate possible_obd_codes from detected_obd_codes if missing
    if result["detected_obd_codes"] and not result["possible_obd_codes"]:
        result["possible_obd_codes"] = [
            c.get("code", "") for c in result["detected_obd_codes"]
            if isinstance(c, dict) and c.get("code")
        ]

    # ── Normalise boolean-like fields ─────────────────────────────────────────

    emerg = result["emergency"]
    if isinstance(emerg, bool):
        result["emergency"] = "כן" if emerg else "לא"
    elif str(emerg).lower() in ("true", "1", "yes"):
        result["emergency"] = "כן"
    else:
        result["emergency"] = "לא"

    # ── Validate / infer safety_recommendation ────────────────────────────────
    valid_recs = {"stop_immediately", "drive_to_garage", "safe_to_drive"}
    if result["safety_recommendation"] not in valid_recs:
        if result["emergency"] == "כן":
            result["safety_recommendation"] = "stop_immediately"
        elif result["need_garage"].startswith("כן"):
            result["safety_recommendation"] = "drive_to_garage"
        else:
            result["safety_recommendation"] = "safe_to_drive"

    # ── Clamp confidence ──────────────────────────────────────────────────────
    try:
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    except (TypeError, ValueError):
        result["confidence"] = 0.7

    # ── Ensure vehicle state values are strings ───────────────────────────────
    vs = result["detected_vehicle_state"]
    for k in ("rpm", "speed", "temperature", "fuel", "battery"):
        if k not in vs or not isinstance(vs[k], str):
            vs[k] = "not_visible"

    return result


# ── OpenAI Vision call with model fallback ─────────────────────────────────────

def _call_openai_vision(b64_image: str) -> str:
    """
    Try each model in MODEL_LIST until one succeeds.
    Model-not-found errors trigger the next fallback.
    Any other API error is re-raised immediately.
    """
    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{b64_image}",
                        "detail": "high",
                    },
                },
                {"type": "text", "text": _USER_PROMPT},
            ],
        },
    ]

    last_exc: Exception | None = None

    for model in MODEL_LIST:
        try:
            log.info("Calling model: %s", model)
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2500,
                temperature=0.05,           # near-zero for factual, consistent output
                response_format={"type": "json_object"},
            )
            ai_text = response.choices[0].message.content or ""
            log.info(
                "Model %s → %d chars | finish=%s | tokens=%s",
                model, len(ai_text),
                response.choices[0].finish_reason,
                response.usage,
            )
            return ai_text

        except OpenAIError as exc:
            err_lower = str(exc).lower()
            is_model_error = any(
                kw in err_lower
                for kw in ("model", "not found", "does not exist",
                            "invalid model", "no such model", "deprecated")
            )
            if is_model_error:
                log.warning("Model %s unavailable (%s) — trying next", model, exc)
                last_exc = exc
                continue
            # Any other API error (quota, auth, network) — re-raise immediately
            raise

    raise last_exc or OpenAIError("No vision-capable OpenAI model is available")


# ── Fallback response ──────────────────────────────────────────────────────────

def _fallback_response(raw_text: str = "") -> dict[str, Any]:
    return {
        "problem": "שגיאה בניתוח התמונה. נסה שוב עם תמונה ברורה יותר.",
        "simple_explanation": "לא הצלחנו לנתח את התמונה. אנא העלה תמונה ברורה יותר של לוח המחוונים.",
        "mechanic_explanation": "ניתוח נכשל עקב תגובת מודל AI לא תקינה. Raw output attached.",
        "severity": "נמוך",
        "safety_recommendation": "safe_to_drive",
        "can_drive": "לא ידוע",
        "need_garage": "לא ידוע",
        "emergency": "לא",
        "confidence": 0.1,
        "uncertainty": "לא ניתן לנתח את התמונה כראוי",
        "detected_warning_lights": [],
        "detected_dashboard_text": "",
        "detected_obd_codes": [],
        "detected_vehicle_state": {
            "rpm": "not_visible", "speed": "not_visible",
            "temperature": "not_visible", "fuel": "not_visible",
            "battery": "not_visible",
        },
        "recommended_steps": ["נסה להעלות תמונה ברורה יותר של לוח המחוונים"],
        "possible_causes": ["תמונה לא ברורה או אינה מציגה לוח מחוונים"],
        "estimated_cost": "לא ידוע",
        "detected_text": raw_text[:300],
        "possible_obd_codes": [],
        "actions": ["נסה להעלות תמונה ברורה יותר של לוח המחוונים"],
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/")
def root() -> dict[str, Any]:
    return {
        "message": "OBD2 AI Backend v3.0",
        "model_priority": MODEL_LIST,
        "max_image_px": MAX_IMAGE_PX,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "models": MODEL_LIST, "version": "3.0.0"}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Accept a vehicle image, run deep visual diagnostic analysis via OpenAI Vision,
    and return a structured JSON report compatible with the Flutter app.
    """
    log.info("Upload: filename=%s content_type=%s", file.filename, file.content_type)

    # 1. Read file bytes
    try:
        raw = await file.read()
    except Exception as exc:
        log.error("File read error: %s", exc)
        raise HTTPException(status_code=400, detail="Cannot read uploaded file") from exc

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    log.info("Image size: %d bytes", len(raw))

    # 2. Resize + base64-encode in memory
    try:
        b64 = _image_to_base64(raw)
    except Exception as exc:
        log.error("Image processing error: %s", exc)
        raise HTTPException(status_code=422, detail="Invalid or unsupported image format") from exc

    # 3. Call OpenAI Vision (with model fallback)
    try:
        ai_text = _call_openai_vision(b64)
    except OpenAIError as exc:
        log.error("OpenAI error: %s", exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc
    except Exception as exc:
        log.error("Unexpected error: %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    # 4. Parse JSON
    try:
        result = _extract_json(ai_text)
    except ValueError as exc:
        log.error("JSON parse failed: %s", exc)
        result = _fallback_response(ai_text)

    # 5. Normalise all fields
    result = _safe_defaults(result)

    log.info(
        "Analysis done: severity=%s safety=%s confidence=%.2f lights=%d codes=%d",
        result["severity"],
        result["safety_recommendation"],
        result["confidence"],
        len(result["detected_warning_lights"]),
        len(result["detected_obd_codes"]),
    )

    return result
