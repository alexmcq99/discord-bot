import asyncio
import traceback

from discord.ext.commands import Context

from config import Config

from .song import Song
from .spotify import SpotifyClientWrapper
from .spotify import is_spotify_url
from .usage_database import UsageDatabase
from .youtube import YoutubeFactory, YoutubePlaylist, YoutubeVideo


class SongFactory:
    def __init__(self, config: Config, usage_db: UsageDatabase, yt_factory: YoutubeFactory) -> None:
        self.config: Config = config
        self.usage_db: UsageDatabase = usage_db
        self.yt_factory = yt_factory
        self.spotify_client = SpotifyClientWrapper(config)
        
    async def create_songs(self, ctx: Context, play_cmd_args: str) -> list[Song]:
        self.ctx = ctx
        self.yt_factory.ctx = ctx

        if is_spotify_url(play_cmd_args):
            yt_args = await self.spotify_client.get_search_queries(play_cmd_args)
        else:
            yt_args = 
        if yt_search_query:
            yt_video = await self.yt_factory.create_yt_video_from_search_query(yt_search_query)
            song = await self.create_song(yt_video)
            if song: yield song
        for yt_video_url in yt_video_urls:
            yt_video = await self.yt_factory.create_yt_video_from_url(yt_video_url)
            song = await self.create_song(yt_video)
            if song: yield song
        for yt_playlist_url in yt_playlist_urls:
            async for yt_video in self.yt_factory.create_yt_videos_from_yt_playlist_url(yt_playlist_url):
                song = await self.create_song(yt_video)
                if song: yield song
        for spotify_url in spotify_urls:
            search_queries = await self.spotify_client.get_search_queries(spotify_url)
            if not search_queries:
                await self.ctx.send(f"Spotify url \"{spotify_url}\" did not yield any results.")
            for yt_search_query in search_queries:
                yt_video = await self.yt_factory.create_yt_video_from_search_query(yt_search_query)
                song = await self.create_song(yt_video)
                if song: yield song

    async def create_song(self, yt_video: YoutubeVideo) -> Song:
        if not yt_video:
            return None
        song = Song(self.config, yt_video, self.ctx)
        await self.usage_db.insert_data(song.create_song_request())
        return song