"""
Contains classes to retrieve Spotify data using asyncspotify.
"""

import asyncio

from asyncspotify import (
    Client,
    ClientCredentialsFlow,
    FullAlbum,
    FullPlaylist,
    FullTrack,
)
from asyncspotify.exceptions import SpotifyException

from config import Config

from .utils import regex_match_spotify_url


class SpotifyClientWrapper:
    """Class that wraps usage of the client from asyncspotify to retrieve Spotify data.

    Handles all interaction with the Spotify client from asyncspotify, wrapping calls with additional logic,
    such as retries.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        spotify_auth: A ClientCredentialsFlow object for asyncspotify that's used to create a Spotify client.
    """

    def __init__(self, config: Config) -> None:
        """Initializes the spotify client wrapper based on the provided config.

        Args:
            config: A Config object representing the configuration of the music bot.
        """
        self.config: Config = config
        self.spotify_auth: ClientCredentialsFlow = ClientCredentialsFlow(
            client_id=config.spotipy_client_id,
            client_secret=config.spotipy_client_secret,
        )

    async def get_spotify_data_with_retry(
        self, url, max_tries=3, retry_interval_sec=5
    ) -> FullTrack | FullAlbum | FullPlaylist:
        """Retrieves Spotify data for a track, album, or playlist using asyncspotify, with retry logic.

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
        async with Client(self.spotify_auth) as spotify_client:
            match = regex_match_spotify_url(url)
            music_type, spotify_id = match.groups()
            get_func = getattr(spotify_client, f"get_{music_type}")

            tries, result = 0, None
            while not result and tries < max_tries:
                try:
                    result = await get_func(spotify_id)
                except SpotifyException as e:
                    print("Exception when getting data from Spotify: ", e)
                    asyncio.sleep(retry_interval_sec)

                tries += 1

            if result:
                print(f"Successfully got Spotify data after {tries} tries.")
                return result
            else:
                raise SpotifyException(
                    f"Failed to get data from Spotify after {tries} tries."
                )
