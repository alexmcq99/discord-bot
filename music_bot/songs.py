import asyncio
import discord
import itertools
import os
from pytube import YouTube
import random
from typing import Any

class Song:
    def __init__(self, video_id: str, music_path: str, ffmpeg_path: str):
        self.music_path: str = music_path
        self.ffmpeg_path: str = ffmpeg_path

        self.yt: YouTube = YouTube.from_id(video_id)
        self.file_name = f"{self.video_id}.mp3"
        self.file_path: str = os.path.join(self.music_path, self.file_name)
        self.download_event: asyncio.Event = asyncio.Event()
        self.guilds_where_queued: set[int] = set()

        self._audio_source: discord.PCMVolumeTransformer = None
        self._embed: discord.Embed = None
    
    @property
    def downloaded(self) -> bool:
        return os.path.exists(self.file_path)

    @property
    def download_necessary(self) -> bool:
        return not self.downloaded and self.guilds_where_queued
    
    @property
    def audio_source(self) -> discord.PCMVolumeTransformer:
        if not self._audio_source:
            self._audio_source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(executable=self.ffmpeg_path, source=self.file_path))
        return self._audio_source

    def __getattr__(self, __name: str) -> Any:
        return getattr(self.yt, __name)
    
    def download(self) -> None:
        if not self.downloaded and self.guilds_queued:
            try:
                stream = self.yt.streams.filter(only_audio=True).first()
                stream.download(output_path=self.music_path, filename=self.file_name)
                self.download_event.set()
            except Exception as e:
                print("Failed to download song", e)

class SongRequest():
    def __init__(self, song: Song, requester: discord.Member, guild_id: int) -> None:
        self.song: Song = song
        self.requester: discord.Member = requester
        self.guild_where_queued: int = guild_id
        self.guilds_where_queued.add(guild_id)

        self._embed: discord.Embed = None
    
    @property
    def embed(self) -> discord.Embed:
        if not self._embed:
            self._embed = (discord.Embed(title="Now playing",
                description=f"```css\n{self.title}\n```",
                color=discord.Color.blurple())
                .add_field(name="Duration", value=self.length)
                .add_field(name="Requested by", value=self.requester.mention)
                .add_field(name="Uploader", value=f"[{self.author}]({self.channel_url})")
                .add_field(name="URL", value=f"[Click]({self.video_url})")
                .set_thumbnail(url=self.thumbnail_url))
        return self._embed
    
    def __del__(self):
        self.guilds_where_queued.remove(self.guild_where_queued)

    def __getattr__(self, __name):
        return getattr(self.song, __name)
    
    def __str__(self):
        return f"**{self.title}** by **{self.author}**"

class SongRequestQueue(asyncio.Queue):
    def __getitem__(self, item):
        if isinstance(item, slice):
            return list(itertools.islice(self._queue, item.start, item.stop, item.step))
        else:
            return self._queue[item]

    def __iter__(self):
        return self._queue.__iter__()

    def __len__(self):
        return self.qsize()

    def clear(self):
        self._queue.clear()

    def shuffle(self):
        random.shuffle(self._queue)

    def put(self, item):
        super().put(item)
        
    def remove(self, index: int):
        del self._queue[index]