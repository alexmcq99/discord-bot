"""Contains classes for playlists of songs from YouTube or Spotify."""

import itertools
from typing import Any, Iterator

import discord
from discord.ext import commands

from config import Config

from .song import Song
from .utils import get_link_markdown
from .ytdl_source import YtdlPlaylistSource


class Playlist:
    """Represents a playlist of songs from YouTube or Spotify.

    Attributes:
        config: A Config object representing the configuration of the music bot.
        ctx: The discord command context in which a command is being invoked.
        title: A string containing the title of the playlist.
        url: A string containing the url of the playlist.
        songs: The list of songs in the playlist.
        requester: The discord member who requested the song.
        playlist_link_markdown: A string containing a hyperlink to the playlist in markdown,
            using the title and url.
        embed_title: A string containing the title for the discord embed that will be displayed in discord.
        embed_description: A string containing the description for the discord embed that will be displayed in discord.
        embed_type: A string containing the type for the discord embed that will be displayed in discord.
        embed_color: A discord.Color object for the color of the discord embed that will be displayed in discord.
        embed_footer: A string containing the footer for the discord embed that will be displayed in discord.
        embed_fields: A dictionary mapping field names to their values for the discord embed that will be displayed in discord.
            Field names and values are both strings.
        thumbnail_url: The url of the thumbnail for the playlist.
    """

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        title: str,
        url: str,
        songs: list[Song],
    ) -> None:
        self.config: Config = config
        self.ctx: commands.Context = ctx

        self.title: str = title
        self.url: str = url
        self.songs: list[Song] = songs

        self.requester: discord.Member = ctx.author
        self.playlist_link_markdown: str = get_link_markdown(self.title, self.url)

        self.embed_title: str = None
        self.embed_description: str = f"## {self.playlist_link_markdown}\n" + "\n".join(
            [
                f"`{i}.`  **{song.link_markdown}**"
                for i, song in enumerate(
                    self.songs[: config.max_displayed_songs], start=1
                )
            ]
        )
        self.embed_type: str = "rich"
        self.embed_color: discord.Color = None
        self.embed_footer: str = (
            f"Only showing the first {self.config.max_displayed_songs} of {len(self.songs)} songs."
        )

        self.embed_fields: dict[str, str] = {
            "Song count": len(self.songs),
            "Requested by": self.requester.mention,
        }

    def __iter__(self) -> Iterator:
        return self.songs.__iter__()

    @property
    def batched_songs(self) -> Iterator[tuple[Song]]:
        return itertools.batched()

    def create_embed(self) -> discord.Embed:
        """Creates and returns the discord embed displaying information about the playlist.

        Uses instance attributes such as embed_title, embed_type, etc., to create a discord embed.

        Returns:
            A discord.Embed object with information about the playlist that will be displayed
            in the channel where the playlist was requested.
        """
        embed = discord.Embed(
            title=self.embed_title,
            type=self.embed_type,
            description=self.embed_description,
            color=self.embed_color,
        )

        if self.thumbnail_url:
            embed = embed.set_thumbnail(url=self.thumbnail_url)

        for field_name, field_value in self.embed_fields.items():
            embed = embed.add_field(name=field_name, value=field_value)

        if len(self.songs) > self.config.max_displayed_songs:
            embed = embed.set_footer(text=self.embed_footer)

        return embed


class SpotifyCollection(Playlist):
    """Represents a collection of songs from Spotify, i.e., an album or playlist.

    Attributes:
        spotify_data: The dictionary of data for the Spotify album or playlist.
        songs: The list of songs in the Spotify album or playlist.
        thumbnail_url: The url of the thumbnail for the Spotify album or playlist.
    """

    SPOTIFY_GREEN_RGB = (29, 185, 84)

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        spotify_data: dict[str, Any],
        songs: list[Song],
    ):
        super().__init__(
            config,
            ctx,
            spotify_data.get("name"),
            spotify_data["external_urls"]["spotify"],
            songs,
        )
        self.spotify_data = spotify_data
        self.thumbnail_url: str = spotify_data["images"][0]["url"]


class SpotifyPlaylist(SpotifyCollection):
    """Represents a Spotify playlist.

    Attributes:
        embed_title: A string containing the title for the discord embed that will be displayed in discord.
        embed_color: A discord.Color object for the color of the discord embed that will be displayed in discord.
        embed_fields: A dictionary mapping field names to their values for the discord embed that will be displayed in discord.
            Field names and values are both strings.
    """

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        spotify_data: dict[str, Any],
        songs: list[Song],
    ):
        super().__init__(
            config,
            ctx,
            spotify_data,
            songs,
        )
        self.embed_title: str = "Processing Spotify playlist:"

        user = spotify_data["owner"]
        self.embed_fields["User"] = get_link_markdown(
            user["display_name"], user["external_urls"]["spotify"]
        )
        self.embed_color: discord.Color = (
            discord.Color.from_str(spotify_data["primary_color"])
            if spotify_data.get("primary_color")
            else discord.Color.from_rgb(*self.SPOTIFY_GREEN_RGB)
        )


class SpotifyAlbum(SpotifyCollection):
    """Represents a Spotify album.

    Attributes:
        embed_title: A string containing the title for the discord embed that will be displayed in discord.
        embed_color: A discord.Color object for the color of the discord embed that will be displayed in discord.
        embed_fields: A dictionary mapping field names to their values for the discord embed that will be displayed in discord.
            Field names and values are both strings.
    """

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        spotify_data: dict[str, Any],
        songs: list[Song],
    ):
        super().__init__(
            config,
            ctx,
            spotify_data,
            songs,
        )
        self.embed_title: str = "Processing Spotify album:"

        artist = spotify_data["artists"][0]
        self.embed_fields["Artist"] = get_link_markdown(
            artist["name"], artist["external_urls"]["spotify"]
        )
        self.embed_color: discord.Color = discord.Color.from_rgb(
            *self.SPOTIFY_GREEN_RGB
        )


class YoutubePlaylist(Playlist):
    """Represents a YouTube playlist.

    Attributes:
        ytdl_playlist_source: The YtdlPlaylistSource object for the YouTube playlist.
        thumbnail_url: The url of the thumbnail for the Spotify album or playlist.
        embed_title: A string containing the title for the discord embed that will be displayed in discord.
        embed_color: A discord.Color object for the color of the discord embed that will be displayed in discord.
        embed_fields: A dictionary mapping field names to their values for the discord embed that will be displayed in discord.
            Field names and values are both strings.
    """

    YOUTUBE_RED_RGB = (255, 0, 0)

    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        ytdl_playlist_source: YtdlPlaylistSource,
        songs: list[Song],
    ):
        super().__init__(
            config, ctx, ytdl_playlist_source.title, ytdl_playlist_source.url, songs
        )
        self.ytdl_playlist_source: YtdlPlaylistSource = ytdl_playlist_source

        self.thumbnail_url: str = ytdl_playlist_source.thumbnail_url

        self.embed_title: str = "Processing YouTube playlist:"
        self.embed_color: discord.Color = discord.Color.from_rgb(*self.YOUTUBE_RED_RGB)

        self.embed_fields["Channel"] = ytdl_playlist_source.uploader_link_markdown
