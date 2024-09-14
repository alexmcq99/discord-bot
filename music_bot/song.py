"""Contains classes Song and SongQueue, which contain logic related to the songs played by the music bot."""

import asyncio
import itertools
import math
import random
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any, Iterator, Optional, override

import discord
import uuid6
from discord.abc import Messageable
from discord.ext.commands import Context

from config import Config

from .usage_tables import SongPlay, SongRequest
from .utils import get_link_markdown, utc_to_pacific
from .ytdl_source import YtdlVideoSource


class Song:
    """Represents a song to be played by the music bot.

    Song objects are used to store and display metadata about the song, as well as stream the song,
    since they are responsible for creating the audio source used to stream it in discord.

    Song objects can be created from both Spotify tracks (dictionary data) and YtdlVideoSource
    objects, processed or unprocessed. However, keep in mind that Song objects cannot be used to stream audio
    until both of these conditions are met:
    1. A YtdlVideoSource object is added with add_ytdl_video_source() (ytdl_video_source is not None).
    2. The YtdlVideoSource object has been processed with yt-dlp (ytdl_video_source.is_processed is True).

    This is because the audio for all songs is streamed from YouTube, and the YtdlVideoSource objects must be processed
    in order to retrieve their stream url. The is_processed_event attribute is an asyncio.Event object that marks
    if the song object has met these conditions, and must be set before the song is added to the queue and played.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        ctx: The discord command context in which a command is being invoked.
        ytdl_video_source: The YtdlVideoSource object for the song. This must be created and processed by yt-dlp
            for the song to be a valid audio source, since audio is streamed from YouTube.
        spotify_track_data: A dictionary containing spotify track data for the song. If songs are created from
            spotify tracks, they eventually have to populate and process ytdl_video_source to be streamed.
        is_processed_event: An asyncio.Event representing if the song has been processed or not.
            The song has been processed when ytdl_video_source is set and ytdl_video_source.is_processed is True.
            This must be set for the song to be streamed in discord.
        guild: The discord guild where the song was requested.
        requester: The discord member who requested the song.
        channel_where_requested: The discord channel where the song was requested.
        timestamp_requested: Datetime when the song was requested, which is
            when the command to request the song was sent.
        timestamp_played: Datetime when the song was played for the first time.
        timestamps_started: List of datetime objects when the song was started.
            This includes initially playing the song and unpausing it.
        timestamps_stopped: List of datetime objects when the song was stopped.
            This includes finishing playing the song and pausing it.
    """

    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }

    def __init__(
        self,
        config: Config,
        ctx: Context,
        ytdl_video_source: Optional[YtdlVideoSource] = None,
        spotify_track_data: Optional[dict[str, Any]] = None,
    ) -> None:
        """Initializes a Song instance.

        This constructor must be called with one of the optional arguments spotify_track_data or ytdl_video_source.

        Args:
            config: A Config object representing the configuration of the music bot.
            ctx: The discord command context in which a command is being invoked.
            ytdl_video_source: The YtdlVideoSource object for the song. This must be created and processed by yt-dlp
                for the song to be a valid audio source, since audio is streamed from YouTube.
            spotify_track_data: A dictionary containing spotify track data for the song. If songs are created from
                spotify tracks, they eventually have to populate and process ytdl_video_source to be streamed.
        """
        self.config: Config = config
        self.ctx: Context = ctx

        # Song must be processed for it to be added to the queue and played
        self.is_processed_event: asyncio.Event = asyncio.Event()

        # Songs are created from YtdlVideoSource objects or Spotify tracks
        # If created from a Spotify track, a YtdlVideoSource is added later, when spotify playlists are processed
        if ytdl_video_source:
            self.add_ytdl_video_source(ytdl_video_source)
        else:
            self.add_spotify_track(spotify_track_data)

        self.guild: discord.Guild = ctx.guild
        self.requester: discord.Member = ctx.author
        self.channel_where_requested: Messageable = ctx.channel
        self.timestamp_requested: datetime = utc_to_pacific(ctx.message.created_at)
        self.timestamp_played: datetime = None
        self.timestamps_started: list[datetime] = []
        self.timestamps_stopped: list[datetime] = []

    def add_ytdl_video_source(self, ytdl_video_source: YtdlVideoSource) -> None:
        """Adds YtdlVideoSource to the song.

        This instance method must be called for the song to be a valid audio source,
        since audio is streamed from YouTube (through ytdl_video_source). Once this method
        is called, is_processed_event is set, meaning the song can now be played by the music bot.

        Args:
            ytdl_video_source: The YtdlVideoSource object to add to the song.
        """
        self.ytdl_video_source: YtdlVideoSource = ytdl_video_source

        self.title: str = ytdl_video_source.title
        self.id: str = ytdl_video_source.id
        self.url: str = ytdl_video_source.url
        self.link_markdown: str = ytdl_video_source.link_markdown

        self.uploader_name: str = ytdl_video_source.uploader_name
        self.uploader_url: str = ytdl_video_source.uploader_url
        self.uploader_link_markdown: str = ytdl_video_source.uploader_link_markdown

        if ytdl_video_source.is_processed:
            self.is_processed_event.set()

    def add_spotify_track(self, spotify_track_data: dict[str, Any]) -> None:
        """Adds Spotify track data to the song.

        This instance method is called if the song is created using data from a Spotify track.
        Eventually, add_ytdl_video_source() must be called for the song to be valid audio source,
        but before then, the song object just acts as a useful way to store and display information.

        Args:
            spotify_track_data: A dictionary containing data on the Spotify track obtained using spotipy.
        """
        self.ytdl_video_source: YtdlVideoSource = None
        self.spotify_track_data = spotify_track_data

        self.title: str = spotify_track_data.get("name")
        self.url: str = spotify_track_data["external_urls"]["spotify"]
        self.link_markdown: str = get_link_markdown(self.title, self.url)

        artist = spotify_track_data["artists"][0]
        self.uploader_name: str = artist.get("name")
        self.uploader_url: str = artist["external_urls"]["spotify"]
        self.uploader_link_markdown: str = get_link_markdown(
            self.uploader_name, self.uploader_url
        )

        self.yt_search_query: str = f"{self.uploader_name} - {self.title}"

    @property
    def audio_source(self) -> discord.FFmpegOpusAudio:
        """Returns a discord.FFmpegOpusAudio object created from the stream url of ytdl_video_source.
        Used to stream the song's audio to discord."""
        return discord.FFmpegOpusAudio(
            source=self.ytdl_video_source.stream_url, **self.FFMPEG_OPTIONS
        )

    @property
    def total_time_played(self) -> timedelta:
        """Returns a timedelta object representing the total time the song has been played."""
        times = list(
            itertools.zip_longest(self.timestamps_started, self.timestamps_stopped)
        )
        print(times)

        x = sum(
            [
                (stop or datetime.now()) - start
                for start, stop in itertools.zip_longest(
                    self.timestamps_started, self.timestamps_stopped
                )
            ],
            start=timedelta(),
        )
        print(x)
        seconds = x.total_seconds()
        print(seconds)
        return x

    def create_song_request(self) -> SongRequest:
        """Creates and returns SongRequest object which is inserted into the request table of the usage database."""
        song_request_uuid = str(uuid6.uuid7())
        song_request = SongRequest(
            uuid=song_request_uuid,
            timestamp=self.timestamp_requested,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.id,
        )
        print(f"Record song request: {song_request!r}")
        return song_request

    def create_song_play(self) -> SongPlay:
        """Creates and returns SongPlay object which is inserted into the play table of the usage database."""
        song_play_uuid = str(uuid6.uuid7())
        print("song_play_uuid: ", song_play_uuid)
        song_play = SongPlay(
            uuid=song_play_uuid,
            timestamp=self.timestamp_played,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.id,
            duration=self.total_time_played.total_seconds(),
        )
        print(f"Created song play: {song_play!r}")
        return song_play

    def create_embed(self) -> discord.Embed:
        """Creates a discord.Embed object that will be displayed in a discord channel when the song is played."""
        return (
            discord.Embed(
                title="Now playing:",
                type="rich",
                description=self.link_markdown,
                color=discord.Color.random(),
            )
            .add_field(name="Duration", value=self.ytdl_video_source.formatted_duration)
            .add_field(name="Requested by", value=self.requester.mention)
            .add_field(name="Uploader", value=self.uploader_link_markdown)
            .set_thumbnail(url=self.ytdl_video_source.thumbnail_url)
        )

    def record_start(self) -> None:
        """Records the song being started or unpaused."""
        timestamp_last_started = datetime.now()
        if not self.timestamp_played:
            self.timestamp_played = timestamp_last_started
        self.timestamps_started.append(timestamp_last_started)

    def record_stop(self) -> None:
        """Records the song being stopped or paused."""
        timestamp_last_stopped = datetime.now()
        self.timestamps_stopped.append(timestamp_last_stopped)

    def __str__(self) -> str:
        return f":notes: **{self.title}** :notes: by **{self.uploader_name}**"


class SongQueue(asyncio.Queue):
    """Represents a queue of songs for the music bot to play.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        is_looping: A boolean indicating if the song queue is looping or not.
    """

    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config: Config = config
        self.is_looping: bool = False

    def flip_is_looping(self) -> None:
        """Flips if the song queue is looping or not."""
        self.is_looping = not self.is_looping

    def create_embed(self, page: int) -> discord.Embed:
        """Creates and returns the discord embed displaying the state of the song queue.

        Args:
            page: The page of the song queue to return. The embed can only display a certain amount
                of songs at once (defined in config), the page determines which set of songs to display
                on the embed.

        Returns:
            A discord.Embed object to be displayed in a discord channel.
        """
        pages = math.ceil(self.qsize() / self.config.max_shown_songs)

        start = (page - 1) * self.config.max_shown_songs
        end = start + self.config.max_shown_songs

        queue_str = "\n".join(
            [
                f"`{i}.`  **{song.link_markdown}**"
                for i, song in enumerate(self[start:end], start=start + 1)
            ]
        )
        embed_title = (
            f"**Song queue has {self.qsize()} track{'s' if self.qsize() > 1 else ''}**:"
        )
        embed = discord.Embed(
            title=embed_title, description=queue_str, color=discord.Color.random()
        ).set_footer(text=f"Viewing page {page}/{pages}")
        return embed

    @override
    async def get(self) -> Song:
        song = await super().get()
        if self.is_looping:
            self.put_nowait(song)
        return song

    def extend_nowait(self, songs: Sequence[Song], play_next: bool = False) -> None:
        """Extends the song queue by a sequence of songs.

        Args:
            songs: The sequence of songs to add to the queue.
            play_next: Whether to play the songs next or after or all the other songs in the queue.

        Raises:
            asyncio.QueueFull: If the queue is too full to fit the entire sequence of songs.
        """
        if len(songs) > self._maxsize - self.qsize():
            raise asyncio.QueueFull
        self._extend(songs, play_next=play_next)
        self._unfinished_tasks += len(songs)
        self._finished.clear()
        self._wakeup_next(self._getters)

    def _extend(self, songs: Sequence[Song], play_next: bool) -> None:
        if play_next:
            self._queue.extendleft(songs[::-1])
        else:
            self._queue.extend(songs)

    def put_nowait(self, item: Song, play_next: bool = False) -> None:
        """Adds a song to the queue.

        Args:
            songs: The song to add to the queue.
            play_next: Whether to play the song next or after or all the other songs in the queue.

        Raises:
            asyncio.QueueFull: If the queue is full.
        """
        if self.full():
            raise asyncio.QueueFull
        self._put(item, play_next=play_next)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)

    @override
    def _put(self, item: Song, play_next: bool = False) -> None:
        if play_next:
            self._queue.appendleft(item)
        else:
            self._queue.append(item)

    def __getitem__(self, item: Song) -> Song:
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __bool__(self) -> bool:
        return self.qsize() > 0

    def __iter__(self) -> Iterator[Song]:
        return iter(self._queue)

    def __len__(self) -> int:
        return self.qsize()

    def clear(self) -> None:
        """Clears the queue of all songs."""
        self._queue.clear()

    def shuffle(self) -> None:
        """Randomly shuffles the song queue."""
        random.shuffle(self._queue)

    def remove(self, index: int = None, song_ids: set[str] = None) -> Song:
        """Removes a song from the queue and returns it.

        Args:
            index: The index of the song to remove.
            song_ids: A set of string song ids to look for when removing a song.

        Returns:
            The song object that was removed.
        """
        if index is None:
            index = next(
                (i for i, song in enumerate(self._queue) if song.id in song_ids), None
            )

        if index is not None and index >= 0 and index < self.qsize():
            song = self._queue[index]
            del self._queue[index]
            return song
        return None
