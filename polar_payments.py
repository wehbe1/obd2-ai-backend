"""
Polar Checkout (one-time payments) + Firestore credit / premium fulfilment.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field
from polar_sdk import Polar
from polar_sdk.webhooks import WebhookVerificationError, validate_event

import firebase_admin_client as fb

log = logging.getLogger("obd2ai.polar")

router = APIRouter()

POLAR_ACCESS_TOKEN = os.getenv("POLAR_ACCESS_TOKEN", "")
POLAR_WEBHOOK_SECRET = os.getenv("POLAR_WEBHOOK_SECRET", "")
FRONTEND_URL = os.getenv("FRONTEND_URL", "https://obd2-ai-aec61.web.app").rstrip("/")
POLAR_SERVER = os.getenv("POLAR_SERVER", "production").strip().lower()

# ── Product catalogue (one-time payments, ILS) ────────────────────────────────
# Create matching one-time products in Polar and set:
#   POLAR_PRODUCT_CREDITS_1, POLAR_PRODUCT_CREDITS_3,
#   POLAR_PRODUCT_CREDITS_10, POLAR_PRODUCT_UNLIMITED

PACKAGES: dict[str, dict[str, Any]] = {
    "credits_1": {
        "name": "OBD2 AI — 1 Analysis Credit",
        "name_he": "קרדיט ניתוח אחד",
        "credits": 1,
        "amount_ils": 1900,  # 19.00 ILS in agorot
        "unlimited": False,
        "product_env": "POLAR_PRODUCT_CREDITS_1",
    },
    "credits_3": {
        "name": "OBD2 AI — 3 Analysis Credits",
        "name_he": "3 קרדיטי ניתוח",
        "credits": 3,
        "amount_ils": 4900,
        "unlimited": False,
        "product_env": "POLAR_PRODUCT_CREDITS_3",
    },
    "credits_10": {
        "name": "OBD2 AI — 10 Analysis Credits",
        "name_he": "10 קרדיטי ניתוח",
        "credits": 10,
        "amount_ils": 14900,
        "unlimited": False,
        "product_env": "POLAR_PRODUCT_CREDITS_10",
    },
    "unlimited": {
        "name": "OBD2 AI — Unlimited Access",
        "name_he": "גישה ללא הגבלה",
        "credits": 0,
        "amount_ils": 49900,
        "unlimited": True,
        "product_env": "POLAR_PRODUCT_UNLIMITED",
    },
}


def polar_configured() -> bool:
    return bool(POLAR_ACCESS_TOKEN)


def _polar_client() -> Polar:
    if not POLAR_ACCESS_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Polar is not configured (POLAR_ACCESS_TOKEN missing)",
        )
    if POLAR_SERVER == "sandbox":
        return Polar(access_token=POLAR_ACCESS_TOKEN, server="sandbox")
    return Polar(access_token=POLAR_ACCESS_TOKEN)


def _product_id_for_package(package_id: str) -> str | None:
    pkg = PACKAGES.get(package_id)
    if not pkg:
        return None
    env_key = pkg.get("product_env", "")
    product_id = os.getenv(env_key, "").strip() if env_key else ""
    return product_id or None


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return authorization.removeprefix("Bearer ").strip()


def _as_dict(obj: Any) -> dict[str, Any]:
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "__dict__"):
        return dict(obj.__dict__)
    return {}


def _metadata_dict(obj: Any) -> dict[str, Any]:
    data = _as_dict(obj)
    metadata = data.get("metadata") or {}
    return metadata if isinstance(metadata, dict) else {}


def _status_value(status: Any) -> str:
    if status is None:
        return ""
    if isinstance(status, str):
        return status.lower()
    return str(getattr(status, "value", status)).lower()


class CheckoutSessionRequest(BaseModel):
    package_id: str = Field(..., description="credits_1 | credits_3 | credits_10 | unlimited")


@router.get("/payment/packages")
def list_packages() -> dict[str, Any]:
    """Public catalogue for the Flutter paywall."""
    items = []
    for pid, pkg in PACKAGES.items():
        items.append({
            "id": pid,
            "name_he": pkg["name_he"],
            "credits": pkg["credits"],
            "unlimited": pkg["unlimited"],
            "price_ils": pkg["amount_ils"] / 100,
        })
    return {"packages": items, "currency": "ILS"}


@router.post("/create-checkout-session")
def create_checkout_session(
    body: CheckoutSessionRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, str]:
    package_id = body.package_id.strip()
    if package_id not in PACKAGES:
        raise HTTPException(status_code=400, detail=f"Unknown package: {package_id}")

    product_id = _product_id_for_package(package_id)
    if not product_id:
        raise HTTPException(
            status_code=503,
            detail=f"Polar product not configured for package: {package_id}",
        )

    token = _extract_bearer(authorization)
    try:
        claims = fb.verify_id_token(token)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase token") from exc

    uid = claims.get("uid") or claims.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Token missing uid")

    pkg = PACKAGES[package_id]
    success_url = f"{FRONTEND_URL}/?payment=success&session_id={{CHECKOUT_ID}}"

    request_body: dict[str, Any] = {
        "products": [product_id],
        "success_url": success_url,
        "external_customer_id": uid,
        "metadata": {
            "firebase_uid": uid,
            "package_id": package_id,
            "credits": str(pkg["credits"]),
            "unlimited": str(pkg["unlimited"]).lower(),
        },
        "prices": {
            product_id: [
                {
                    "amount_type": "fixed",
                    "price_amount": pkg["amount_ils"],
                    "price_currency": "ils",
                }
            ]
        },
    }

    try:
        with _polar_client() as polar:
            checkout = polar.checkouts.create(request=request_body)
    except Exception as exc:
        log.error("Polar checkout create failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Polar error: {exc}") from exc

    checkout_data = _as_dict(checkout)
    checkout_url = checkout_data.get("url") or getattr(checkout, "url", "")
    checkout_id = checkout_data.get("id") or getattr(checkout, "id", "")

    if not checkout_url:
        raise HTTPException(status_code=502, detail="Polar did not return a checkout URL")

    log.info(
        "Checkout session created | uid=%s package=%s checkout=%s",
        uid,
        package_id,
        checkout_id,
    )
    return {"checkout_url": checkout_url, "session_id": str(checkout_id)}


@router.get("/verify-checkout-session/{session_id}")
def verify_checkout_session(
    session_id: str,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    """
    Client-side verification after Polar redirect.
    Webhook is authoritative; this endpoint lets the app refresh UI immediately.
    """
    token = _extract_bearer(authorization)
    try:
        claims = fb.verify_id_token(token)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid Firebase token") from exc

    uid = claims.get("uid") or claims.get("user_id")
    if not uid:
        raise HTTPException(status_code=401, detail="Token missing uid")

    try:
        with _polar_client() as polar:
            checkout = polar.checkouts.get(id=session_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Polar error: {exc}") from exc

    checkout_data = _as_dict(checkout)
    checkout_uid = checkout_data.get("external_customer_id") or _metadata_dict(checkout).get(
        "firebase_uid"
    )
    if checkout_uid != uid:
        raise HTTPException(status_code=403, detail="Session does not belong to this user")

    status = _status_value(checkout_data.get("status") or getattr(checkout, "status", ""))
    if status != "succeeded":
        return {
            "status": status or "unknown",
            "fulfilled": False,
        }

    fulfilled = _apply_purchase(
        session_id=str(checkout_data.get("id") or session_id),
        uid=uid,
        metadata=_metadata_dict(checkout),
        amount_total=checkout_data.get("total_amount") or checkout_data.get("amount"),
        source="verify",
    )
    return {
        "status": "paid",
        "fulfilled": fulfilled,
        "package_id": _metadata_dict(checkout).get("package_id"),
    }


@router.post("/polar-webhook")
async def polar_webhook(request: Request) -> dict[str, str]:
    if not POLAR_WEBHOOK_SECRET:
        raise HTTPException(status_code=503, detail="POLAR_WEBHOOK_SECRET not configured")

    payload = await request.body()
    headers = {k: v for k, v in request.headers.items()}

    try:
        event = validate_event(
            body=payload,
            headers=headers,
            secret=POLAR_WEBHOOK_SECRET,
        )
    except WebhookVerificationError as exc:
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    event_type = event.get("type") if isinstance(event, dict) else getattr(event, "type", "")
    event_data = event.get("data") if isinstance(event, dict) else getattr(event, "data", {})

    if event_type == "order.paid":
        order = _as_dict(event_data)
        _apply_purchase_from_order(order, source="webhook")
    else:
        log.debug("Ignoring Polar webhook event: %s", event_type)

    return {"status": "ok"}


def _apply_purchase_from_order(order: dict[str, Any], source: str) -> bool:
    metadata = order.get("metadata") or {}
    if not isinstance(metadata, dict):
        metadata = {}

    customer = order.get("customer") or {}
    if not isinstance(customer, dict):
        customer = _as_dict(customer)

    uid = (
        customer.get("external_id")
        or metadata.get("firebase_uid")
        or order.get("external_customer_id")
    )
    package_id = metadata.get("package_id", "")

    session_id = (
        order.get("checkout_id")
        or order.get("id")
        or metadata.get("checkout_id")
    )

    amount_total = order.get("total_amount") or order.get("amount")

    return _apply_purchase(
        session_id=str(session_id),
        uid=str(uid) if uid else "",
        metadata=metadata,
        amount_total=amount_total,
        source=source,
        package_id_fallback=package_id,
    )


def _apply_purchase(
    session_id: str,
    uid: str,
    metadata: dict[str, Any],
    amount_total: Any,
    source: str,
    package_id_fallback: str = "",
) -> bool:
    """Apply credits / premium to Firestore. Idempotent per session_id."""
    try:
        db = fb.get_db()
    except RuntimeError as exc:
        log.error("Cannot fulfil purchase — Firebase Admin not ready: %s", exc)
        return False

    from firebase_admin import firestore as fs

    package_id = metadata.get("package_id") or package_id_fallback
    if not uid or not package_id or package_id not in PACKAGES:
        log.error("Purchase missing uid/package | session=%s", session_id)
        return False

    pkg = PACKAGES[package_id]
    credits = int(metadata.get("credits") or pkg["credits"])
    unlimited_raw = metadata.get("unlimited", str(pkg["unlimited"]))
    unlimited = str(unlimited_raw).lower() == "true"

    if amount_total is None:
        amount_agorot = pkg["amount_ils"]
    else:
        amount_agorot = int(amount_total)

    user_ref = db.collection("users").document(uid)
    snap = user_ref.get()
    if snap.exists:
        existing = snap.to_dict() or {}
        for p in existing.get("purchases", []):
            if isinstance(p, dict) and p.get("sessionId") == session_id:
                log.info("Purchase already applied (idempotent) | session=%s", session_id)
                return True

    purchase_record = {
        "sessionId": session_id,
        "packageId": package_id,
        "creditsAdded": 0 if unlimited else credits,
        "unlimited": unlimited,
        "amountIls": amount_agorot / 100,
        "purchasedAt": datetime.now(timezone.utc).isoformat(),
        "source": source,
    }

    if unlimited:
        user_ref.set(
            {
                "accountType": "premium",
                "purchases": fs.ArrayUnion([purchase_record]),
                "lastSeenAt": fs.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        log.info("Premium granted | uid=%s session=%s", uid, session_id)
    else:
        user_ref.set(
            {
                "paidCredits": fs.Increment(credits),
                "purchases": fs.ArrayUnion([purchase_record]),
                "lastSeenAt": fs.SERVER_TIMESTAMP,
            },
            merge=True,
        )
        log.info("Credits +%d | uid=%s session=%s", credits, uid, session_id)

    return True
