from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError

from app.db.models import UserProfile
from app.db.session import async_session


class DuplicateUserProfileError(ValueError):
    pass


@dataclass(frozen=True)
class UserProfileRecord:
    id: str
    display_name: str
    created_at: datetime


def normalize_profile_name(display_name: str) -> str:
    return " ".join(display_name.split()).casefold()


def profile_record(profile: UserProfile) -> UserProfileRecord:
    return UserProfileRecord(
        id=str(profile.id),
        display_name=profile.display_name,
        created_at=profile.created_at,
    )


async def fetch_user_profiles() -> list[UserProfileRecord]:
    async with async_session() as session:
        result = await session.execute(
            select(UserProfile).order_by(UserProfile.created_at.asc())
        )
        return [profile_record(profile) for profile in result.scalars().all()]


async def create_user_profile(display_name: str) -> UserProfileRecord:
    clean_name = " ".join(display_name.split())
    profile = UserProfile(
        id=uuid.uuid4(),
        display_name=clean_name,
        normalized_name=normalize_profile_name(clean_name),
    )

    async with async_session() as session:
        session.add(profile)
        try:
            await session.commit()
        except IntegrityError as exc:
            await session.rollback()
            raise DuplicateUserProfileError(
                "A user with this display name already exists."
            ) from exc
        await session.refresh(profile)

    return profile_record(profile)


async def delete_user_profile(user_id: str) -> bool:
    try:
        profile_id = uuid.UUID(user_id)
    except ValueError:
        return False

    async with async_session() as session:
        result = await session.execute(
            delete(UserProfile).where(UserProfile.id == profile_id)
        )
        if result.rowcount == 0:
            await session.rollback()
            return False
        await session.commit()
        return True
