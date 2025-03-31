# backend/app/database.py
from sqlalchemy import JSON, Column, DateTime, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite+aiosqlite:///./data/youtube_data.db"

engine = create_async_engine(DATABASE_URL, echo=True)  # echo=True for debugging SQL
SessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
Base = declarative_base()


# Define the Video model
class Video(Base):
    __tablename__ = "videos"
    videoId = Column(String, primary_key=True, index=True)
    playlistId = Column(String, index=True)
    title = Column(String)
    fetch_timestamp_utc = Column(DateTime)
    transcript = Column(Text, nullable=True)  # Store full transcript
    # Store parsed analysis fields
    analysis_core_topic = Column(Text, nullable=True)
    analysis_summary = Column(Text, nullable=True)
    analysis_structure = Column(Text, nullable=True)
    analysis_takeaways = Column(JSON, nullable=True)  # Store list as JSON
    analysis_categories = Column(JSON, nullable=True)  # Store list as JSON
    analysis_verdict = Column(String, nullable=True)
    analysis_justification = Column(Text, nullable=True)


async def get_db():
    async with SessionLocal() as session:
        yield session


# Function to create tables (call this once initially, maybe via Alembic later)
async def init_db():
    async with engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Use drop_all carefully only during dev
        await conn.run_sync(Base.metadata.create_all)
