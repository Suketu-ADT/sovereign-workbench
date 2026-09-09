"""
Authentication routes — register, login, current user profile.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    RegisterRequest,
    UserResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Role mapping by clearance level ───────────────────────────

_CLEARANCE_META = {
    1: {
        "role": "Maintenance_Engineer",
        "clearance_name": "Level 1 — Maintenance Engineer",
        "tier": "standard",
    },
    2: {
        "role": "Systems_Specialist",
        "clearance_name": "Level 2 — Systems Specialist",
        "tier": "specialist",
    },
    3: {
        "role": "Chief_Safety_Auditor",
        "clearance_name": "Level 3 — Chief Safety Auditor · All Systems",
        "tier": "chief",
    },
}


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new operator account",
)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_db)):
    # Check for existing email
    result = await db.execute(select(User).where(User.email == body.email))
    if result.scalars().first() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    meta = _CLEARANCE_META[body.clearance_level]

    user = User(
        full_name=body.full_name,
        email=body.email,
        password_hash=hash_password(body.password),
        role=meta["role"],
        clearance_level=body.clearance_level,
        clearance_name=meta["clearance_name"],
        tier=meta["tier"],
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Authenticate and receive a JWT access token",
)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalars().first()

    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    token = create_access_token(
        {
            "sub": str(user.id),
            "email": user.email,
            "role": user.role,
            "clearance_level": user.clearance_level,
            "clearance_name": user.clearance_name,
        }
    )

    return LoginResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
async def me(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(current_user["sub"]))
    )
    user = result.scalars().first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user
