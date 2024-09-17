"""Contains class SongFactory to create Song objects from YouTube and Spotify."""

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
from .spotify import SpotifyClientWrapper
from .ytdl_source import YtdlSourceFactory


class SongFactory:
    """Class responsible for creating Song objects from YouTube and Spotify.

    Attribute:
        config: A Config object representing the configuration of the music bot.
        ytdl_source_factory: YtdlSourceFactory object used to create and process YtdlSource objects
            with YouTube data retrieved from yt-dlp.
        spotify_client_wrapper: SpotifyClientWrapper object used to retrieve data from Spotify using spotipy.
        ctx: The discord command context in which a command is being invoked.
    """

    def __init__(
        self,
        config: Config,
        ytdl_source_factory: YtdlSourceFactory,
        spotify_client_wrapper: SpotifyClientWrapper,
    ) -> None:
        """Initializes the SongFactory object.

        Args:
            config: A Config object representing the configuration of the music bot.
            ctx: The discord command context in which a command is being invoked.
            ytdl_source_factory: YtdlSourceFactory object used to create and process YtdlSource objects
                with YouTube data retrieved from yt-dlp.
            spotify_client_wrapper: SpotifyClientWrapper object used to retrieve data from Spotify using spotipy.
        """
        self.config: Config = config
        self.ctx: Context = None
        self.ytdl_source_factory: YtdlSourceFactory = ytdl_source_factory
        self.spotify_client_wrapper: SpotifyClientWrapper = spotify_client_wrapper

    async def process_playlist(self, playlist: Playlist) -> None:
        """Processes an existing Playlist, making its songs valid audio sources for the music bot to play in discord.

        Processes both YouTube and Spotify playlists (and albums) so that their songs can be played.
        YouTube and Spotify songs have to be processed differently.

        Args:
            playlist: The Playlist object to process.
        """
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

    async def create_song_from_spotify_track(self, spotify_track_args: str) -> Song:
        """Creates a Song from a Spotify track url or uri.

        Args:
            spotify_track_args: A string containing the Spotify track's url or uri.

        Returns:
            The Song object for the Spotify track. It should already be processed and ready to be played.
        """
        spotify_track_data = await self.spotify_client_wrapper.get_spotify_data(
            spotify_track_args
        )
        song = Song(self.config, self.ctx, spotify_track_data=spotify_track_data)
        await self.process_song_from_spotify(song)
        return song

    async def process_song_from_spotify(self, song: Song) -> None:
        """Processes an existing Song created from Spotify, making it a valid audio source to be played.

        Args:
            song: The Song object to process.
        """
        ytdl_video_source = await self.ytdl_source_factory.create_ytdl_video_source(
            song.yt_search_query, is_yt_search=True
        )
        song.add_ytdl_video_source(ytdl_video_source)
        print(f"Finished processing song: {song.id}, {song.title}")

    async def process_song_from_yt_playlist(self, song: Song) -> None:
        """Processes an existing song created from  YouTube playlsit, making it a valid audio source to be played.

        Args:
            song: The Song object to process.
        """
        await self.ytdl_source_factory.process_ytdl_video_source(song.ytdl_video_source)
        song.is_processed_event.set()

    async def create_spotify_collection(self, spotify_args: str) -> SpotifyCollection:
        """Creates a SpotifyCollection from a Spotify album or playlist url or uri.

        Args:
            spotify_args: The Spotify album or playlist url or uri.

        Returns:
            The SpotifyCollection object for the Spotify album or playlist.
        """
        start = time.time()
        spotify_data = await self.spotify_client_wrapper.get_spotify_data(spotify_args)
        songs = [
            Song(
                self.config,
                self.ctx,
                spotify_track_data=(
                    spotify_track_data["track"]
                    if "track" in spotify_track_data
                    else spotify_track_data
                ),
            )
            for spotify_track_data in spotify_data["tracks"]["items"]
        ]

        if spotify_data.get("type") == "album":
            collection = SpotifyAlbum(self.config, self.ctx, spotify_data, songs)
        else:
            collection = SpotifyPlaylist(self.config, self.ctx, spotify_data, songs)
        end = time.time()
        print(f"Created spotify collection in {end - start} seconds.")
        return collection

    async def create_yt_playlist(
        self, ytdl_args: str, is_yt_search: bool = False
    ) -> YoutubePlaylist:
        """Creates a YouTubePlaylist from a YouTube playlist url or search query.

        Args:
            ytdl_args: The YouTube playlist url or search query.
            is_search_query: A boolean indicating if ytdl_args is a search query or not.

        Returns:
            The YoutubePlaylist object for YouTube playlist.
        """
        ytdl_playlist_source = (
            await self.ytdl_source_factory.create_ytdl_playlist_source(
                ytdl_args, is_yt_search=is_yt_search
            )
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
        """Creates a Song from a YouTube video url or search query.

        Args:
            yt_video_args: The YouTube video url or search query.

        Returns:
            The Song object for the YouTube video.
        """
        ytdl_video_source = await self.ytdl_source_factory.create_ytdl_video_source(
            yt_video_args, is_yt_search=is_yt_search
        )
        song = Song(self.config, self.ctx, ytdl_video_source=ytdl_video_source)
        return song
