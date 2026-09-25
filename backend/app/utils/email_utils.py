"""VSIT student email validation."""

import re

VSIT_EMAIL_REGEX = re.compile(r"^(?P<local>[a-z]+)\.(?P<surname>[a-z]+)@vsit\.edu\.in$")


def validate_student_email(email: str) -> bool:
    if not email:
        return False
    email = email.strip().lower()
    if " " in email:
        return False
    return bool(VSIT_EMAIL_REGEX.match(email))
