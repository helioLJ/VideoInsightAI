import asyncio
import uuid

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession

from . import crud, database, schemas, services

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],  # Frontend origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for task statuses (replace with DB/Redis for production)
tasks_status: dict[str, dict] = {}


# Dependency to get DB session
async def get_db_session():
    async with database.SessionLocal() as session:
        yield session


@app.on_event("startup")
async def startup_event():
    # Initialize DB tables if they don't exist
    await database.init_db()
    # Initialize YouTube service (load token)
    services.initialize_youtube_service()
    print("Database and YouTube service initialized.")


@app.post("/process/", status_code=202)
async def trigger_playlist_processing(
    request: schemas.PlaylistRequest,
):
    """Triggers background processing of a YouTube playlist."""
    task_id = str(uuid.uuid4())
    tasks_status[task_id] = {
        "message": "Initializing...",
        "processed_count": 0,
        "skipped_count": 0,
        "failed_count": 0,
    }

    # Using asyncio.create_task for better potential status tracking (though status dict is basic here)
    async def run_processing_task():
        # Need a separate DB session for the background task
        async with database.SessionLocal() as task_db_session:
            await services.process_playlist_videos(
                task_db_session, request.playlist_id, tasks_status[task_id]
            )

    task = asyncio.create_task(run_processing_task())
    print(f"Task created: {task}")

    return {"message": "Playlist processing started.", "task_id": task_id}


@app.get("/status/{task_id}", response_model=schemas.ProcessingStatus)
async def get_processing_status(task_id: str):
    """Gets the status of a processing task."""
    status = tasks_status.get(task_id)
    if not status:
        raise HTTPException(status_code=404, detail="Task not found")
    return status


@app.get("/videos/", response_model=list[schemas.VideoResponse])
async def read_videos(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieves a list of processed videos (basic info + analysis)."""
    db_videos = await crud.get_videos(db, skip=skip, limit=limit)
    response_videos = []
    for vid in db_videos:
        analysis_data = schemas.VideoAnalysis(
            core_topic=vid.analysis_core_topic,
            summary=vid.analysis_summary,
            structure=vid.analysis_structure,
            takeaways=vid.analysis_takeaways,
            categories=vid.analysis_categories,
            verdict=vid.analysis_verdict,
            justification=vid.analysis_justification,
        )
        resp_vid = schemas.VideoResponse(
            videoId=vid.videoId,
            playlistId=vid.playlistId,
            title=vid.title,
            fetch_timestamp_utc=vid.fetch_timestamp_utc,
            analysis=analysis_data,
            has_transcript=bool(vid.transcript),
        )
        response_videos.append(resp_vid)
    return response_videos


@app.get("/videos/{video_id}", response_model=schemas.VideoDetailResponse)
async def read_video_detail(
    video_id: str,
    db: AsyncSession = Depends(get_db_session),
):
    """Retrieves detailed info for a single video, including transcript."""
    db_video = await crud.get_video(db, video_id=video_id)
    if db_video is None:
        raise HTTPException(status_code=404, detail="Video not found")

    analysis_data = schemas.VideoAnalysis(
        core_topic=db_video.analysis_core_topic,
        summary=db_video.analysis_summary,
        structure=db_video.analysis_structure,
        takeaways=db_video.analysis_takeaways,
        categories=db_video.analysis_categories,
        verdict=db_video.analysis_verdict,
        justification=db_video.analysis_justification,
    )
    return schemas.VideoDetailResponse(
        videoId=db_video.videoId,
        playlistId=db_video.playlistId,
        title=db_video.title,
        fetch_timestamp_utc=db_video.fetch_timestamp_utc,
        analysis=analysis_data,
        has_transcript=bool(db_video.transcript),
        transcript=db_video.transcript,
    )
