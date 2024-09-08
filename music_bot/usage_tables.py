from datetime import datetime

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SongRequest(Base):
    __tablename__ = "song_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str]

    def __repr__(self) -> str:
        return f"SongRequest(id={self.id!r}, timestamp={self.timestamp!r}, guild_id={self.guild_id!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r})"


class SongPlay(Base):
    __tablename__ = "song_play"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str]
    duration: Mapped[float]

    def __repr__(self) -> str:
        return f"SongPlay(id={self.id!r}, timestamp={self.timestamp!r}, guild_id={self.guild_id!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r}, duration={self.duration!r})"
