from typing import Any

import discord
from discord.ext import commands

from config import Config

from .song import Song
from .utils import get_link_markdown
from .ytdl_source import YtdlPlaylistSource


class Playlist:
    def __init__(
        self,
        config: Config,
        ctx: commands.Context,
        title: str,
        url: str,
        songs: list[Song],
    ):
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
                for i, song in enumerate(self.songs[: config.max_shown_songs], start=1)
            ]
        )
        self.embed_type: str = "rich"
        self.embed_color: discord.Color = None
        self.embed_footer: str = (
            f"Only showing the first {self.config.max_shown_songs} of {len(self.songs)} songs."
        )

        self.embed_fields: dict[str, str] = {
            "Song count": len(self.songs),
            "Requested by": self.requester.mention,
        }

    def __iter__(self):
        return self.songs.__iter__()

    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.embed_title,
            type=self.embed_type,
            description=self.embed_description,
            color=self.embed_color,
        ).set_thumbnail(url=self.thumbnail_url)

        for field_name, field_value in self.embed_fields.items():
            embed = embed.add_field(name=field_name, value=field_value)

        if len(self.songs) > self.config.max_shown_songs:
            embed = embed.set_footer(text=self.embed_footer)

        return embed


class SpotifyCollection(Playlist):
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
