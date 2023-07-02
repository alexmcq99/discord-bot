from config import Config
from discord.ext.commands import Context
from typing import Any, AsyncIterator

from .song import Song
from .spotify_wrapper import SpotifyWrapper
from .usage_database import UsageDatabase
from .utils import is_spotify_url
from .ytdl_wrapper import YtdlWrapper

class SongFactory:
    def __init__(self, config: Config, usage_db: UsageDatabase, ytdl_wrapper: YtdlWrapper) -> None:
        self.config: Config = config
        self.ytdl_wrapper: YtdlWrapper = ytdl_wrapper
        self.usage_db: UsageDatabase = usage_db
        self.ctx: Context = None
        self.spotify_wrapper = SpotifyWrapper(config.spotipy_client_id, config.spotipy_client_secret)
        
    async def create_songs(self, ctx: Context, play_cmd_args: str) -> AsyncIterator[Song]:
        self.ctx = ctx
        if is_spotify_url(play_cmd_args):
            yt_search_queries = await self.spotify_wrapper.get_search_queries(play_cmd_args)
            for query in yt_search_queries:
                async for ytdl_source in self.ytdl_wrapper.create_ytdl_sources(query):
                    song = await self.create_song(ytdl_source)
                    yield song
        else:
            async for ytdl_source in self.ytdl_wrapper.create_ytdl_sources(play_cmd_args):
                song = await self.create_song(ytdl_source)
                yield song

    async def create_song(self, ytdl_data: dict[str, Any]) -> Song:
        song = Song(self.config, ytdl_data, self.ctx)
        await self.usage_db.insert_data(song.create_song_request())
        return song