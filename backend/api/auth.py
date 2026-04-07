"""Auth endpoints - sync authenticated user to local DB."""

from fastapi import APIRouter
from pydantic import BaseModel

from backend.api.deps import Auth, DbSession

router = APIRouter()


class UserProfileResponse(BaseModel):
    id: str
    display_name: str | None
    email: str | None
    preferred_language: str


class UpdateProfileRequest(BaseModel):
    display_name: str | None = None
    preferred_language: str | None = None


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(auth: Auth, db: DbSession):
    """Get or create user profile from auth token."""
    from sqlalchemy import select
    from backend.db.models import User

    result = await db.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()

    if not user:
        # First login - create local user record
        user = User(id=auth.user_id, preferred_language="zh")
        db.add(user)
        await db.commit()
        await db.refresh(user)

    return UserProfileResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        preferred_language=user.preferred_language,
    )


@router.patch("/me", response_model=UserProfileResponse)
async def update_profile(
    req: UpdateProfileRequest, auth: Auth, db: DbSession
):
    """Update user profile."""
    from sqlalchemy import select
    from backend.db.models import User

    result = await db.execute(select(User).where(User.id == auth.user_id))
    user = result.scalar_one_or_none()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")

    if req.display_name is not None:
        user.display_name = req.display_name
    if req.preferred_language is not None:
        user.preferred_language = req.preferred_language

    await db.commit()
    await db.refresh(user)

    return UserProfileResponse(
        id=user.id,
        display_name=user.display_name,
        email=user.email,
        preferred_language=user.preferred_language,
    )
