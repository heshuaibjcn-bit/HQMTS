"""Authentication dependencies for FastAPI routes."""

from __future__ import annotations

from functools import wraps
from typing import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from hqmts.api.deps import get_db
from hqmts.core.enums import UserRole
from hqmts.db.models.user import UserORM
from hqmts.db.repositories.user_repo import UserRepository


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> UserORM:
    """Extract and validate user from JWT Bearer token."""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid Authorization header",
        )

    token = auth_header[7:]
    secret_key = request.app.state.settings.auth.secret_key

    try:
        from hqmts.core.auth import decode_token

        payload = decode_token(token, secret_key)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )
    except jwt.PyJWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Store token payload on request state for downstream use
    request.state.token_payload = payload
    request.state.user = user

    return user


def require_role(*roles: UserRole) -> Callable:
    """Dependency that requires the user to have one of the specified roles."""

    async def _check(
        user: UserORM = Depends(get_current_user),
    ) -> UserORM:
        if UserRole(user.role) not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user.role}' not authorized. Required: {[r.value for r in roles]}",
            )
        return user

    return _check
