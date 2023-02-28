from typing import Any, Optional

import discord
from discord.ext.commands import Context

from .time_utils import format_datetime, format_time_str
from .usage_database import UsageDatabase
from .youtube import YoutubeVideo

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime as dt

class Stats:
    def __init__(self, embed_title: str, embed_description: str, thumbnail_url: str, stats: dict[str, str]) -> None:
        self.embed_title: str = embed_title
        self.embed_description: str = embed_description
        self.thumbnail_url: str = thumbnail_url
        self.stats: dict[str, str] = stats
    
    def create_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=self.embed_title, 
            color=discord.Color.random(),
            description=self.embed_description
        )
        embed.set_thumbnail(url=self.thumbnail_url)
        for name, value in self.stats.items():
            inline = len(str(value)) <= 20
            embed.add_field(name=name, value=value, inline=inline)
        return embed

class StatsFactory:
    def __init__(self, usage_db: UsageDatabase) -> None:
        self.usage_db: UsageDatabase = usage_db
        self.ctx: Context = None
    
    async def create_stats(
            self, ctx: Context, *,
            user: Optional[discord.Member] = None,
            yt_search_query: Optional[str] = None,
            yt_video_url: Optional[str] = None) -> Stats:
        
        self.ctx = ctx
        filter_kwargs = {
            "guild_id": ctx.guild.id
        }

        yt_video = None
        if yt_search_query:
            yt_video = await YoutubeVideo.from_search_query(yt_search_query)
        elif yt_video_url:
            yt_video = await YoutubeVideo.from_url(yt_video_url)
        
        if user:
            filter_kwargs["requester_id"] = user.id
            thumbnail_url = user.avatar.url
        if yt_video:
            filter_kwargs["song_id"] = yt_video.video_id

        requests_made = await self.usage_db.get_song_request_count(filter_kwargs)

        songs_played = await self.usage_db.get_song_play_count(filter_kwargs)
        songs_played += int(ctx.audio_player.is_playing)

        total_duration = await self.usage_db.get_total_play_duration(filter_kwargs)
        if ctx.audio_player.is_playing:
            total_duration += ctx.audio_player.current_song.total_seconds_played
        formatted_total_duration = format_time_str(total_duration)

        first_request = await self.usage_db.get_first_request(filter_kwargs)
        formatted_first_request = f"At {format_datetime(first_request.timestamp)}"

        latest_request = await self.usage_db.get_latest_request(filter_kwargs)
        formatted_latest_request = f"At {format_datetime(latest_request.timestamp)}"

        stats_dict = {
            "Requests Made": requests_made,
            "Songs Played":  songs_played,
            "Total Time Playing": formatted_total_duration,
            "First Request": formatted_first_request,
            "Most Recent Request": formatted_latest_request
        }

        if not user:
            first_requester = self.ctx.guild.get_member(first_request.requester_id)
            latest_requester = self.ctx.guild.get_member(latest_request.requester_id)
            stats_dict["First Request"] += f", by {first_requester.mention}"
            stats_dict["Most Recent Request"] += f", by {latest_requester.mention}"
            stats_dict["Most Frequent Requester"] = await self.get_most_frequent_requester_formatted(filter_kwargs)
        if not yt_video:
            first_yt_video = await YoutubeVideo.from_id(first_request.song_id)
            latest_yt_video = await YoutubeVideo.from_id(latest_request.song_id)
            stats_dict["First Request"] += f", requesting {first_yt_video.video_link_markdown}"
            stats_dict["Most Recent Request"] += f", requesting {latest_yt_video.video_link_markdown}"
            stats_dict["Most Requested Song"] = await self.get_most_requested_song_formatted(filter_kwargs)
        
        if user and yt_video:
            embed_title = "User/Song Stats:"
            embed_description = f"{user.mention} and {yt_video.video_link_markdown}"
        elif user:
            embed_title = "User Stats:"
            embed_description = user.mention
        elif yt_video:
            embed_title = "Song Stats:"
            embed_description = yt_video.video_link_markdown
            thumbnail_url = yt_video.thumbnail_url
        else:
            embed_title = "Server Stats:"
            embed_description = ctx.guild.name
            thumbnail_url = ctx.guild.icon.url
        
        stats = Stats(embed_title, embed_description, thumbnail_url, stats_dict)
        return stats

    async def get_most_frequent_requester_formatted(self, filter_kwargs: dict[str, Any]) -> str:
        requester_id, request_count = await self.usage_db.get_most_frequent_requester(filter_kwargs)
        if not requester_id or not request_count:
            return "N/A"
        requester = self.ctx.guild.get_member(requester_id)
        formatted = f"{requester.mention} with {request_count} request{'s' if request_count > 1 else ''}"
        return formatted

    async def get_most_requested_song_formatted(self, filter_kwargs: dict[str, Any]) -> str:
        song_id, request_count = await self.usage_db.get_most_requested_song(filter_kwargs)
        if not song_id or not request_count:
            return "N/A"
        yt_video = await YoutubeVideo.from_id(song_id)
        formatted = f"{yt_video.video_link_markdown} with {request_count} request{'s' if request_count > 1 else ''}"
        return formatted
    