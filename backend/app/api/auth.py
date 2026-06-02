import asyncio
import logging
import smtplib
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import is_rate_limited
from app.core.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.models.email_verification import EmailVerificationToken
from app.models.password_reset import PasswordResetToken
from app.models.user import User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])
_bearer = HTTPBearer()

_UTC = timezone.utc


def _now_utc() -> datetime:
    """Naive UTC datetime for TIMESTAMP WITHOUT TIME ZONE columns."""
    return datetime.now(_UTC).replace(tzinfo=None)


# ── Request / Response models ─────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = ""


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    is_verified: bool = False


class UserResponse(BaseModel):
    id: str
    email: str
    name: str | None
    is_admin: bool = False
    is_verified: bool = False
    streaming_enabled: bool = False
    sql_approval_required: bool = False


class ProfileUpdateRequest(BaseModel):
    name: str
    email: EmailStr


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class VerifyEmailRequest(BaseModel):
    code: str


# ── Email helpers ─────────────────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, body: str) -> None:
    if not settings.SMTP_HOST:
        return
    msg = MIMEText(body, "plain")
    msg["Subject"] = subject
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to_email
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as smtp:
            smtp.ehlo()
            if settings.SMTP_USER:
                smtp.starttls()
                smtp.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            smtp.sendmail(settings.SMTP_FROM, [to_email], msg.as_string())
    except Exception as exc:
        logger.error("[auth] SMTP send failed: %s", exc)


def _send_verification_email(to_email: str, code: str) -> None:
    if not settings.SMTP_HOST:
        logger.info("[auth] Verification code for %s: %s", to_email, code)
        print(f"\n[EMAIL VERIFICATION] Code for {to_email}:  {code}\n")  # noqa: T201
        return
    _send_email(
        to_email,
        "Verify your Business Assistant account",
        f"Hello,\n\nYour Business Assistant verification code is:\n\n    {code}\n\n"
        "This code expires in 15 minutes.\n"
        "If you didn't create a Business Assistant account, you can safely ignore this email.",
    )


def _send_reset_email(to_email: str, reset_url: str) -> None:
    if not settings.SMTP_HOST:
        logger.info("[auth] Password reset link for %s (no SMTP): %s", to_email, reset_url)
        print(f"\n[PASSWORD RESET] Link for {to_email}:\n  {reset_url}\n")  # noqa: T201
        return
    _send_email(
        to_email,
        "Reset your Business Assistant password",
        f"Hello,\n\nClick the link below to reset your Business Assistant password:\n\n{reset_url}\n\n"
        "This link expires in 1 hour. If you didn't request a reset, ignore this email.",
    )


# ── Auth helpers ──────────────────────────────────────────────────────────────

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = decode_access_token(credentials.credentials)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    if user.is_blocked:
        raise HTTPException(status_code=401, detail="Account suspended. Contact support.")
    return user


def _user_is_admin(user: User) -> bool:
    if user.is_admin:
        return True
    raw = settings.ADMIN_EMAILS.strip()
    if not raw:
        return True  # no restriction — all authenticated users are admins
    emails = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return user.email.lower() in emails


async def _invalidate_verification_tokens(user_id: str, db: AsyncSession) -> None:
    existing = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == user_id,
            EmailVerificationToken.used.is_(False),
        )
    )
    for tok in existing.scalars():
        tok.used = True


# ── Signup / Login ────────────────────────────────────────────────────────────

@router.post("/signup", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=body.email,
        hashed_password=hash_password(body.password),
        name=body.name.strip() or None,
    )
    db.add(user)
    await db.flush()  # get user.id before commit

    token = EmailVerificationToken(
        user_id=user.id,
        expires_at=_now_utc() + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()

    try:
        await asyncio.to_thread(_send_verification_email, user.email, token.code)
    except Exception as exc:
        logger.error("[auth] Verification email send failed: %s", exc)

    return TokenResponse(access_token=create_access_token(user.id), is_verified=False)


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    if is_rate_limited(f"login:{body.email.lower()}", limit=10, window_seconds=60):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait a minute.")
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return TokenResponse(
        access_token=create_access_token(user.id),
        is_verified=user.is_verified,
    )


# ── Email verification ────────────────────────────────────────────────────────

@router.post("/send-verification")
async def send_verification(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_verified:
        return {"message": "Email already verified"}

    await _invalidate_verification_tokens(current_user.id, db)

    token = EmailVerificationToken(
        user_id=current_user.id,
        expires_at=_now_utc() + timedelta(minutes=15),
    )
    db.add(token)
    await db.commit()

    await asyncio.to_thread(_send_verification_email, current_user.email, token.code)
    return {"message": "Verification code sent"}


@router.post("/verify-email")
async def verify_email(
    body: VerifyEmailRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if current_user.is_verified:
        return {"message": "Email already verified", "is_verified": True}

    result = await db.execute(
        select(EmailVerificationToken).where(
            EmailVerificationToken.user_id == current_user.id,
            EmailVerificationToken.code == body.code,
            EmailVerificationToken.used.is_(False),
        )
    )
    token = result.scalar_one_or_none()

    if not token:
        raise HTTPException(status_code=400, detail="Invalid verification code")

    if token.expires_at < _now_utc():
        raise HTTPException(
            status_code=400,
            detail="Code has expired. Click Resend to get a new one.",
        )

    token.used = True
    current_user.is_verified = True
    await db.commit()

    return {"message": "Email verified successfully", "is_verified": True}


# ── Profile ───────────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_admin=_user_is_admin(current_user),
        is_verified=current_user.is_verified,
        streaming_enabled=current_user.streaming_enabled,
        sql_approval_required=current_user.sql_approval_required,
    )


@router.get("/profile", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_admin=_user_is_admin(current_user),
        is_verified=current_user.is_verified,
    )


@router.put("/profile", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.email != current_user.email:
        existing = await db.execute(select(User).where(User.email == body.email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already in use")
        current_user.email = body.email

    current_user.name = body.name.strip() or None
    await db.commit()
    await db.refresh(current_user)
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        name=current_user.name,
        is_admin=_user_is_admin(current_user),
        is_verified=current_user.is_verified,
    )


@router.put("/password")
async def change_password(
    body: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    current_user.hashed_password = hash_password(body.new_password)
    await db.commit()
    return {"message": "Password updated successfully"}


# ── Password reset ────────────────────────────────────────────────────────────

@router.post("/forgot-password")
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()
    if not user:
        return {"message": "If that email exists, a reset link has been sent."}

    existing = await db.execute(
        select(PasswordResetToken).where(
            PasswordResetToken.user_id == user.id,
            PasswordResetToken.used.is_(False),
        )
    )
    for old_token in existing.scalars():
        old_token.used = True

    token = PasswordResetToken(
        user_id=user.id,
        expires_at=_now_utc() + timedelta(hours=1),
    )
    db.add(token)
    await db.commit()

    reset_url = f"{settings.APP_URL}/reset-password?token={token.token}"
    await asyncio.to_thread(_send_reset_email, user.email, reset_url)

    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
async def reset_password(
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == body.token)
    )
    record = result.scalar_one_or_none()

    if not record or record.used or record.expires_at < _now_utc():
        raise HTTPException(status_code=400, detail="Reset link is invalid or has expired")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    user_result = await db.execute(select(User).where(User.id == record.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="User not found")

    user.hashed_password = hash_password(body.new_password)
    record.used = True
    await db.commit()

    return {"message": "Password reset successfully. You can now sign in."}
