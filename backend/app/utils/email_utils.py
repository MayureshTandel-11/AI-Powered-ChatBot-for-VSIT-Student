"""Utilities for student email validation and OTP generation/hashing."""

import re
import secrets
import bcrypt


VSIT_EMAIL_REGEX = re.compile(r"^(?P<local>[a-z]+)\.(?P<surname>[a-z]+)@vsit\.edu\.in$")


def validate_student_email(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    if " " in email:
        return False
    m = VSIT_EMAIL_REGEX.match(email)
    return bool(m)


def generate_6_digit_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_otp(otp: str) -> str:
    return bcrypt.hashpw(otp.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_otp(otp: str, otp_hash: str) -> bool:
    try:
        return bcrypt.checkpw(otp.encode("utf-8"), otp_hash.encode("utf-8"))
    except Exception:
        return False
