from config import Config
from typing import Any, Optional

from datetime import datetime, timedelta
import discord
from discord.ext.commands import Context

from .time_utils import format_datetime, format_time_str
from .usage_database import UsageDatabase
from .usage_tables import SongRequest
from .youtube import YoutubeFactory

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as mticker
import numpy as np
import os

class Stats:
    def __init__(self, embed_title: str, embed_description: str, thumbnail_url: str, stats: dict[str, str], figure_filename: str) -> None:
        self.embed_title: str = embed_title
        self.embed_description: str = embed_description
        self.thumbnail_url: str = thumbnail_url
        self.stats: dict[str, str] = stats
        self.figure_filename: str = figure_filename
    
    def create_main_embed(self) -> discord.Embed:
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

    def create_figure_embed(self) -> tuple[discord.File, discord.Embed]:
        figure_file = discord.File(self.figure_filename)
        embed = discord.Embed(title="Usage Graph")
        # embed.set_image(url=f"attachment://{self.figure_filename}")
        return figure_file, embed

class StatsFactory:
    def __init__(self, config: Config, usage_db: UsageDatabase, yt_factory: YoutubeFactory) -> None:
        self.config = config
        self.usage_db: UsageDatabase = usage_db
        self.yt_factory: YoutubeFactory = yt_factory

        self.ctx: Context = None
        self.filter_kwargs: dict[str, Any] = None
    
    async def create_stats(
            self, ctx: Context, *,
            user: Optional[discord.Member] = None,
            yt_search_query: Optional[str] = None,
            yt_video_url: Optional[str] = None) -> Stats:
        
        self.ctx = ctx
        self.filter_kwargs = {
            "guild_id": ctx.guild.id
        }

        yt_video = None
        if yt_search_query:
            yt_video = await self.yt_factory.create_yt_video_from_search_query(yt_search_query)
        elif yt_video_url:
            yt_video = await self.yt_factory.create_yt_video_from_url(yt_video_url)
        
        if user:
            self.filter_kwargs["requester_id"] = user.id
        if yt_video:
            self.filter_kwargs["song_id"] = yt_video.video_id

        stats_dict = {
            "Requests": await self.usage_db.get_song_request_count(self.filter_kwargs),
            "Plays": await self.get_num_songs_played(),
            "Total Time Played": await self.get_total_duration_formatted(),
            "First Request": await self.get_first_request_formatted(),
            "Most Recent Request": await self.get_most_recent_request_formatted()
        }

        if not user:
            stats_dict["Most Frequent Requester"] = await self.get_most_frequent_requester_formatted()
        if not yt_video:
            stats_dict["Most Requested Song"] = await self.get_most_requested_song_formatted()
        
        if user and yt_video:
            embed_title = "User/Song Stats:"
            embed_description = f"{user.mention} and {yt_video.video_link_markdown}"
        elif user:
            embed_title = "User Stats:"
            embed_description = user.mention
            thumbnail_url = user.avatar.url
        elif yt_video:
            embed_title = "Song Stats:"
            embed_description = yt_video.video_link_markdown
            thumbnail_url = yt_video.thumbnail_url
        else:
            embed_title = "Server Stats:"
            embed_description = ctx.guild.name
            thumbnail_url = ctx.guild.icon.url

        figure_filename = await self.create_figure()
        stats = Stats(embed_title, embed_description, thumbnail_url, stats_dict, figure_filename)
        return stats
    
    async def get_num_songs_played(self) -> int:
        num_songs_played = await self.usage_db.get_song_play_count(self.filter_kwargs)
        num_songs_played += int(self.is_current_song_relevant())
        return num_songs_played

    async def get_total_duration_formatted(self) -> int:
        total_duration = await self.usage_db.get_total_play_duration(self.filter_kwargs)
        if self.is_current_song_relevant():
            total_duration += self.ctx.audio_player.current_song.total_seconds_played
        formatted_total_duration = format_time_str(total_duration)
        return formatted_total_duration
    
    def is_current_song_relevant(self) -> bool:
        return self.ctx.audio_player.is_playing \
            and ("song_id" not in self.filter_kwargs or self.filter_kwargs["song_id"] == self.ctx.audio_player.current_song.video_id)
    
    async def get_first_request_formatted(self) -> str:
        first_request = await self.usage_db.get_first_request(self.filter_kwargs)
        formatted_first_request = await self.format_request(first_request)
        return formatted_first_request
        
    async def get_most_recent_request_formatted(self) -> str:
        latest_request = await self.usage_db.get_latest_request(self.filter_kwargs)
        formatted_latest_request = await self.format_request(latest_request)
        return formatted_latest_request

    async def format_request(self, request: SongRequest) -> str:
        if not request:
            return "N/A"
        formatted_request = f"At {format_datetime(request.timestamp)}"
        if "requester_id" not in self.filter_kwargs:
            requester = self.ctx.guild.get_member(request.requester_id)
            formatted_request += f", by {requester.mention}"
        if "song_id" not in self.filter_kwargs:
            yt_video = await self.yt_factory.create_yt_video_from_id(request.song_id)
            formatted_request += f", requesting {yt_video.video_link_markdown}"
        return formatted_request

    async def get_most_frequent_requester_formatted(self) -> str:
        requester_id, request_count = await self.usage_db.get_most_frequent_requester(self.filter_kwargs)
        if not requester_id or not request_count:
            return "N/A"
        requester = self.ctx.guild.get_member(requester_id)
        formatted = f"{requester.mention} with {request_count} request{'s' if request_count > 1 else ''}"
        return formatted

    async def get_most_requested_song_formatted(self) -> str:
        song_id, request_count = await self.usage_db.get_most_requested_song(self.filter_kwargs)
        if not song_id or not request_count:
            return "N/A"
        yt_video = await self.yt_factory.create_yt_video_from_id(song_id)
        formatted = f"{yt_video.video_link_markdown} with {request_count} request{'s' if request_count > 1 else ''}"
        return formatted

    async def create_figure(self) -> str:
        if not self.config.get_usage_graph_with_stats:
            return None
        
        request_counts_raw = await self.usage_db.get_song_request_counts_by_date(self.filter_kwargs)
        print(request_counts_raw)
        print(len(request_counts_raw))
        if not request_counts_raw:
            return None
        
        request_counts_dict = {row.date: row.count for row in request_counts_raw}

        play_counts_raw = await self.usage_db.get_song_play_counts_by_date(self.filter_kwargs)
        play_counts_dict = {row.date: row.count for row in play_counts_raw}

        start_date, end_date = min(request_counts_dict), max(request_counts_dict)
        num_days = (end_date - start_date).days
        dates = [start_date + timedelta(days=i) for i in range(num_days + 1)]

        request_counts = [request_counts_dict.get(date, 0) for date in dates]
        play_counts = [play_counts_dict.get(date, 0) for date in dates]

        print(dates)
        print(request_counts)
        print(play_counts)

        ax = plt.gca()
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%m-%d'))
        date_interval = max(1, num_days // 8)
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=date_interval))
        ax.yaxis.set_major_locator(mticker.MaxNLocator(integer=True))
        max_count = max(max(request_counts), max(play_counts))
        max_y = ((max_count // 5) + 1) * 5
        y_step = max(1, max_y // 5)
        y_ticks = np.arange(0, max_y, y_step)
        print(y_ticks)
        plt.ylim((0, max_y))
        t = plt.yticks(y_ticks)
        print(t)
        plt.plot(dates, request_counts, "bo-")
        plt.plot(dates, play_counts, "ro-")
        plt.legend(['Song Requests', 'Song Plays'], loc='upper right')
        plt.title("Usage by Date", y=1.05)
        plt.xlabel("Date")
        plt.ylabel("Count")

        filename = f"usage_figure_{self.filter_kwargs['guild_id']}_"
        if "requester_id" in self.filter_kwargs:
            filename += f"{self.filter_kwargs['requester_id']}_"
        if "song_id" in self.filter_kwargs:
            filename += f"{self.filter_kwargs['song_id']}_"
        filename += f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S_%f')}.png"
        figure_filename = os.path.join(self.config.figure_dir, filename)
        plt.savefig(figure_filename, bbox_inches='tight')
        
        return figure_filename
    