from datetime import datetime

from pydantic import BaseModel


class PlaylistRequest(BaseModel):
    playlist_id: str


class VideoBase(BaseModel):
    videoId: str
    playlistId: str
    title: str


class VideoAnalysis(BaseModel):
    core_topic: str | None = None
    summary: str | None = None
    structure: str | None = None
    takeaways: list[str] | None = None
    categories: list[str] | None = None
    verdict: str | None = None
    justification: str | None = None


class VideoResponse(VideoBase):
    fetch_timestamp_utc: datetime | None = None
    analysis: VideoAnalysis | None = None
    has_transcript: bool = False  # Indicate if transcript is stored

    class Config:
        from_attributes = True  # Replaces orm_mode=True


class VideoDetailResponse(VideoResponse):
    transcript: str | None = None  # Include transcript only in detail view


class ProcessingStatus(BaseModel):
    message: str
    processed_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    current_video_id: str | None = None
    current_video_title: str | None = None
