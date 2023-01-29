import aiosqlite
from config.config import Config
from datetime import datetime

from typing import Optional
from sqlalchemy import ForeignKey
from sqlalchemy import String
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import create_session
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Song(Base):
    __tablename__ = "song"

    id: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str]
    channel_name: Mapped[str]
    duration: Mapped[int]

    def __repr__(self) -> str:
        return f"User(id={self.id!r}, name={self.title!r}, fullname={self.channel_name!r}, duration={self.duration!r})"

# TODO: Add guild for song requests and plays
class SongRequest(Base):
    __tablename__ = "song_request"

    timestamp: Mapped[datetime]
    requester_id: Mapped[int]
    song_id: Mapped[str] = mapped_column(ForeignKey("song.id"))

    def __repr__(self) -> str:
        return f"User(id={self.timestamp!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r})"

class SongPlay(Base):
    __tablename__ = "song_play"

    timestamp: Mapped[datetime]
    requester_id: Mapped[int]
    song_id: Mapped[str] = mapped_column(ForeignKey("song.id"))
    duration: Mapped[int]

    def __repr__(self) -> str:
        return f"User(id={self.timestamp!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r}, duration={self.duration!r})"

class MusicDatabase():
    DROP_TABLE_SQL = "drop table if exists {0};"
    CREATE_SONGS_SQL = """create table if not exists songs(
        id text not null primary key,
        title text not null,
        channel_name text not null,
        duration int not null);"""
    CREATE_SONG_REQUESTS_SQL = """create table if not exists song_requests(
        requester_id integer not null,
        song_id text not null,
        timestamp text not null,
        foreign key(song_id) references songs(id));"""
    CREATE_SONG_PLAYS_SQL = """create table if not exists song_plays(
        requester_id integer not null,
        song_id text not null,
        timestamp text not null,
        duration int not null,
        foreign key(song_id) references songs(id));"""
    
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

    async def insert_song(self, song: Song) -> None:
        async with self.async_session() as session:
            async with session.begin():
                session.add(song)
    
    # TODO: CURRENT PLAN FOR STATS EMBEDS/DATABASE
    # Create embed in SongQueue object to be consistent with Song embed and future Stats embeds
    # Add guild id to song requests and plays to add support for multiple servers and to be consistent with audio_players in MusicCog
    # Separate classes for Stats and MusicDatabase: 
    # Stats has instance of MusicDatabase and uses it to get stats data, then transforms it into a discord embed
    # Stats class also creates graphs, which can be embedded
    # add argument parsing logic to stats command in MusicCog to get stats for song, user, or everything
    # may share logic with already existing argument parsing logic for the play command, reuse code as necessary
    async def get_song_stats(self, song_id: str) -> tuple:
        async with self.async_session() as session:
            pass
