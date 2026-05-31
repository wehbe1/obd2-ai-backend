"""
Firebase Admin SDK — used by Polar webhooks to update Firestore user documents.
Requires env var FIREBASE_SERVICE_ACCOUNT_JSON (full service-account JSON string).
"""

from __future__ import annotations

import json
import logging
import os

log = logging.getLogger("obd2ai.firebase")

_db = None
_auth = None
_initialized = False


def init() -> bool:
    """Initialise Firebase Admin once. Returns True when ready."""
    global _db, _auth, _initialized
    if _initialized:
        return _db is not None

    _initialized = True
    raw = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON", "").strip()
    if not raw:
        log.warning(
            "FIREBASE_SERVICE_ACCOUNT_JSON not set — Polar webhooks cannot "
            "update Firestore until this is configured on Render."
        )
        return False

    try:
        import firebase_admin
        from firebase_admin import auth, credentials, firestore

        if not firebase_admin._apps:
            cred = credentials.Certificate(json.loads(raw))
            firebase_admin.initialize_app(cred)

        _db = firestore.client()
        _auth = auth
        log.info("Firebase Admin initialised")
        return True
    except Exception as exc:
        log.error("Firebase Admin init failed: %s", exc)
        _db = None
        _auth = None
        return False


def verify_id_token(id_token: str) -> dict:
    """Verify a Firebase ID token and return decoded claims."""
    if not init() or _auth is None:
        raise RuntimeError("Firebase Admin is not configured")
    return _auth.verify_id_token(id_token)


def get_db():
    if not init() or _db is None:
        raise RuntimeError("Firebase Admin is not configured")
    return _db
