"""
OBD2 AI Backend  v4.0  — Professional Automotive Diagnostic Platform
──────────────────────────────────────────────────────────────────────
Architecture:
  POST /upload
    │
    ├─ Pass 1  (fast, ~4 s)  — Extract visible OBD codes from image
    │      ↓
    │   Python OBD Database  →  structured causes, actions, cost (₪)
    │      ↓
    ├─ Pass 2  (full, ~25 s) — Deep visual diagnosis + DB context
    │      ↓
    │   Post-processing: enrich detected_obd_codes with DB data
    │      ↓
    └─ Return rich JSON  (compatible with Flutter v3 models)
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

import obd_database as db

# ── Environment ────────────────────────────────────────────────────────────────

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
MAX_IMAGE_PX   = int(os.getenv("MAX_IMAGE_PX", "1536"))

if not OPENAI_API_KEY:
    print("FATAL: OPENAI_API_KEY is not set.")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

# Model priority — strongest vision model first.  Override via OPENAI_MODEL env var.
_PRIMARY        = os.getenv("OPENAI_MODEL", "gpt-4o")
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
log.info("OBD2 AI v4.0 starting. Models: %s | DB entries: %d", MODEL_LIST, db.db_size())

# ── FastAPI ────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OBD2 AI Backend",
    description="Professional Automotive Diagnostic Platform — v4.0",
    version="4.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── PASS 1 — Code extraction prompt ───────────────────────────────────────────

_EXTRACTION_SYSTEM = (
    "You are a vehicle diagnostic code reader. "
    "Your ONLY task is to extract OBD/DTC codes visible in the image. "
    "Return ONLY valid JSON — no prose."
)

_EXTRACTION_PROMPT = (
    'List ALL OBD/DTC diagnostic codes visible in this image '
    '(each code is one letter followed by 4 digits, e.g. P0420, C0031, B0001, U0100). '
    'Return ONLY this JSON: {"codes": ["P0420", "C0031"]}\n'
    'If no codes are visible, return: {"codes": []}'
)

# ── PASS 2 — Full diagnostic system prompt ────────────────────────────────────

_SYSTEM = """\
You are a senior automotive diagnostic technician with 20+ years of hands-on
workshop experience. You hold ASE Master Technician certification and have worked
with European, Asian and American vehicles.

Your job is to perform a thorough, professional visual inspection of the uploaded
vehicle image and produce a comprehensive diagnostic report.

ABSOLUTE RULES:
1. Return ONLY valid JSON. No prose, no markdown, no code fences.
2. NEVER hallucinate. If a value is not clearly visible write exactly: "not_visible"
3. All narrative/explanation fields MUST be written in Hebrew (עברית).
4. OBD code format: one letter + 4 digits (P0420, C0031, B0001, U0100).
5. severity must be EXACTLY one of: קריטי | גבוה | בינוני | נמוך
6. safety_recommendation must be EXACTLY one of:
     stop_immediately | drive_to_garage | safe_to_drive
7. repair_urgency must be EXACTLY one of:
     immediate | within_24h | within_week | routine | not_required
8. confidence: decimal 0.0–1.0 (your honest certainty).
9. If the image is unclear, still try your best and report uncertainty honestly.
10. Write like a professional speaking to a worried car owner — clear, direct, no panic.
"""

# ── PASS 2 — Full diagnostic user prompt template ─────────────────────────────
# {db_context} is replaced at runtime with database lookup results

_ANALYSIS_PROMPT_TMPL = """\
{db_context}

═══════════════════════════════════════════════════════════
DIAGNOSTIC TASK
═══════════════════════════════════════════════════════════

Perform a COMPLETE professional automotive inspection of this image.

The image may show: car dashboard, instrument cluster, OBD/DTC scanner screen,
warning-light panel, mechanic diagnostic report, or error message screen.

INSPECT AND REPORT ON ALL OF THE FOLLOWING:

1. INSTRUMENT CLUSTER READINGS
   • RPM (tachometer reading)
   • Speed (speedometer)
   • Coolant temperature
   • Fuel level
   • Battery voltage / charge indicator
   • Odometer / trip meter reading
   • Gear position (P/R/N/D/1/2/3 / gear number)

2. WARNING LIGHTS & INDICATORS (every illuminated light)
   For each detected light report: name (Hebrew), colour, severity, technical meaning

   Common lights to look for:
   Check Engine (MIL) • ABS • Airbag/SRS • Oil Pressure • Battery/Alternator
   Brake Warning • TPMS (tyre pressure) • Coolant Temperature • Service Due
   Traction Control (TCS) • ESP/DSC/VSC • Glow Plug (diesel) • DPF (diesel)
   AdBlue/DEF • Hybrid/EV battery • Transmission temperature • Power steering
   Fuel low • Door ajar • Seatbelt • Pre-collision warning

3. OBD / DTC CODES
   Extract ALL visible scanner codes. For each code return:
   exact code, what system it affects, Hebrew explanation, severity.
   If database context was provided above — USE IT as authoritative source.

4. DASHBOARD TEXT
   All readable text verbatim (Hebrew, English, numbers, error messages).

5. OVERALL DIAGNOSIS
   Based on EVERYTHING you observe, produce a professional diagnosis.
   Consider the combination of all warning lights + codes + readings together.

═══════════════════════════════════════════════════════════
REQUIRED JSON OUTPUT — Return EXACTLY this structure:
═══════════════════════════════════════════════════════════

{{
  "problem": "2–3 sentence Hebrew summary of the main problem(s). If no issues: 'לא זוהו בעיות ברורות בתמונה'",
  "simple_explanation": "Non-technical explanation in Hebrew for the car owner: what does this mean for them today? What should they do RIGHT NOW?",
  "mechanic_explanation": "Professional Hebrew explanation at senior-technician level: affected systems, likely root cause, diagnostic workflow, tests to confirm.",
  "severity": "קריטי | גבוה | בינוני | נמוך",
  "safety_recommendation": "stop_immediately | drive_to_garage | safe_to_drive",
  "repair_urgency": "immediate | within_24h | within_week | routine | not_required",
  "can_drive": "'כן' or 'לא' followed by a brief Hebrew explanation",
  "need_garage": "'כן' or 'לא' followed by a brief Hebrew explanation",
  "emergency": "'כן' or 'לא'",
  "confidence": 0.92,
  "uncertainty": "Empty string '' if image is clear and analysis is confident. Otherwise briefly describe image quality issues in Hebrew.",
  "detected_warning_lights": [
    {{
      "name": "Hebrew name of warning light (e.g. 'בדוק מנוע', 'לחץ שמן נמוך', 'ABS')",
      "color": "red | orange | yellow | blue | green | white",
      "severity": "קריטי | גבוה | בינוני | נמוך",
      "description": "Hebrew: what this light means technically and why it activates"
    }}
  ],
  "detected_dashboard_text": "All readable text verbatim. Preserve original language.",
  "detected_obd_codes": [
    {{
      "code": "P0420",
      "description": "Hebrew: what this code means and which system it affects",
      "severity": "קריטי | גבוה | בינוני | נמוך"
    }}
  ],
  "detected_vehicle_state": {{
    "rpm": "Numeric RPM or 'not_visible'",
    "speed": "Speed with unit e.g. '85 km/h' or 'not_visible'",
    "temperature": "Coolant temp with unit e.g. '92°C' or 'not_visible'",
    "fuel": "Fuel level e.g. '1/4', '30%', 'נמוך' or 'not_visible'",
    "battery": "Battery voltage/indicator e.g. '12.4V', 'תקין' or 'not_visible'",
    "odometer": "Odometer reading e.g. '87,432 km' or 'not_visible'",
    "gear_position": "Gear position e.g. 'D', 'P', 'N', '3', 'מנוע כבוי' or 'not_visible'"
  }},
  "possible_causes": [
    "Most likely cause in Hebrew",
    "Second most likely cause in Hebrew",
    "Third possible cause in Hebrew"
  ],
  "recommended_steps": [
    "Immediate action step 1 in Hebrew",
    "Action step 2 in Hebrew",
    "Action step 3 in Hebrew"
  ],
  "estimated_cost": "Realistic repair cost in Israel in NIS with Hebrew explanation e.g. '800–3,000 ₪ להחלפת קטליזטור'",
  "detected_text": "Same as detected_dashboard_text (legacy field)",
  "possible_obd_codes": ["P0420"],
  "actions": ["Same content as recommended_steps (legacy field)"]
}}

FINAL RULES:
• detected_warning_lights: [] if no warning lights visible — do NOT guess.
• detected_obd_codes: [] if no codes visible — do NOT invent codes.
• possible_obd_codes = flat string list extracted from detected_obd_codes.
• actions = same content as recommended_steps.
• detected_text = same as detected_dashboard_text.
• If no problems detected: severity='נמוך', safety_recommendation='safe_to_drive',
  repair_urgency='not_required', emergency='לא'.
• Prioritise the database context entries above when explaining detected codes.
• Be specific — name the exact component, not just "system malfunction".
"""

# ── Image processing ───────────────────────────────────────────────────────────

def _image_to_base64(raw_bytes: bytes) -> str:
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
    img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=92, optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


# ── JSON helpers ───────────────────────────────────────────────────────────────

def _extract_json(text: str) -> dict[str, Any]:
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


# ── OpenAI Vision call with fallback ──────────────────────────────────────────

def _call_model(messages: list[dict], max_tokens: int = 400,
                *, json_mode: bool = True) -> str:
    """Call models in priority order; retry on model-not-found errors only."""
    last_exc: Exception | None = None
    fmt = {"type": "json_object"} if json_mode else {"type": "text"}

    for model in MODEL_LIST:
        try:
            log.info("Calling %s (max_tokens=%d)", model, max_tokens)
            resp = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.05,
                response_format=fmt,
            )
            text = resp.choices[0].message.content or ""
            log.info("Model %s → %d chars | finish=%s | tokens=%s",
                     model, len(text), resp.choices[0].finish_reason, resp.usage)
            return text
        except OpenAIError as exc:
            err = str(exc).lower()
            is_model_err = any(kw in err for kw in (
                "model", "not found", "does not exist",
                "invalid model", "no such model", "deprecated",
            ))
            if is_model_err:
                log.warning("Model %s unavailable — trying next. Error: %s", model, exc)
                last_exc = exc
                continue
            raise  # quota / auth / network — fail fast

    raise last_exc or OpenAIError("No vision-capable model available")


# ── Pass 1: Code extraction ────────────────────────────────────────────────────

def _pass1_extract_codes(b64: str) -> list[str]:
    """
    Quick pass to extract visible OBD codes from the image.
    Returns a list of uppercase code strings like ['P0420', 'C0031'].
    Falls back to empty list on any error — never blocks Pass 2.
    """
    try:
        messages = [
            {"role": "system", "content": _EXTRACTION_SYSTEM},
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "low"},
                    },
                    {"type": "text", "text": _EXTRACTION_PROMPT},
                ],
            },
        ]
        text = _call_model(messages, max_tokens=200)
        parsed = _extract_json(text)
        raw_codes = parsed.get("codes", [])
        codes = [c.strip().upper() for c in raw_codes if isinstance(c, str) and c.strip()]
        log.info("Pass 1 extracted codes: %s", codes)
        return codes
    except Exception as exc:
        log.warning("Pass 1 extraction failed (non-fatal): %s", exc)
        return []


# ── Pass 2: Full diagnosis ─────────────────────────────────────────────────────

def _pass2_full_analysis(b64: str, db_context: str) -> str:
    prompt = _ANALYSIS_PROMPT_TMPL.format(db_context=db_context)
    messages = [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{b64}", "detail": "high"},
                },
                {"type": "text", "text": prompt},
            ],
        },
    ]
    return _call_model(messages, max_tokens=3200)


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

    def _float_f(key: str, default: float) -> None:
        try:
            result[key] = float(result.get(key, default))
        except (TypeError, ValueError):
            result[key] = default

    def _dict_f(key: str, default: dict) -> None:
        if not isinstance(result.get(key), dict):
            result[key] = default

    # Legacy fields — required by existing Flutter clients
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

    # v3 / v4 fields
    _str("simple_explanation",      "")
    _str("mechanic_explanation",    "")
    _str("safety_recommendation",   "safe_to_drive")
    _str("repair_urgency",          "routine")
    _str("detected_dashboard_text", result.get("detected_text", ""))
    _str("uncertainty",             "")
    _float_f("confidence",          0.7)
    _list("recommended_steps")
    _list("detected_warning_lights")
    _list("detected_obd_codes")
    _dict_f("detected_vehicle_state", {
        "rpm": "not_visible", "speed": "not_visible",
        "temperature": "not_visible", "fuel": "not_visible",
        "battery": "not_visible", "odometer": "not_visible",
        "gear_position": "not_visible",
    })

    # Cross-field sync
    if result["recommended_steps"] and not result["actions"]:
        result["actions"] = result["recommended_steps"]
    elif result["actions"] and not result["recommended_steps"]:
        result["recommended_steps"] = result["actions"]

    if result["detected_dashboard_text"] and not result["detected_text"]:
        result["detected_text"] = result["detected_dashboard_text"]
    elif result["detected_text"] and not result["detected_dashboard_text"]:
        result["detected_dashboard_text"] = result["detected_text"]

    # Populate flat possible_obd_codes list
    if result["detected_obd_codes"] and not result["possible_obd_codes"]:
        result["possible_obd_codes"] = [
            c.get("code", "") for c in result["detected_obd_codes"]
            if isinstance(c, dict) and c.get("code")
        ]

    # Normalise emergency
    emerg = result["emergency"]
    if isinstance(emerg, bool):
        result["emergency"] = "כן" if emerg else "לא"
    elif str(emerg).lower() in ("true", "1", "yes"):
        result["emergency"] = "כן"
    else:
        result["emergency"] = "לא"

    # Validate safety_recommendation
    valid_recs = {"stop_immediately", "drive_to_garage", "safe_to_drive"}
    if result["safety_recommendation"] not in valid_recs:
        if result["emergency"] == "כן":
            result["safety_recommendation"] = "stop_immediately"
        elif result["need_garage"].startswith("כן"):
            result["safety_recommendation"] = "drive_to_garage"
        else:
            result["safety_recommendation"] = "safe_to_drive"

    # Validate repair_urgency
    valid_urgency = {"immediate", "within_24h", "within_week", "routine", "not_required"}
    if result["repair_urgency"] not in valid_urgency:
        rec = result["safety_recommendation"]
        if rec == "stop_immediately":
            result["repair_urgency"] = "immediate"
        elif rec == "drive_to_garage":
            result["repair_urgency"] = "within_24h"
        else:
            result["repair_urgency"] = "routine"

    # Clamp confidence
    try:
        result["confidence"] = max(0.0, min(1.0, float(result["confidence"])))
    except (TypeError, ValueError):
        result["confidence"] = 0.7

    # Ensure vehicle state values are strings; fill in missing new fields
    vs = result["detected_vehicle_state"]
    for k in ("rpm", "speed", "temperature", "fuel", "battery", "odometer", "gear_position"):
        if k not in vs or not isinstance(vs[k], str):
            vs[k] = "not_visible"

    return result


# ── Fallback response ──────────────────────────────────────────────────────────

def _fallback_response(raw_text: str = "") -> dict[str, Any]:
    return {
        "problem": "שגיאה בניתוח התמונה. נסה שוב עם תמונה ברורה יותר.",
        "simple_explanation": "לא הצלחנו לנתח את התמונה. אנא העלה תמונה ברורה יותר של לוח המחוונים.",
        "mechanic_explanation": "Analysis failed — raw model output attached for debugging.",
        "severity": "נמוך",
        "safety_recommendation": "safe_to_drive",
        "repair_urgency": "not_required",
        "can_drive": "לא ידוע",
        "need_garage": "לא ידוע",
        "emergency": "לא",
        "confidence": 0.1,
        "uncertainty": "לא ניתן לנתח את התמונה כראוי",
        "detected_warning_lights": [],
        "detected_dashboard_text": "",
        "detected_obd_codes": [],
        "detected_vehicle_state": {
            "rpm": "not_visible", "speed": "not_visible", "temperature": "not_visible",
            "fuel": "not_visible", "battery": "not_visible",
            "odometer": "not_visible", "gear_position": "not_visible",
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
        "message": "OBD2 AI Backend v4.0 — Professional Diagnostic Platform",
        "model_priority": MODEL_LIST,
        "obd_db_size": db.db_size(),
        "max_image_px": MAX_IMAGE_PX,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "version": "4.0.0", "models": MODEL_LIST,
            "obd_db_size": db.db_size()}


@app.post("/upload")
async def upload_image(file: UploadFile = File(...)) -> dict[str, Any]:
    """
    Two-pass diagnostic pipeline:
      Pass 1 — fast code extraction
      Pass 2 — full visual diagnosis enriched with OBD knowledge base
    """
    log.info("Upload: filename=%s content_type=%s", file.filename, file.content_type)

    # 1. Read bytes
    try:
        raw = await file.read()
    except Exception as exc:
        log.error("File read error: %s", exc)
        raise HTTPException(status_code=400, detail="Cannot read uploaded file") from exc

    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    log.info("Image size: %d bytes", len(raw))

    # 2. Resize + encode
    try:
        b64 = _image_to_base64(raw)
    except Exception as exc:
        log.error("Image processing error: %s", exc)
        raise HTTPException(status_code=422, detail="Invalid or unsupported image") from exc

    # 3. Pass 1 — extract OBD codes (non-blocking: errors ignored)
    extracted_codes = _pass1_extract_codes(b64)

    # 4. DB lookup — build context block for Pass 2
    db_entries   = db.lookup(extracted_codes) if extracted_codes else []
    db_context   = db.build_context_block(db_entries) if db_entries else (
        "No OBD codes were detected in Pass 1 — perform visual inspection only."
    )
    log.info("DB context built for codes: %s", extracted_codes)

    # 5. Pass 2 — full diagnosis with DB context
    try:
        ai_text = _pass2_full_analysis(b64, db_context)
    except OpenAIError as exc:
        log.error("OpenAI error (Pass 2): %s", exc)
        raise HTTPException(status_code=502, detail=f"AI service error: {exc}") from exc
    except Exception as exc:
        log.error("Unexpected error (Pass 2): %s", exc)
        raise HTTPException(status_code=500, detail="Internal server error") from exc

    # 6. Parse JSON
    try:
        result = _extract_json(ai_text)
    except ValueError as exc:
        log.error("JSON parse failed: %s", exc)
        result = _fallback_response(ai_text)

    # 7. Enrich detected OBD codes with full DB data
    if isinstance(result.get("detected_obd_codes"), list):
        result["detected_obd_codes"] = db.enrich_detected_codes(
            result["detected_obd_codes"]
        )

    # 8. Normalise all fields
    result = _safe_defaults(result)

    log.info(
        "Analysis complete | severity=%s safety=%s urgency=%s confidence=%.2f "
        "lights=%d codes=%d",
        result["severity"], result["safety_recommendation"], result["repair_urgency"],
        result["confidence"], len(result["detected_warning_lights"]),
        len(result["detected_obd_codes"]),
    )

    return result
