"""Client for the internal Node.js email service."""

import logging
from typing import Tuple

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def send_otp_email(email: str, student_name: str, otp: str) -> Tuple[bool, str]:
    if settings.email_dev_mode:
        logger.info("EMAIL_DEV_MODE: OTP for %s (%s) is %s", email, student_name, otp)
        return True, "OTP logged in dev mode"

    url = settings.email_service_url.rstrip("/") + "/send-otp"
    payload = {"email": email, "student_name": student_name, "otp": otp}
    try:
        resp = httpx.post(url, json=payload, timeout=settings.email_service_timeout)
        if resp.status_code >= 200 and resp.status_code < 300:
            return True, "OTP email sent"
        logger.warning("Email service returned %s: %s", resp.status_code, resp.text)
        return False, "Email service error"
    except httpx.RequestError as exc:
        logger.exception("Failed to contact email service: %s", exc)
        return False, "Email service unavailable"
