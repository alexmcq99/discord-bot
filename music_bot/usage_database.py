from collections.abc import Sequence
import os
from typing import Any, Optional, Type

from sqlalchemy import asc, func, select
from sqlalchemy import Date
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import aliased, sessionmaker
from sqlalchemy.orm.attributes import InstrumentedAttribute

from config import Config

from .song import Song
from .usage_tables import Base, SongPlay, SongRequest


class UsageDatabase():
    def __init__(self, config: Config):
        self.config: Config = config
        self.reset_database: bool = config.reset_database
        connection_string = f"sqlite+aiosqlite:///{config.database_file_path}"
        self.engine = create_async_engine(connection_string)
        self.async_session: sessionmaker = sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )

    async def initialize(self) -> None:
        if not os.path.exists(self.config.data_dir):
            os.makedirs(self.config.data_dir)
            
        if self.reset_database:
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            Song.request_id_counter = await self.get_next_id(SongRequest)
            Song.play_id_counter = await self.get_next_id(SongPlay)

    async def get_next_id(self, table: type):
        async with self.async_session() as session:
            max_id = await session.scalar(select(func.max(table.id)))
            next_id = max_id + 1 if max_id else 0
            return next_id

    async def insert_data(self, data: Base) -> None:
        async with self.async_session() as session:
            async with session.begin():
                session.add(data)
                print(f"added data: {data!r}")
    
    # TODO: CURRENT PLAN FOR STATS EMBEDS/DATABASE
    # DONE: Create embed in SongQueue object to be consistent with Song embed and future Stats embeds
    # DONE: Add guild id to song requests and plays to add support for multiple servers and to be consistent with audio_players in MusicCog
    # DONE:  Separate classes for Stats and UsageDatabase: 
    # DONE: Stats has instance of UsageDatabase and uses it to get stats data, then transforms it into a discord embed
    # Stats class also creates graphs, which can be embedded
    # DONE: add argument parsing logic to stats command in MusicCog to get stats for song, user, or everything
    # may share logic with already existing argument parsing logic for the play command, reuse code as necessary
    async def get_song_requests(self, filter_kwargs: dict[str, Any]) -> Sequence[SongRequest]:
        song_requests = await self.get_data(SongRequest, filter_kwargs)
        return song_requests
    
    async def get_song_plays(self, filter_kwargs: dict[str, Any]) -> Sequence[SongPlay]:
        song_plays = await self.get_data(SongPlay, filter_kwargs)
        return song_plays
    
    async def get_data(self, table: type, filter_kwargs: dict[str, Any]) -> Sequence[SongRequest | SongPlay]:
        async with self.async_session() as session:
            result = await session.scalars(select(table).filter_by(**filter_kwargs).order_by(asc(table.timestamp)))
            data = result.all()
            return data

    async def get_song_request_counts_by_date(self, filter_kwargs: dict[str, Any]):
        song_request_counts = await self.get_counts_by_date(SongRequest, filter_kwargs)
        return song_request_counts
    
    async def get_song_play_counts_by_date(self, filter_kwargs: dict[str, Any]):
        song_play_counts = await self.get_counts_by_date(SongPlay, filter_kwargs)
        return song_play_counts
    
    async def get_counts_by_date(self, table: type, filter_kwargs: dict[str, Any]):
        async with self.async_session() as session:
            dates_statement = (select(
                func.date(table.timestamp, type_=Date).label("date"))
                .filter_by(**filter_kwargs))
            dates = aliased(dates_statement.subquery())
            statement = (select(
                dates.c.date,
                func.count(dates.c.date).label("count"))
                .group_by(dates.c.date))
            counts = await session.execute(statement)
            return counts.all()

    async def get_song_request_count(self, filter_kwargs: dict[str, Any]) -> int:
        song_request_count = await self.get_count(SongRequest, filter_kwargs)
        print("Times requested: ", song_request_count)
        return song_request_count
    
    async def get_song_play_count(self, filter_kwargs: dict[str, Any]) -> int:
        song_play_count = await self.get_count(SongPlay, filter_kwargs)
        print("Times played: ", song_play_count)
        return song_play_count
    
    async def get_count(self, table: type, filter_kwargs: dict[str, Any]) -> int:
        async with self.async_session() as session:
            statement = select(func.count(table.id)).filter_by(**filter_kwargs)
            count = await session.scalar(statement)
            return count or 0
    
    async def get_first_request(self, filter_kwargs: dict[str, Any]) -> SongRequest:
        first_request = await self.get_request(func.min, filter_kwargs)
        return first_request
    
    async def get_latest_request(self, filter_kwargs: dict[str, Any]) -> SongRequest:
        latest_request = await self.get_request(func.max, filter_kwargs)
        return latest_request
    
    async def get_request(self, agg_func: Type[func.min] | Type[func.max], filter_kwargs: dict[str, Any]) -> SongRequest:
        print(filter_kwargs)
        async with self.async_session() as session:
            timestamp_statement = select(agg_func(SongRequest.timestamp)).filter_by(**filter_kwargs)
            request_timestamp = await session.scalar(timestamp_statement)
            request_statement = select(SongRequest).filter_by(timestamp = request_timestamp, **filter_kwargs)
            result = await session.scalars(request_statement)
            request = result.first()
            return request

    async def get_total_play_duration(self, filter_kwargs: dict[str, Any]) -> float:
        async with self.async_session() as session:
            statement = select(func.sum(SongPlay.duration)).filter_by(**filter_kwargs)
            total_play_duration = await session.scalar(statement)
            return total_play_duration or 0
    
    async def get_most_requested_song(self, filter_kwargs: dict[str, Any]) -> tuple[str, int]:
        song_id, request_count = await self.get_most_common_id(SongRequest.song_id, filter_kwargs)
        return song_id, request_count

    async def get_most_frequent_requester(self, filter_kwargs: dict[str, Any]) -> tuple[int, int]:
        requester_id, request_count = await self.get_most_common_id(SongRequest.requester_id, filter_kwargs)
        return requester_id, request_count
    
    async def get_most_common_id(self, id_attribute: InstrumentedAttribute, filter_kwargs: dict[str, Any]) -> tuple[str | int, int]:
        async with self.async_session() as session:
            request_counts_statement = (select(
                id_attribute.label("id"), 
                func.count(id_attribute).label("count"))
                .filter_by(**filter_kwargs)
                .group_by(id_attribute))
            request_counts = aliased(request_counts_statement.subquery())
            max_count_statement = select(func.max(request_counts.c.count))
            max_count = await session.scalar(max_count_statement)
            most_common_id_statement = select(request_counts.c.id).where(request_counts.c.count == max_count)
            most_common_id = await session.scalar(most_common_id_statement)
            return most_common_id, max_count
