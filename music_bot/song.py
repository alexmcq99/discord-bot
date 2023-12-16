import asyncio
import itertools
import math
import random
from datetime import datetime, timedelta

import discord
from discord.abc import Messageable
from discord.ext.commands import Context

from config import Config

from .usage_tables import SongPlay, SongRequest
from .ytdl_wrapper import YtdlSource


class Song:
    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
    }
    request_id_counter = 0
    play_id_counter = 0

    def __init__(self, config: Config, ytdl_source: YtdlSource, ctx: Context) -> None:
        self.config: Config = config

        self.guild: discord.Guild = ctx.guild
        self.requester: discord.Member = ctx.author
        self.channel_where_requested: Messageable = ctx.channel
        self.timestamp_requested: datetime = datetime.now()
        self.timestamp_last_played: datetime = None
        self.time_played: timedelta = timedelta()

        # Copy attributes from YTDLSource object
        self.__dict__.update(ytdl_source.__dict__)

    @property
    def audio_source(self) -> discord.FFmpegOpusAudio:
        return discord.FFmpegOpusAudio(source=self.stream_url, **self.FFMPEG_OPTIONS)

    @property
    def total_seconds_played(self) -> float:
        seconds = self.time_played.total_seconds()
        if self.timestamp_last_played:
            seconds += (datetime.now() - self.timestamp_last_played).total_seconds()
        return seconds

    def create_song_request(self) -> SongRequest:
        song_request = SongRequest(
            id=self.request_id_counter,
            timestamp=self.timestamp_requested,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.video_id
        )
        Song.request_id_counter += 1
        return song_request
    
    def create_song_play(self) -> SongPlay:
        song_play = SongPlay(
            id=self.play_id_counter,
            timestamp=self.timestamp_requested,
            guild_id=self.guild.id,
            requester_id=self.requester.id,
            song_id=self.video_id,
            duration=self.time_played.total_seconds()
        )
        Song.play_id_counter += 1
        return song_play
    
    def create_embed(self) -> discord.Embed:
        return (discord.Embed(title="Now playing:",
                type="rich",
                description=self.video_link_markdown,
                color=discord.Color.random())
                .add_field(name="Duration", value=self.formatted_duration)
                .add_field(name="Requested by", value=self.requester.mention)
                .add_field(name="Uploader", value=self.uploader_link_markdown)
                .set_thumbnail(url=self.thumbnail_url))

    def record_stop(self):
        if self.timestamp_last_played:
            end_timestamp = datetime.now()
            delta = end_timestamp - self.timestamp_last_played
            self.time_played += delta
            self.timestamp_last_played = None

    def __str__(self):
        return f":notes: **{self.title}** :notes: by **{self.uploader_name}**"

class SongQueue(asyncio.Queue):
    def __init__(self, max_shown_songs: int):
        self.max_shown_songs: int = max_shown_songs
        super().__init__()
    
    def create_embed(self, page: int) -> discord.Embed:
        pages = math.ceil(len(self._queue) / self.max_shown_songs)

        start = (page - 1) * self.max_shown_songs
        end = start + self.max_shown_songs

        queue_str = ""
        for i, song in enumerate(self[start:end], start=start):
            queue_str += f"`{i + 1}.`  [**{song.title}**]({song.video_url})\n"

        embed_title = f"**Song queue has {len(self._queue)} track{'s' if len(self._queue) > 1 else ''}**:"
        embed = (discord.Embed(title=embed_title,
                description=queue_str,
                color=discord.Color.random()
                ).set_footer(text=f"Viewing page {page}/{pages}"))
        return embed
    
    def put_left(self, item):
        if self.full():
            raise asyncio.QueueFull
        self._queue.appendleft(item)
        self._unfinished_tasks += 1
        self._finished.clear()
        self._wakeup_next(self._getters)
    
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __bool__(self):
        return len(self._queue) > 0

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)
        
    def remove(self, index: int):
        del self._queue[index]