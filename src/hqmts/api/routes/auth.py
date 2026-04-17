"""Authentication API routes."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.api.deps_auth import get_current_user
from hqmts.core.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_session_id,
    verify_password,
)
from hqmts.core.enums import SessionStatus, UserRole
from hqmts.db.models.user import SessionORM, UserORM
from hqmts.db.repositories.user_repo import SessionRepository, UserRepository
from hqmts.domain.user import SessionInfo, UserInfo

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


@router.post("/login", response_model=TokenResponse)
async def login(
    req: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Authenticate user and return JWT tokens."""
    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(req.username)

    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    settings = request.app.state.settings

    # Check max concurrent sessions
    session_repo = SessionRepository(db)
    active_count = await session_repo.count_active_sessions(user.user_id)
    if active_count >= settings.auth.max_sessions:
        # Revoke oldest session
        active_sessions = await session_repo.get_active_sessions(user.user_id)
        if active_sessions:
            await session_repo.revoke_session(active_sessions[-1].session_id)

    # Create new session
    session_id = generate_session_id()
    now = datetime.now(timezone.utc)
    session_obj = SessionORM(
        session_id=session_id,
        user_id=user.user_id,
        status=SessionStatus.ACTIVE.value,
        ip_address=request.client.host if request.client else "",
        user_agent=request.headers.get("user-agent", "")[:256],
        expired_at=now + timedelta(days=settings.auth.refresh_token_expire_days),
    )
    await session_repo.create(session_obj)

    # Create tokens
    access_token = create_access_token(
        user_id=user.user_id,
        role=UserRole(user.role),
        session_id=session_id,
        secret_key=settings.auth.secret_key,
        expires_minutes=settings.auth.access_token_expire_minutes,
    )
    refresh_token = create_refresh_token(
        user_id=user.user_id,
        session_id=session_id,
        secret_key=settings.auth.secret_key,
        expires_days=settings.auth.refresh_token_expire_days,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.auth.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    req: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Refresh access token using refresh token."""
    settings = request.app.state.settings

    try:
        payload = decode_token(req.refresh_token, settings.auth.secret_key)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    session_id = payload.get("session_id")
    session_repo = SessionRepository(db)
    session_obj = await session_repo.get_by_id(session_id or "")

    if session_obj is None or session_obj.status != SessionStatus.ACTIVE.value:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session not found or revoked",
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_id(session_obj.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Issue new access token
    access_token = create_access_token(
        user_id=user.user_id,
        role=UserRole(user.role),
        session_id=session_id,
        secret_key=settings.auth.secret_key,
        expires_minutes=settings.auth.access_token_expire_minutes,
    )

    # Rotate refresh token
    new_refresh = create_refresh_token(
        user_id=user.user_id,
        session_id=session_id,
        secret_key=settings.auth.secret_key,
        expires_days=settings.auth.refresh_token_expire_days,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=new_refresh,
        expires_in=settings.auth.access_token_expire_minutes * 60,
    )


@router.get("/me")
async def get_me(user: UserORM = Depends(get_current_user)) -> dict:
    """Get current user info and active sessions."""
    return {
        "user_id": user.user_id,
        "username": user.username,
        "role": user.role,
        "display_name": user.display_name,
        "is_active": user.is_active,
    }


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    user: UserORM = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke current session."""
    payload = request.state.token_payload
    session_id = payload.get("session_id")
    if session_id:
        session_repo = SessionRepository(db)
        await session_repo.revoke_session(session_id)
