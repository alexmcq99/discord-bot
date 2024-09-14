"""
Contains class to retrieve Spotify data using spotipy.
"""

import asyncio
import functools
import math
import os
import time
from concurrent.futures import Executor
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from config import Config

from .utils import parse_spotify_url_or_uri


def get_spotify_data(
    spotify_client_id: str,
    spotify_client_secret: str,
    spotify_args: str,
    track_limit: int = math.inf,
) -> dict[str, Any]:
    """Retrieves Spotify data for a track, album, or playlist using spotipy.

    Args:
        spotify_client_id: A string containing a Spotify API client id.
        spotify_client_secret: A string containing a Spotify API client secret.
        spotify_args: A string containing a Spotify url or uri to a track, album, or playlist.
        track_limit: The integer limit on the number of tracks returned for Spotify albums and playlists.

    Returns:
        A dictionary of data for the Spotify track, album, or playlist.

    Raises:
        SpotifyException: If the Spotify data cannot be retrieved after the maximum amount of tries.
    """
    print(f"Should be in different process. Process id: {os.getpid()}")

    creds_mgr = SpotifyClientCredentials(
        client_id=spotify_client_id,
        client_secret=spotify_client_secret,
    )
    sp_client = spotipy.Spotify(client_credentials_manager=creds_mgr)

    music_type, spotify_id = parse_spotify_url_or_uri(spotify_args)
    get_data = getattr(sp_client, music_type)
    spotify_data = get_data(spotify_id)

    if "tracks" in spotify_data:
        curr_page = spotify_data["tracks"]
        tracks = curr_page["items"]
        while curr_page.get("next") and len(tracks) < track_limit:
            curr_page = sp_client.next(curr_page)
            tracks_to_add = curr_page["items"]
            if len(tracks) + len(tracks_to_add) > track_limit:
                end = track_limit - len(tracks)
                tracks_to_add = tracks_to_add[:end]
            tracks.extend(tracks_to_add)

    return spotify_data


class SpotifyClientWrapper:
    """Class that wraps usage of the spotipy client to retrieve Spotify data.

    Handles all interaction with the Spotify client from spotipy.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        executor: An Executor object used to execute the spotify calls.
    """

    def __init__(self, config: Config, executor: Executor) -> None:
        """Initializes the spotify client wrapper based on the provided config.

        Args:
            config: A Config object representing the configuration of the music bot.
        """
        self.config: Config = config
        self.executor: Executor = executor

    async def get_spotify_data(self, spotify_args: str):
        """Retrieves Spotify data for a track, album, or playlist using spotipy.

        Args:
            spotify_args: A string containing a Spotify url or uri to a track, album, or playlist.

        Returns:
            A dictionary of data for the Spotify track, album, or playlist.

        Raises:
            SpotifyException: If the Spotify data cannot be retrieved after the maximum amount of tries.
        """
        print(f"Current process id: {os.getpid()}")
        start = time.time()

        partial_func = functools.partial(
            get_spotify_data,
            self.config.spotipy_client_id,
            self.config.spotipy_client_secret,
            spotify_args,
            self.config.spotify_song_limit,
        )
        spotify_data = await asyncio.get_running_loop().run_in_executor(
            self.executor, partial_func
        )
        end = time.time()
        print(f"Getting spotify data took {end - start} seconds.")
        return spotify_data
