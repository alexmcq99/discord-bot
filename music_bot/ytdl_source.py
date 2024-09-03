import asyncio
import functools

from discord.ext import commands
from typing import Any, AsyncIterator

from yt_dlp import YoutubeDL
from yt_dlp.utils import YoutubeDLError

from .utils import format_time_str

class YtdlSource():
    def __init__(self, ytdl_data: dict[str, Any]) -> None:
        print('creating yt object')
        self.video_id: str = ytdl_data['id']
        self.video_url: str = ytdl_data['webpage_url']
        self.title: str = ytdl_data['title']
        self.video_link_markdown: str = f'[{self.title}]({self.video_url})'

        self.uploader_name: str = ytdl_data.get('channel') or ytdl_data.get('uploader')
        self.uploader_url: str = ytdl_data.get('channel_url') or ytdl_data.get('uploader_url')
        self.uploader_link_markdown: str = f'[{self.uploader_name}]({self.uploader_url})' if self.uploader_url else self.uploader_name

        self.thumbnail_url: str = ytdl_data['thumbnail']

        self.duration: int = ytdl_data['duration']
        self.formatted_duration: str = format_time_str(self.duration)
        
        self.stream_url: str = ytdl_data['url']

class YtdlSourceFactory:
    YTDL_OPTIONS = {
        'format': 'bestaudio/best',
        'extractaudio': True,
        'extract_flat': 'in_playlist',
        'audioformat': 'opus',
        'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
        'restrictfilenames': True,
        'noplaylist': True,
        'nocheckcertificate': True,
        'ignoreerrors': False,
        'logtostderr': False,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'auto',
        'source_address': '0.0.0.0',
    }
        
    def __init__(self, bot: commands.Bot) -> None:
        self.bot: commands.Bot = bot
        self.ytdl: YoutubeDL = YoutubeDL(self.YTDL_OPTIONS)

    async def create_ytdl_sources(self, ytdl_args: str) -> (YtdlSource | list[YtdlSource]):
        print('ytdl_args: ', ytdl_args)
        partial_func = functools.partial(self.ytdl.extract_info, ytdl_args, download=False, process=True)
        ytdl_data = await self.bot.loop.run_in_executor(None, partial_func)
        print(ytdl_data)

        # Youtube search will always return a playlist with 1 entry
        if ytdl_data.get('_type') == 'playlist' and len(ytdl_data.get('entries')) == 1:
            entry = ytdl_data['entries'][0]
            ytdl_source = await self.create_ytdl_source(entry["id"])
            return ytdl_source
        elif ytdl_data.get('_type') == 'playlist': # Playlist with multiple videos
            ytdl_tasks = [self.create_ytdl_source(entry["id"]) for entry in ytdl_data['entries']]
            ytdl_sources = await asyncio.gather(*ytdl_tasks)
            return ytdl_sources
        else: # Single video
            ytdl_source = YtdlSource(ytdl_data)
            return ytdl_source
    
    async def create_ytdl_source(self, yt_video_id: str) -> YtdlSource:
        try:
            partial_func = functools.partial(self.ytdl.extract_info, yt_video_id, download=False, process=True)
            entry_ytdl_data = await self.bot.loop.run_in_executor(None, partial_func)
            return YtdlSource(entry_ytdl_data)
        except YoutubeDLError as e:
            print(f"Encountered YTDL error: {e}")