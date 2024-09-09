import asyncio
import time

from discord.ext.commands import Context

from config import Config

from .playlist import (
    Playlist,
    SpotifyAlbum,
    SpotifyCollection,
    SpotifyPlaylist,
    YoutubePlaylist,
)
from .song import Song
from .spotify_client_wrapper import SpotifyClientWrapper
from .ytdl_source import YtdlSourceFactory


class SongFactory:
    def __init__(
        self,
        config: Config,
        ytdl_source_factory: YtdlSourceFactory,
        spotify_client_wrapper: SpotifyClientWrapper,
    ) -> None:
        self.config: Config = config
        self.ytdl_source_factory: YtdlSourceFactory = ytdl_source_factory
        self.spotify_client_wrapper: SpotifyClientWrapper = spotify_client_wrapper
        self.ctx: Context = None

    async def process_playlist(self, playlist: Playlist) -> None:
        start = time.time()
        process_song_task = (
            self.process_song_from_spotify
            if isinstance(playlist, SpotifyCollection)
            else self.process_song_from_yt_playlist
        )
        process_song_tasks = [process_song_task(song) for song in playlist]
        await asyncio.gather(*process_song_tasks)
        end = time.time()
        print(f"Processing the spotify playlist took {end - start} seconds.")

    async def create_song_from_spotify_track(self, spotify_track_url: str) -> Song:
        spotify_track = await self.spotify_client_wrapper.get_spotify_data(
            spotify_track_url
        )
        song = Song(self.config, self.ctx, spotify_track_data=spotify_track)
        await self.process_song_from_spotify(song)
        return song

    async def process_song_from_spotify(self, song: Song) -> None:
        ytdl_video_source = await self.ytdl_source_factory.create_ytdl_video_source(
            song.yt_search_query, is_yt_search=True
        )
        song.add_ytdl_video_source(ytdl_video_source)
        print(f"Finished processing song: {song.id}, {song.title}")

    async def process_song_from_yt_playlist(self, song: Song) -> None:
        await self.ytdl_source_factory.process_ytdl_video_source(song.ytdl_video_source)
        song.is_processed_event.set()

    async def create_spotify_collection(self, spotify_url: str) -> SpotifyCollection:
        spotify_data = await self.spotify_client_wrapper.get_spotify_data(spotify_url)
        songs = [
            Song(self.config, self.ctx, spotify_track_data=spotify_track_data["track"])
            for spotify_track_data in spotify_data["tracks"]["items"]
        ]

        if spotify_data.get("type") == "album":
            collection = SpotifyAlbum(self.config, self.ctx, spotify_data, songs)
        else:
            collection = SpotifyPlaylist(self.config, self.ctx, spotify_data, songs)
        print("Created spotify collection")
        return collection

    async def create_yt_playlist(self, yt_playlist_url: str) -> YoutubePlaylist:
        ytdl_playlist_source = (
            await self.ytdl_source_factory.create_ytdl_playlist_source(yt_playlist_url)
        )
        songs = [
            Song(self.config, self.ctx, ytdl_video_source=ytdl_video_source)
            for ytdl_video_source in ytdl_playlist_source.video_sources
        ]
        playlist = YoutubePlaylist(self.config, self.ctx, ytdl_playlist_source, songs)
        return playlist

    async def create_song_from_yt_video(
        self, yt_video_args: str, is_yt_search: bool = False
    ) -> Song:
        ytdl_video_source = await self.ytdl_source_factory.create_ytdl_video_source(
            yt_video_args, is_yt_search=is_yt_search
        )
        song = Song(self.config, self.ctx, ytdl_video_source=ytdl_video_source)
        return song
