"""Authentication API routes with student-only email + OTP verification."""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import create_access_token, hash_password, verify_password
from app.core.config import get_settings
from app.db.database import get_db
from app.db.models import User, EmailVerificationOTP
from app.schemas.auth import (
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
    MessageResponse,
    OTPVerifyRequest,
    ResendOtpRequest,
)
from app.services.email_service import send_otp_email
from app.utils.email_utils import (
    validate_student_email,
    generate_6_digit_otp,
    hash_otp,
    verify_otp,
)

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/auth", tags=["auth"])


def _mask_email(email: str) -> str:
    try:
        local, domain = email.split("@", 1)
        parts = local.split(".")
        if len(parts) == 2:
            a, b = parts
            return f"{a[0]}****.{b[0]}****@{domain}"
    except Exception:
        pass
    return email


@router.post("/register", response_model=MessageResponse, status_code=status.HTTP_202_ACCEPTED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)) -> MessageResponse:
    """Initiate student registration and send OTP to VSIT email.

    This endpoint always creates/updates a student account with `role='student'`
    and marks it unverified until OTP verification completes.
    """
    # Normalize and validate email
    email = payload.email.strip().lower()
    if not validate_student_email(email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please use a valid VSIT student email in the format name.surname@vsit.edu.in.",
        )

    if payload.password != payload.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match")

    # Ensure public registration is always a student
    user = db.query(User).filter(User.email == email).first()
    if user and user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already registered. Please log in.")

    full_name = f"{payload.first_name.strip()} {payload.surname.strip()}"
    if not user:
        user = User(name=full_name, email=email, password_hash=hash_password(payload.password), role="student", email_verified=False)
        db.add(user)
        db.commit()
        db.refresh(user)
    else:
        # Update existing unverified user with new name/password
        user.name = full_name
        user.password_hash = hash_password(payload.password)
        user.role = "student"
        db.add(user)
        db.commit()

    # Invalidate previous unverified OTPs for this email
    db.query(EmailVerificationOTP).filter(EmailVerificationOTP.email == email, EmailVerificationOTP.verified == False).delete()

    # Generate OTP
    otp = generate_6_digit_otp()
    otp_hashed = hash_otp(otp)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.otp_expiry_minutes)

    otp_row = EmailVerificationOTP(
        user_id=user.id,
        email=email,
        otp_hash=otp_hashed,
        expires_at=expires_at,
        attempts=0,
        verified=False,
        last_sent_at=datetime.now(timezone.utc),
    )
    db.add(otp_row)
    db.commit()

    # Send OTP via internal email service (do not expose OTP)
    ok, msg = send_otp_email(email=email, student_name=full_name, otp=otp)
    if not ok:
        logger.warning("Failed to send OTP email to %s: %s", email, msg)
        # Do not expose internal failure details
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to send verification email. Please try again later.")

    logger.info("Registration initiated for %s", email)
    return MessageResponse(message=f"A verification OTP has been sent to your VSIT email address: {_mask_email(email)}")


@router.post("/verify-email-otp", response_model=MessageResponse)
def verify_email_otp(payload: OTPVerifyRequest, db: Session = Depends(get_db)) -> MessageResponse:
    email = payload.email.strip().lower()
    if not validate_student_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please use a valid VSIT student email in the format name.surname@vsit.edu.in.")

    otp_row = (
        db.query(EmailVerificationOTP)
        .filter(EmailVerificationOTP.email == email, EmailVerificationOTP.verified == False)
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )
    if not otp_row:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending verification found for this email.")

    now = datetime.now(timezone.utc)
    if otp_row.expires_at < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OTP has expired. Please request a new OTP.")

    if otp_row.attempts >= settings.otp_max_attempts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Too many incorrect OTP attempts. Please request a new OTP.")

    if not verify_otp(payload.otp, otp_row.otp_hash):
        otp_row.attempts += 1
        db.add(otp_row)
        db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OTP.")

    # Successful verification
    otp_row.verified = True
    db.add(otp_row)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="User record not found")

    user.email_verified = True
    user.email_verified_at = datetime.now(timezone.utc)
    db.add(user)
    db.commit()

    logger.info("Email verified for %s", email)
    return MessageResponse(message="Email verified successfully. Your student account is now active.")


@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(payload: ResendOtpRequest, db: Session = Depends(get_db)) -> MessageResponse:
    email = payload.email.strip().lower()
    if not validate_student_email(email):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please use a valid VSIT student email in the format name.surname@vsit.edu.in.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        # Do not reveal whether account exists; return generic message
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No pending verification found for this email.")

    if user.email_verified:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This email is already registered. Please log in.")

    last = (
        db.query(EmailVerificationOTP)
        .filter(EmailVerificationOTP.email == email)
        .order_by(EmailVerificationOTP.created_at.desc())
        .first()
    )
    now = datetime.now(timezone.utc)
    if last and last.last_sent_at:
        delta = (now - last.last_sent_at).total_seconds()
        if delta < settings.otp_resend_cooldown_seconds:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please wait before requesting another OTP.")

    # Invalidate previous unverified OTPs
    db.query(EmailVerificationOTP).filter(EmailVerificationOTP.email == email, EmailVerificationOTP.verified == False).delete()

    otp = generate_6_digit_otp()
    otp_hashed = hash_otp(otp)
    expires_at = now + timedelta(minutes=settings.otp_expiry_minutes)

    otp_row = EmailVerificationOTP(
        user_id=user.id,
        email=email,
        otp_hash=otp_hashed,
        expires_at=expires_at,
        attempts=0,
        verified=False,
        last_sent_at=now,
    )
    db.add(otp_row)
    db.commit()

    ok, msg = send_otp_email(email=email, student_name=user.name, otp=otp)
    if not ok:
        logger.warning("Failed to resend OTP to %s: %s", email, msg)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to send verification email. Please try again later.")

    return MessageResponse(message="A new verification OTP has been sent if the email is pending verification.")


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """Authenticate a user and return a JWT access token."""
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.email_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Please verify your VSIT email address before logging in.")

    logger.info("User logged in: %s", user.email)

    token = create_access_token(subject=user.email, role=user.role)
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> UserResponse:
    """Return the currently authenticated user."""
    return UserResponse.model_validate(current_user)
