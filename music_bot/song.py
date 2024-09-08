import asyncio
import itertools
import math
import random
from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

import discord
from asyncspotify import SimpleTrack
from discord.abc import Messageable
from discord.ext.commands import Context

from config import Config

from .usage_tables import SongPlay, SongRequest
from .utils import get_link_markdown, utc_to_pacific
from .ytdl_source import YtdlVideoSource


class Song:
    FFMPEG_OPTIONS = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": "-vn",
    }
    request_id_counter = 0
    play_id_counter = 0

    def __init__(
        self,
        config: Config,
        ctx: Context,
        ytdl_video_source: YtdlVideoSource = None,
        spotify_track: SimpleTrack = None,
    ) -> None:
        self.config: Config = config
        self.ctx: Context = ctx

        # Song must be processed for it to be added to the queue
        self.is_processed_event: asyncio.Event = asyncio.Event()

        # Songs are created from ytdl sources or spotify tracks
        # A ytdl video source is added later, when spotify playlists are processed
        if ytdl_video_source:
            self.add_ytdl_video_source(ytdl_video_source)
        else:
            self.add_spotify_track(spotify_track)

        self.guild: discord.Guild = ctx.guild
        self.requester: discord.Member = ctx.author
        self.channel_where_requested: Messageable = ctx.channel
        self.timestamp_requested: datetime = utc_to_pacific(ctx.message.created_at)
        self.timestamp_played: datetime = None
        self.timestamps_started: list[datetime] = []
        self.timestamps_stopped: list[datetime] = []

    def add_ytdl_video_source(self, ytdl_video_source: YtdlVideoSource) -> None:
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

    def add_spotify_track(self, spotify_track: SimpleTrack) -> None:
        self.ytdl_video_source: YtdlVideoSource = None
        self.spotify_track: SimpleTrack = spotify_track

        self.title: str = spotify_track.name
        self.url: str = spotify_track.link
        self.link_markdown: str = get_link_markdown(self.title, self.url)

        artist = spotify_track.artists[0]
        self.uploader_name: str = artist.name
        self.uploader_url: str = artist.link
        self.uploader_link_markdown: str = get_link_markdown(artist.name, artist.link)

        self.yt_search_query: str = f"{artist.name} - {spotify_track.name}"

    @property
    def audio_source(self) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(
            source=self.ytdl_video_source.stream_url, **self.FFMPEG_OPTIONS
        )

    @property
    def total_time_played(self) -> timedelta:
        return sum(
            [
                stop or datetime.now() - start
                for start, stop in itertools.zip_longest(
                    self.timestamps_started, self.timestamps_stopped
                )
            ]
        )

    def create_song_request(self) -> SongRequest:
        song_request = SongRequest(
            id=self.request_id_counter,
            timestamp=self.timestamp_requested,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.id,
        )
        Song.request_id_counter += 1
        return song_request

    def create_song_play(self) -> SongPlay:
        song_play = SongPlay(
            id=self.play_id_counter,
            timestamp=self.timestamp_played,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.id,
            duration=self.total_time_played.total_seconds(),
        )
        Song.play_id_counter += 1
        return song_play

    def create_embed(self) -> discord.Embed:
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

    def record_start(self):
        timestamp_last_started = datetime.now()
        if not self.timestamp_played:
            self.timestamp_played = timestamp_last_started
        self.timestamps_started.append(timestamp_last_started)

    def record_stop(self):
        timestamp_last_stopped = datetime.now()
        self.timestamps_stopped.append(timestamp_last_stopped)

    def __str__(self):
        return f":notes: {self.title} :notes: by {self.uploader_name}"


class SongQueue(asyncio.Queue):
    def __init__(self, config: Config) -> None:
        super().__init__()
        self.config: Config = config
        self.is_looping: bool = False

    def flip_is_looping(self) -> None:
        self.is_looping = not self.is_looping

    def create_embed(self, page: int) -> discord.Embed:
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

    async def get(self) -> Song:
        song = await super().get()
        if self.is_looping:
            self.put_nowait(song)
        return song

    def extend_nowait(self, songs: Sequence[Song], play_next: bool = False) -> None:
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
        if self.full():
            raise asyncio.QueueFull
        self._put(item, play_next=play_next)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)

    def _put(self, item: Song, play_next: bool = False):
        if play_next:
            self._queue.appendleft(item)
        else:
            self._queue.append(item)

    def __getitem__(self, item: Any):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __bool__(self):
        return self.qsize() > 0

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def remove(self, index: int) -> Song:
        song = self._queue[index]
        if index < self.qsize():
            del self._queue[index]
            return song
        return None
