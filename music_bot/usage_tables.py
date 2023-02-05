from datetime import datetime
from sqlalchemy.orm import declarative_base, mapped_column
from sqlalchemy.orm import Mapped

Base = declarative_base()

class SongRequest(Base):
    __tablename__ = "song_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str]

    def __repr__(self) -> str:
        return f"User(id={self.timestamp!r}, guild_id={self.guild_id!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r})"

class SongPlay(Base):
    __tablename__ = "song_play"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime]
    guild_id: Mapped[int]
    requester_id: Mapped[int]
    song_id: Mapped[str]
    duration: Mapped[int]

    def __repr__(self) -> str:
        return f"User(id={self.timestamp!r}, guild_id={self.guild_id!r}, requester_id={self.requester_id!r}, song_id={self.song_id!r}, duration={self.duration!r})"