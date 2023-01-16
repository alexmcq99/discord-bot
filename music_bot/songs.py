import asyncio
import discord
import itertools
import os
from pytube import YouTube
import random
from typing import Any

class Song:
    def __init__(self, video_id: str, requester: discord.Member, channel: discord.ChannelType, ffmpeg_path: str):
        self.yt: YouTube = YouTube.from_id(video_id)
        self.requester: discord.Member = requester
        self.channel_where_requested: discord.ChannelType = channel # GuildChannel?
        self.ffmpeg_path: str = ffmpeg_path

        self.formatted_duration = Song.format_duration(self.length)
    
    @property
    def downloaded(self) -> bool:
        return os.path.exists(self.file_path)

    @property
    def download_necessary(self) -> bool:
        return not self.downloaded and self.guilds_where_queued
    
    @property
    def audio_source(self) -> discord.PCMVolumeTransformer:
        # return discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(executable=self.ffmpeg_path, source=self.watch_url, **FFMPEG_OPTIONS))
        FFMPEG_OPTIONS = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
        }
        # return discord.FFmpegPCMAudio(source=self.watch_url, executable=self.ffmpeg_path, **FFMPEG_OPTIONS)
        # return discord.FFmpegPCMAudio(source=os.path.join("music", "BtyHYIpykN0.mp3"), executable=self.ffmpeg_path, **FFMPEG_OPTIONS)
        # return discord.FFmpegPCMAudio(source=os.path.join("music", "BtyHYIpykN0.mp3"), executable=self.ffmpeg_path)
        return discord.FFmpegOpusAudio(source=self.watch_url, executable=self.ffmpeg_path, **FFMPEG_OPTIONS)
    
    def create_embed(self) -> discord.Embed:
        return (discord.Embed(title="Current song:",
                type="rich",
                description=f"[{self.title}]({self.watch_url})",
                color=discord.Color.blurple())
                .add_field(name="Duration", value=self.formatted_duration)
                .add_field(name="Requested by", value=self.requester.mention)
                .add_field(name="Uploader", value=f"[{self.author}]({self.channel_url})")
                .set_thumbnail(url=self.thumbnail_url))

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.yt, __name)
    
    def __str__(self):
        return f"**{self.title}** by **{self.author}**"
    
    @staticmethod
    def format_duration(duration: int):
        minutes, seconds = divmod(duration, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{str(hours).zfill(2)}:{str(minutes).zfill(2)}:{str(seconds).zfill(2)}"

class SongQueue(asyncio.Queue):
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