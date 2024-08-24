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

class YtdlWrapper:
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

    async def create_ytdl_sources(self, ytdl_args: str) -> AsyncIterator[YtdlSource]:
        print('ytdl_args: ', ytdl_args)
        ytdl_data = await self.bot.loop.run_in_executor(None, self.ytdl.extract_info, ytdl_args, False)
        print(ytdl_data)

        is_playlist_or_yt_search = ytdl_data.get('_type') == 'playlist'
        if is_playlist_or_yt_search:
            # Youtube search will always return a playlist with 1 entry
            for entry in ytdl_data['entries']:
                try:
                    entry_ytdl_data = await self.bot.loop.run_in_executor(None, self.ytdl.extract_info, entry['id'], False)
                    yield YtdlSource(entry_ytdl_data)
                except YoutubeDLError:
                    pass
        else:
            # Single video
            yield YtdlSource(ytdl_data)