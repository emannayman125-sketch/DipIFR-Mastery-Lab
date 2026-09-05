from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session
from sqlalchemy import select, update

from ..core.config import settings
from ..core.limiter import limiter
from ..core.email import send_verification_email, send_password_reset_email
from ..db import get_db
from ..models import User, RefreshToken, OneTimeToken
from ..schemas.auth import (
    RegisterRequest,
    LoginRequest,
    AuthResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
    ResendVerificationRequest,
)
from ..core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
    refresh_token_expiry,
    generate_one_time_token,
    hash_one_time_token,
)

router = APIRouter(prefix="/auth", tags=["auth"])

# Generic messages used deliberately in the "forgot password" / "resend
# verification" flows so the API never confirms whether a given email is
# registered (avoids account enumeration).
GENERIC_EMAIL_SENT_MESSAGE = {"detail": "If that email is registered, we've sent instructions to it."}


def _set_refresh_cookie(response: Response, raw_refresh: str) -> None:
    """The refresh token is only ever handed to the browser as an HttpOnly
    cookie — never in a JSON body — so it can't be read or exfiltrated by
    client-side JavaScript (e.g. via an XSS payload)."""
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=raw_refresh,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.refresh_cookie_samesite,
        domain=settings.cookie_domain,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        path="/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        domain=settings.cookie_domain,
        path="/auth",
    )


def _issue_tokens(db: Session, response: Response, user: User) -> AuthResponse:
    access_token = create_access_token(str(user.id))
    raw_refresh = generate_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=hash_refresh_token(raw_refresh),
            expires_at=refresh_token_expiry(),
        )
    )
    db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return AuthResponse(access_token=access_token)


def _create_one_time_token(db: Session, user_id: int, purpose: str, ttl: timedelta) -> str:
    # Invalidate older outstanding tokens for the same purpose.
    for old in db.scalars(
        select(OneTimeToken).where(OneTimeToken.user_id == user_id, OneTimeToken.purpose == purpose, OneTimeToken.used.is_(False))
    ):
        old.used = True

    raw = generate_one_time_token()
    db.add(OneTimeToken(
        user_id=user_id,
        token_hash=hash_one_time_token(raw),
        purpose=purpose,
        expires_at=datetime.now(timezone.utc) + ttl,
    ))
    db.commit()
    return raw


def _consume_one_time_token(db: Session, raw: str, purpose: str) -> OneTimeToken:
    token = db.scalar(
        select(OneTimeToken).where(
            OneTimeToken.token_hash == hash_one_time_token(raw),
            OneTimeToken.purpose == purpose,
        )
    )
    if not token or not token.is_valid():
        raise HTTPException(status_code=400, detail="Invalid or expired link")
    token.used = True
    db.commit()
    return token


@router.post("/register", response_model=AuthResponse, status_code=201)
@limiter.limit(settings.rate_limit_auth)
def register(
    request: Request,
    response: Response,
    data: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    email = data.email.lower()
    if db.scalar(select(User).where(User.email == email)):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(email=email, password_hash=hash_password(data.password), display_name=data.display_name.strip())
    db.add(user)
    db.commit()
    db.refresh(user)

    verify_token = _create_one_time_token(db, user.id, "email_verify", timedelta(hours=settings.verification_token_hours))
    verify_url = f"{settings.frontend_url}/verify-email?token={verify_token}"
    background_tasks.add_task(send_verification_email, user.email, verify_url)

    return _issue_tokens(db, response, user)


@router.post("/login", response_model=AuthResponse)
@limiter.limit(settings.rate_limit_auth)
def login(request: Request, response: Response, data: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return _issue_tokens(db, response, user)


@router.post("/refresh", response_model=AuthResponse)
@limiter.limit(settings.rate_limit_auth)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    token_hash = hash_refresh_token(refresh_token)
    token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if not token_row or not token_row.is_valid():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")

    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

    # Rotate: revoke the presented refresh token so it can never be reused,
    # then issue a brand new access/refresh pair.
    token_row.revoked = True
    db.commit()

    return _issue_tokens(db, response, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: Session = Depends(get_db),
    refresh_token: str | None = Cookie(default=None, alias=settings.refresh_cookie_name),
):
    if refresh_token:
        token_hash = hash_refresh_token(refresh_token)
        token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
        if token_row:
            token_row.revoked = True
            db.commit()
    _clear_refresh_cookie(response)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/password/forgot")
@limiter.limit(settings.rate_limit_auth)
def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Always return the same generic message, whether or not the email is
    # registered, so this endpoint can't be used to enumerate accounts.
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user:
        reset_token = _create_one_time_token(db, user.id, "password_reset", timedelta(minutes=settings.reset_token_minutes))
        reset_url = f"{settings.frontend_url}/reset-password?token={reset_token}"
        background_tasks.add_task(send_password_reset_email, user.email, reset_url)
    return GENERIC_EMAIL_SENT_MESSAGE


@router.post("/password/reset")
@limiter.limit(settings.rate_limit_auth)
def reset_password(request: Request, data: ResetPasswordRequest, db: Session = Depends(get_db)):
    token_row = _consume_one_time_token(db, data.token, "password_reset")
    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    user.password_hash = hash_password(data.new_password)
    # Revoke every existing refresh token so a stolen session can't survive
    # a password reset.
    db.execute(
        update(RefreshToken).where(RefreshToken.user_id == user.id).values(revoked=True)
    )
    db.commit()
    return {"detail": "Password updated successfully."}


@router.post("/verify-email")
@limiter.limit(settings.rate_limit_auth)
def verify_email(request: Request, data: VerifyEmailRequest, db: Session = Depends(get_db)):
    token_row = _consume_one_time_token(db, data.token, "email_verify")
    user = db.get(User, token_row.user_id)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired link")

    user.is_verified = True
    db.commit()
    return {"detail": "Email verified successfully."}


@router.post("/resend-verification")
@limiter.limit(settings.rate_limit_auth)
def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    # Same anti-enumeration approach as forgot-password.
    user = db.scalar(select(User).where(User.email == data.email.lower()))
    if user and not user.is_verified:
        verify_token = _create_one_time_token(db, user.id, "email_verify", timedelta(hours=settings.verification_token_hours))
        verify_url = f"{settings.frontend_url}/verify-email?token={verify_token}"
        background_tasks.add_task(send_verification_email, user.email, verify_url)
    return GENERIC_EMAIL_SENT_MESSAGE
