"""Contains classes that define the tables in the usage database."""

from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SongRequest(Base):
    """Represents a song being requested.

    Attributes:
        uuid: A string containing the uuid for the song request, which is a generated guid/uuid. Also the primary key.
        timestamp: Datetime when the song was requested.
        guild_id: The integer id of the guild where the song was requested.
        requester_id: The integer id of the discord user who requested the song.
        song_id: String containing the YouTube video id for the song.
    """

    __tablename__ = "song_request"

    uuid: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str]

    def __repr__(self) -> str:
        return (
            f"SongRequest(uuid={self.uuid!r}, timestamp={self.timestamp!r}, guild_id={self.guild_id!r},"
            + f" requester_id={self.requester_id!r}, song_id={self.song_id!r})"
        )


class SongPlay(Base):
    """Represents a song being played.

    Attributes:
        uuid: A string containing the uuid for the song request, which is a generated guid/uuid. Also the primary key.
        timestamp: Datetime when the song was played for the first time.
        guild_id: The integer id of the guild where the song was played.
        requester_id: The integer id of the discord user who requested the song.
        song_id: String containing the YouTube video id for the song.
    """

    __tablename__ = "song_play"

    uuid: Mapped[str] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str]
    duration: Mapped[float]

    def __repr__(self) -> str:
        return (
            f"SongPlay(uuid={self.uuid!r}, timestamp={self.timestamp!r}, guild_id={self.guild_id!r},"
            + f" requester_id={self.requester_id!r}, song_id={self.song_id!r}, duration={self.duration!r})"
        )
