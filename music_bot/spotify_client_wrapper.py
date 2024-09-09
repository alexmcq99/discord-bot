"""
Contains classes to retrieve Spotify data using asyncspotify.
"""

import asyncio
import functools
import os
from concurrent.futures import Executor
from typing import Any

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from config import Config

from .utils import parse_spotify_url_or_uri


def get_spotify_data(
    spotify_client_id: str, spotify_client_secret: str, url: str
) -> dict[str, Any]:
    print(f"Should be in different process. Process id: {os.getpid()}")

    creds_mgr = SpotifyClientCredentials(
        client_id=spotify_client_id,
        client_secret=spotify_client_secret,
    )
    sp_client = spotipy.Spotify(client_credentials_manager=creds_mgr)

    music_type, spotify_id = parse_spotify_url_or_uri(url)
    get_data = getattr(sp_client, music_type)
    spotify_data = get_data(spotify_id)

    if "tracks" in spotify_data:
        curr_page = spotify_data["tracks"]
        tracks = curr_page["items"]
        while curr_page.get("next"):
            curr_page = sp_client.next(curr_page)
            tracks.extend(curr_page["items"])

    return spotify_data


class SpotifyClientWrapper:
    """Class that wraps usage of the client from asyncspotify to retrieve Spotify data.

    Handles all interaction with the Spotify client from asyncspotify, wrapping calls with additional logic,
    such as retries.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        spotify_auth: A ClientCredentialsFlow object for asyncspotify that's used to create a Spotify client.
    """

    def __init__(self, config: Config, executor: Executor) -> None:
        """Initializes the spotify client wrapper based on the provided config.

        Args:
            config: A Config object representing the configuration of the music bot.
        """
        self.config: Config = config
        self.executor: Executor = executor

    async def get_spotify_data(self, url: str):
        """Retrieves Spotify data for a track, album, or playlist using asyncspotify.

        Args:
            url: A string containing a Spotify url to a track, album, or playlist.
            max_tries: Integer representing the how many times to try calling extract_info() before giving up.
                Defaults to 3.
            retry_interval_sec: Integer representing how long to wait between retries, in seconds. Defaults to 5.

        Returns:
            Either a FullTrack, FullAlbum, or FullPlaylist object representing
            a Spotify track, album, or playlist, respectively.
            This object can then be parsed for relevant information.

        Raises:
            SpotifyException: If the Spotify data cannot be retrieved after the maximum amount of tries.
        """
        print(f"Current process id: {os.getpid()}")

        partial_func = functools.partial(
            get_spotify_data,
            self.config.spotipy_client_id,
            self.config.spotipy_client_secret,
            url,
        )
        spotify_data = await asyncio.get_running_loop().run_in_executor(
            self.executor, partial_func
        )
        return spotify_data
