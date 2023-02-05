from config.config import Config
from datetime import datetime

from typing import Any, Optional
from sqlalchemy import ForeignKey
from sqlalchemy import asc
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class SongRequest(Base):
    __tablename__ = "song_request"

    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str] = mapped_column(ForeignKey("song.id"))

    def __repr__(self) -> str:
        return f"User(id={self.timestamp!r}, guild_id={self.guild_id!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r})"

class SongPlay(Base):
    __tablename__ = "song_play"

    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str] = mapped_column(ForeignKey("song.id"))
    duration: Mapped[int]

    def __repr__(self) -> str:
        return f"User(id={self.timestamp!r}, guild_id={self.guild_id!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r}, duration={self.duration!r})"

class MusicDatabase():
    def __init__(self, config: Config):
        self.reset_database: bool = config.reset_database
        connection_string = f"sqlite+aiosqlite:///{config.database_file_path}"
        self.engine = create_async_engine(connection_string)
        self.async_session: sessionmaker = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def initialize(self) -> None:
        if self.reset_database:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def insert_data(self, data: Base) -> None:
        async with self.async_session() as session:
            async with session.begin():
                session.add(data)
    
    # TODO: CURRENT PLAN FOR STATS EMBEDS/DATABASE
    # DONE: Create embed in SongQueue object to be consistent with Song embed and future Stats embeds
    # DONE: Add guild id to song requests and plays to add support for multiple servers and to be consistent with audio_players in MusicCog
    # DONE:  Separate classes for Stats and MusicDatabase: 
    # DONE: Stats has instance of MusicDatabase and uses it to get stats data, then transforms it into a discord embed
    # Stats class also creates graphs, which can be embedded
    # add argument parsing logic to stats command in MusicCog to get stats for song, user, or everything
    # may share logic with already existing argument parsing logic for the play command, reuse code as necessary
    async def get_song_requests(self, filter_kwargs: dict[str, Any]) -> list[SongRequest]:
        song_requests = await self.get_data(SongRequest, **filter_kwargs)
        return song_requests
    
    async def get_song_plays(self, filter_kwargs: dict[str, Any]) -> list[SongPlay]:
        song_plays = await self.get_data(SongPlay, **filter_kwargs)
        return song_plays
    
    async def get_data(self, table: type, filter_kwargs: dict[str, Any]) -> list[Base]:
        async with self.async_session() as session:
            data = await session.query(table).filter_by(**filter_kwargs).order_by(asc(table.timestamp)).all()
            return data

    async def get_song_request_count(self, filter_kwargs: dict[str, Any]) -> int:
        song_request_count = await self.get_count(SongPlay, **filter_kwargs)
        return song_request_count
    
    async def get_song_play_count(self, filter_kwargs: dict[str, Any]) -> int:
        song_play_count = await self.get_count(SongPlay, **filter_kwargs)
        return song_play_count
    
    async def get_count(self, table: type, filter_kwargs: dict[str, Any]) -> int:
        async with self.async_session() as session:
            counts = await session.query(func.count(table)).filter_by(**filter_kwargs).scalar()
            return counts
    
    async def get_first_request(self, filter_kwargs: dict[str, Any]) -> SongRequest:
        async with self.async_session() as session:
            first_request_timestamp = await session.query(func.min(SongRequest.timestamp)).filter_by(**filter_kwargs).scalar()
            first_request = await session.query(SongRequest).filter_by(timestamp = first_request_timestamp, **filter_kwargs).first()
            return first_request
    
    async def get_latest_request(self, filter_kwargs: dict[str, Any]) -> SongRequest:
        async with self.async_session() as session:
            latest_request_timestamp = await session.query(func.max(SongRequest.timestamp)).filter_by(**filter_kwargs).scalar()
            latest_request = await session.query(SongRequest).filter_by(timestamp = latest_request_timestamp, **filter_kwargs).first()
            return latest_request

    async def get_total_play_duration(self, filter_kwargs: dict[str, Any]) -> int:
        async with self.async_session() as session:
            total_play_duration = await session.query(func.sum(SongPlay.duration)).filter_by(**filter_kwargs).scalar()
            return total_play_duration
    
    async def get_most_requested_song(self, filter_kwargs: dict[str, Any]) -> tuple[str, int]:
        async with self.async_session() as session:
            request_counts = await (session.query(
                SongRequest.song_id, 
                func.count(SongRequest.song_id).label("count"))
                .filter_by(**filter_kwargs)
                .group_by(SongRequest.song_id)
                .subquery("request_counts"))
            max_request_count = await session.query(func.max(request_counts.count)).scalar()
            most_requested_song_id = await session.query(request_counts.song_id).filter_by(count = max_request_count).first()
            return most_requested_song_id, max_request_count

    async def get_most_frequent_requester(self, filter_kwargs: dict[str, Any]) -> int:
        async with self.async_session() as session:
            request_counts = await (session.query(
                SongRequest.requester_id, 
                func.count(SongRequest.requester_id).label("count"))
                .filter_by(**filter_kwargs)
                .group_by(SongRequest.requester_id)
                .subquery("request_counts"))
            max_request_count = await session.query(func.max(request_counts.count)).scalar()
            most_frequent_requester_id = await session.query(request_counts.song_id).filter_by(count = max_request_count).first()
            return most_frequent_requester_id, max_request_count
