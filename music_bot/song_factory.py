import asyncio
from config import Config
from discord.ext.commands import Context
from .usage_database import UsageDatabase
from .song import Song
from .spotify import SpotifyClientWrapper
import traceback
from .youtube import YoutubePlaylist, YoutubeVideo

class SongFactory:
    def __init__(self, config: Config, music_db: UsageDatabase) -> None:
        self.config: Config = config
        self.music_db: UsageDatabase = music_db
        self.ctx: Context = None
        self.spotify_client_wrapper = SpotifyClientWrapper(config)
        
    async def create_songs(
            self, ctx: Context, *,
            yt_search_query: str = None,
            yt_video_urls: list[str] = [],
            yt_playlist_urls: list[str] = [],
            spotify_urls: list[str] = []) -> list[Song]:
        self.ctx = ctx
        songs = []
        print("about to create song")
        songs.append(await self.create_song_from_yt_search(yt_search_query))
        songs.extend(await self.create_songs_from_yt_video_urls(yt_video_urls))
        songs.extend(await self.create_songs_from_yt_playlist_urls(yt_playlist_urls))
        songs.extend(await self.create_songs_from_spotify_urls(spotify_urls))
        print("got song requests, returning")
        return [song for song in songs if song]
    
    async def create_songs_from_yt_playlist_urls(self, yt_playlist_urls: list[str]) -> list[Song]:
        tasks = [self.create_songs_from_yt_playlist_url(yt_playlist_url) for yt_playlist_url in yt_playlist_urls]
        song_lists = await asyncio.gather(*tasks, return_exceptions=True)
        for p in song_lists:
            if isinstance(p, Exception):
                traceback.print_exception(p)
        return [song for song_list in song_lists for song in song_list]
    
    async def create_songs_from_yt_playlist_url(self, yt_playlist_url: str) -> list[Song]:
        yt_playlist = await YoutubePlaylist.from_url(yt_playlist_url)
        return [await self.create_song(yt_video) for yt_video in yt_playlist.videos]

    async def create_songs_from_spotify_urls(self, spotify_urls: list[str]) -> list[Song]:
        tasks = [self.create_songs_from_spotify_url(spotify_url) for spotify_url in spotify_urls]
        song_lists = await asyncio.gather(*tasks, return_exceptions=True)
        for p in song_lists:
            if isinstance(p, Exception):
                traceback.print_exception(p)
            print(p)
        return [song for song_list in song_lists for song in song_list]
    
    async def create_songs_from_spotify_url(self, spotify_url: str) -> list[Song]:
        search_queries = await self.spotify_client_wrapper.get_search_queries(spotify_url)
        if not search_queries:
            await self.ctx.send(f"Spotify url \"{spotify_url}\" did not yield any results.")
        tasks = [self.create_song_from_yt_search(search_query) for search_query in search_queries]
        return await asyncio.gather(*tasks, return_exceptions=True)

    async def create_song_from_yt_search(self, yt_search_query: str) -> Song:
        yt_video = await YoutubeVideo.from_search_query(yt_search_query)
        if yt_search_query and not yt_video:
            await self.ctx.send(f"Youtube search \"{yt_search_query}\" did not yield any results.")
        return await self.create_song(yt_video)

    async def create_songs_from_yt_video_urls(self, yt_video_urls: list[str]) -> list[Song]:
        tasks = [self.create_song_from_yt_video_url(yt_video_url) for yt_video_url in yt_video_urls]
        songs = await asyncio.gather(*tasks, return_exceptions=True)
        for song in songs:
            if not isinstance(song, Song):
                print("NOT A SONG:", song)
        return songs
    
    async def create_song_from_yt_video_url(self, yt_video_url: str) -> Song:
        yt_video = await YoutubeVideo.from_url(yt_video_url)
        if not yt_video:
            await self.ctx.send(f"Youtube video at \"{yt_video_url}\" is not available.")
        return await self.create_song(yt_video)

    async def create_song(self, yt_video: YoutubeVideo) -> Song:
        if not yt_video:
            return None
        song = Song(self.config, yt_video, self.ctx)
        await self.music_db.insert_data(song.song_request)
        return song