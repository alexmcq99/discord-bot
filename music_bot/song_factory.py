import asyncio

from collections.abc import Sequence
from config import Config
from discord.ext.commands import Context
from typing import Any, AsyncIterator

from .song import Song
from .spotify_wrapper import SpotifyWrapper
from .usage_database import UsageDatabase
from .utils import is_spotify_url
from .ytdl_source import YtdlSource, YtdlSourceFactory

class SongFactory:
    def __init__(self, config: Config, usage_db: UsageDatabase, ytdl_source_factory: YtdlSourceFactory) -> None:
        self.config: Config = config
        self.ytdl_source_factory: YtdlSourceFactory = ytdl_source_factory
        self.spotify_wrapper = SpotifyWrapper(config.spotipy_client_id, config.spotipy_client_secret)
        self.usage_db: UsageDatabase = usage_db
        self.ctx: Context = None
        
    async def create_songs(self, ctx: Context, play_cmd_args: str) -> (Song | list[Song]):
        self.ctx = ctx
        if is_spotify_url(play_cmd_args):
            yt_search_queries = await self.spotify_wrapper.get_search_queries(play_cmd_args)
            if len(yt_search_queries) == 1:
                songs = await self.create_songs_from_yt(yt_search_queries[0])
            else:
                create_songs_tasks = [self.create_songs_from_yt(yt_search_query) for yt_search_query in yt_search_queries]
                songs = await asyncio.gather(*create_songs_tasks)
        else:
            songs = await self.create_songs_from_yt(play_cmd_args)
        
        return songs

    async def create_songs_from_yt(self, yt_query: str) -> (Song | list[Song]):
        ytdl_result = await self.ytdl_source_factory.create_ytdl_sources(yt_query)
        if isinstance(ytdl_result, YtdlSource):
            song = await self.create_song(ytdl_result)
            return song
        else:
            create_song_tasks = [self.create_song(ytdl_source) for ytdl_source in ytdl_result]
            songs = await asyncio.gather(*create_song_tasks)
            return songs

    async def create_song(self, ytdl_source: YtdlSource) -> Song:
        song = Song(self.config, ytdl_source, self.ctx)
        await self.usage_db.insert_data(song.create_song_request())
        return song