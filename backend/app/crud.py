from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from . import database


async def get_video(db: AsyncSession, video_id: str) -> database.Video | None:
    result = await db.execute(
        select(database.Video).filter(database.Video.videoId == video_id)
    )
    return result.scalars().first()


async def create_or_update_video(
    db: AsyncSession, video_data: dict[str, Any]
) -> database.Video:
    db_video = await get_video(db, video_data["videoId"])
    if db_video:
        # Update existing record if needed (e.g., re-analyzed)
        for key, value in video_data.items():
            setattr(db_video, key, value)
    else:
        # Create new record
        db_video = database.Video(**video_data)
        db.add(db_video)
    await db.commit()
    await db.refresh(db_video)
    return db_video


async def get_videos(
    db: AsyncSession, skip: int = 0, limit: int = 100
) -> list[database.Video]:
    result = await db.execute(select(database.Video).offset(skip).limit(limit))
    return result.scalars().all()
